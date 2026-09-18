from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd

from quant_backtest_template_v2_8 import (
    BacktestConfig,
    run_four_periods,
    combine_period_payloads,
    save_chat_payload,
)

AS_OF = pd.Timestamp("2026-09-18")
LATEST_COMPLETE_MONTH = pd.Timestamp("2026-08-31")
INITIAL_CAPITAL = 10_000.0
W_STOCK, W_BOND = 0.60, 0.40
BASE_COST_BPS = 5.0
COST_SCENARIOS_BPS = (0.0, 5.0, 15.0)

BOOK_START = "1970-01-01"
BOOK_END = "2021-12-31"

OUT = Path("results/60_40_template_v28")
OUT.mkdir(parents=True, exist_ok=True)

POFO_SP500 = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/SP500.csv"
POFO_IEF = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/IEF.csv"


def load_proxy(url: str, name: str) -> pd.Series:
    df = pd.read_csv(url, comment="#")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    s = (
        df.dropna(subset=["date", "close"])
        .drop_duplicates("date")
        .set_index("date")["close"]
        .sort_index()
        .rename(name)
    )
    if s.empty:
        raise RuntimeError(f"{name}: proxy data is empty")
    return s


def load_actual(path: str, name: str) -> pd.Series:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    df[col] = pd.to_numeric(df[col], errors="coerce")
    s = (
        df.dropna(subset=["Date", col])
        .drop_duplicates("Date")
        .set_index("Date")[col]
        .sort_index()
        .rename(name)
    )
    if s.empty:
        raise RuntimeError(f"{name}: actual ETF data is empty")
    return s


def stitch_proxy_to_actual(proxy: pd.Series, actual: pd.Series, end: pd.Timestamp) -> pd.Series:
    idx = pd.bdate_range(proxy.index.min(), end)
    p = proxy.reindex(idx).ffill()
    a = actual.reindex(idx).ffill()

    first = actual.index.min()
    if first > end:
        return p.loc[:end]

    if pd.isna(p.loc[first]) or pd.isna(a.loc[first]):
        raise RuntimeError(f"splice failure at {first.date()}")

    scale = float(p.loc[first]) / float(a.loc[first])
    out = p.copy()
    out.loc[first:] = a.loc[first:] * scale
    return out.loc[:end]


def build_asset_levels() -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    stock_proxy = load_proxy(POFO_SP500, "Stock_proxy")
    bond_proxy = load_proxy(POFO_IEF, "Bond_proxy")

    spy = load_actual("data/etf_us/SPY.csv", "SPY")
    ief = load_actual("data/etf_us/IEF.csv", "IEF")

    stock = stitch_proxy_to_actual(stock_proxy, spy, LATEST_COMPLETE_MONTH)
    bond = stitch_proxy_to_actual(bond_proxy, ief, LATEST_COMPLETE_MONTH)

    levels = pd.concat(
        [stock.rename("Stock"), bond.rename("Bond")], axis=1
    ).dropna()

    if levels.index[-1] < LATEST_COMPLETE_MONTH:
        raise RuntimeError(
            f"asset data ends too early: {levels.index[-1].date()} < "
            f"{LATEST_COMPLETE_MONTH.date()}"
        )

    return levels, spy.index.min(), ief.index.min()


def simulate_annual_6040(levels: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.DataFrame]:
    """Annual 60/40 rebalance using close-to-close returns.

    Rebalance is applied at the turn of the calendar year before the first
    business-day return of the new year. Cost is charged only on gross traded
    notional at rebalance; initial deployment cost is excluded.
    """
    ret = levels.pct_change().fillna(0.0)

    stock_value = W_STOCK
    bond_value = W_BOND
    nav_rows: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict] = []

    prev_year = levels.index[0].year

    for i, (dt, row) in enumerate(ret.iterrows()):
        if i > 0 and dt.year != prev_year:
            pre_nav = stock_value + bond_value
            target_stock = pre_nav * W_STOCK
            target_bond = pre_nav * W_BOND
            gross_notional = abs(target_stock - stock_value) + abs(target_bond - bond_value)
            cost = gross_notional * cost_bps / 10_000.0
            post_nav = pre_nav - cost

            stock_value = post_nav * W_STOCK
            bond_value = post_nav * W_BOND

            trade_rows.append(
                {
                    "Date": dt,
                    "GrossTurnover": gross_notional / pre_nav if pre_nav > 0 else np.nan,
                    "CostNAV": cost,
                }
            )
            prev_year = dt.year

        if i > 0:
            stock_value *= 1.0 + float(row["Stock"])
            bond_value *= 1.0 + float(row["Bond"])

        nav_rows.append((dt, stock_value + bond_value))

    nav = pd.Series(dict(nav_rows), dtype=float).sort_index()
    nav /= float(nav.iloc[0])

    trades = pd.DataFrame(trade_rows)
    return nav, trades


