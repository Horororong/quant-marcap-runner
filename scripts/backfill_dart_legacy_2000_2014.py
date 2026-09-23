from __future__ import annotations

import hashlib
import io
import math
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

API_KEY = os.getenv("DART_API_KEY", "").strip()
START_YEAR = int(os.getenv("LEGACY_DART_START_YEAR", "2000"))
END_YEAR = int(os.getenv("LEGACY_DART_END_YEAR", "2014"))
MAX_INDEX_TASKS = max(1, int(os.getenv("LEGACY_DART_INDEX_TASKS", "6")))
MAX_DOCS = max(1, int(os.getenv("LEGACY_DART_MAX_DOCS", "20")))
WORKERS = max(1, min(8, int(os.getenv("LEGACY_DART_WORKERS", "4"))))
BASE = "https://opendart.fss.or.kr/api"

ROOT = Path("data/financials/legacy_2000_2014")
NORM_DIR = ROOT / "normalized"
STATUS_DIR = Path("data/status")
INDEX_FILE = ROOT / "legacy_filings.csv.gz"
INDEX_STATE_FILE = STATUS_DIR / "dart_legacy_index_state.csv"
STATE_FILE = STATUS_DIR / "dart_legacy_backfill_state.csv"
STATUS_FILE = STATUS_DIR / "dart_legacy_backfill_status.csv"
COVERAGE_FILE = STATUS_DIR / "dart_legacy_coverage_by_period.csv"
NAME_MAP_FILE = ROOT / "krx_name_intervals.csv.gz"
LIFE_FILE = Path("results/security_life_table.csv")
MODERN_MAP_FILE = Path("data/financials/dart_historical_code_map.csv")
KRX_YEARLY = Path("data/krx_equities/yearly")

ROOT.mkdir(parents=True, exist_ok=True)
NORM_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)

QUARTERS = [
    ("Q1", "0101", "0331"),
    ("Q2", "0401", "0630"),
    ("Q3", "0701", "0930"),
    ("Q4", "1001", "1231"),
]
CORP_CLASSES = ("Y", "K", "E")
PERIODIC_RE = re.compile(r"(사업보고서|반기보고서|분기보고서)")
PERIOD_END_RE = re.compile(r"\((\d{4})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?\)")

ALIASES = {
    "equity": [
        "자본총계", "자본합계", "자기자본", "자본총액", "자본",
    ],
    "revenue": [
        "매출액", "매출", "영업수익", "영업수익합계", "수익(매출액)", "수익",
    ],
    "net_income": [
        "당기순이익", "당기순이익(손실)", "당기순손익", "분기순이익", "분기순이익(손실)",
        "분기순손익", "반기순이익", "반기순이익(손실)", "반기순손익", "당기순손실",
    ],
    "ocf": [
        "영업활동으로인한현금흐름", "영업활동현금흐름", "영업활동으로부터의현금흐름",
        "영업활동에의한현금흐름", "영업활동으로부터의순현금흐름",
    ],
}
STATEMENT_HINTS = {
    "equity": ("대차대조표", "재무상태표"),
    "revenue": ("손익계산서", "포괄손익계산서"),
    "net_income": ("손익계산서", "포괄손익계산서"),
    "ocf": ("현금흐름표",),
}
UNIT_MULTIPLIERS = {
    "원": 1.0,
    "천원": 1_000.0,
    "백만원": 1_000_000.0,
    "억원": 100_000_000.0,
}


class RateLimitExceeded(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_name(x: str) -> str:
    s = str(x or "").strip().lower()
    s = s.replace("주식회사", "").replace("(주)", "").replace("㈜", "")
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def norm_account(x: str) -> str:
    s = str(x or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("ㆍ", "").replace("·", "").replace("*", "")
    s = re.sub(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVXLC0-9.()\-]+", "", s)
    return s


def parse_number(x: str) -> float:
    s = str(x or "").strip()
    if not s:
        return math.nan
    s = s.replace(",", "").replace(" ", "")
    s = s.replace("△", "-")
    if s in {"-", "—", "–"}:
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = re.sub(r"[^0-9.+\-]", "", s)
    if s in {"", ".", "+", "-"}:
        return math.nan
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return math.nan


def dart_get_json(path: str, params: dict, timeout: int = 30) -> dict:
    last = None
    for attempt in range(4):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=timeout)
            r.raise_for_status()
            obj = r.json()
            status = str(obj.get("status", ""))
            if status == "020":
                raise RateLimitExceeded(obj.get("message", "DART request limit exceeded"))
            return obj
        except RateLimitExceeded:
            raise
        except (requests.Timeout, requests.ConnectionError, ValueError) as e:
            last = e
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"DART JSON request failed: {last!r}")


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False, **kwargs)


