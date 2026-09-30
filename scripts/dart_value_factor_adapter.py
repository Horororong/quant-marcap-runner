from __future__ import annotations

"""Reusable DART PIT value-factor adapter.

This module extracts the four-factor value logic that was previously embedded in
backtest_super_value_v216.py. It reconstructs standalone-quarter values using
only filings available on or before each signal date, prefers CFS over OFS when
both provide a complete row, and exposes standardized factor fields for the DSL.
"""

from pathlib import Path
from typing import Optional
import re

import numpy as np
import pandas as pd

DART_HISTORY_DIR = "data/financials/full_history"
DART_CODE_MAP_FILE = "data/financials/dart_historical_code_map.csv"
DART_BACKFILL_STATE_FILE = "data/status/dart_full_backfill_state.csv"

VALUE_FACTOR_FIELDS = (
    "earnings_yield",
    "book_to_price",
    "cashflow_yield",
    "sales_yield",
)


def _to_num(x) -> float:
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


def _normalize_name(x: str) -> str:
    return re.sub(r"\s+", "", str(x or "")).lower()



def load_historical_code_map(repo_root: str | Path) -> pd.DataFrame:
    path = Path(repo_root) / DART_CODE_MAP_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"DART PIT completeness gate requires historical code map: {path}"
        )
    x = pd.read_csv(path, dtype={"stock_code": str, "corp_code": str})
    required = {"stock_code", "corp_code", "first_date", "last_date"}
    missing = required - set(x.columns)
    if missing:
        raise KeyError(f"{path}: missing columns {sorted(missing)}")
    x["stock_code"] = x["stock_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    x["corp_code"] = x["corp_code"].fillna("").astype(str).str.strip()
    x["first_date"] = pd.to_datetime(x["first_date"], errors="coerce")
    x["last_date"] = pd.to_datetime(x["last_date"], errors="coerce")
    return x


def load_backfill_state(repo_root: str | Path) -> pd.DataFrame:
    path = Path(repo_root) / DART_BACKFILL_STATE_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"DART PIT completeness gate requires backfill state: {path}"
        )
    x = pd.read_csv(path, dtype={"stock_code": str, "corp_code": str})
    required = {"stock_code", "year", "period", "fs_div", "status"}
    missing = required - set(x.columns)
    if missing:
        raise KeyError(f"{path}: missing columns {sorted(missing)}")
    x["stock_code"] = x["stock_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    x["year"] = pd.to_numeric(x["year"], errors="coerce").astype("Int64")
    x["period"] = x["period"].astype(str)
    x["fs_div"] = x["fs_div"].astype(str).str.upper()
    x["status"] = x["status"].astype(str).str.upper()
    return x


def expected_codes_for_period(mapping: pd.DataFrame, year: int) -> set[str]:
    """Conservative expected DART population for a report year."""
    x = mapping[
        mapping["corp_code"].str.fullmatch(r"\d{8}", na=False)
        & mapping["first_date"].notna()
        & mapping["last_date"].notna()
        & (mapping["first_date"].dt.year <= int(year))
        & (mapping["last_date"].dt.year >= int(year))
    ]
    return set(x["stock_code"].astype(str))


def period_completeness(
    repo_root: str | Path,
    mapping: pd.DataFrame,
    state: pd.DataFrame,
    year: int,
    period: str,
) -> dict:
    """CFS-first completion gate; OFS is required only after CFS NO_DATA."""
    expected = expected_codes_for_period(mapping, year)
    sub = state[(state["year"] == int(year)) & (state["period"] == str(period))].copy()

    cfs = (
        sub[sub["fs_div"] == "CFS"]
        .drop_duplicates("stock_code", keep="last")
        .set_index("stock_code")["status"]
        .to_dict()
    )
    ofs = (
        sub[sub["fs_div"] == "OFS"]
        .drop_duplicates("stock_code", keep="last")
        .set_index("stock_code")["status"]
        .to_dict()
    )

    complete = cfs_ok = cfs_no_data = ofs_fallback_terminal = ofs_fallback_ok = 0
    terminal = {"OK", "NO_DATA"}
    for code in expected:
        cfs_status = cfs.get(code, "")
        if cfs_status == "OK":
            complete += 1
            cfs_ok += 1
        elif cfs_status == "NO_DATA":
            cfs_no_data += 1
            ofs_status = ofs.get(code, "")
            if ofs_status in terminal:
                complete += 1
                ofs_fallback_terminal += 1
                if ofs_status == "OK":
                    ofs_fallback_ok += 1

    base = Path(repo_root) / DART_HISTORY_DIR
    cfs_shards = list(base.glob(f"dart_full_{year}_{period}_CFS_*.csv.gz"))
    ofs_shards = list(base.glob(f"dart_full_{year}_{period}_OFS_*.csv.gz"))
    raw_ok = (cfs_ok == 0 or bool(cfs_shards)) and (ofs_fallback_ok == 0 or bool(ofs_shards))
    n_expected = len(expected)
    ratio = complete / n_expected if n_expected else 0.0
    return {
        "year": int(year),
        "period": str(period),
        "completed_codes": int(complete),
        "expected_codes": int(n_expected),
        "ratio": float(ratio),
        "cfs_ok_codes": int(cfs_ok),
        "cfs_no_data_codes": int(cfs_no_data),
        "ofs_fallback_terminal_codes": int(ofs_fallback_terminal),
        "cfs_raw_shards": len(cfs_shards),
        "ofs_raw_shards": len(ofs_shards),
        "raw_ok": bool(raw_ok),
    }


def signal_completeness_report(
    repo_root: str | Path,
    signal: pd.Timestamp,
    mapping: pd.DataFrame | None = None,
    state: pd.DataFrame | None = None,
) -> list[dict]:
    mapping = load_historical_code_map(repo_root) if mapping is None else mapping
    state = load_backfill_state(repo_root) if state is None else state
    rows = []
    for year, period in required_periods(pd.Timestamp(signal)):
        row = period_completeness(repo_root, mapping, state, year, period)
        row["signal_date"] = pd.Timestamp(signal).normalize()
        rows.append(row)
    return rows


def assert_signal_complete(
    repo_root: str | Path,
    signal: pd.Timestamp,
    mapping: pd.DataFrame | None = None,
    state: pd.DataFrame | None = None,
) -> list[dict]:
    rows = signal_completeness_report(repo_root, signal, mapping=mapping, state=state)
    bad = [r for r in rows if r["ratio"] < 1.0 or not r["raw_ok"]]
    if bad:
        detail = "; ".join(
            f'{r["year"]}-{r["period"]}: {r["completed_codes"]}/{r["expected_codes"]} '
            f'({r["ratio"]:.2%}), raw_ok={r["raw_ok"]}'
            for r in bad
        )
        raise RuntimeError(
            f"{pd.Timestamp(signal).date()}: DART PIT source is incomplete; "
            f"refusing partial-universe backtest. {detail}"
        )
    return rows


def required_periods(signal: pd.Timestamp) -> list[tuple[int, str]]:
    signal = pd.Timestamp(signal)
    y = signal.year
    if signal.month == 10:
        return [(y, "Q1"), (y, "H1")]
    if signal.month == 4:
        return [(y - 1, "Q3"), (y - 1, "FY")]
    raise ValueError(f"value-factor adapter currently supports April/October signals only: {signal.date()}")


def load_financial_raw(repo_root: Path, year: int, period: str) -> pd.DataFrame:
    root = Path(repo_root)
    base = root / DART_HISTORY_DIR
    files: list[Path] = []
    for fs in ("CFS", "OFS"):
        files.extend(sorted(base.glob(f"dart_full_{year}_{period}_{fs}_*.csv.gz")))
    if not files:
        raise FileNotFoundError(f"No DART full_history shards for {year} {period}")

    wanted = {
        "_stock_code", "stock_code", "_filing_date", "filing_date",
        "_fs_div_requested", "fs_div_requested", "fs_div",
        "_period", "period", "_requested_year", "requested_year",
        "rcept_no", "sj_div", "account_id", "account_nm",
        "thstrm_amount", "thstrm_add_amount",
    }
    chunks: list[pd.DataFrame] = []
    for path in files:
        x = pd.read_csv(path, low_memory=False, dtype=str, usecols=lambda z: z in wanted)
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
        x["stock_code"] = x["stock_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
        if "filing_date" not in x.columns and "rcept_no" in x.columns:
            x["filing_date"] = x["rcept_no"].astype(str).str[:8]
        x["filing_date"] = pd.to_datetime(
            x["filing_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce"
        )
        if "fs_div_requested" not in x.columns:
            x["fs_div_requested"] = x.get("fs_div", "")
        x["fs_div_requested"] = x["fs_div_requested"].fillna(x.get("fs_div", "")).astype(str).str.upper()

        sj = x["sj_div"].fillna("").astype(str).str.upper()
        aid = x["account_id"].fillna("").astype(str).str.lower()
        nm = x["account_nm"].fillna("").astype(str).str.replace(r"\s+", "", regex=True)
        is_equity = (sj == "BS") & (
            aid.str.contains("equity", regex=False)
            | nm.isin(["자본총계", "자본합계", "자기자본", "총자본"])
        )
        is_revenue = sj.isin(["IS", "CIS"]) & (
            aid.str.contains("revenue", regex=False)
            | nm.isin(["매출액", "매출", "영업수익", "수익", "수익(매출액)", "영업수익합계"])
        )
        is_profit = sj.isin(["IS", "CIS"]) & (
            aid.str.contains("profitloss", regex=False)
            | nm.isin([
                "당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)",
                "반기순이익", "반기순이익(손실)", "연결당기순이익", "당기순손익",
                "분기순손익", "반기순손익",
            ])
        )
        is_ocf = (sj == "CF") & (
            aid.str.contains("cashflowsfromusedinoperatingactivities", regex=False)
            | nm.isin([
                "영업활동현금흐름", "영업활동으로인한현금흐름",
                "영업활동으로부터의현금흐름", "영업활동에의한현금흐름",
            ])
        )
        x = x[is_equity | is_revenue | is_profit | is_ocf].copy()
        if len(x):
            chunks.append(x)

    if not chunks:
        raise ValueError(f"No candidate DART financial rows for {year} {period}")
    out = pd.concat(chunks, ignore_index=True, sort=False)
    dedup = [z for z in ["stock_code", "rcept_no", "fs_div_requested", "sj_div", "account_id", "account_nm"] if z in out.columns]
    if dedup:
        out = out.drop_duplicates(dedup, keep="last")
    return out


def _metric_priority(row: pd.Series) -> tuple[Optional[str], int]:
    """Map only explicit financial-statement concepts to standardized metrics.

    Exact IFRS concept IDs are preferred. Korean account names are a fallback.
    Broad substring matching is intentionally rejected because e.g.
    ProfitLossBeforeTax or attributable-profit concepts must not be treated as
    total ProfitLoss.
    """
    sj = str(row.get("sj_div", "") or "").upper()
    aid = _normalize_name(row.get("account_id", ""))
    nm = _normalize_name(row.get("account_nm", ""))

    equity_ids = {"ifrs-full_equity", "ifrs_equity"}
    revenue_ids = {"ifrs-full_revenue", "ifrs_revenue"}
    profit_ids = {"ifrs-full_profitloss", "ifrs_profitloss"}
    ocf_ids = {
        "ifrs-full_cashflowsfromusedinoperatingactivities",
        "ifrs_cashflowsfromusedinoperatingactivities",
    }

    if sj == "BS":
        if aid in equity_ids:
            return "equity", 0
        if nm in {"자본총계", "총자본"}:
            return "equity", 2

    if sj in {"IS", "CIS"}:
        statement_penalty = 0 if sj == "IS" else 1
        if aid in revenue_ids:
            return "revenue", statement_penalty
        if nm in {"매출액", "영업수익", "수익", "수익(매출액)", "매출"}:
            return "revenue", 2 + statement_penalty
        if aid in profit_ids:
            return "net_income", statement_penalty
        if nm in {
            "당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)",
            "반기순이익", "반기순이익(손실)", "연결당기순이익",
        }:
            return "net_income", 2 + statement_penalty

    if sj == "CF":
        if aid in ocf_ids:
            return "ocf", 0
        if nm in {"영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로부터의현금흐름"}:
            return "ocf", 2

    return None, 99

def report_snapshots(raw: pd.DataFrame) -> pd.DataFrame:
    if "rcept_no" not in raw.columns:
        raise KeyError("rcept_no missing")
    rows = []
    for (code, fs, rcept, fdate), group in raw.groupby(
        ["stock_code", "fs_div_requested", "rcept_no", "filing_date"], dropna=False
    ):
        cand = []
        for _, row in group.iterrows():
            metric, priority = _metric_priority(row)
            if metric is None:
                continue
            cand.append({
                "metric": metric,
                "priority": priority,
                "current": _to_num(row.get("thstrm_amount")),
                "cumulative": _to_num(row.get("thstrm_add_amount")),
                "account_nm": row.get("account_nm", ""),
                "account_id": row.get("account_id", ""),
            })
        if not cand:
            continue
        c = pd.DataFrame(cand)
        rec = {
            "Code": str(code).zfill(6),
            "fs_div": str(fs),
            "rcept_no": str(rcept),
            "filing_date": pd.Timestamp(fdate) if pd.notna(fdate) else pd.NaT,
        }
        for metric in ("equity", "revenue", "net_income", "ocf"):
            z = c[c["metric"] == metric].copy()
            if z.empty:
                rec[f"{metric}_current"] = np.nan
                rec[f"{metric}_cum"] = np.nan
                continue
            z["has_value"] = z[["current", "cumulative"]].notna().any(axis=1).astype(int)
            z["account_key"] = (
                z["account_id"].fillna("").astype(str).map(_normalize_name)
                + "|"
                + z["account_nm"].fillna("").astype(str).map(_normalize_name)
            )
            z = z.sort_values(
                ["has_value", "priority", "account_key"],
                ascending=[False, True, True],
                kind="mergesort",
            )
            best = z.iloc[0]
            rec[f"{metric}_current"] = best["current"]
            rec[f"{metric}_cum"] = best["cumulative"]
        rows.append(rec)
    return pd.DataFrame(rows)


def latest_snapshot(snap: pd.DataFrame, signal: pd.Timestamp) -> pd.DataFrame:
    x = snap[snap["filing_date"].notna() & (snap["filing_date"] <= pd.Timestamp(signal))].copy()
    if x.empty:
        return x
    x = x.sort_values(["Code", "fs_div", "filing_date", "rcept_no"])
    return x.groupby(["Code", "fs_div"], as_index=False).tail(1)


def build_raw_value_inputs(signal: pd.Timestamp, period_cache: dict[tuple[int, str], pd.DataFrame]) -> pd.DataFrame:
    signal = pd.Timestamp(signal)
    y = signal.year
    rows = []
    if signal.month == 10:
        q1 = latest_snapshot(period_cache[(y, "Q1")], signal)
        h1 = latest_snapshot(period_cache[(y, "H1")], signal)
        merged = h1.merge(q1, on=["Code", "fs_div"], how="left", suffixes=("_h1", "_q1"))
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
                "revenue_q": rev_q,
                "net_income_q": ni_q,
                "ocf_q": ocf_h1 - ocf_q1 if pd.notna(ocf_h1) and pd.notna(ocf_q1) else np.nan,
            })
    elif signal.month == 4:
        fy_year = y - 1
        q3 = latest_snapshot(period_cache[(fy_year, "Q3")], signal)
        fy = latest_snapshot(period_cache[(fy_year, "FY")], signal)
        merged = fy.merge(q3, on=["Code", "fs_div"], how="left", suffixes=("_fy", "_q3"))
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
    out["complete"] = out[["equity", "revenue_q", "net_income_q", "ocf_q"]].notna().all(axis=1)
    out["fs_priority"] = out["fs_div"].map({"CFS": 0, "OFS": 1}).fillna(9)
    out = out.sort_values(["Code", "complete", "fs_priority"], ascending=[True, False, True])
    out = out.groupby("Code", as_index=False).head(1)
    return out.drop(columns=["complete", "fs_priority"])


class DartValueFactorAdapter:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)
        self._period_cache: dict[tuple[int, str], pd.DataFrame] = {}
        self._mapping: pd.DataFrame | None = None
        self._state: pd.DataFrame | None = None
        self._coverage_cache: dict[pd.Timestamp, list[dict]] = {}

    def coverage_report(self, signal: pd.Timestamp) -> list[dict]:
        signal = pd.Timestamp(signal).normalize()
        if self._mapping is None:
            self._mapping = load_historical_code_map(self.repo_root)
        if self._state is None:
            self._state = load_backfill_state(self.repo_root)
        if signal not in self._coverage_cache:
            self._coverage_cache[signal] = assert_signal_complete(
                self.repo_root, signal, mapping=self._mapping, state=self._state
            )
        return self._coverage_cache[signal]

    def _snapshot(self, year: int, period: str) -> pd.DataFrame:
        key = (int(year), str(period))
        if key not in self._period_cache:
            raw = load_financial_raw(self.repo_root, *key)
            self._period_cache[key] = report_snapshots(raw)
        return self._period_cache[key]

    def factor_frame(self, signal: pd.Timestamp, cross_section: pd.DataFrame) -> pd.DataFrame:
        signal = pd.Timestamp(signal).normalize()
        self.coverage_report(signal)
        periods = required_periods(signal)
        cache = {k: self._snapshot(*k) for k in periods}
        raw = build_raw_value_inputs(signal, cache)
        if raw.empty:
            return raw

        marcap = cross_section[["Code", "Marcap"]].copy()
        marcap["Code"] = marcap["Code"].astype(str).str.zfill(6)
        marcap["Marcap"] = pd.to_numeric(marcap["Marcap"], errors="coerce")
        out = raw.merge(marcap, on="Code", how="inner")
        valid_mc = out["Marcap"].notna() & (out["Marcap"] > 0)
        out["earnings_yield"] = np.where(valid_mc, out["net_income_q"] / out["Marcap"], np.nan)
        out["book_to_price"] = np.where(valid_mc, out["equity"] / out["Marcap"], np.nan)
        out["cashflow_yield"] = np.where(valid_mc, out["ocf_q"] / out["Marcap"], np.nan)
        out["sales_yield"] = np.where(valid_mc, out["revenue_q"] / out["Marcap"], np.nan)
        out["signal_date"] = signal
        return out[[
            "Code", "signal_date", "available_date", "fs_div",
            "equity", "revenue_q", "net_income_q", "ocf_q",
            *VALUE_FACTOR_FIELDS,
        ]].copy()
