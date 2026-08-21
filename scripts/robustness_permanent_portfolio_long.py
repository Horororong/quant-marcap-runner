from pathlib import Path
import math

import numpy as np
import pandas as pd

from backtest_permanent_portfolio_long import (
    ASSETS,
    INITIAL_CAPITAL,
    TARGET_WEIGHT,
    build_master_calendar,
    build_asset_returns,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"

# One-way trading-cost assumptions applied to traded notional.
COST_SCENARIOS = {
    "gross_0bp": 0.0000,
    "base_10bp": 0.0010,
    "conservative_30bp": 0.0030,
}


def rebalance_flags(dates: pd.DatetimeIndex, month: int) -> pd.Series:
    """First US trading day of the chosen month in each calendar year."""
    flags = pd.Series(False, index=dates)
    frame = pd.DataFrame(index=dates)
    frame["year"] = dates.year
    frame["month"] = dates.month
    candidates = frame[frame["month"] == month]
    if candidates.empty:
        return flags
    first_dates = candidates.groupby("year").apply(lambda x: x.index.min())
    for d in first_dates:
        if d != dates[0]:
            flags.loc[d] = True
    return flags


def run_variant(
    returns: pd.DataFrame,
    rf_ret: pd.Series,
    rebalance_month: int,
    cost_rate: float,
):
    dates = returns.index
    flags = rebalance_flags(dates, rebalance_month)

    sleeves = pd.Series(INITIAL_CAPITAL * TARGET_WEIGHT, index=ASSETS, dtype=float)
    nav = pd.Series(index=dates, dtype=float)
    nav.iloc[0] = INITIAL_CAPITAL
    annual_turnovers = []
    total_cost = 0.0

    for i in range(1, len(dates)):
        d = dates[i]
        sleeves *= (1.0 + returns.loc[d, ASSETS])
        nav_before = float(sleeves.sum())

        if flags.loc[d]:
            target = pd.Series(nav_before * TARGET_WEIGHT, index=ASSETS)
            traded = float((target - sleeves).abs().sum())
            turnover = traded / nav_before if nav_before > 0 else np.nan
            cost = traded * cost_rate
            nav_after_cost = nav_before - cost
            if nav_after_cost <= 0:
                raise RuntimeError("Trading costs exhausted portfolio value")
            sleeves = pd.Series(nav_after_cost * TARGET_WEIGHT, index=ASSETS)
            annual_turnovers.append(turnover)
            total_cost += cost

        nav.iloc[i] = float(sleeves.sum())

    portfolio_ret = nav.pct_change().fillna(0.0)
    years = (dates[-1] - dates[0]).days / 365.2425
    final = float(nav.iloc[-1])
    cagr = (final / INITIAL_CAPITAL) ** (1.0 / years) - 1.0

    dd = nav / nav.cummax() - 1.0
    mdd = float(dd.min())
    mdd_date = dd.idxmin()

    excess = (portfolio_ret - rf_ret).iloc[1:]
    sharpe = np.nan
    if excess.std(ddof=1) > 0:
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(252.0))

    ann_vol = float(portfolio_ret.iloc[1:].std(ddof=1) * math.sqrt(252.0))
    avg_turnover = float(np.nanmean(annual_turnovers)) if annual_turnovers else 0.0

    return {
        "rebalance_month": rebalance_month,
        "cost_rate": cost_rate,
        "final_asset_usd": final,
        "cagr": cagr,
        "mdd": mdd,
        "mdd_date": mdd_date.date().isoformat(),
        "sharpe_excess_dtb3_sqrt252": sharpe,
        "annualized_volatility": ann_vol,
        "average_annual_rebalance_turnover": avg_turnover,
        "cumulative_trading_cost_usd_nominal": total_cost,
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)

    master = build_master_calendar()
    returns = build_asset_returns(master)
    rf = returns["RF_RETURN"]

    rows = []
    for month in range(1, 13):
        for cost_name, cost_rate in COST_SCENARIOS.items():
            row = run_variant(returns, rf, month, cost_rate)
            row["cost_scenario"] = cost_name
            rows.append(row)

    detail = pd.DataFrame(rows)
    detail = detail[
        [
            "rebalance_month",
            "cost_scenario",
            "cost_rate",
            "final_asset_usd",
            "cagr",
            "mdd",
            "mdd_date",
            "sharpe_excess_dtb3_sqrt252",
            "annualized_volatility",
            "average_annual_rebalance_turnover",
            "cumulative_trading_cost_usd_nominal",
        ]
    ].sort_values(["cost_rate", "rebalance_month"])
    detail.to_csv(RESULTS / "robustness_rebalance_month_cost.csv", index=False, encoding="utf-8-sig")

    gross = detail[detail["cost_scenario"] == "gross_0bp"].copy()
    summary_rows = [
        {
            "test": "rebalance_month_gross",
            "cagr_min": gross["cagr"].min(),
            "cagr_median": gross["cagr"].median(),
            "cagr_max": gross["cagr"].max(),
            "mdd_best": gross["mdd"].max(),
            "mdd_median": gross["mdd"].median(),
            "mdd_worst": gross["mdd"].min(),
            "sharpe_min": gross["sharpe_excess_dtb3_sqrt252"].min(),
            "sharpe_median": gross["sharpe_excess_dtb3_sqrt252"].median(),
            "sharpe_max": gross["sharpe_excess_dtb3_sqrt252"].max(),
        }
    ]

    jan = detail[detail["rebalance_month"] == 1].copy()
    for _, r in jan.iterrows():
        summary_rows.append(
            {
                "test": f"january_{r['cost_scenario']}",
                "cagr_min": r["cagr"],
                "cagr_median": r["cagr"],
                "cagr_max": r["cagr"],
                "mdd_best": r["mdd"],
                "mdd_median": r["mdd"],
                "mdd_worst": r["mdd"],
                "sharpe_min": r["sharpe_excess_dtb3_sqrt252"],
                "sharpe_median": r["sharpe_excess_dtb3_sqrt252"],
                "sharpe_max": r["sharpe_excess_dtb3_sqrt252"],
            }
        )

    pd.DataFrame(summary_rows).to_csv(
        RESULTS / "robustness_summary.csv", index=False, encoding="utf-8-sig"
    )

    print("=== Permanent Portfolio Robustness ===")
    print("Rebalance timing: first US trading day of each selected month, close; effective next trading day")
    print("Months tested: 1 through 12")
    print("One-way cost scenarios: 0bp, 10bp, 30bp of traded notional")
    print(gross[["rebalance_month", "cagr", "mdd", "sharpe_excess_dtb3_sqrt252"]].to_string(index=False))
    print("\nJanuary cost sensitivity:")
    print(jan[["cost_scenario", "cagr", "mdd", "sharpe_excess_dtb3_sqrt252", "final_asset_usd"]].to_string(index=False))


if __name__ == "__main__":
    main()