def save_index(df: pd.DataFrame) -> None:
    if df.empty:
        return
    df = df.drop_duplicates("rcept_no", keep="last").sort_values(["rcept_dt", "rcept_no"])
    df.to_csv(INDEX_FILE, index=False, encoding="utf-8-sig", compression="gzip")


def infer_report_fields(report_nm: str, filing_date: pd.Timestamp) -> dict:
    name = str(report_nm or "")
    if "사업보고서" in name and "분기보고서" not in name and "반기보고서" not in name:
        kind = "FY"
    elif "반기보고서" in name:
        kind = "H1"
    elif "분기보고서" in name:
        kind = "QX"
    else:
        kind = "OTHER"

    m = PERIOD_END_RE.search(name)
    if m:
        y = int(m.group(1)); mo = int(m.group(2)); d = int(m.group(3) or 1)
        try:
            period_end = pd.Timestamp(year=y, month=mo, day=d)
        except Exception:
            period_end = pd.Timestamp(year=y, month=mo, day=1)
    else:
        period_end = pd.NaT

    return {
        "report_kind": kind,
        "period_end": period_end,
        "period_year": int(period_end.year) if pd.notna(period_end) else pd.NA,
        "period_month": int(period_end.month) if pd.notna(period_end) else pd.NA,
    }


def build_index_tasks() -> pd.DataFrame:
    rows = []
    for y in range(START_YEAR, END_YEAR + 1):
        for q, start_mmdd, end_mmdd in QUARTERS:
            for cls in CORP_CLASSES:
                rows.append({
                    "year": y,
                    "quarter": q,
                    "corp_cls": cls,
                    "bgn_de": f"{y}{start_mmdd}",
                    "end_de": f"{y}{end_mmdd}",
                    "task_key": f"{y}_{q}_{cls}",
                })
    return pd.DataFrame(rows)


def load_index_state() -> pd.DataFrame:
    x = load_csv(INDEX_STATE_FILE, dtype=str)
    if x.empty:
        return pd.DataFrame(columns=["task_key","status","rows_found","updated_at_utc","error"])
    return x


def upsert_state(path: Path, rows: list[dict], key: str) -> None:
    old = load_csv(path, dtype=str)
    new = pd.DataFrame(rows)
    if old.empty:
        out = new
    else:
        out = pd.concat([old, new], ignore_index=True, sort=False)
    out = out.drop_duplicates(key, keep="last")
    out.to_csv(path, index=False, encoding="utf-8-sig")


def fetch_index_task(row: pd.Series) -> tuple[list[dict], dict]:
    found: list[dict] = []
    page = 1
    try:
        while True:
            params = {
                "crtfc_key": API_KEY,
                "bgn_de": row["bgn_de"],
                "end_de": row["end_de"],
                "pblntf_ty": "A",
                "corp_cls": row["corp_cls"],
                "last_reprt_at": "N",
                "sort": "date",
                "sort_mth": "asc",
                "page_no": str(page),
                "page_count": "100",
            }
            obj = dart_get_json("list.json", params)
            status = str(obj.get("status", ""))
            if status == "013":
                break
            if status != "000":
                raise RuntimeError(f"status={status} message={obj.get('message')}")
            items = obj.get("list", []) or []
            for item in items:
                report_nm = str(item.get("report_nm", ""))
                if not PERIODIC_RE.search(report_nm):
                    continue
                r = dict(item)
                r["index_task_key"] = row["task_key"]
                r["query_corp_cls"] = row["corp_cls"]
                found.append(r)
            total_page = int(obj.get("total_page") or 1)
            if page >= total_page:
                break
            page += 1
            time.sleep(0.03)
        state = {
            "task_key": row["task_key"], "status": "OK", "rows_found": len(found),
            "updated_at_utc": now_utc(), "error": "",
        }
        return found, state
    except Exception as e:
        state = {
            "task_key": row["task_key"], "status": "ERROR", "rows_found": len(found),
            "updated_at_utc": now_utc(), "error": repr(e),
        }
        return found, state


