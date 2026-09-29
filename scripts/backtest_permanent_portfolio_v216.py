from __future__ import annotations

from pathlib import Path
import json
import importlib.util
import sys

import numpy as np
import pandas as pd

_TEMPLATE_PATH = Path(__file__).with_name("quant_backtest_template_PROJECT_v2-16_CURRENT.py")
_spec = importlib.util.spec_from_file_location("quant_backtest_template_v216_current", _TEMPLATE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load CURRENT template: {_TEMPLATE_PATH}")
_qbt = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _qbt
_spec.loader.exec_module(_qbt)
BacktestConfig = _qbt.BacktestConfig
TradingCostAssumptions = _qbt.TradingCostAssumptions
ExecutionAssumptions = _qbt.ExecutionAssumptions
run_execution_backtest = _qbt.run_execution_backtest
run_four_periods = _qbt.run_four_periods
combine_period_payloads = _qbt.combine_period_payloads
save_chat_payload = _qbt.save_chat_payload

ROOT = Path(__file__).resolve().parents[1]
RET_FILE = ROOT / "data/proxy_long/derived/permanent_portfolio_asset_returns_daily.csv"
ETF_DIR = ROOT / "data/etf_us"
OUT = ROOT / "results/permanent_portfolio_v216"
OUT.mkdir(parents=True, exist_ok=True)

AS_OF = pd.Timestamp("2026-09-29")
INITIAL_CAPITAL = 10_000.0
BOOK_START = "1970-01-01"
BOOK_END = "2021-12-31"
ASSETS = ["STOCK", "LONG_TREASURY", "GOLD", "TBILL"]
ETF_MAP = {
    "STOCK": "SPY",
    "LONG_TREASURY": "TLT",
    "GOLD": "GLD",
    "TBILL": "BIL",
}
TARGET_WEIGHT = 0.25

COST_SCENARIOS = {
    "min_0bp": TradingCostAssumptions(),
    "base_5bp": TradingCostAssumptions(spread_bps=2.0, slippage_bps=3.0),
    "conservative_15bp": TradingCostAssumptions(spread_bps=5.0, slippage_bps=10.0),
}


def load_returns_panel() -> tuple[pd.DataFrame, dict]:
    if not RET_FILE.exists():
        raise FileNotFoundError(RET_FILE)
    df = pd.read_csv(RET_FILE, encoding="utf-8-sig")
    need = ["Date", *ASSETS, "RF_RETURN"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"derived return panel missing columns: {missing}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
    if df["Date"].isna().any() or df["Date"].duplicated().any():
        raise AssertionError("invalid/duplicate Date in derived return panel")
    df = df.sort_values("Date").set_index("Date")
    for c in ASSETS + ["RF_RETURN"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[ASSETS + ["RF_RETURN"]].isna().any().any():
        raise AssertionError("NaN in derived return panel")
    if (df[ASSETS] <= -1.0).any().any():
        raise AssertionError("asset return <= -100% in derived return panel")

    proxy_end = df.index[-1]
    actual_returns = {}
    actual_last = {}
    overlap_diffs = {}
    for asset, ticker in ETF_MAP.items():
        p = ETF_DIR / f"{ticker}.csv"
        if not p.exists():
            raise FileNotFoundError(p)
        x = pd.read_csv(p)
        if "Date" not in x.columns or "Adj Close" not in x.columns:
            raise KeyError(f"{ticker}: Date/Adj Close missing")
        x["Date"] = pd.to_datetime(x["Date"], errors="coerce").dt.normalize()
        x["Adj Close"] = pd.to_numeric(x["Adj Close"], errors="coerce")
        x = x.dropna(subset=["Date", "Adj Close"]).drop_duplicates("Date").sort_values("Date")
        s = x.set_index("Date")["Adj Close"].astype(float)
        if s.empty or (s <= 0).any():
            raise AssertionError(f"{ticker}: invalid Adj Close")
        r = s.pct_change(fill_method=None)
        actual_returns[asset] = r
        actual_last[asset] = s.index[-1].date().isoformat()

        common = df.index.intersection(r.index)
        common = common[common >= max(df.index[0], proxy_end - pd.Timedelta(days=90))]
        if len(common) >= 5:
            diff = (df.loc[common, asset] - r.loc[common]).abs().dropna()
            overlap_diffs[asset] = {
                "n": int(len(diff)),
                "max_abs_daily_return_diff": float(diff.max()),
                "mean_abs_daily_return_diff": float(diff.mean()),
            }

    actual_ret = pd.concat(actual_returns, axis=1).sort_index()
    new = actual_ret.loc[actual_ret.index > proxy_end, ASSETS].dropna(how="any")
    if not new.empty:
        ext = pd.DataFrame(index=new.index, columns=df.columns, dtype=float)
        ext[ASSETS] = new[ASSETS]
        ext["RF_RETURN"] = new["TBILL"]
        df = pd.concat([df, ext], axis=0).sort_index()

    if df.index[-1] < pd.Timestamp("2026-08-31"):
        raise RuntimeError(f"return panel ends too early for latest complete month: {df.index[-1].date()}")

    meta = {
        "derived_start": df.index[0].date().isoformat(),
        "derived_original_end": proxy_end.date().isoformat(),
        "extended_end": df.index[-1].date().isoformat(),
        "actual_etf_last_dates": actual_last,
        "recent_overlap_check": overlap_diffs,
    }
    return df, meta


def returns_to_synthetic_prices(returns: pd.DataFrame) -> pd.DataFrame:
    r = returns[ASSETS].astype(float).copy()
    levels = (1.0 + r).cumprod()
    levels.iloc[0] = 1.0
    if levels.isna().any().any() or (levels <= 0).any().any():
        raise AssertionError("invalid synthetic total-return levels")
    return levels


def annual_equal_weight_signals(index: pd.DatetimeIndex) -> pd.DataFrame:
    idx = pd.DatetimeIndex(index).sort_values().unique()
    if len(idx) < 2:
        raise ValueError("not enough price observations")
    signal_dates = [idx[0] - pd.Timedelta(days=1)]
    years = pd.Series(idx, index=idx).groupby(idx.year).max()
    for _, d in years.items():
        d = pd.Timestamp(d)
        if d < idx[-1]:
            signal_dates.append(d)
    w = pd.DataFrame(TARGET_WEIGHT, index=pd.DatetimeIndex(signal_dates), columns=ASSETS, dtype=float)
    return w[~w.index.duplicated(keep="first")].sort_index()


def flatten_results(results: dict) -> pd.DataFrame:
    rows = []
    for period_key, result in results.items():
        m = result["metrics"].reset_index()
        m.insert(0, "Period", period_key)
        m.insert(1, "PeriodLabel", result["label"])
        m.insert(2, "Start", pd.Timestamp(result["start"]).date().isoformat())
        m.insert(3, "End", pd.Timestamp(result["end"]).date().isoformat())
        rows.append(m)
    return pd.concat(rows, ignore_index=True)


def build_chart_rows(results: dict) -> None:
    for key in ["from_2000", "from_2021", "longest"]:
        r = results[key]
        m = r["monthly_nav"].copy()
        d = r["daily_nav"].copy()
        dd = d / d.cummax() - 1.0
        mr = m.reset_index()
        mr = mr.rename(columns={mr.columns[0]: "Date"})
        mr.to_csv(OUT / f"chart_{key}_monthly.csv", index=False, encoding="utf-8-sig")
        dr = dd.reset_index()
        dr = dr.rename(columns={dr.columns[0]: "Date"})
        dr.to_csv(OUT / f"chart_{key}_drawdown.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    # exchange_calendars 4.x defaults to a rolling ~20-year schedule when no
    # explicit bounds are supplied. CURRENT v2-16 asks get_calendar("XNYS")
    # without bounds, so widen that lookup for the 1970 historical audit while
    # preserving the real XNYS session calendar.
    import exchange_calendars as xcals
    _real_get_calendar = xcals.get_calendar
    def _wide_get_calendar(name, start=None, end=None, side=None):
        if str(name).upper() == "XNYS" and start is None and end is None:
            return _real_get_calendar(name, start="1969-01-01", end="2027-12-31", side=side)
        return _real_get_calendar(name, start=start, end=end, side=side)
    xcals.get_calendar = _wide_get_calendar

    returns, data_meta = load_returns_panel()
    prices = returns_to_synthetic_prices(returns)
    signals = annual_equal_weight_signals(prices.index)

    cfg = BacktestConfig(
        title="거인의 포트폴리오 3번 - 영구 포트폴리오",
        initial_capital=INITIAL_CAPITAL,
        periods_per_year=12,
        risk_free_rate=0.0,
        book_start=BOOK_START,
        book_end=BOOK_END,
        expected_end="2026-08",
        standard_end_year=2026,
        as_of_date=str(AS_OF.date()),
        market_calendar="XNYS",
    )
    ex = ExecutionAssumptions(execution_lag_sessions=1, execution_price="next_close")

    execution = run_execution_backtest(
        close_prices=prices,
        target_weights=signals,
        config=cfg,
        cost_scenarios=COST_SCENARIOS,
        execution_assumptions=ex,
    )

    formal_daily = execution["formal_daily_nav"].copy()
    bm = prices["STOCK"].reindex(formal_daily.index)
    bm = bm / float(bm.iloc[0])
    formal_daily["S&P500 100%"] = bm
    formal_daily = formal_daily.rename(columns={
        "Gross": "영구포트폴리오 비용전",
        "Net_min_0bp": "영구포트폴리오 비용후 최소(0bp)",
        "Net_base_5bp": "영구포트폴리오 비용후 기준(5bp)",
        "Net_conservative_15bp": "영구포트폴리오 비용후 보수(15bp)",
    })
    formal_daily.attrs["market_calendar"] = "XNYS"

    monthly = formal_daily.groupby(formal_daily.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    monthly.attrs["market_calendar"] = "XNYS"

    results = run_four_periods(monthly, cfg, formal_daily)
    summary = flatten_results(results)
    summary.to_csv(OUT / "summary_four_periods_v216.csv", index=False, encoding="utf-8-sig")

    bmrow = results["book_validation"]["metrics"].loc["영구포트폴리오 비용전"]
    book = pd.DataFrame([
        {"Metric": "Final_Asset_USD", "Book": 762000.0, "Backtest_v216": float(bmrow["최종자산"])},
        {"Metric": "CAGR", "Book": 0.088, "Backtest_v216": float(bmrow["CAGR"])},
        {"Metric": "MDD", "Book": -0.127, "Backtest_v216": float(bmrow["MDD"])},
        {"Metric": "Sharpe", "Book": 0.57, "Backtest_v216": float(bmrow["Sharpe"])},
    ])
    book.to_csv(OUT / "book_comparison_v216.csv", index=False, encoding="utf-8-sig")

    cost_rows = []
    for name, out in execution["execution_scenarios"].items():
        trades = out["trades"]
        traded = trades[trades["traded_fraction"] > 0]
        cost_rows.append({
            "Scenario": name,
            "TradeCount": int(len(traded)),
            "MeanOneWayTurnoverOnTradeDays": float(traded["one_way_turnover"].mean()) if len(traded) else 0.0,
            "MeanCostFractionOnTradeDays": float(traded["cost_fraction"].mean()) if len(traded) else 0.0,
            "LatestExecutionDate": None if traded.empty else traded.index[-1].date().isoformat(),
        })
    pd.DataFrame(cost_rows).to_csv(OUT / "execution_cost_audit.csv", index=False, encoding="utf-8-sig")

    build_chart_rows(results)
    combined = combine_period_payloads(*[results[k]["chat_payload"] for k in ["from_2000", "from_2021", "longest"]])
    save_chat_payload(combined, str(OUT / "chat_payload_v216.json"))

    metadata = {
        "status": "COMPLETE_WITH_LIMITATIONS",
        "as_of": AS_OF.date().isoformat(),
        "formal_performance_end": execution["latest_daily_snapshot"]["formal_performance_end"].date().isoformat(),
        "latest_daily_date": execution["latest_daily_snapshot"]["latest_daily_date"].date().isoformat(),
        "engine": "scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py",
        "engine_version": "v2-16",
        "strategy": "SPY/TLT/GLD/BIL economic sleeves, 25% each, annual rebalance",
        "execution": "signal on prior year final session; next XNYS session close execution; effective following return interval",
        "book_period": "1970-01 through 2021-12",
        "initial_capital_usd": INITIAL_CAPITAL,
        "benchmark": "S&P 500 total-return proxy from STOCK sleeve",
        "cost_scenarios": {
            "min_0bp": "0bp",
            "base_5bp": "2bp spread + 3bp slippage on traded notional",
            "conservative_15bp": "5bp spread + 10bp slippage on traded notional",
        },
        "taxes": "not included (investor-specific taxes excluded)",
        "data": data_meta,
        "data_method": {
            "STOCK": "S&P500 price + Shiller dividend reconstruction, then SPY Adj Close; extended with SPY Adj Close",
            "LONG_TREASURY": "synthetic 20Y constant-maturity Treasury return, then TLT Adj Close; extended with TLT Adj Close",
            "GOLD": "LBMA PM USD gold, then GLD Adj Close; extended with GLD Adj Close",
            "TBILL": "3M T-bill accrued return, then BIL Adj Close; extended with BIL Adj Close",
        },
        "limitations": [
            "Pre-ETF history uses reconstructed proxies, so it is not directly executable ETF history.",
            "Gold pre-GLD history is spot gold while GLD later includes fund expenses.",
            "Long-Treasury pre-TLT history is a duration/coupon model, so model error can materially affect historical drawdowns.",
            "Template Sharpe uses monthly returns and a constant annual risk-free rate of 0%; the book's Sharpe methodology is not stated.",
        ],
    }
    (OUT / "run_metadata_v216.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== SUMMARY V2-16 ===")
    print(summary.to_string(index=False))
    print("\n=== BOOK COMPARISON ===")
    print(book.to_string(index=False))
    print("\n=== METADATA ===")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
