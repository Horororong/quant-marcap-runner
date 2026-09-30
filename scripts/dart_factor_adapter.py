from __future__ import annotations

"""Point-in-time DART factor adapter for Strategy DSL.

This module extracts the financial-factor logic that was previously embedded in
backtest_super_value_v216.py. It deliberately produces only PIT factor inputs;
portfolio construction, execution and performance metrics remain elsewhere.

The first supported family is the four "super value" yields:
- earnings_yield = standalone-quarter net income / signal-date market cap
- book_to_price = latest reported equity / signal-date market cap
- cashflow_yield = standalone-quarter operating cash flow / signal-date market cap
- sales_yield = standalone-quarter revenue / signal-date market cap

Quarter reconstruction matches the legacy v2-16 research implementation:
- April signal: prior FY cumulative/current minus prior Q3 cumulative
- October signal: H1 current if supplied, otherwise H1 cumulative minus Q1 cumulative
- CFS first, OFS fallback when the CFS row set is incomplete
- only filings available on or before the signal date are eligible
"""

from pathlib import Path
from typing import Any, Iterable, Optional
import re

import numpy as np
import pandas as pd

DART_VALUE_FACTOR_FIELDS = {
    "earnings_yield",
    "book_to_price",
    "cashflow_yield",
    "sales_yield",
}

_BASE_METRIC_COLUMNS = ("equity", "revenue_q", "net_income_q", "ocf_q")


def to_num(x: Any) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).strip().replace(",", "")
    if s in {"", "-", "--", "nan", "None"}:
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        value = float(s)
        return -value if neg else value
    except Exception:
        return np.nan


def normalize_name(x: Any) -> str:
    return re.sub(r"\s+", "", str(x or "")).lower()


def metric_priority(row: pd.Series) -> tuple[Optional[str], int]:
    """Map one DART raw account row to the canonical metric used by super-value."""
    sj = str(row.get("sj_div", "") or "").upper()
    aid = normalize_name(row.get("account_id", ""))
    nm = normalize_name(row.get("account_nm", ""))

    if sj == "BS" and (
        "ifrs-full_equity" in aid or aid.endswith("equity") or nm in {"자본총계", "총자본"}
    ):
        pri = 0 if ("ifrs-full-equity" in aid or nm == "자본총계") else 2
        return "equity", pri

    if sj in {"IS", "CIS"} and (
        "revenue" in aid
        or nm in {"매출액", "영업수익", "수익", "수익(매출액)", "매출"}
    ):
        pri = 0 if ("revenue" in aid or nm == "매출액") else 2
        return "revenue", pri + (0 if sj == "IS" else 1)

    if sj in {"IS", "CIS"} and (
        "profitloss" in aid
        or nm in {
            "당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)",
            "반기순이익", "반기순이익(손실)", "연결당기순이익",
        }
    ):
        pri = 0 if "profitloss" in aid else 2
        return "net_income", pri + (0 if sj == "IS" else 1)

    if sj == "CF" and (
        "cashflowsfromusedinoperatingactivities" in aid
        or nm in {"영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로부터의현금흐름"}
    ):
        pri = 0 if "cashflowsfromusedinoperatingactivities" in aid else 2
        return "ocf", pri

    return None, 99


def required_periods_for_signal(signal: pd.Timestamp) -> list[tuple[int, str]]:
    signal = pd.Timestamp(signal).normalize()
    if signal.month == 10:
        return [(signal.year, "Q1"), (signal.year, "H1")]
    if signal.month == 4:
        return [(signal.year - 1, "Q3"), (signal.year - 1, "FY")]
    raise ValueError(
        f"DART standalone-quarter adapter currently supports April/October signals only; got {signal.date()}"
    )