def update_filing_index() -> pd.DataFrame:
    existing = load_csv(INDEX_FILE, dtype={"rcept_no": str, "corp_code": str})
    tasks = build_index_tasks()
    st = load_index_state()
    done = set(st.loc[st["status"] == "OK", "task_key"].astype(str)) if not st.empty else set()
    todo = tasks[~tasks["task_key"].isin(done)].head(MAX_INDEX_TASKS)

    new_rows: list[dict] = []
    state_rows: list[dict] = []
    for _, task in todo.iterrows():
        rows, state = fetch_index_task(task)
        new_rows.extend(rows)
        state_rows.append(state)
        if state["status"] == "ERROR" and "RateLimitExceeded" in state["error"]:
            break

    if state_rows:
        upsert_state(INDEX_STATE_FILE, state_rows, "task_key")

    if new_rows:
        add = pd.DataFrame(new_rows)
        all_idx = pd.concat([existing, add], ignore_index=True, sort=False) if not existing.empty else add
    else:
        all_idx = existing

    if all_idx.empty:
        return all_idx

    for c in ["rcept_no","corp_code","corp_name","report_nm","rcept_dt","corp_cls"]:
        if c not in all_idx.columns:
            all_idx[c] = ""
        all_idx[c] = all_idx[c].fillna("").astype(str)
    all_idx["rcept_dt"] = pd.to_datetime(all_idx["rcept_dt"], format="%Y%m%d", errors="coerce")

    inferred = all_idx.apply(lambda r: infer_report_fields(r["report_nm"], r["rcept_dt"]), axis=1, result_type="expand")
    for c in inferred.columns:
        all_idx[c] = inferred[c]
    all_idx = assign_fiscal_periods(all_idx)
    all_idx = map_filings_to_krx(all_idx)
    save_index(all_idx)
    return all_idx


def build_krx_name_intervals() -> pd.DataFrame:
    if NAME_MAP_FILE.exists():
        x = pd.read_csv(NAME_MAP_FILE, parse_dates=["first_date","last_date"], dtype={"stock_code":str})
        x["stock_code"] = x["stock_code"].astype(str).str.zfill(6)
        return x

    chunks = []
    for y in range(max(1999, START_YEAR - 1), END_YEAR + 2):
        p = KRX_YEARLY / f"marcap-{y}.parquet"
        if not p.exists():
            continue
        x = pd.read_parquet(p, columns=["Date","Code","Name","Market"])
        x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
        x["Code"] = x["Code"].astype(str).str.zfill(6)
        x["Market"] = x["Market"].astype(str).str.upper()
        x = x[x["Market"].isin(["KOSPI","KOSDAQ"])]
        g = x.groupby(["Code","Name","Market"], dropna=False)["Date"].agg(["min","max"]).reset_index()
        g.columns = ["stock_code","stock_name","market","first_date","last_date"]
        chunks.append(g)
    if not chunks:
        return pd.DataFrame(columns=["stock_code","stock_name","market","first_date","last_date","norm_name"])
    out = pd.concat(chunks, ignore_index=True)
    out = out.groupby(["stock_code","stock_name","market"], as_index=False).agg(
        first_date=("first_date","min"), last_date=("last_date","max")
    )
    out["norm_name"] = out["stock_name"].map(norm_name)
    out.to_csv(NAME_MAP_FILE, index=False, encoding="utf-8-sig", compression="gzip")
    return out


def assign_fiscal_periods(idx: pd.DataFrame) -> pd.DataFrame:
    x = idx.copy()
    annual = x[(x["report_kind"] == "FY") & x["period_month"].notna()].copy()
    fy_month = {}
    if not annual.empty:
        for corp, g in annual.groupby("corp_code"):
            vals = pd.to_numeric(g["period_month"], errors="coerce").dropna().astype(int)
            if len(vals):
                fy_month[str(corp)] = int(vals.mode().iloc[0])

    periods = []
    fiscal_years = []
    fy_months = []
    for _, r in x.iterrows():
        corp = str(r.get("corp_code",""))
        kind = str(r.get("report_kind",""))
        pm = pd.to_numeric(r.get("period_month"), errors="coerce")
        py = pd.to_numeric(r.get("period_year"), errors="coerce")
        fm = fy_month.get(corp, 12)
        fy_months.append(fm)

        if kind == "FY":
            period = "FY"
        elif kind == "H1":
            period = "H1"
        elif kind == "QX" and pd.notna(pm):
            delta = (int(pm) - fm) % 12
            if delta in {2,3,4}:
                period = "Q1"
            elif delta in {8,9,10}:
                period = "Q3"
            else:
                period = "QX"
        else:
            period = kind

        if pd.notna(py) and pd.notna(pm):
            # Fiscal year is labelled by the year containing the fiscal-year end.
            fiscal_year = int(py) if int(pm) <= fm else int(py) + 1
        else:
            fiscal_year = pd.NA
        periods.append(period)
        fiscal_years.append(fiscal_year)

    x["fiscal_year_end_month"] = fy_months
    x["period"] = periods
    x["fiscal_year"] = fiscal_years
    return x


