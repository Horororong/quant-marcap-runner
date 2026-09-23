from __future__ import annotations

import json
import math
import re
import importlib.util
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "super_value_v216"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 10_000_000.0
AS_OF = pd.Timestamp("2026-09-23")

_TEMPLATE_PATH = ROOT / "scripts" / "quant_backtest_template_PROJECT_v2-16_CURRENT.py"
_spec = importlib.util.spec_from_file_location("quant_current_v216", _TEMPLATE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load CURRENT v2-16 template: {_TEMPLATE_PATH}")
CURRENT = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = CURRENT
_spec.loader.exec_module(CURRENT)

METRIC_CONFIG = CURRENT.BacktestConfig(
    title="오리지널 강환국 슈퍼 가치 전략",
    initial_capital=INITIAL_CAPITAL,
    risk_free_rate=0.0,
    as_of_date=str(AS_OF.date()),
    market_calendar="XKRX",
)

TOP_NS = (20, 30, 50)
BASE_TOP_N = 20
MARKETS = ("KOSPI", "KOSDAQ")


@dataclass(frozen=True)
class CostScenario:
    name: str
    commission_bps: float
    spread_bps: float
    slippage_bps: float
    market_impact_bps: float

    @property
    def common_bps(self) -> float:
        return self.commission_bps + self.spread_bps + self.slippage_bps + self.market_impact_bps


COSTS = {
    "gross": CostScenario("gross", 0.0, 0.0, 0.0, 0.0),
    "minimum": CostScenario("minimum", 1.5, 0.0, 0.0, 0.0),
    "base": CostScenario("base", 1.5, 10.0, 10.0, 0.0),
    "conservative": CostScenario("conservative", 2.0, 20.0, 20.0, 10.0),
}


def sell_tax_bps(dt: pd.Timestamp) -> float:
    # Verified historical regime needed by the currently complete PIT window.
    # KOSPI: transaction tax + rural special tax; KOSDAQ: transaction tax.
    # Both totaled 30bp before 2019-05-30, then 25bp from 2019-05-30.
    return 30.0 if pd.Timestamp(dt) < pd.Timestamp("2019-06-03") else 25.0


def to_num(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).strip().replace(",", "")
    if s in {"", "-", "--", "nan", "None"}:
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return np.nan


def normalize_name(x: str) -> str:
    return re.sub(r"\s+", "", str(x or "")).lower()


def load_map() -> pd.DataFrame:
    p = ROOT / "data/financials/dart_historical_code_map.csv"
    x = pd.read_csv(p, dtype={"stock_code": str, "corp_code": str})
    x["stock_code"] = x["stock_code"].astype(str).str.zfill(6)
    x["corp_code"] = x["corp_code"].fillna("").astype(str).str.strip()
    x["first_date"] = pd.to_datetime(x["first_date"], errors="coerce")
    x["last_date"] = pd.to_datetime(x["last_date"], errors="coerce")
    return x


def load_state() -> pd.DataFrame:
    p = ROOT / "data/status/dart_full_backfill_state.csv"
    x = pd.read_csv(p, dtype={"stock_code": str, "corp_code": str})
    x["stock_code"] = x["stock_code"].astype(str).str.zfill(6)
    x["corp_code"] = x["corp_code"].astype(str).str.strip()
    x["year"] = pd.to_numeric(x["year"], errors="coerce").astype("Int64")
    x["period"] = x["period"].astype(str)
    x["fs_div"] = x["fs_div"].astype(str)
    return x


def expected_codes_for_period(mapping: pd.DataFrame, year: int, period: str) -> set[str]:
    # Conservative completeness gate. A code is expected when it was mapped and
    # existed at some point in the report year. This is stricter than the actual
    # signal cross-section and therefore does not falsely call an incomplete year complete.
    x = mapping[
        mapping["corp_code"].str.fullmatch(r"\d{8}", na=False)
        & mapping["first_date"].notna()
        & mapping["last_date"].notna()
        & (mapping["first_date"].dt.year <= year)
        & (mapping["last_date"].dt.year >= year)
    ]
    return set(x["stock_code"].astype(str))


def completion_ratio(mapping: pd.DataFrame, state: pd.DataFrame, year: int, period: str, fs_div: str) -> tuple[int, int, float]:
    expected = expected_codes_for_period(mapping, year, period)
    done = state[
        (state["year"] == year)
        & (state["period"] == period)
        & (state["fs_div"] == fs_div)
        & state["status"].isin(["OK", "NO_DATA"])
    ]
    done_codes = set(done["stock_code"].astype(str))
    n_exp = len(expected)
    n_done = len(expected & done_codes)
    return n_done, n_exp, (n_done / n_exp if n_exp else 0.0)


def required_periods(signal: pd.Timestamp) -> list[tuple[int, str]]:
    y = signal.year
    if signal.month == 10:
        return [(y, "Q1"), (y, "H1")]
    if signal.month == 4:
        return [(y - 1, "Q3"), (y - 1, "FY")]
    raise ValueError(signal)


def signal_completeness(mapping: pd.DataFrame, state: pd.DataFrame, signal: pd.Timestamp) -> tuple[bool, list[dict]]:
    rows = []
    ok = True
    for y, p in required_periods(signal):
        for fs in ("CFS", "OFS"):
            d, e, r = completion_ratio(mapping, state, y, p, fs)
            shards = list((ROOT / "data/financials/full_history").glob(f"dart_full_{y}_{p}_{fs}_*.csv.gz"))
            has_raw_shard = len(shards) > 0
            rows.append({"signal_date": signal, "year": y, "period": p, "fs_div": fs,
                         "completed_codes": d, "expected_codes": e, "ratio": r,
                         "raw_shards": len(shards), "has_raw_shard": has_raw_shard})
            # NO_DATA tasks can be 'complete' without any usable standardized report rows.
            # A signal is accepted only when task coverage is complete AND raw shards exist.
            if r < 1.0 or not has_raw_shard:
                ok = False
    return ok, rows


def load_krx(start: str, end: str) -> pd.DataFrame:
    chunks = []
    y0, y1 = pd.Timestamp(start).year, pd.Timestamp(end).year
    cols = ["Date", "Code", "Name", "Market", "Open", "Close", "Volume", "Amount",
            "Marcap", "Stocks", "ChangesRatio", "Change"]
    for year in range(y0, y1 + 1):
        p = ROOT / f"data/krx_equities/yearly/marcap-{year}.parquet"
        if not p.exists():
            raise FileNotFoundError(p)
        raw = pd.read_parquet(p)
        use = [c for c in cols if c in raw.columns]
        x = raw[use].copy()
        x["Date"] = pd.to_datetime(x["Date"], errors="coerce").dt.normalize()
        x["Code"] = x["Code"].astype(str).str.zfill(6)
        x["Market"] = x["Market"].astype(str).str.upper().str.strip()
        x = x[x["Market"].isin(MARKETS)]
        if "Change" not in x.columns:
            if "ChangesRatio" not in x.columns:
                raise AssertionError(f"{p.name}: ChangesRatio/Change both missing")
            x["Change"] = pd.to_numeric(x["ChangesRatio"], errors="coerce") / 100.0
        else:
            x["Change"] = pd.to_numeric(x["Change"], errors="coerce")
        for c in ("Close", "Volume", "Amount", "Marcap"):
            x[c] = pd.to_numeric(x[c], errors="coerce")
        chunks.append(x)
    out = pd.concat(chunks, ignore_index=True)
    out = out[(out["Date"] >= pd.Timestamp(start)) & (out["Date"] <= pd.Timestamp(end))]
    out = out.sort_values(["Date", "Code"]).drop_duplicates(["Date", "Code"], keep="last")
    if out.duplicated(["Date", "Code"]).any():
        raise AssertionError("KRX duplicate Date+Code")
    return out.reset_index(drop=True)


def load_financial_raw(year: int, period: str) -> pd.DataFrame:
    files = []
    for fs in ("CFS", "OFS"):
        files += sorted((ROOT / "data/financials/full_history").glob(f"dart_full_{year}_{period}_{fs}_*.csv.gz"))
    if not files:
        raise FileNotFoundError(f"No full_history shards for {year} {period}")

    wanted = {
        "_stock_code","stock_code","_filing_date","filing_date",
        "_fs_div_requested","fs_div_requested","fs_div",
        "_period","period","_requested_year","requested_year",
        "rcept_no","sj_div","account_id","account_nm",
        "thstrm_amount","thstrm_add_amount",
    }
    chunks = []
    for p in files:
        x = pd.read_csv(p, low_memory=False, dtype=str, usecols=lambda z: z in wanted)
        ren = {}
        if "_stock_code" in x.columns and "stock_code" not in x.columns:
            ren["_stock_code"] = "stock_code"
        if "_filing_date" in x.columns and "filing_date" not in x.columns:
            ren["_filing_date"] = "filing_date"
        if "_fs_div_requested" in x.columns and "fs_div_requested" not in x.columns:
            ren["_fs_div_requested"] = "fs_div_requested"
        if "_period" in x.columns and "period" not in x.columns:
            ren["_period"] = "period"
        if "_requested_year" in x.columns and "requested_year" not in x.columns:
            ren["_requested_year"] = "requested_year"
        x = x.rename(columns=ren)
        if "stock_code" not in x.columns:
            continue
        x["stock_code"] = x["stock_code"].astype(str).str.replace(".0","",regex=False).str.zfill(6)
        if "filing_date" not in x.columns and "rcept_no" in x.columns:
            x["filing_date"] = x["rcept_no"].astype(str).str[:8]
        x["filing_date"] = pd.to_datetime(x["filing_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce")
        if "fs_div_requested" not in x.columns:
            x["fs_div_requested"] = x.get("fs_div", "")
        x["fs_div_requested"] = x["fs_div_requested"].fillna(x.get("fs_div","")).astype(str).str.upper()

        # Fast prefilter: keep only plausible rows for the four required value factors.
        sj = x["sj_div"].fillna("").astype(str).str.upper()
        aid = x["account_id"].fillna("").astype(str).str.lower()
        nm = x["account_nm"].fillna("").astype(str).str.replace(r"\s+","",regex=True)
        is_equity = (sj=="BS") & (
            aid.str.contains("equity",regex=False)
            | nm.isin(["자본총계","자본합계","자기자본","총자본"])
        )
        is_revenue = sj.isin(["IS","CIS"]) & (
            aid.str.contains("revenue",regex=False)
            | nm.isin(["매출액","매출","영업수익","수익","수익(매출액)","영업수익합계"])
        )
        is_profit = sj.isin(["IS","CIS"]) & (
            aid.str.contains("profitloss",regex=False)
            | nm.isin(["당기순이익","당기순이익(손실)","분기순이익","분기순이익(손실)",
                       "반기순이익","반기순이익(손실)","연결당기순이익","당기순손익",
                       "분기순손익","반기순손익"])
        )
        is_ocf = (sj=="CF") & (
            aid.str.contains("cashflowsfromusedinoperatingactivities",regex=False)
            | nm.isin(["영업활동현금흐름","영업활동으로인한현금흐름",
                       "영업활동으로부터의현금흐름","영업활동에의한현금흐름"])
        )
        x = x[is_equity | is_revenue | is_profit | is_ocf].copy()
        if len(x):
            chunks.append(x)

    if not chunks:
        raise ValueError(f"No candidate financial rows {year} {period}")
    out = pd.concat(chunks, ignore_index=True, sort=False)
    dedup = [z for z in ["stock_code","rcept_no","fs_div_requested","sj_div","account_id","account_nm"] if z in out.columns]
    if dedup:
        out = out.drop_duplicates(dedup, keep="last")
    return out

def metric_priority(row: pd.Series) -> tuple[Optional[str], int]:
    sj = str(row.get("sj_div", "") or "").upper()
    aid = normalize_name(row.get("account_id", ""))
    nm = normalize_name(row.get("account_nm", ""))

    if sj == "BS" and (
        "ifrs-full_equity" in aid or aid.endswith("equity") or nm in {"자본총계", "총자본"}
    ):
        pri = 0 if ("ifrs-full_equity" in aid or nm == "자본총계") else 2
        return "equity", pri

    if sj in {"IS", "CIS"} and (
        "revenue" in aid
        or nm in {"매출액", "영업수익", "수익", "수익(매출액)", "매출"}
    ):
        pri = 0 if ("revenue" in aid or nm == "매출액") else 2
        return "revenue", pri + (0 if sj == "IS" else 1)

    if sj in {"IS", "CIS"} and (
        "profitloss" in aid
        or nm in {"당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)",
                  "반기순이익", "반기순이익(손실)", "연결당기순이익"}
    ):
        # Prefer total ProfitLoss/current-period NI; do not mix EPS or comprehensive income.
        pri = 0 if "profitloss" in aid else 2
        return "net_income", pri + (0 if sj == "IS" else 1)

    if sj == "CF" and (
        "cashflowsfromusedinoperatingactivities" in aid
        or nm in {"영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로부터의현금흐름"}
    ):
        pri = 0 if "cashflowsfromusedinoperatingactivities" in aid else 2
        return "ocf", pri

    return None, 99


def report_snapshots(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if "rcept_no" not in raw.columns:
        raise KeyError("rcept_no missing")
    for (code, fs, rcept, fdate), g in raw.groupby(
        ["stock_code", "fs_div_requested", "rcept_no", "filing_date"], dropna=False
    ):
        cand = []
        for _, r in g.iterrows():
            metric, pri = metric_priority(r)
            if metric is None:
                continue
            cand.append({
                "metric": metric, "priority": pri,
                "current": to_num(r.get("thstrm_amount")),
                "cumulative": to_num(r.get("thstrm_add_amount")),
                "account_nm": r.get("account_nm", ""),
                "account_id": r.get("account_id", ""),
            })
        if not cand:
            continue
        c = pd.DataFrame(cand)
        rec = {"Code": str(code).zfill(6), "fs_div": str(fs), "rcept_no": str(rcept),
               "filing_date": pd.Timestamp(fdate) if pd.notna(fdate) else pd.NaT}
        for metric in ("equity","revenue","net_income","ocf"):
            z = c[c["metric"] == metric].copy()
            if z.empty:
                rec[f"{metric}_current"] = np.nan
                rec[f"{metric}_cum"] = np.nan
                continue
            z["has_value"] = z[["current","cumulative"]].notna().any(axis=1).astype(int)
            z = z.sort_values(["has_value","priority"], ascending=[False, True])
            best = z.iloc[0]
            rec[f"{metric}_current"] = best["current"]
            rec[f"{metric}_cum"] = best["cumulative"]
        rows.append(rec)
    return pd.DataFrame(rows)


def latest_snapshot(snap: pd.DataFrame, signal: pd.Timestamp) -> pd.DataFrame:
    x = snap[snap["filing_date"].notna() & (snap["filing_date"] <= signal)].copy()
    if x.empty:
        return x
    x = x.sort_values(["Code","fs_div","filing_date","rcept_no"])
    return x.groupby(["Code","fs_div"], as_index=False).tail(1)


def build_factor_table(signal: pd.Timestamp, period_cache: dict[tuple[int,str], pd.DataFrame]) -> pd.DataFrame:
    y = signal.year
    rows = []
    if signal.month == 10:
        q1 = latest_snapshot(period_cache[(y, "Q1")], signal)
        h1 = latest_snapshot(period_cache[(y, "H1")], signal)
        merged = h1.merge(q1, on=["Code","fs_div"], how="left", suffixes=("_h1","_q1"))
        for _, r in merged.iterrows():
            rev_q = r.get("revenue_current_h1", np.nan)
            ni_q = r.get("net_income_current_h1", np.nan)
            if pd.isna(rev_q):
                rev_q = r.get("revenue_cum_h1", np.nan) - r.get("revenue_cum_q1", np.nan)
            if pd.isna(ni_q):
                ni_q = r.get("net_income_cum_h1", np.nan) - r.get("net_income_cum_q1", np.nan)
            ocf_h1 = r.get("ocf_cum_h1", np.nan)
            if pd.isna(ocf_h1):
                ocf_h1 = r.get("ocf_current_h1", np.nan)
            ocf_q1 = r.get("ocf_cum_q1", np.nan)
            if pd.isna(ocf_q1):
                ocf_q1 = r.get("ocf_current_q1", np.nan)
            rows.append({
                "Code": r["Code"], "fs_div": r["fs_div"],
                "available_date": r.get("filing_date_h1"),
                "equity": r.get("equity_current_h1", np.nan),
                "revenue_q": rev_q, "net_income_q": ni_q,
                "ocf_q": ocf_h1 - ocf_q1 if pd.notna(ocf_h1) and pd.notna(ocf_q1) else np.nan,
            })
    elif signal.month == 4:
        fy_year = y - 1
        q3 = latest_snapshot(period_cache[(fy_year, "Q3")], signal)
        fy = latest_snapshot(period_cache[(fy_year, "FY")], signal)
        merged = fy.merge(q3, on=["Code","fs_div"], how="left", suffixes=("_fy","_q3"))
        for _, r in merged.iterrows():
            rev_fy = r.get("revenue_current_fy", np.nan)
            if pd.isna(rev_fy):
                rev_fy = r.get("revenue_cum_fy", np.nan)
            ni_fy = r.get("net_income_current_fy", np.nan)
            if pd.isna(ni_fy):
                ni_fy = r.get("net_income_cum_fy", np.nan)
            ocf_fy = r.get("ocf_cum_fy", np.nan)
            if pd.isna(ocf_fy):
                ocf_fy = r.get("ocf_current_fy", np.nan)
            rev_q3 = r.get("revenue_cum_q3", np.nan)
            ni_q3 = r.get("net_income_cum_q3", np.nan)
            ocf_q3 = r.get("ocf_cum_q3", np.nan)
            if pd.isna(ocf_q3):
                ocf_q3 = r.get("ocf_current_q3", np.nan)
            rows.append({
                "Code": r["Code"], "fs_div": r["fs_div"],
                "available_date": r.get("filing_date_fy"),
                "equity": r.get("equity_current_fy", np.nan),
                "revenue_q": rev_fy - rev_q3 if pd.notna(rev_fy) and pd.notna(rev_q3) else np.nan,
                "net_income_q": ni_fy - ni_q3 if pd.notna(ni_fy) and pd.notna(ni_q3) else np.nan,
                "ocf_q": ocf_fy - ocf_q3 if pd.notna(ocf_fy) and pd.notna(ocf_q3) else np.nan,
            })
    else:
        raise ValueError(signal)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["complete"] = out[["equity","revenue_q","net_income_q","ocf_q"]].notna().all(axis=1)
    out["fs_priority"] = out["fs_div"].map({"CFS":0,"OFS":1}).fillna(9)
    out = out.sort_values(["Code","complete","fs_priority"], ascending=[True,False,True])
    out = out.groupby("Code", as_index=False).head(1)
    return out.drop(columns=["complete","fs_priority"])


def last_trading_day(panel: pd.DataFrame, year: int, month: int) -> Optional[pd.Timestamp]:
    ds = panel[(panel["Date"].dt.year == year) & (panel["Date"].dt.month == month)]["Date"]
    return None if ds.empty else pd.Timestamp(ds.max())


def next_trading_day(all_dates: pd.DatetimeIndex, dt: pd.Timestamp) -> Optional[pd.Timestamp]:
    pos = all_dates.searchsorted(pd.Timestamp(dt), side="right")
    return None if pos >= len(all_dates) else pd.Timestamp(all_dates[pos])


def build_selection(panel: pd.DataFrame, signal: pd.Timestamp, factors: pd.DataFrame, top_n: int) -> tuple[pd.DataFrame, dict]:
    xs = panel[panel["Date"] == signal][["Code","Name","Market","Marcap","Amount","Volume","Close"]].copy()
    xs["Marcap"] = pd.to_numeric(xs["Marcap"], errors="coerce")
    m = xs.merge(factors, on="Code", how="left")
    audit = {
        "signal_date": signal, "cross_section": len(xs),
        "factor_rows": int(factors["Code"].nunique()) if len(factors) else 0,
    }
    audit["missing_equity"] = int(m["equity"].isna().sum())
    audit["missing_revenue_q"] = int(m["revenue_q"].isna().sum())
    audit["missing_net_income_q"] = int(m["net_income_q"].isna().sum())
    audit["missing_ocf_q"] = int(m["ocf_q"].isna().sum())
    valid = m[
        m["Marcap"].notna() & (m["Marcap"] > 0)
        & m[["equity","revenue_q","net_income_q","ocf_q"]].notna().all(axis=1)
    ].copy()
    audit["valid_four_factor"] = len(valid)
    if len(valid) < top_n:
        raise RuntimeError(f"{signal.date()}: only {len(valid)} valid four-factor stocks for top{top_n}")

    valid["EY_1_PER"] = 4.0 * valid["net_income_q"] / valid["Marcap"]
    valid["BY_1_PBR"] = valid["equity"] / valid["Marcap"]
    valid["CFY_1_PCR"] = 4.0 * valid["ocf_q"] / valid["Marcap"]
    valid["SY_1_PSR"] = 4.0 * valid["revenue_q"] / valid["Marcap"]
    factor_cols = ["EY_1_PER","BY_1_PBR","CFY_1_PCR","SY_1_PSR"]
    for c in factor_cols:
        valid[c + "_rank"] = valid[c].rank(method="average", ascending=False)
    valid["avg_rank"] = valid[[c+"_rank" for c in factor_cols]].mean(axis=1)
    valid = valid.sort_values(["avg_rank","Code"]).reset_index(drop=True)
    valid["overall_rank"] = np.arange(1, len(valid)+1)
    sel = valid.head(top_n).copy()
    sel["signal_date"] = signal
    sel["target_weight"] = 1.0 / top_n
    return sel, audit


def panel_lookup(panel: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(dt): g.set_index("Code", drop=False) for dt, g in panel.groupby("Date")}


def simulate(panel: pd.DataFrame, selections: dict[pd.Timestamp,pd.DataFrame],
             top_n: int, cost: CostScenario, delist_mode: str = "last_close",
             performance_end: Optional[pd.Timestamp] = None) -> tuple[pd.DataFrame,pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(panel["Date"].unique()))
    lookup = panel_lookup(panel)
    last_obs = panel.groupby("Code")["Date"].max().to_dict()
    events = {}
    for signal, sel in selections.items():
        ex = next_trading_day(dates, signal)
        if ex is not None:
            events[ex] = (signal, sel)

    if not events:
        raise RuntimeError("No execution events")
    first_exec = min(events)
    # The holdings selected at the last validated rebalance remain valid until the next
    # scheduled rebalance. We may therefore measure them through the close of the first
    # incomplete next signal, but must not rebalance using incomplete factors there.
    end_date = pd.Timestamp(performance_end) if performance_end is not None else max(selections)
    run_dates = dates[(dates >= first_exec) & (dates <= end_date)]

    weights: Dict[str,float] = {"__CASH__":1.0}
    gross_nav = 1.0
    net_nav = 1.0
    nav_rows = []
    turn_rows = []

    for dt in run_dates:
        day = lookup.get(pd.Timestamp(dt))
        # 1) Existing holdings earn today's close-to-close adjusted return.
        port_ret = 0.0
        new_values = {}
        for code, w in weights.items():
            if code == "__CASH__":
                r = 0.0
            else:
                if day is not None and code in day.index:
                    r = day.loc[code, "Change"]
                    r = 0.0 if pd.isna(r) else float(r)
                else:
                    if delist_mode == "minus100" and pd.Timestamp(last_obs.get(code, dt)) < pd.Timestamp(dt):
                        r = -1.0
                    else:
                        r = 0.0
            v = w * max(0.0, 1.0 + r)
            new_values[code] = v
            port_ret += w * r
        tot = sum(new_values.values())
        weights = ({k:v/tot for k,v in new_values.items()} if tot > 0 else {"__CASH__":1.0})
        gross_nav *= max(0.0, 1.0 + port_ret)
        net_nav *= max(0.0, 1.0 + port_ret)

        # 2) Rebalance at today's close to the prior signal's target; new holdings earn from next session.
        cost_fraction = 0.0
        if dt in events:
            signal, sel = events[dt]
            target: Dict[str,float] = {"__CASH__":0.0}
            untradable = []
            markets = {}
            for _, r in sel.iterrows():
                code = str(r["Code"]).zfill(6)
                tradable = (
                    day is not None and code in day.index
                    and pd.notna(day.loc[code,"Close"]) and float(day.loc[code,"Close"]) > 0
                    and pd.notna(day.loc[code,"Volume"]) and float(day.loc[code,"Volume"]) > 0
                )
                if tradable:
                    target[code] = target.get(code,0.0) + 1.0/top_n
                    markets[code] = str(day.loc[code,"Market"])
                else:
                    target["__CASH__"] += 1.0/top_n
                    untradable.append(code)

            keys = set(weights) | set(target)
            buy = 0.0
            sell = 0.0
            for code in keys:
                if code == "__CASH__":
                    continue
                old = weights.get(code,0.0); tar = target.get(code,0.0)
                if tar > old: buy += tar-old
                if old > tar: sell += old-tar
            common = cost.common_bps / 10000.0
            tax = sell_tax_bps(dt) / 10000.0
            cost_fraction = (buy + sell) * common + sell * tax
            net_nav *= (1.0 - cost_fraction)
            weights = target

            turn_rows.append({
                "signal_date": signal, "execution_date": dt, "top_n": top_n,
                "buy_turnover": buy, "sell_turnover": sell,
                "two_way_turnover": buy+sell, "sell_tax_bps": sell_tax_bps(dt),
                "common_cost_bps": cost.common_bps,
                "cost_fraction": cost_fraction,
                "untradable_count": len(untradable),
                "untradable_codes": "|".join(untradable),
                "delist_mode": delist_mode, "cost_scenario": cost.name,
            })

        nav_rows.append({"Date":dt, "Gross":gross_nav, "Net":net_nav,
                         "daily_gross_return":port_ret, "cost_fraction":cost_fraction})
    return pd.DataFrame(nav_rows).set_index("Date"), pd.DataFrame(turn_rows)


def drawdown(nav: pd.Series) -> pd.Series:
    running = np.maximum.accumulate(np.r_[1.0, nav.to_numpy(float)])[1:]
    return pd.Series(nav.to_numpy(float)/running - 1.0, index=nav.index)


def max_recovery(nav: pd.Series, baseline_date: pd.Timestamp) -> tuple[int,float]:
    peak_value = 1.0
    peak_date = pd.Timestamp(baseline_date)
    underwater_start = None
    longest = 0
    for dt, value in nav.items():
        value = float(value)
        if value >= peak_value:
            if underwater_start is not None:
                longest = max(longest, (pd.Timestamp(dt)-underwater_start).days)
                underwater_start = None
            peak_value = value
            peak_date = pd.Timestamp(dt)
        else:
            if underwater_start is None:
                underwater_start = peak_date
    if underwater_start is not None:
        longest = max(longest, (pd.Timestamp(nav.index[-1])-underwater_start).days)
    return int(longest), round(longest/30.4375,1)


def metrics(nav: pd.Series, baseline_date: pd.Timestamp, name: str) -> dict:
    """Delegate every final performance/risk metric to CURRENT v2-16."""
    s = nav.astype(float).dropna().rename(name)
    daily = s.to_frame()
    monthly = daily.groupby(daily.index.to_period("M")).tail(1).copy()

    # Preserve the true strategy performance baseline (signal-day close before
    # next-session execution) so CURRENT annualises a partial inception month correctly.
    monthly.attrs["performance_baseline_date"] = pd.Timestamp(baseline_date)
    daily.attrs["coverage_verified"] = True

    m = CURRENT.calculate_metrics(monthly, METRIC_CONFIG, daily)
    row = m.loc[name].to_dict()
    row["전략"] = name
    row["start"] = s.index[0].date().isoformat()
    row["end"] = s.index[-1].date().isoformat()
    row["template_version"] = CURRENT.TEMPLATE_VERSION
    return row

def load_kospi_nav(start: pd.Timestamp, end: pd.Timestamp, baseline_date: pd.Timestamp) -> pd.Series:
    x = pd.read_csv(ROOT/"data/indices/KOSPI.csv", parse_dates=["Date"])
    x = x.sort_values("Date")
    x["Close"] = pd.to_numeric(x["Close"], errors="coerce")
    base = x[x["Date"] <= baseline_date].iloc[-1]["Close"]
    y = x[(x["Date"] >= start) & (x["Date"] <= end)].copy()
    s = y.set_index("Date")["Close"].astype(float) / float(base)
    s.name = "KOSPI"
    return s


def adv_audit(panel: pd.DataFrame, selections: dict[pd.Timestamp,pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for signal, sel in selections.items():
        hist = panel[(panel["Date"] <= signal) & (panel["Date"] >= signal - pd.Timedelta(days=40))]
        adv = hist.sort_values("Date").groupby("Code").tail(20).groupby("Code")["Amount"].mean()
        for _, r in sel.iterrows():
            code = str(r["Code"]).zfill(6)
            a = float(adv.get(code, np.nan))
            w = float(r["target_weight"])
            rows.append({
                "signal_date":signal,"Code":code,"Name":r["Name"],"rank":int(r["overall_rank"]),
                "weight":w,"ADV20_KRW":a,
                "order_at_10m_KRW":INITIAL_CAPITAL*w,
                "order_pct_ADV_at_10m":(INITIAL_CAPITAL*w/a if np.isfinite(a) and a>0 else np.nan),
                "capacity_at_5pct_ADV_KRW":(0.05*a/w if np.isfinite(a) and a>0 else np.nan),
                "capacity_at_1pct_ADV_KRW":(0.01*a/w if np.isfinite(a) and a>0 else np.nan),
            })
    return pd.DataFrame(rows)


def make_dashboard(nav: pd.DataFrame, title: str, path: Path):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=False,
                        subplot_titles=("누적자산", "Log2 누적자산", "Drawdown"),
                        vertical_spacing=0.09)
    for c in nav.columns:
        s = nav[c].dropna()
        fig.add_trace(go.Scatter(x=s.index,y=s*INITIAL_CAPITAL,name=c,legendgroup=c),row=1,col=1)
        fig.add_trace(go.Scatter(x=s.index,y=np.log2(s),name=c,legendgroup=c,showlegend=False),row=2,col=1)
        fig.add_trace(go.Scatter(x=s.index,y=drawdown(s)*100,name=c,legendgroup=c,showlegend=False),row=3,col=1)
    fig.update_yaxes(title_text="자산(원)",row=1,col=1)
    fig.update_yaxes(title_text="log2(NAV)",row=2,col=1)
    fig.update_yaxes(title_text="낙폭(%)",row=3,col=1)
    fig.update_layout(title=title,height=1100,hovermode="x unified")
    fig.write_html(path, include_plotlyjs="cdn")


def main():
    mapping = load_map()
    state = load_state()

    # Load a small surrounding window; exact usable interval is decided by PIT completeness.
    panel = load_krx("2016-01-01","2020-12-31")
    all_dates = pd.DatetimeIndex(sorted(panel["Date"].unique()))

    candidate_signals = []
    completion_rows = []
    for y in range(2016, 2021):
        for m in (4,10):
            s = last_trading_day(panel,y,m)
            if s is None:
                continue
            ok, rows = signal_completeness(mapping,state,s)
            for row in rows:
                row["signal_complete"] = ok
                completion_rows.append(row)
            candidate_signals.append((s,ok))

    complete_signals = [s for s,ok in candidate_signals if ok]
    complete_signals = sorted(complete_signals)
    if not complete_signals:
        raise RuntimeError("No fully PIT-complete signals")
    # Require a contiguous run from first complete signal; stop before first incomplete signal thereafter.
    start_signal = complete_signals[0]
    validated = []
    started = False
    for s,ok in sorted(candidate_signals):
        if s == start_signal:
            started = True
        if not started:
            continue
        if not ok:
            break
        validated.append(s)

    if len(validated) < 2:
        raise RuntimeError(f"Too few contiguous validated signals: {validated}")

    required = sorted(set(p for s in validated for p in required_periods(s)))
    period_cache = {}
    financial_file_rows = []
    for y,p in required:
        raw = load_financial_raw(y,p)
        financial_file_rows.append({"year":y,"period":p,"raw_rows":len(raw),"codes":raw["stock_code"].nunique()})
        period_cache[(y,p)] = report_snapshots(raw)

    selections_by_n = {n:{} for n in TOP_NS}
    audit_rows = []
    all_selection_rows = []
    for s in validated:
        factors = build_factor_table(s, period_cache)
        for n in TOP_NS:
            sel,audit = build_selection(panel,s,factors,n)
            selections_by_n[n][s] = sel
            a = dict(audit); a["top_n"] = n
            audit_rows.append(a)
            tmp = sel.copy(); tmp["top_n"] = n
            all_selection_rows.append(tmp)

    # Stop performance on the next (incomplete) scheduled signal date, not after it.
    next_incomplete = None
    last_valid = validated[-1]
    for s,ok in sorted(candidate_signals):
        if s > last_valid and not ok:
            next_incomplete = s
            break
    if next_incomplete is None:
        next_incomplete = last_valid

    # Run primary cost scenarios for top20.
    nav_series = {}
    turnover_all = []
    primary_nav = None
    baseline_date = validated[0]
    for cname,cost in COSTS.items():
        nav,turn = simulate(panel,selections_by_n[BASE_TOP_N],BASE_TOP_N,cost,"last_close",next_incomplete)
        # Trim to the day before/at the first incomplete signal generated by simulate's internal stop.
        if cname == "gross":
            nav_series["Top20_Gross"] = nav["Gross"]
        else:
            nav_series[f"Top20_{cname.capitalize()}"] = nav["Net"]
        turn["variant"] = f"Top20_{cname}"
        turnover_all.append(turn)
        if cname == "base":
            primary_nav = nav

    # Top-N robustness with base cost.
    robustness_nav = {}
    for n in TOP_NS:
        nav,turn = simulate(panel,selections_by_n[n],n,COSTS["base"],"last_close",next_incomplete)
        robustness_nav[f"Top{n}_Base"] = nav["Net"]
        turn["variant"] = f"Top{n}_base"
        turnover_all.append(turn)

    # Delisting worst-case stress for top20.
    stress_nav,stress_turn = simulate(panel,selections_by_n[20],20,COSTS["base"],"minus100",next_incomplete)
    robustness_nav["Top20_Base_DelistMinus100"] = stress_nav["Net"]
    stress_turn["variant"] = "Top20_base_delist_minus100"
    turnover_all.append(stress_turn)

    combined = pd.concat(nav_series,axis=1).sort_index()
    kospi = load_kospi_nav(combined.index[0],combined.index[-1],baseline_date)
    combined["KOSPI"] = kospi.reindex(combined.index).ffill()
    combined.to_csv(OUT/"daily_nav.csv",encoding="utf-8-sig")

    summary = pd.DataFrame([metrics(combined[c].dropna(),baseline_date,c) for c in combined.columns]).set_index("전략")
    summary.to_csv(OUT/"summary_verified_period.csv",encoding="utf-8-sig")

    robust_df = pd.concat(robustness_nav,axis=1).sort_index()
    robust_metrics = pd.DataFrame([metrics(robust_df[c].dropna(),baseline_date,c) for c in robust_df.columns]).set_index("전략")
    robust_metrics.to_csv(OUT/"robustness_metrics.csv",encoding="utf-8-sig")
    robust_df.to_csv(OUT/"robustness_daily_nav.csv",encoding="utf-8-sig")

    sels = pd.concat(all_selection_rows,ignore_index=True)
    sels.to_csv(OUT/"selections.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(audit_rows).to_csv(OUT/"rebalance_audit.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(completion_rows).to_csv(OUT/"pit_completion_audit.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(financial_file_rows).to_csv(OUT/"financial_rows_audit.csv",index=False,encoding="utf-8-sig")
    pd.concat(turnover_all,ignore_index=True).to_csv(OUT/"turnover_cost_audit.csv",index=False,encoding="utf-8-sig")

    adv = adv_audit(panel,selections_by_n[20])
    adv.to_csv(OUT/"liquidity_capacity.csv",index=False,encoding="utf-8-sig")

    # Standard template periods cannot be claimed unless financial PIT data cover them.
    std = pd.DataFrame([
        {"period":"book_period","status":"UNAVAILABLE","reason":"Book validation dates not recoverable from supplied photo/source extract and PIT financial backfill is incomplete before 2016."},
        {"period":"2000_to_latest","status":"UNAVAILABLE","reason":"KRX prices exist, but PIT DART financial-factor history is not fully parsed/backfilled for 2000~latest."},
        {"period":"2021_to_latest","status":"UNAVAILABLE","reason":"PIT DART full_history is still sequentially backfilling; a contiguous complete 2021~latest financial panel is not yet present."},
        {"period":"longest_to_latest","status":"UNAVAILABLE","reason":"Price history begins 1995, but required PIT financial history does not yet cover a complete longest-to-latest window."},
        {"period":"verified_contiguous_PIT","status":"AVAILABLE",
         "reason":f"All required Q1/H1 or Q3/FY tasks complete for both CFS and OFS at each signal from {validated[0].date()} through {validated[-1].date()}."}
    ])
    std.to_csv(OUT/"standard_period_status.csv",index=False,encoding="utf-8-sig")

    # Calendar-year returns for the core net strategy.
    core = combined["Top20_Base"]
    dr = core.pct_change().fillna(0.0)
    ann = (1.0+dr).groupby(dr.index.year).prod()-1.0
    ann.rename("Top20_Base_Return").to_csv(OUT/"annual_returns.csv",encoding="utf-8-sig")

    make_dashboard(combined[["Top20_Gross","Top20_Base","KOSPI"]],
                   "오리지널 강환국 슈퍼 가치 전략 — PIT 검증 가능 연속구간", OUT/"interactive_dashboard.html")

    meta = {
        "strategy":"Original Kang Hwan-kuk Super Value (photo rules)",
        "template_version":CURRENT.TEMPLATE_VERSION,
        "signal":"Rank descending 1/PER, 1/PBR, 1/PCR, 1/PSR; buy lowest average rank",
        "factor_formulas":{
            "1/PER":"latest standalone-quarter net income / market cap",
            "1/PBR":"latest quarter-end total equity / market cap",
            "1/PCR":"latest standalone-quarter operating cash flow / market cap",
            "1/PSR":"latest standalone-quarter revenue / market cap",
        },
        "quarter_reconstruction":{
            "October":"H1 current-period revenue/net income; OCF = H1 cumulative - Q1 cumulative",
            "April":"Q4 = FY annual/cumulative - Q3 cumulative; equity = FY",
        },
        "universe":"PIT KOSPI+KOSDAQ individual securities from historical marcap panel; preferred shares retained; ETF/ETN/KONEX excluded upstream.",
        "execution":"Signal at Apr/Oct last trading-day close; execute at next trading-day close; new holdings earn from following session.",
        "weighting":"equal weight",
        "validated_signals":[x.date().isoformat() for x in validated],
        "validated_performance_start":combined.index[0].date().isoformat(),
        "validated_performance_end":combined.index[-1].date().isoformat(),
        "cost_scenarios":{k:asdict(v) for k,v in COSTS.items()},
        "sell_tax":"30bp through 2019-06-02; 25bp from 2019-06-03 in the validated historical window",
        "delisting_baseline":"last observed market value converted to cash if security disappears; stress case applies -100% after permanent disappearance",
        "missing_or_suspended_target":"target weight stays in cash; no substitution using future information",
        "initial_capital_krw":INITIAL_CAPITAL,
        "risk_free_rate":0.0,
        "metrics":"All final performance/risk metrics delegated to CURRENT v2-16 calculate_metrics(); strategy code produces daily NAV only.",
        "data_as_of":AS_OF.date().isoformat(),
    }
    (OUT/"run_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2,default=str),encoding="utf-8")

    print("VALIDATED SIGNALS:", [x.date().isoformat() for x in validated])
    print("\nSTANDARD PERIOD STATUS")
    print(std.to_string(index=False))
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nROBUSTNESS")
    print(robust_metrics.to_string(index=False))
    print("\nLIQUIDITY")
    if len(adv):
        print(adv.groupby("signal_date")["ADV20_KRW"].agg(["min","median"]).to_string())


if __name__ == "__main__":
    main()