def stock_benchmark(levels: pd.DataFrame) -> pd.Series:
    s = levels["Stock"].astype(float).copy()
    return (s / float(s.iloc[0])).rename("S&P500 100%")


def month_end_nav(daily: pd.DataFrame) -> pd.DataFrame:
    m = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    m.index = m.index.to_period("M").to_timestamp("M")
    return m.loc[:LATEST_COMPLETE_MONTH]


def flatten_four_period_results(results: dict) -> pd.DataFrame:
    rows = []
    for period_key, result in results.items():
        metrics = result["metrics"].copy().reset_index()
        metrics.insert(0, "Period", period_key)
        metrics.insert(1, "PeriodLabel", result["label"])
        metrics.insert(2, "Start", result["start"].strftime("%Y-%m-%d"))
        metrics.insert(3, "End", result["end"].strftime("%Y-%m-%d"))
        rows.append(metrics)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    levels, spy_start, ief_start = build_asset_levels()

    gross, trades_0 = simulate_annual_6040(levels, 0.0)
    net_5, trades_5 = simulate_annual_6040(levels, BASE_COST_BPS)
    benchmark = stock_benchmark(levels)

    daily_nav = pd.concat(
        [
            gross.rename("60/40 비용전"),
            net_5.rename("60/40 비용후(5bp)"),
            benchmark,
        ],
        axis=1,
    ).dropna()

    monthly_nav = month_end_nav(daily_nav)

    config = BacktestConfig(
        title="거인의 포트폴리오 2번 - 60/40",
        initial_capital=INITIAL_CAPITAL,
        periods_per_year=12,
        risk_free_rate=0.0,
        book_start=BOOK_START,
        book_end=BOOK_END,
        standard_end_year=2026,
        as_of_date=str(AS_OF.date()),
    )

    # 핵심: 성과/위험지표와 4개 기간, 차트 payload는 모두 첨부 표준 템플릿으로 계산.
    results = run_four_periods(monthly_nav, config, daily_nav)
    summary = flatten_four_period_results(results)
    summary.to_csv(OUT / "summary_four_periods_template.csv", index=False, encoding="utf-8-sig")

    combined_payload = combine_period_payloads(
        *[results[k]["chat_payload"] for k in ["book_validation", "from_2000", "from_2021", "longest"]]
    )
    save_chat_payload(combined_payload, str(OUT / "chat_payload_four_periods.json"))

    daily_nav.to_csv(OUT / "daily_nav_full.csv.gz", compression="gzip")
    monthly_nav.to_csv(OUT / "monthly_nav_full.csv", encoding="utf-8-sig")

    # 비용 민감도도 동일 템플릿으로 재계산.
    sensitivity_rows = []
    for bps in COST_SCENARIOS_BPS:
        nav, trades = simulate_annual_6040(levels, bps)
        d = pd.DataFrame({f"60/40_{bps:g}bp": nav})
        m = month_end_nav(d)
        r = run_four_periods(m, config, d)

        avg_turnover = float(trades["GrossTurnover"].mean()) if len(trades) else 0.0
        for period_key, result in r.items():
            metric = result["metrics"].iloc[0]
            sensitivity_rows.append(
                {
                    "Period": period_key,
                    "Cost_bps": bps,
                    "CAGR": metric["CAGR"],
                    "MDD": metric["MDD"],
                    "Sharpe": metric["Sharpe"],
                    "Annualized_Std": metric["연환산_표준편차"],
                    "Max_Recovery_Months": metric["최대회복기간_개월"],
                    "Final_Asset_USD": metric["최종자산"],
                    "MDD_Source": metric["MDD_source"],
                    "Avg_Annual_Gross_Turnover": avg_turnover,
                }
            )

    pd.DataFrame(sensitivity_rows).to_csv(
        OUT / "cost_sensitivity_template.csv", index=False, encoding="utf-8-sig"
    )

    # 책의 1970~2021 수치와 템플릿 결과 비교.
    book_metric = results["book_validation"]["metrics"].loc["60/40 비용전"]
    book_compare = pd.DataFrame(
        [
            {"Metric": "Final_Asset_USD", "Book": 1_250_000.0, "Template_Backtest": float(book_metric["최종자산"])},
            {"Metric": "CAGR", "Book": 0.098, "Template_Backtest": float(book_metric["CAGR"])},
            {"Metric": "MDD", "Book": -0.295, "Template_Backtest": float(book_metric["MDD"])},
            {"Metric": "Sharpe", "Book": 0.52, "Template_Backtest": float(book_metric["Sharpe"])},
        ]
    )
    book_compare.to_csv(OUT / "book_verification_template.csv", index=False, encoding="utf-8-sig")

    # 실제 ETF 공통기간에서 hybrid와 실제 ETF의 수익률 연결 검증.
    actual_levels = pd.concat(
        [
            load_actual("data/etf_us/SPY.csv", "Stock"),
            load_actual("data/etf_us/IEF.csv", "Bond"),
        ],
        axis=1,
        join="inner",
    ).dropna().loc[:LATEST_COMPLETE_MONTH]

    actual_nav, _ = simulate_annual_6040(actual_levels, 0.0)
    hybrid_same_dates, _ = simulate_annual_6040(
        levels.reindex(actual_levels.index).ffill().dropna(), 0.0
    )

    overlap = pd.DataFrame(
        {
            "Actual_SPY_IEF": actual_nav,
            "Hybrid_same_dates": hybrid_same_dates,
        }
    ).dropna()
    overlap_ret = overlap.pct_change().dropna()
    overlap_check = {
        "start": overlap.index[0].date().isoformat(),
        "end": overlap.index[-1].date().isoformat(),
        "max_abs_daily_return_diff": float(
            (overlap_ret["Actual_SPY_IEF"] - overlap_ret["Hybrid_same_dates"]).abs().max()
        ),
        "final_multiple_actual": float(overlap["Actual_SPY_IEF"].iloc[-1] / overlap["Actual_SPY_IEF"].iloc[0]),
        "final_multiple_hybrid": float(overlap["Hybrid_same_dates"].iloc[-1] / overlap["Hybrid_same_dates"].iloc[0]),
    }
    (OUT / "actual_etf_overlap_check.json").write_text(
        json.dumps(overlap_check, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    metadata = {
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE_MONTH.date().isoformat(),
        "strategy": "SPY 60% + IEF 40%, annual rebalance",
        "book_validation": "1970-01 through 2021-12",
        "initial_capital_usd": INITIAL_CAPITAL,
        "risk_free_rate_for_template_sharpe": 0.0,
        "base_cost_bps_on_gross_rebalance_notional": BASE_COST_BPS,
        "initial_deployment_cost_included": False,
        "taxes_included": False,
        "execution_assumption": "rebalance at calendar-year turn before first business-day close-to-close return",
        "stock_proxy_before_actual": spy_start.date().isoformat(),
        "bond_proxy_before_actual": ief_start.date().isoformat(),
        "post_inception_data": "actual adjusted close from repository ETF files",
        "proxy_sources": [POFO_SP500, POFO_IEF],
        "actual_sources": ["data/etf_us/SPY.csv", "data/etf_us/IEF.csv"],
        "standard_template": "scripts/quant_backtest_template_v2_8.py copied from attached project template",
        "notes": [
            "Pre-ETF history is a reconstructed proxy, not executable ETF history.",
            "Book Sharpe methodology is not stated, so the template rf=0 Sharpe is not directly comparable.",
        ],
    }
    (OUT / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(summary.to_string(index=False))
    print("\nSELF-CHECK: all four period MDD sources")
    print(summary[["Period", "전략", "MDD_source"]].to_string(index=False))


if __name__ == "__main__":
    main()