def map_filings_to_krx(idx: pd.DataFrame) -> pd.DataFrame:
    x = idx.copy()
    intervals = build_krx_name_intervals()
    intervals["first_date"] = pd.to_datetime(intervals["first_date"], errors="coerce")
    intervals["last_date"] = pd.to_datetime(intervals["last_date"], errors="coerce")
    intervals["norm_name"] = intervals["norm_name"].fillna("").astype(str)

    modern = load_csv(MODERN_MAP_FILE, dtype={"stock_code":str,"corp_code":str})
    if not modern.empty:
        modern["stock_code"] = modern["stock_code"].astype(str).str.zfill(6)
        modern["corp_code"] = modern["corp_code"].fillna("").astype(str)
        modern["first_date"] = pd.to_datetime(modern["first_date"], errors="coerce")
        modern["last_date"] = pd.to_datetime(modern["last_date"], errors="coerce")
        modern_by_corp = modern[modern["corp_code"] != ""].drop_duplicates("corp_code").set_index("corp_code")
    else:
        modern_by_corp = pd.DataFrame()

    stocks=[]; methods=[]; map_conf=[]
    for _, r in x.iterrows():
        corp = str(r.get("corp_code",""))
        dt = pd.Timestamp(r["rcept_dt"]) if pd.notna(r.get("rcept_dt")) else pd.NaT
        chosen = ""
        method = "unmapped"
        confidence = 0.0

        if corp and not modern_by_corp.empty and corp in modern_by_corp.index:
            mr = modern_by_corp.loc[corp]
            if isinstance(mr, pd.DataFrame):
                mr = mr.iloc[-1]
            code = str(mr["stock_code"]).zfill(6)
            if pd.notna(dt):
                active = intervals[(intervals["stock_code"] == code) & (intervals["first_date"] <= dt) & (intervals["last_date"] >= dt)]
            else:
                active = intervals[intervals["stock_code"] == code]
            if len(active):
                chosen = code; method = "corp_code_active"; confidence = 1.0

        if not chosen and pd.notna(dt):
            nn = norm_name(r.get("corp_name",""))
            cand = intervals[
                (intervals["norm_name"] == nn)
                & (intervals["first_date"] <= dt)
                & (intervals["last_date"] >= dt)
            ].copy()
            cls = str(r.get("corp_cls",""))
            want_market = "KOSPI" if cls == "Y" else ("KOSDAQ" if cls == "K" else "")
            if want_market and len(cand[cand["market"] == want_market]):
                cand = cand[cand["market"] == want_market]
            codes = cand["stock_code"].drop_duplicates().tolist()
            if len(codes) == 1:
                chosen = str(codes[0]).zfill(6); method = "historical_name_active"; confidence = 0.95

        stocks.append(chosen)
        methods.append(method)
        map_conf.append(confidence)

    x["stock_code"] = stocks
    x["mapping_method"] = methods
    x["mapping_confidence"] = map_conf
    return x


