from __future__ import annotations

import hashlib
import io
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import requests

API_KEY = os.getenv("DART_API_KEY", "").strip()
MAX_TASKS = max(1, int(os.getenv("DART_FULL_BACKFILL_TASKS", "3000")))
WORKERS = max(1, min(8, int(os.getenv("DART_FULL_BACKFILL_WORKERS", "6"))))
BASE = "https://opendart.fss.or.kr/api"

REPORT_CODES = {
    "Q1": "11013",
    "H1": "11012",
    "Q3": "11014",
    "FY": "11011",
}
PERIOD_END_MMDD = {
    "Q1": "03-31",
    "H1": "06-30",
    "Q3": "09-30",
    "FY": "12-31",
}
FS_DIVS = ("CFS", "OFS")

ROOT = Path("data/financials")
FULL_DIR = ROOT / "full_history"
STATUS_DIR = Path("data/status")
LIFE_FILE = Path("results/security_life_table.csv")
CURRENT_YEAR_DIR = Path("data/krx_equities/yearly")
MAP_FILE = ROOT / "dart_historical_code_map.csv"
TASK_FILE = STATUS_DIR / "dart_full_backfill_state.csv"
STATUS_FILE = STATUS_DIR / "dart_full_backfill_status.csv"

ROOT.mkdir(parents=True, exist_ok=True)
FULL_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)


class RateLimitExceeded(RuntimeError):
    pass