def _load_financial_raw(repo_root: Path, year: int, period: str) -> pd.DataFrame:
    """Load and prefilter both CFS/OFS shards using the legacy v2-16 account contract."""
    base = repo_root / "data/financials/full_history"
    files: list[Path] = []
    for fs in ("CFS", "OFS"):
        files.extend(sorted(base.glob(f"dart_full_{int(year)}_{str(period).upper()}_{fs}_*.csv.gz")))
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
        ren: dict[str, str] = {}
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
        fallback_fs = x["fs_div"] if "fs_div" in x.columns else ""
        x["fs_div_requested"] = x["fs_div_requested"].fillna(fallback_fs).astype(str).str.upper()

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
        raise ValueError(f"No candidate DART factor rows for {year} {period}")
    out = pd.concat(chunks, ignore_index=True, sort=False)
    dedup = [
        z for z in ["stock_code", "rcept_no", "fs_div_requested", "sj_div", "account_id", "account_nm"]
        if z in out.columns
    ]
    if dedup:
        out = out.drop_duplicates(dedup, keep="last")
    return out


def report_snapshots(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if "rcept_no" not in raw.columns:
        raise KeyError("rcept_no missing")
    required = {"stock_code", "fs_div_requested", "filing_date"}
    missing = required - set(raw.columns)
    if missing:
        raise KeyError(f"DART raw rows missing columns: {sorted(missing)}")

    for (code, fs, rcept, filing_date), g in raw.groupby(
        ["stock_code", "fs_div_requested", "rcept_no", "filing_date"], dropna=False
    ):
        candidates: list[dict[str, Any]] = []
        for _, row in g.iterrows():
            metric, priority = metric_priority(row)
            if metric is None:
                continue
            candidates.append({
                "metric": metric,
                "priority": priority,
                "current": to_num(row.get("thstrm_amount")),
                "cumulative": to_num(row.get("thstrm_add_amount")),
            })
        if not candidates:
            continue

        cand = pd.DataFrame(candidates)
        rec: dict[str, Any] = {
            "Code": str(code).zfill(6),
            "fs_div": str(fs),
            "rcept_no": str(rcept),
            "filing_date": pd.Timestamp(filing_date) if pd.notna(filing_date) else pd.NaT,
        }
        for metric in ("equity", "revenue", "net_income", "ocf"):
            z = cand[cand["metric"] == metric].copy()
            if z.empty:
                rec[f"{metric}_current"] = np.nan
                rec[f"{metric}_cum"] = np.nan
                continue
            z["has_value"] = z[["current", "cumulative"]].notna().any(axis=1).astype(int)
            z = z.sort_values(["has_value", "priority"], ascending=[False, True])
            best = z.iloc[0]
            rec[f"{metric}_current"] = best["current"]
            rec[f"{metric}_cum"] = best["cumulative"]
        rows.append(rec)
    return pd.DataFrame(rows)


def latest_snapshot(snapshots: pd.DataFrame, signal: pd.Timestamp) -> pd.DataFrame:
    if snapshots.empty:
        return snapshots.copy()
    signal = pd.Timestamp(signal).normalize()
    x = snapshots[
        snapshots["filing_date"].notna() & (pd.to_datetime(snapshots["filing_date"]) <= signal)
    ].copy()
    if x.empty:
        return x
    x = x.sort_values(["Code", "fs_div", "filing_date", "rcept_no"])
    return x.groupby(["Code", "fs_div"], as_index=False).tail(1)


class DartValueFactorAdapter:
    """Cached PIT adapter for the four DART value yields."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self._snapshot_cache: dict[tuple[int, str], pd.DataFrame] = {}

    def _snapshots(self, year: int, period: str) -> pd.DataFrame:
        key = (int(year), str(period).upper())
        if key not in self._snapshot_cache:
            raw = _load_financial_raw(self.repo_root, *key)
            self._snapshot_cache[key] = report_snapshots(raw)
        return self._snapshot_cache[key]

    def base_metrics(self, signal: pd.Timestamp) -> pd.DataFrame:
        """Return one CFS-first/OFS-fallback PIT metric row per stock for a signal."""
        signal = pd.Timestamp(signal).normalize()
        rows: list[dict[str, Any]] = []

        if signal.month == 10:
            y = signal.year
            q1 = latest_snapshot(self._snapshots(y, "Q1"), signal)
            h1 = latest_snapshot(self._snapshots(y, "H1"), signal)
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

                dates = [r.get("filing_date_h1"), r.get("filing_date_q1")]
                available = max([pd.Timestamp(d) for d in dates if pd.notna(d)], default=pd.NaT)
                rows.append({
                    "Code": r["Code"],
                    "fs_div": r["fs_div"],
                    "available_date": available,
                    "equity": r.get("equity_current_h1", np.nan),
                    "revenue_q": rev_q,
                    "net_income_q": ni_q,
                    "ocf_q": ocf_h1 - ocf_q1 if pd.notna(ocf_h1) and pd.notna(ocf_q1) else np.nan,
                })

        elif signal.month == 4:
            fy_year = signal.year - 1
            q3 = latest_snapshot(self._snapshots(fy_year, "Q3"), signal)
            fy = latest_snapshot(self._snapshots(fy_year, "FY"), signal)
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

                dates = [r.get("filing_date_fy"), r.get("filing_date_q3")]
                available = max([pd.Timestamp(d) for d in dates if pd.notna(d)], default=pd.NaT)
                rows.append({
                    "Code": r["Code"],
                    "fs_div": r["fs_div"],
                    "available_date": available,
                    "equity": r.get("equity_current_fy", np.nan),
                    "revenue_q": rev_fy - rev_q3 if pd.notna(rev_fy) and pd.notna(rev_q3) else np.nan,
                    "net_income_q": ni_fy - ni_q3 if pd.notna(ni_fy) and pd.notna(ni_q3) else np.nan,
                    "ocf_q": ocf_fy - ocf_q3 if pd.notna(ocf_fy) and pd.notna(ocf_q3) else np.nan,
                })
        else:
            required_periods_for_signal(signal)  # raises a descriptive error
            raise AssertionError("unreachable")

        out = pd.DataFrame(rows)
        if out.empty:
            return out
        out["complete"] = out[list(_BASE_METRIC_COLUMNS)].notna().all(axis=1)
        out["fs_priority"] = out["fs_div"].map({"CFS": 0, "OFS": 1}).fillna(9)
        out = out.sort_values(["Code", "complete", "fs_priority"], ascending=[True, False, True])
        out = out.groupby("Code", as_index=False).head(1).drop(columns=["complete", "fs_priority"])
        if out.duplicated("Code").any():
            raise AssertionError("DART adapter produced duplicate Code rows")
        if out["available_date"].notna().any() and (out["available_date"].dropna() > signal).any():
            raise AssertionError("DART adapter exposed a filing after the signal date")
        return out.reset_index(drop=True)

    def enrich_cross_section(
        self,
        cross_section: pd.DataFrame,
        signal: pd.Timestamp,
        fields: Iterable[str],
    ) -> pd.DataFrame:
        requested = {str(x) for x in fields}
        unsupported = requested - DART_VALUE_FACTOR_FIELDS
        if unsupported:
            raise ValueError(f"unsupported DART value factor fields: {sorted(unsupported)}")
        x = cross_section.copy()
        if "Code" not in x.columns or "Marcap" not in x.columns:
            raise KeyError("cross_section requires Code and Marcap for DART value factors")
        x["Code"] = x["Code"].astype(str).str.zfill(6)
        metrics = self.base_metrics(pd.Timestamp(signal))
        x = x.merge(metrics, on="Code", how="left", validate="one_to_one")
        marcap = pd.to_numeric(x["Marcap"], errors="coerce")
        valid_cap = marcap > 0
        formulas = {
            "earnings_yield": "net_income_q",
            "book_to_price": "equity",
            "cashflow_yield": "ocf_q",
            "sales_yield": "revenue_q",
        }
        for field in requested:
            numerator = pd.to_numeric(x[formulas[field]], errors="coerce")
            x[field] = (numerator / marcap).where(valid_cap)
        return x