def decode_legacy(data: bytes) -> str:
    for enc in ("cp949", "euc-kr", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("cp949", errors="replace")


def detect_unit(text: str) -> tuple[str, float]:
    s = re.sub(r"\s+", "", str(text or ""))
    m = re.search(r"단위[:：]?\(?\s*(백만원|천원|억원|원)\)?", s)
    if not m:
        return "", math.nan
    u = m.group(1)
    return u, UNIT_MULTIPLIERS[u]


def infer_scope(context: str) -> str:
    s = re.sub(r"\s+", "", str(context or ""))
    if "연결재무" in s or "연결대차대조표" in s or "연결손익계산서" in s or "연결현금흐름표" in s:
        return "CFS"
    if "별도재무" in s or "개별재무" in s:
        return "OFS"
    return "OFS"


def infer_statement(context: str) -> str:
    s = re.sub(r"\s+", "", str(context or ""))
    if "현금흐름표" in s:
        return "CF"
    if "포괄손익계산서" in s or "손익계산서" in s:
        return "IS"
    if "재무상태표" in s or "대차대조표" in s:
        return "BS"
    return ""


def previous_context(table) -> str:
    parts=[]
    for el in table.find_all_previous(limit=25):
        try:
            t=el.get_text(" ", strip=True)
        except Exception:
            continue
        if t:
            parts.append(t)
        if sum(len(x) for x in parts) > 1200:
            break
    return " ".join(reversed(parts))[-1400:]


def choose_metric(account: str, statement: str) -> tuple[str, int] | tuple[None, int]:
    a = norm_account(account)
    best = None
    best_score = 999
    for metric, aliases in ALIASES.items():
        if statement:
            hints = STATEMENT_HINTS[metric]
            required = "BS" if metric == "equity" else ("CF" if metric == "ocf" else "IS")
            if statement != required:
                continue
        for rank, alias in enumerate(aliases):
            na = norm_account(alias)
            if a == na:
                score = rank
            elif na and na in a and len(a) <= len(na) + 8:
                score = 20 + rank
            else:
                continue
            if score < best_score:
                best = metric; best_score = score
    return best, best_score


def table_candidates(text: str) -> list[dict]:
    soup = BeautifulSoup(text, "lxml")
    out=[]
    for ti, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        if not rows:
            continue
        ctx = previous_context(table) + " " + table.get_text(" ", strip=True)[:500]
        statement = infer_statement(ctx)
        scope = infer_scope(ctx)

        unit_text = table.get_text(" ", strip=True)[:1000] + " " + previous_context(table)[-500:]
        unit, mult = detect_unit(unit_text)

        header_rows=[]
        for ri, tr in enumerate(rows[:8]):
            cells=[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"])]
            header_rows.append(cells)
        note_cols=set()
        for hr in header_rows:
            for ci, cell in enumerate(hr):
                if "주석" in cell:
                    note_cols.add(ci)

        for ri, tr in enumerate(rows):
            cells=[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"])]
            if len(cells) < 2:
                continue
            for ci, cell in enumerate(cells):
                metric, priority = choose_metric(cell, statement)
                if metric is None:
                    continue
                val=math.nan; raw_val=""; value_col=-1
                for cj in range(ci+1, len(cells)):
                    if cj in note_cols:
                        continue
                    v=parse_number(cells[cj])
                    if not math.isnan(v):
                        val=v; raw_val=cells[cj]; value_col=cj
                        break
                if math.isnan(val):
                    continue
                amount_krw = val * mult if not math.isnan(mult) else math.nan
                conf = 0.45
                if statement: conf += 0.20
                if priority < 10: conf += 0.15
                if unit: conf += 0.15
                if scope == "CFS": conf += 0.02
                out.append({
                    "metric":metric, "scope":scope, "statement":statement,
                    "account_name":cell, "raw_amount":raw_val, "amount_reported":val,
                    "unit":unit, "unit_multiplier":mult, "amount_krw":amount_krw,
                    "priority":priority, "parser_confidence":min(conf,0.99),
                    "table_index":ti, "row_index":ri, "value_col":value_col,
                })
                break
    return out


def select_best_candidates(cands: list[dict]) -> list[dict]:
    if not cands:
        return []
    df=pd.DataFrame(cands)
    df["unit_known"]=df["unit"].astype(str).ne("")
    df=df.sort_values(
        ["metric","scope","unit_known","parser_confidence","priority","table_index","row_index"],
        ascending=[True,True,False,False,True,True,True]
    )
    best=df.groupby(["metric","scope"],as_index=False).head(1).copy()
    counts=df.groupby(["metric","scope"]).size().rename("candidate_count").reset_index()
    best=best.merge(counts,on=["metric","scope"],how="left")
    return best.to_dict("records")


def fetch_document(rcept_no: str) -> tuple[bytes, str]:
    last=None
    for attempt in range(4):
        try:
            r=requests.get(f"{BASE}/document.xml",params={"crtfc_key":API_KEY,"rcept_no":rcept_no},timeout=90)
            r.raise_for_status()
            if r.content[:2] != b"PK":
                txt=r.text[:500]
                if "020" in txt:
                    raise RateLimitExceeded(txt)
                raise RuntimeError(f"document not zip: {txt}")
            return r.content, hashlib.sha256(r.content).hexdigest()
        except RateLimitExceeded:
            raise
        except (requests.Timeout, requests.ConnectionError) as e:
            last=e
            if attempt<3:
                time.sleep(2*(attempt+1))
    raise RuntimeError(f"document fetch failed {last!r}")


def process_filing(meta: dict) -> tuple[list[dict], dict]:
    rcept=str(meta["rcept_no"])
    try:
        blob, sha=fetch_document(rcept)
        all_cands=[]
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names=[n for n in z.namelist() if not n.endswith("/")]
            for n in names:
                try:
                    data=z.read(n)
                    text=decode_legacy(data)
                    all_cands.extend(table_candidates(text))
                except Exception:
                    continue
        best=select_best_candidates(all_cands)
        rows=[]
        for rec in best:
            rec.update({
                "rcept_no":rcept,
                "corp_code":str(meta.get("corp_code","")),
                "corp_name":str(meta.get("corp_name","")),
                "stock_code":str(meta.get("stock_code","")).zfill(6) if str(meta.get("stock_code","")) else "",
                "report_nm":str(meta.get("report_nm","")),
                "filing_date":str(pd.Timestamp(meta["rcept_dt"]).date()) if pd.notna(meta.get("rcept_dt")) else "",
                "period_end":str(pd.Timestamp(meta["period_end"]).date()) if pd.notna(meta.get("period_end")) else "",
                "fiscal_year":meta.get("fiscal_year",pd.NA),
                "period":meta.get("period",""),
                "document_sha256":sha,
            })
            rows.append(rec)

        scopes={}
        for scope in ("CFS","OFS"):
            have={r["metric"] for r in rows if r["scope"]==scope and not math.isnan(float(r["amount_krw"]))}
            scopes[scope]=len(have)
        best_scope=max(scopes,key=scopes.get) if scopes else ""
        usable=max(scopes.values()) if scopes else 0
        status="PARSED_4F" if usable>=4 else ("PARSED_PARTIAL" if rows else "NO_METRICS")
        state={
            "rcept_no":rcept,"status":status,"metric_rows":len(rows),
            "best_scope":best_scope,"usable_metric_count":usable,
            "document_sha256":sha,"updated_at_utc":now_utc(),"error":""
        }
        return rows,state
    except RateLimitExceeded as e:
        return [],{"rcept_no":rcept,"status":"RATE_LIMIT","metric_rows":0,"best_scope":"",
                   "usable_metric_count":0,"document_sha256":"","updated_at_utc":now_utc(),"error":repr(e)}
    except Exception as e:
        return [],{"rcept_no":rcept,"status":"ERROR","metric_rows":0,"best_scope":"",
                   "usable_metric_count":0,"document_sha256":"","updated_at_utc":now_utc(),"error":repr(e)}


def append_normalized(rows: list[dict]) -> None:
    if not rows:
        return
    add=pd.DataFrame(rows)
    add["fiscal_year"]=pd.to_numeric(add["fiscal_year"],errors="coerce").astype("Int64")
    for y,g in add.groupby("fiscal_year",dropna=False):
        label="unknown" if pd.isna(y) else str(int(y))
        p=NORM_DIR/f"legacy_metrics_{label}.csv.gz"
        old=load_csv(p,dtype={"rcept_no":str,"stock_code":str,"corp_code":str})
        out=pd.concat([old,g],ignore_index=True,sort=False) if not old.empty else g
        out=out.drop_duplicates(["rcept_no","metric","scope"],keep="last")
        out.to_csv(p,index=False,encoding="utf-8-sig",compression="gzip")


def process_pending(idx: pd.DataFrame) -> None:
    if idx.empty:
        return
    state=load_csv(STATE_FILE,dtype={"rcept_no":str})
    terminal={"PARSED_4F","PARSED_PARTIAL","NO_METRICS"}
    done=set(state.loc[state["status"].isin(terminal),"rcept_no"].astype(str)) if not state.empty else set()
    eligible=idx[
        idx["stock_code"].fillna("").astype(str).str.fullmatch(r"\d{6}")
        & idx["rcept_no"].astype(str).ne("")
        & ~idx["rcept_no"].astype(str).isin(done)
    ].copy()
    eligible=eligible.sort_values(["rcept_dt","rcept_no"]).head(MAX_DOCS)
    if eligible.empty:
        return

    metric_rows=[]
    state_rows=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(process_filing,r.to_dict()):str(r["rcept_no"]) for _,r in eligible.iterrows()}
        rate_limited=False
        for fut in as_completed(futs):
            rows,st=fut.result()
            metric_rows.extend(rows); state_rows.append(st)
            if st["status"]=="RATE_LIMIT":
                rate_limited=True
        # already submitted requests cannot be cancelled reliably; next run resumes safely.

    append_normalized(metric_rows)
    if state_rows:
        upsert_state(STATE_FILE,state_rows,"rcept_no")


def write_coverage(idx: pd.DataFrame) -> None:
    state=load_csv(STATE_FILE,dtype={"rcept_no":str})
    if idx.empty:
        pd.DataFrame().to_csv(COVERAGE_FILE,index=False,encoding="utf-8-sig")
        return

    x=idx.copy()
    x["mapped"]=x["stock_code"].fillna("").astype(str).str.fullmatch(r"\d{6}")
    if not state.empty:
        keep=[c for c in ["rcept_no","status","usable_metric_count"] if c in state.columns]
        x=x.merge(state[keep].drop_duplicates("rcept_no",keep="last"),on="rcept_no",how="left")
    else:
        x["status"]=""; x["usable_metric_count"]=0
    x["processed"]=x["status"].isin(["PARSED_4F","PARSED_PARTIAL","NO_METRICS"])
    x["usable_4f"]=x["status"].eq("PARSED_4F")

    cov=x.groupby(["fiscal_year","period"],dropna=False).agg(
        indexed_filings=("rcept_no","nunique"),
        mapped_filings=("mapped","sum"),
        processed_filings=("processed","sum"),
        usable_four_factor_filings=("usable_4f","sum"),
        mapped_companies=("stock_code",lambda s:s[s.astype(str).str.fullmatch(r"\d{6}")].nunique()),
    ).reset_index()
    cov["processing_pct"]=(100*cov["processed_filings"]/cov["mapped_filings"].replace(0,pd.NA)).round(2)
    cov["usable_pct_of_processed"]=(100*cov["usable_four_factor_filings"]/cov["processed_filings"].replace(0,pd.NA)).round(2)
    cov["generated_at_utc"]=now_utc()
    cov.to_csv(COVERAGE_FILE,index=False,encoding="utf-8-sig")

    tasks=build_index_tasks()
    ist=load_index_state()
    done=set(ist.loc[ist["status"]=="OK","task_key"].astype(str)) if not ist.empty else set()
    indexed_complete=len(done)==len(tasks)

    total_mapped=int(x["mapped"].sum())
    processed=int(x["processed"].sum())
    usable=int(x["usable_4f"].sum())
    status=pd.DataFrame([{
        "mode":"BACKFILL_ACTIVE" if not indexed_complete or processed<total_mapped else "COMPLETE",
        "index_tasks_total":len(tasks),
        "index_tasks_completed":len(done),
        "index_complete":indexed_complete,
        "indexed_filings":int(x["rcept_no"].nunique()),
        "mapped_filings":total_mapped,
        "processed_filings":processed,
        "usable_four_factor_filings":usable,
        "remaining_mapped_filings":max(total_mapped-processed,0),
        "document_batch_limit":MAX_DOCS,
        "workers":WORKERS,
        "updated_at_utc":now_utc(),
    }])
    status.to_csv(STATUS_FILE,index=False,encoding="utf-8-sig")


def main() -> None:
    if not API_KEY:
        pd.DataFrame([{"mode":"SKIPPED","reason":"DART_API_KEY missing","updated_at_utc":now_utc()}]).to_csv(
            STATUS_FILE,index=False,encoding="utf-8-sig"
        )
        return

    idx=update_filing_index()
    process_pending(idx)
    # Reload index/state after writes for accurate status.
    idx=load_csv(INDEX_FILE,dtype={"rcept_no":str,"corp_code":str,"stock_code":str})
    if not idx.empty:
        idx["rcept_dt"]=pd.to_datetime(idx["rcept_dt"],errors="coerce")
        idx["period_end"]=pd.to_datetime(idx["period_end"],errors="coerce")
    write_coverage(idx)

    if STATUS_FILE.exists():
        print(pd.read_csv(STATUS_FILE).to_string(index=False),flush=True)
    if COVERAGE_FILE.exists():
        cov=pd.read_csv(COVERAGE_FILE)
        print(cov.head(30).to_string(index=False),flush=True)


if __name__ == "__main__":
    main()