class FatalDartError(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    s = str(value or "").strip().lower()
    s = s.replace("주식회사", "").replace("(주)", "").replace("㈜", "")
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def load_all_dart_corps() -> pd.DataFrame:
    r = requests.get(f"{BASE}/corpCode.xml", params={"crtfc_key": API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    root = ET.fromstring(xml)
    rows = [{child.tag: child.text for child in node} for node in root.findall("list")]
    df = pd.DataFrame(rows)
    for c in ["corp_code", "corp_name", "stock_code", "modify_date"]:
        if c not in df.columns:
            df[c] = ""
    df["corp_code"] = df["corp_code"].fillna("").astype(str).str.strip()
    df["corp_name"] = df["corp_name"].fillna("").astype(str).str.strip()
    raw_code = df["stock_code"].fillna("").astype(str).str.strip()
    df["stock_code"] = raw_code.where(raw_code.str.fullmatch(r"\d{6}"), "")
    df["norm_name"] = df["corp_name"].map(normalize_name)
    return df.drop_duplicates("corp_code", keep="last").reset_index(drop=True)


def load_current_year_first_dates(now_kst: datetime) -> dict[str, pd.Timestamp]:
    p = CURRENT_YEAR_DIR / f"marcap-{now_kst.year}.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p, columns=["Date", "Code"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Code"] = df["Code"].astype(str).str.zfill(6)
    out = df.dropna(subset=["Date"]).groupby("Code")["Date"].min()
    return out.to_dict()


def build_historical_code_map(corp: pd.DataFrame, now_kst: datetime) -> pd.DataFrame:
    if not LIFE_FILE.exists():
        raise FileNotFoundError(f"Missing {LIFE_FILE}")

    life = pd.read_csv(LIFE_FILE, dtype={"Code": str})
    life["Code"] = life["Code"].astype(str).str.zfill(6)
    life["first_date"] = pd.to_datetime(life["first_date"], errors="coerce")
    life["last_date"] = pd.to_datetime(life["last_date"], errors="coerce")
    life = life[life["last_date"] >= pd.Timestamp("2015-01-01")].copy()
    life["norm_name"] = life["name"].map(normalize_name)

    by_code = (
        corp[corp["stock_code"] != ""][["stock_code", "corp_code", "corp_name"]]
        .drop_duplicates("stock_code", keep="last")
        .set_index("stock_code")
    )

    name_counts = corp[corp["norm_name"] != ""].groupby("norm_name")["corp_code"].nunique()
    unique_norm_names = set(name_counts[name_counts == 1].index)
    by_name = (
        corp[corp["norm_name"].isin(unique_norm_names)][["norm_name", "corp_code", "corp_name"]]
        .drop_duplicates("norm_name", keep="last")
        .set_index("norm_name")
    )

    rows: list[dict] = []
    seen_codes: set[str] = set()
    for _, r in life.iterrows():
        stock_code = r["Code"]
        seen_codes.add(stock_code)
        corp_code = ""
        dart_name = ""
        method = "unmatched"

        if stock_code in by_code.index:
            d = by_code.loc[stock_code]
            corp_code = str(d["corp_code"])
            dart_name = str(d["corp_name"])
            method = "stock_code"
        elif r["norm_name"] and r["norm_name"] in by_name.index:
            d = by_name.loc[r["norm_name"]]
            corp_code = str(d["corp_code"])
            dart_name = str(d["corp_name"])
            method = "normalized_name_unique"

        rows.append(
            {
                "stock_code": stock_code,
                "marcap_name": r.get("name", ""),
                "corp_code": corp_code,
                "dart_name": dart_name,
                "mapping_method": method,
                "first_date": r["first_date"],
                "last_date": r["last_date"],
            }
        )

    # Add newly listed/current companies missing from the historical life-table snapshot.
    first_dates = load_current_year_first_dates(now_kst)
    current = corp[corp["stock_code"].str.fullmatch(r"\d{6}")].copy()
    for _, r in current.iterrows():
        stock_code = str(r["stock_code"]).zfill(6)
        if stock_code in seen_codes:
            continue
        first_date = first_dates.get(stock_code, pd.Timestamp(f"{now_kst.year}-01-01"))
        rows.append(
            {
                "stock_code": stock_code,
                "marcap_name": r["corp_name"],
                "corp_code": r["corp_code"],
                "dart_name": r["corp_name"],
                "mapping_method": "current_stock_code",
                "first_date": first_date,
                "last_date": pd.Timestamp(now_kst.date()),
            }
        )

    out = pd.DataFrame(rows).sort_values("stock_code").reset_index(drop=True)
    out.to_csv(MAP_FILE, index=False, encoding="utf-8-sig")
    return out


def report_available_after(year: int, period: str) -> pd.Timestamp:
    # Conservative collection cutoffs only. Backtests must use actual filing_date.
    if period == "Q1":
        return pd.Timestamp(f"{year}-05-16")
    if period == "H1":
        return pd.Timestamp(f"{year}-08-16")
    if period == "Q3":
        return pd.Timestamp(f"{year}-11-16")
    if period == "FY":
        return pd.Timestamp(f"{year + 1}-04-01")
    raise ValueError(f"Unknown period: {period}")


def build_tasks(mapping: pd.DataFrame, now_kst: datetime) -> pd.DataFrame:
    today = pd.Timestamp(now_kst.date())
    current_year = now_kst.year
    rows: list[dict] = []

    mapped = mapping[mapping["corp_code"].astype(str).str.fullmatch(r"\d{8}")].copy()
    for _, r in mapped.iterrows():
        first_date = pd.Timestamp(r["first_date"])
        last_date = pd.Timestamp(r["last_date"])
        start_year = max(2015, first_date.year - 1)
        end_year = min(current_year, last_date.year)

        for year in range(start_year, end_year + 1):
            periods = ["FY"] if year < first_date.year else ["Q1", "H1", "Q3", "FY"]
            for period in periods:
                if today < report_available_after(year, period):
                    continue
                for fs_div in FS_DIVS:
                    rows.append(
                        {
                            "stock_code": r["stock_code"],
                            "corp_code": r["corp_code"],
                            "year": year,
                            "period": period,
                            "period_end": f"{year}-{PERIOD_END_MMDD[period]}",
                            "reprt_code": REPORT_CODES[period],
                            "fs_div": fs_div,
                        }
                    )

    tasks = pd.DataFrame(rows)
    if tasks.empty:
        return tasks

    period_order = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}
    fs_order = {"CFS": 1, "OFS": 2}
    tasks["_period_order"] = tasks["period"].map(period_order)
    tasks["_fs_order"] = tasks["fs_div"].map(fs_order)
    return (
        tasks.drop_duplicates(["stock_code", "corp_code", "year", "period", "fs_div"])
        .sort_values(["year", "_period_order", "_fs_order", "stock_code"])
        .drop(columns=["_period_order", "_fs_order"])
        .reset_index(drop=True)
    )


def api_call(task: dict) -> list[dict]:
    params = {
        "crtfc_key": API_KEY,
        "corp_code": str(task["corp_code"]),
        "bsns_year": str(int(task["year"])),
        "reprt_code": str(task["reprt_code"]),
        "fs_div": str(task["fs_div"]),
    }
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/fnlttSinglAcntAll.json", params=params, timeout=30)
            r.raise_for_status()
            obj = r.json()
            status = str(obj.get("status", ""))
            if status == "000":
                return obj.get("list", []) or []
            if status in {"013", "014"}:
                return []
            if status == "020":
                raise RateLimitExceeded(obj.get("message", "request limit exceeded"))
            if status in {"010", "011", "012", "901"}:
                raise FatalDartError(f'DART status={status}: {obj.get("message")}')
            raise RuntimeError(f'DART status={status}: {obj.get("message")}')
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
            time.sleep(1.0 + attempt)
    return []


def process_task(task: dict) -> tuple[dict, list[dict]]:
    raw = api_call(task)
    now_utc = datetime.now(timezone.utc).isoformat()
    stock_code = str(task["stock_code"]).zfill(6)
    corp_code = str(task["corp_code"])
    year = int(task["year"])
    period = str(task["period"])
    fs_div = str(task["fs_div"])

    state = {
        "stock_code": stock_code,
        "corp_code": corp_code,
        "year": year,
        "period": period,
        "period_end": task["period_end"],
        "reprt_code": task["reprt_code"],
        "fs_div": fs_div,
        "status": "OK" if raw else "NO_DATA",
        "rows_saved": len(raw),
        "error": "",
        "updated_at_utc": now_utc,
    }

    rows: list[dict] = []
    for item in raw:
        out = dict(item)
        rcept_no = str(out.get("rcept_no", "") or "")
        out.update(
            {
                "_stock_code": stock_code,
                "_corp_code": corp_code,
                "_requested_year": year,
                "_period": period,
                "_period_end": task["period_end"],
                "_reprt_code": task["reprt_code"],
                "_fs_div_requested": fs_div,
                "_filing_date": rcept_no[:8] if len(rcept_no) >= 8 else "",
                "_collected_at_utc": now_utc,
            }
        )
        rows.append(out)
    return state, rows


def read_done_keys() -> set[tuple[str, str, int, str, str]]:
    if not TASK_FILE.exists():
        return set()
    state = pd.read_csv(TASK_FILE, dtype={"stock_code": str, "corp_code": str})
    done = state[state["status"].isin(["OK", "NO_DATA"])].copy()
    return set(
        zip(
            done["stock_code"].astype(str).str.zfill(6),
            done["corp_code"].astype(str),
            done["year"].astype(int),
            done["period"].astype(str),
            done["fs_div"].astype(str),
        )
    )


def save_state(new_rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(new_rows)
    if TASK_FILE.exists():
        old = pd.read_csv(TASK_FILE, dtype={"stock_code": str, "corp_code": str})
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new

    if len(out):
        out["stock_code"] = out["stock_code"].astype(str).str.zfill(6)
        out = out.sort_values("updated_at_utc").drop_duplicates(
            ["stock_code", "corp_code", "year", "period", "fs_div"], keep="last"
        )
    out.to_csv(TASK_FILE, index=False, encoding="utf-8-sig")
    return out


def shard_path(year: int, period: str, fs_div: str) -> Path:
    return FULL_DIR / f"dart_full_{year}_{period}_{fs_div}.csv.gz"


def _batch_digest(df: pd.DataFrame) -> str:
    cols = [
        c
        for c in [
            "_stock_code",
            "_corp_code",
            "_requested_year",
            "_period",
            "_fs_div_requested",
            "rcept_no",
            "sj_div",
            "account_id",
            "account_nm",
            "thstrm_nm",
        ]
        if c in df.columns
    ]
    if not cols:
        payload = str(len(df)).encode("utf-8")
    else:
        stable = df[cols].fillna("").astype(str).sort_values(cols)
        payload = stable.to_csv(index=False).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def merge_full_rows(new_rows: list[dict]) -> int:
    """Write immutable compressed batches instead of rewriting historical blobs.

    Git stores binary gzip blobs inefficiently when they are rewritten. Immutable
    batches keep repository growth predictable and preserve collection lineage.
    Downstream factor builders should read all matching batch files and deduplicate
    on filing/account keys.
    """
    if not new_rows:
        return 0

    new = pd.DataFrame(new_rows)
    total_written = 0
    grouping = ["_requested_year", "_period", "_fs_div_requested"]
    max_rows_per_file = 100_000

    for (year, period, fs_div), group in new.groupby(grouping, dropna=False):
        out = group.copy()
        if "_stock_code" in out.columns:
            out["_stock_code"] = out["_stock_code"].astype(str).str.zfill(6)

        preferred_keys = [
            "_stock_code",
            "_corp_code",
            "_requested_year",
            "_period",
            "_fs_div_requested",
            "rcept_no",
            "sj_div",
            "account_id",
            "account_nm",
            "thstrm_nm",
        ]
        keys = [c for c in preferred_keys if c in out.columns]
        if keys:
            out = out.drop_duplicates(keys, keep="last")

        sort_cols = [
            c
            for c in [
                "_stock_code",
                "rcept_no",
                "sj_div",
                "ord",
                "account_id",
                "account_nm",
            ]
            if c in out.columns
        ]
        if sort_cols:
            out = out.sort_values(sort_cols).reset_index(drop=True)

        for start in range(0, len(out), max_rows_per_file):
            chunk = out.iloc[start : start + max_rows_per_file].copy()
            digest = _batch_digest(chunk)
            path = FULL_DIR / (
                f"dart_full_{int(year)}_{str(period)}_{str(fs_div)}_{digest}.csv.gz"
            )
            if not path.exists():
                chunk.to_csv(path, index=False, encoding="utf-8-sig", compression="gzip")
            total_written += len(chunk)

    return total_written


def main() -> None:
    if not API_KEY:
        raise FatalDartError("DART_API_KEY is missing")

    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)

    corp = load_all_dart_corps()
    mapping = build_historical_code_map(corp, now_kst)
    tasks = build_tasks(mapping, now_kst)
    done = read_done_keys()

    if len(tasks):
        keys = list(
            zip(
                tasks["stock_code"].astype(str).str.zfill(6),
                tasks["corp_code"].astype(str),
                tasks["year"].astype(int),
                tasks["period"].astype(str),
                tasks["fs_div"].astype(str),
            )
        )
        pending_mask = [key not in done for key in keys]
        pending = tasks.loc[pending_mask].head(MAX_TASKS).copy()
    else:
        pending = tasks

    mapped_count = int((mapping["mapping_method"] != "unmatched").sum())
    print(
        f"DART full backfill: mapped={mapped_count}/{len(mapping)} "
        f"total_tasks={len(tasks)} run_tasks={len(pending)} workers={WORKERS}",
        flush=True,
    )

    states: list[dict] = []
    full_rows: list[dict] = []
    rate_limited = False

    if len(pending):
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            future_map = {
                executor.submit(process_task, row.to_dict()): row.to_dict()
                for _, row in pending.iterrows()
            }
            completed = 0
            for future in as_completed(future_map):
                task = future_map[future]
                try:
                    state, rows = future.result()
                    states.append(state)
                    full_rows.extend(rows)
                except RateLimitExceeded as exc:
                    rate_limited = True
                    states.append(
                        {
                            **task,
                            "status": "ERROR",
                            "rows_saved": 0,
                            "error": f"RATE_LIMIT: {exc}",
                            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                except FatalDartError:
                    raise
                except Exception as exc:
                    states.append(
                        {
                            **task,
                            "status": "ERROR",
                            "rows_saved": 0,
                            "error": repr(exc),
                            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                completed += 1
                if completed % 250 == 0 or completed == len(pending):
                    print(f"DART full backfill progress {completed}/{len(pending)}", flush=True)

    rows_written_this_run = merge_full_rows(full_rows)

    if states:
        state_df = save_state(states)
    elif TASK_FILE.exists():
        state_df = pd.read_csv(TASK_FILE)
    else:
        state_df = pd.DataFrame()

    done_count = int(state_df["status"].isin(["OK", "NO_DATA"]).sum()) if len(state_df) else 0
    error_count = int((state_df["status"] == "ERROR").sum()) if len(state_df) else 0
    unmatched_count = int((mapping["mapping_method"] == "unmatched").sum())

    status_df = pd.DataFrame(
        [
            {
                "status": "RATE_LIMITED" if rate_limited else "OK",
                "historical_codes": len(mapping),
                "mapped_codes": mapped_count,
                "unmatched_codes": unmatched_count,
                "total_available_tasks": len(tasks),
                "completed_tasks": done_count,
                "remaining_tasks_estimate": max(0, len(tasks) - done_count),
                "error_tasks": error_count,
                "full_rows_written_this_run": rows_written_this_run,
                "full_shards_present": len(list(FULL_DIR.glob("dart_full_*.csv.gz"))),
                "max_tasks_per_run": MAX_TASKS,
                "workers": WORKERS,
                "updated_at_utc": now_utc.isoformat(),
            }
        ]
    )
    status_df.to_csv(STATUS_FILE, index=False, encoding="utf-8-sig")
    print(status_df.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
