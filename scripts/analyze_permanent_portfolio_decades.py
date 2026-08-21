from pathlib import Path
import math

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"
DAILY_FILE = RESULTS / "daily_nav.csv"
OUTPUT_FILE = RESULTS / "decade_metrics.csv"

SEGMENTS = [
    ("1970s", pd.Timestamp("1970-01-02"), pd.Timestamp("1979-12-31")),
    ("1980s", pd.Timestamp("1980-01-01"), pd.Timestamp("1989-12-31")),
    ("1990s", pd.Timestamp("1990-01-01"), pd.Timestamp("1999-12-31")),
    ("2000s", pd.Timestamp("2000-01-01"), pd.Timestamp("2009-12-31")),
    ("2010s", pd.Timestamp("2010-01-01"), pd.Timestamp("2019-12-31")),
    ("2020s_to_2026-08-19", pd.Timestamp("2020-01-01"), pd.Timestamp("2026-08-19")),
]


def load_daily() -> pd.DataFrame:
    if not DAILY_FILE.exists():
        raise FileNotFoundError(f"Missing file: {DAILY_FILE}")

    df = pd.read_csv(DAILY_FILE)
    if "Date" not in df.columns:
        # daily_nav.csv is saved with the DatetimeIndex; pandas normally names it Date.
        df = df.rename(columns={df.columns[0]: "Date"})

    required = {"Date", "NAV", "PortfolioReturn", "RiskFreeReturn_DTB3"}
    missing = required.difference(df.columns)
    if missing:
        raise RuntimeError(f"Missing daily-nav columns: {sorted(missing)}")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["NAV", "PortfolioReturn", "RiskFreeReturn_DTB3"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Date", "NAV", "PortfolioReturn", "RiskFreeReturn_DTB3"])
    df = df.sort_values("Date").drop_duplicates("Date").set_index("Date")
    return df


def interval_path(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Return the segment plus the prior trading-day NAV as the opening anchor when available."""
    seg = df.loc[start:end].copy()
    if seg.empty:
        raise RuntimeError(f"No observations for {start.date()} to {end.date()}")

    first_pos = df.index.get_loc(seg.index[0])
    if first_pos > 0:
        prev = df.iloc[[first_pos - 1]].copy()
        path = pd.concat([prev, seg])
    else:
        path = seg
    return path


def compute_recovery(df: pd.DataFrame, peak_date: pd.Timestamp, trough_date: pd.Timestamp, peak_nav: float):
    future = df.loc[trough_date:]
    recovered = future[future["NAV"] >= peak_nav]
    if recovered.empty:
        return None, None, None, "ongoing"

    recovery_date = recovered.index[0]
    peak_to_recovery_days = int((recovery_date - peak_date).days)
    trough_to_recovery_days = int((recovery_date - trough_date).days)
    return recovery_date, peak_to_recovery_days, trough_to_recovery_days, "recovered"


def analyze_segment(df: pd.DataFrame, label: str, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    seg = df.loc[start:end].copy()
    if seg.empty:
        raise RuntimeError(f"No observations in segment {label}")

    path = interval_path(df, start, end)
    opening_date = path.index[0]
    first_segment_date = seg.index[0]
    last_date = seg.index[-1]

    opening_nav = float(path["NAV"].iloc[0])
    ending_nav = float(seg["NAV"].iloc[-1])
    total_return = ending_nav / opening_nav - 1.0
    years = (last_date - opening_date).days / 365.2425
    cagr = (ending_nav / opening_nav) ** (1.0 / years) - 1.0

    running_max = path["NAV"].cummax()
    dd = path["NAV"] / running_max - 1.0
    trough_date = dd.idxmin()
    mdd = float(dd.loc[trough_date])

    peak_nav = float(running_max.loc[trough_date])
    peak_candidates = path.loc[:trough_date, "NAV"]
    peak_date = peak_candidates[peak_candidates == peak_nav].index[-1]

    recovery_date, peak_to_recovery_days, trough_to_recovery_days, recovery_status = compute_recovery(
        df, peak_date, trough_date, peak_nav
    )

    excess = seg["PortfolioReturn"] - seg["RiskFreeReturn_DTB3"]
    sharpe = np.nan
    if len(excess) > 1 and excess.std(ddof=1) > 0:
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(252.0))

    annual_returns = (1.0 + seg["PortfolioReturn"]).groupby(seg.index.year).prod() - 1.0
    worst_year = int(annual_returns.idxmin())
    worst_year_return = float(annual_returns.min())
    worst_year_is_partial = bool(
        worst_year == last_date.year and last_date < pd.Timestamp(f"{last_date.year}-12-31")
    )

    return {
        "period": label,
        "first_trading_date": first_segment_date.date().isoformat(),
        "last_trading_date": last_date.date().isoformat(),
        "opening_anchor_date": opening_date.date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "daily_mdd": mdd,
        "mdd_peak_date": peak_date.date().isoformat(),
        "mdd_trough_date": trough_date.date().isoformat(),
        "recovery_date": recovery_date.date().isoformat() if recovery_date is not None else "",
        "peak_to_recovery_calendar_days": peak_to_recovery_days,
        "trough_to_recovery_calendar_days": trough_to_recovery_days,
        "recovery_status": recovery_status,
        "sharpe_excess_dtb3_sqrt252": sharpe,
        "worst_year": worst_year,
        "worst_year_return": worst_year_return,
        "worst_year_is_partial": worst_year_is_partial,
    }


def validate_full_history(df: pd.DataFrame) -> None:
    compounded = float((1.0 + df["PortfolioReturn"]).prod())
    nav_ratio = float(df["NAV"].iloc[-1] / df["NAV"].iloc[0])
    if not np.isclose(compounded, nav_ratio, rtol=1e-10, atol=1e-10):
        raise RuntimeError(
            f"Daily-return compounding check failed: compounded={compounded}, nav_ratio={nav_ratio}"
        )


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    df = load_daily()
    validate_full_history(df)

    rows = [analyze_segment(df, label, start, end) for label, start, end in SEGMENTS]
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print("=== Permanent Portfolio Decade Metrics ===")
    print("MDD: daily, local to each segment; prior trading-day NAV is the opening anchor.")
    print("Sharpe: daily portfolio return minus DTB3 risk-free return, annualized by sqrt(252).")
    print("Recovery: MDD peak to first later date the full-history NAV regains that peak; may cross decade boundaries.")
    print("Worst year: exact compounding of daily portfolio returns within each calendar year.")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
