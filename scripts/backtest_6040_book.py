from __future__ import annotations

from pathlib import Path
import json
import math
import urllib.request

import numpy as np
import pandas as pd


# =========================================================
# Strategy / standard-template settings
# =========================================================
AS_OF = pd.Timestamp("2026-09-17")
LATEST_COMPLETE_MONTH_END = pd.Timestamp("2026-08-31")
INITIAL_CAPITAL = 10_000.0
STOCK_WEIGHT = 0.60
BOND_WEIGHT = 0.40
BASE_COST_BPS = 5.0
COST_SCENARIOS_BPS = [0.0, 5.0, 15.0]
RISK_FREE_RATE = 0.0

BOOK_START = pd.Timestamp("1970-01-01")
BOOK_END = pd.Timestamp("2021-12-31")

OUT = Path("results/60_40_book")
OUT.mkdir(parents=True, exist_ok=True)

POFO_SP500 = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/SP500.csv"
POFO_IEF = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/IEF.csv"

BOOK_REPORTED = {
    "Final_Asset_USD": 1_250_000.0,
    "CAGR": 0.098,
    "MDD": -0.295,
    "Sharpe": 0.52,
}


def read_remote_csv(url: str) -> pd.Series:
    # Keep the source file comments for reproducibility but parse only date/close.
    df = pd.read_csv(url, comment="#")
    if not {"date", "close"}.issubset(df.columns):
        raise RuntimeError(f"Unexpected columns from {url}: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date")
    if df.empty:
        raise RuntimeError(f"No usable observations: {url}")
    return df.set_index("date")["close"].astype(float)


def load_proxy_levels() -> pd.DataFrame:
    stock = read_remote_csv(POFO_SP500).rename("SP500_TR")
    bond = read_remote_csv(POFO_IEF).rename("IEF_TR_proxy")

    start = max(stock.index.min(), bond.index.min())
    end = min(LATEST_COMPLETE_MONTH_END, stock.index.max(), bond.index.max())
    if end < LATEST_COMPLETE_MONTH_END:
        raise RuntimeError(
            f"Proxy data do not reach the required complete month: end={end.date()}, "
            f"required={LATEST_COMPLETE_MONTH_END.date()}"
        )

    # Portfolio valuation calendar: US business days. Holiday gaps are forward-filled.
    # This avoids inventing returns while keeping the daily NAV calendar continuous enough
    # for the standard template's daily MDD/recovery checks.
    idx = pd.bdate_range(start.normalize(), end.normalize())
    levels = pd.concat([stock, bond], axis=1).reindex(idx).ffill()

    # Do not silently backfill before first real observation.
    levels = levels.dropna()
    if levels.index.min() > pd.Timestamp("1962-01-02"):
        raise RuntimeError(f"Unexpectedly late proxy start: {levels.index.min().date()}")

    # Sanity checks.
    if (levels <= 0).any().any() or not np.isfinite(levels.to_numpy()).all():
        raise RuntimeError("Proxy levels contain nonpositive/nonfinite values")
    return levels


def load_actual_etf_levels() -> pd.DataFrame:
    def one(path: str, name: str) -> pd.Series:
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        col = "Adj Close" if "Adj Close" in df.columns else "Close"
        df[col] = pd.to_numeric(df[col], errors="coerce")
        s = df.dropna(subset=["Date", col]).drop_duplicates("Date").set_index("Date")[col].sort_index()
        return s.rename(name).astype(float)

    spy = one("data/etf_us/SPY.csv", "SPY")
    ief = one("data/etf_us/IEF.csv", "IEF")
    x = pd.concat([spy, ief], axis=1, join="inner").dropna()
    x = x.loc[x.index <= LATEST_COMPLETE_MONTH_END]
    if x.empty:
        raise RuntimeError("Actual SPY/IEF overlap is empty")
    return x


def simulate_6040(levels: pd.DataFrame, cost_bps: float = 0.0) -> tuple[pd.Series, pd.DataFrame]:
    """60/40 buy-and-hold within year; rebalance before first valuation day of each new year.

    Cost is charged per dollar of gross traded notional (sum of absolute buy/sell notionals).
    Initial deployment cost is excluded so gross/net series share the same baseline 1.0.
    """
    if levels.shape[1] != 2:
        raise ValueError("simulate_6040 expects exactly two asset columns")
    levels = levels.sort_index().astype(float)
    returns = levels.pct_change().fillna(0.0)

    stock_value = STOCK_WEIGHT
    bond_value = BOND_WEIGHT
    nav_rows: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict] = []
    prev_year = levels.index[0].year

    for i, dt in enumerate(levels.index):
        if i > 0 and dt.year != prev_year:
            nav_pre = stock_value + bond_value
            target_stock = nav_pre * STOCK_WEIGHT
            target_bond = nav_pre * BOND_WEIGHT
            gross_traded = abs(target_stock - stock_value) + abs(target_bond - bond_value)
            cost = gross_traded * float(cost_bps) / 10_000.0
            nav_after_cost = nav_pre - cost
            if nav_after_cost <= 0:
                raise RuntimeError("Trading cost exhausted portfolio")
            stock_value = nav_after_cost * STOCK_WEIGHT
            bond_value = nav_after_cost * BOND_WEIGHT
            trade_rows.append({
                "Date": dt,
                "NAV_pre_cost": nav_pre,
                "Gross_traded_notional": gross_traded,
                "Gross_turnover": gross_traded / nav_pre,
                "Cost_NAV_units": cost,
                "Cost_bps": float(cost_bps),
            })
            prev_year = dt.year

        if i > 0:
            rs = float(returns.iloc[i, 0])
            rb = float(returns.iloc[i, 1])
            stock_value *= 1.0 + rs
            bond_value *= 1.0 + rb

        nav_rows.append((dt, stock_value + bond_value))

    nav = pd.Series(dict(nav_rows), name=f"60_40_{cost_bps:g}bp").sort_index()
    nav /= float(nav.iloc[0])
    trades = pd.DataFrame(trade_rows)
    return nav, trades


def simulate_stock100(level: pd.Series) -> pd.Series:
    s = level.astype(float).sort_index()
    out = s / float(s.iloc[0])
    out.name = "SP500_100"
    return out


def month_end_nav(daily: pd.DataFrame) -> pd.DataFrame:
    m = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    m.index = m.index.to_period("M").to_timestamp("M")
    # Standard template contract: only completed months.
    m = m.loc[m.index <= LATEST_COMPLETE_MONTH_END]
    expected = pd.period_range(m.index[0].to_period("M"), m.index[-1].to_period("M"), freq="M")
    if len(m) != len(expected):
        raise RuntimeError("Monthly NAV has missing months")
    return m


def _baseline_rebase(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    x = s.loc[(s.index >= start) & (s.index <= end)].copy()
    if x.empty:
        raise ValueError(f"No data in window {start}~{end}")
    pos = s.index.searchsorted(x.index[0])
    base = float(s.iloc[pos - 1]) if pos > 0 else 1.0
    return x.astype(float) / base


def _drawdown(nav: pd.Series) -> pd.Series:
    vals = nav.to_numpy(dtype=float)
    peak = np.maximum.accumulate(np.r_[1.0, vals])[1:]
    return pd.Series(vals / peak - 1.0, index=nav.index)


def _recovery_details(nav: pd.Series) -> dict:
    s = nav.astype(float).sort_index()
    baseline_date = s.index[0] - pd.offsets.BDay(1)
    peak_value = 1.0
    peak_date = baseline_date
    underwater_start = None
    longest_days = 0
    longest_start = pd.NaT
    longest_end = pd.NaT

    for dt, value in s.items():
        if value >= peak_value:
            if underwater_start is not None:
                days = (dt - underwater_start).days
                if days > longest_days:
                    longest_days = days
                    longest_start = underwater_start
                    longest_end = dt
                underwater_start = None
            peak_value = float(value)
            peak_date = dt
        else:
            if underwater_start is None:
                underwater_start = peak_date

    if underwater_start is not None:
        days = (s.index[-1] - underwater_start).days
        if days > longest_days:
            longest_days = days
            longest_start = underwater_start
            longest_end = pd.NaT

    return {
        "Max_Recovery_Days": int(longest_days),
        "Max_Recovery_Months": round(longest_days / 30.4375, 1),
        "Max_Recovery_Start": None if pd.isna(longest_start) else pd.Timestamp(longest_start).date().isoformat(),
        "Max_Recovery_End": None if pd.isna(longest_end) else pd.Timestamp(longest_end).date().isoformat(),
    }


def standard_metrics(full_monthly: pd.Series, full_daily: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    # Match the attached standard template's conventions:
    # CAGR/Sharpe/vol = monthly NAV; MDD/recovery = daily NAV.
    m = _baseline_rebase(full_monthly, start.to_period("M").to_timestamp("M"), end.to_period("M").to_timestamp("M"))
    d = _baseline_rebase(full_daily, start.to_period("M").start_time, end.to_period("M").end_time)

    prior = m.index[0] - pd.offsets.MonthEnd(1)
    r = pd.concat([pd.Series([1.0], index=[prior]), m]).pct_change().dropna()
    years = len(r) / 12.0
    final_multiple = float(m.iloc[-1])
    cagr = final_multiple ** (1.0 / years) - 1.0
    ann_vol = float(r.std(ddof=1) * np.sqrt(12)) if len(r) >= 2 else np.nan
    monthly_rf = (1.0 + RISK_FREE_RATE) ** (1.0 / 12.0) - 1.0
    excess = r - monthly_rf
    exstd = float(excess.std(ddof=1)) if len(excess) >= 2 else np.nan
    sharpe = float(excess.mean() / exstd * np.sqrt(12)) if np.isfinite(exstd) and exstd > 0 else np.nan

    dd = _drawdown(d)
    rec = _recovery_details(d)
    out = {
        "Start": m.index[0].date().isoformat(),
        "End": m.index[-1].date().isoformat(),
        "Months": int(len(r)),
        "Final_Multiple": final_multiple,
        "Final_Asset_USD": final_multiple * INITIAL_CAPITAL,
        "Cumulative_Return": final_multiple - 1.0,
        "CAGR": float(cagr),
        "Annualized_Vol": ann_vol,
        "MDD": float(dd.min()),
        "Sharpe_rf0": sharpe,
        "MDD_Source": "daily",
    }
    out.update(rec)
    return out


def detailed_mdd_dates(full_daily: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    d = _baseline_rebase(full_daily, start.to_period("M").start_time, end.to_period("M").end_time)
    dd = _drawdown(d)
    trough = dd.idxmin()
    peak = d.loc[:trough].idxmax()
    peak_value = float(d.loc[peak])
    after = d.loc[trough:]
    recovered = after[after >= peak_value]
    recovery = recovered.index[0] if len(recovered) else pd.NaT
    return {
        "MDD_Peak": peak.date().isoformat(),
        "MDD_Trough": trough.date().isoformat(),
        "MDD_Recovery": recovery.date().isoformat() if pd.notna(recovery) else "UNRECOVERED",
    }


def period_windows(monthly: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    data_start = monthly.index[0]
    data_end = monthly.index[-1]
    if data_end != LATEST_COMPLETE_MONTH_END:
        raise RuntimeError(f"Unexpected monthly end: {data_end.date()}")
    if data_start > pd.Timestamp("2000-01-31"):
        raise RuntimeError("Data do not satisfy fixed 2000 start")
    return {
        "book_validation": (BOOK_START, BOOK_END),
        "from_2000": (pd.Timestamp("2000-01-01"), data_end),
        "from_2021": (pd.Timestamp("2021-01-01"), data_end),
        "longest": (data_start.to_period("M").start_time, data_end),
    }


def cost_sensitivity(levels: pd.DataFrame, windows: dict) -> pd.DataFrame:
    rows = []
    for bps in COST_SCENARIOS_BPS:
        nav, trades = simulate_6040(levels, bps)
        monthly = month_end_nav(pd.DataFrame({"x": nav}))["x"]
        for key, (start, end) in windows.items():
            met = standard_metrics(monthly, nav, start, end)
            # Trades whose rebalance date lies inside performance window.
            if len(trades):
                t = trades[(pd.to_datetime(trades["Date"]) >= start) & (pd.to_datetime(trades["Date"]) <= end)]
                avg_turn = float(t["Gross_turnover"].mean()) if len(t) else 0.0
                total_cost = float(t["Cost_NAV_units"].sum()) if len(t) else 0.0
            else:
                avg_turn = 0.0
                total_cost = 0.0
            rows.append({
                "Period": key,
                "Cost_bps_per_gross_dollar": bps,
                "CAGR": met["CAGR"],
                "MDD": met["MDD"],
                "Final_Asset_USD": met["Final_Asset_USD"],
                "Avg_Annual_Gross_Turnover": avg_turn,
                "Total_Cost_NAV_Units": total_cost,
            })
    return pd.DataFrame(rows)


def actual_etf_robustness(proxy_levels: pd.DataFrame) -> pd.DataFrame:
    actual = load_actual_etf_levels()
    actual_nav, _ = simulate_6040(actual, 0.0)

    start = actual.index[0]
    end = actual.index[-1]
    proxy = proxy_levels.loc[(proxy_levels.index >= start) & (proxy_levels.index <= end)].copy()
    # Use actual trading dates for an apples-to-apples overlap comparison.
    proxy = proxy.reindex(actual.index).ffill().dropna()
    actual = actual.loc[proxy.index]
    actual_nav, _ = simulate_6040(actual, 0.0)
    proxy_nav, _ = simulate_6040(proxy, 0.0)

    def simple(nav: pd.Series, name: str) -> dict:
        years = (nav.index[-1] - nav.index[0]).days / 365.2425
        cagr = (float(nav.iloc[-1]) / float(nav.iloc[0])) ** (1.0 / years) - 1.0
        dd = nav / nav.cummax() - 1.0
        return {
            "Series": name,
            "Start": nav.index[0].date().isoformat(),
            "End": nav.index[-1].date().isoformat(),
            "Final_Multiple": float(nav.iloc[-1] / nav.iloc[0]),
            "CAGR": float(cagr),
            "MDD": float(dd.min()),
        }

    return pd.DataFrame([
        simple(actual_nav, "Actual_SPY_IEF"),
        simple(proxy_nav, "Pofo_SP500_IEF_proxy_same_dates"),
    ])


def write_plotly_html(monthly: pd.DataFrame, daily: pd.DataFrame, windows: dict) -> None:
    # Plotly is optional for computation; workflow installs it for interactive artifacts.
    import plotly.graph_objects as go

    # Default display period = 2000~latest; all series in one graph.
    start, end = windows["from_2000"]
    m = monthly.loc[(monthly.index >= start) & (monthly.index <= end)].copy()
    base = monthly.loc[monthly.index < m.index[0]].iloc[-1]
    m = m.div(base, axis=1)

    fig = go.Figure()
    for c in m.columns:
        fig.add_trace(go.Scatter(x=m.index, y=m[c] * INITIAL_CAPITAL, mode="lines", name=c))
    fig.update_layout(title="60/40 포트폴리오 — 누적자산 (2000~2026-08)", xaxis_title="날짜", yaxis_title="USD")
    fig.write_html(OUT / "01_cumulative_wealth.html", include_plotlyjs="cdn")

    fig2 = go.Figure()
    for c in m.columns:
        fig2.add_trace(go.Scatter(x=m.index, y=np.log2(m[c]), mode="lines", name=c))
    ymin = math.floor(float(np.log2(m.min().min())))
    ymax = math.ceil(float(np.log2(m.max().max())))
    ticks = list(range(min(0, ymin), max(1, ymax) + 1))
    fig2.update_yaxes(tickmode="array", tickvals=ticks, ticktext=[f"{2**p:g}배" for p in ticks])
    fig2.update_layout(title="60/40 포트폴리오 — Log2 누적자산 (2000~2026-08)", xaxis_title="날짜", yaxis_title="초기자산 대비 배수")
    fig2.write_html(OUT / "02_log2_wealth.html", include_plotlyjs="cdn")

    d = daily.loc[(daily.index >= start) & (daily.index <= end)].copy()
    prior = daily.loc[daily.index < d.index[0]].iloc[-1]
    d = d.div(prior, axis=1)
    fig3 = go.Figure()
    for c in d.columns:
        dd = d[c] / d[c].cummax() - 1.0
        fig3.add_trace(go.Scatter(x=dd.index, y=dd * 100.0, mode="lines", name=c))
    fig3.update_layout(title="60/40 포트폴리오 — Drawdown (일별, 2000~2026-08)", xaxis_title="날짜", yaxis_title="고점 대비 하락률 (%)")
    fig3.write_html(OUT / "03_drawdown_daily.html", include_plotlyjs="cdn")


def main() -> None:
    levels = load_proxy_levels()

    gross, gross_trades = simulate_6040(levels, 0.0)
    net5, net5_trades = simulate_6040(levels, BASE_COST_BPS)
    stock = simulate_stock100(levels.iloc[:, 0])

    daily = pd.DataFrame({
        "60/40 비용전": gross,
        "60/40 비용후(5bp)": net5,
        "S&P500 100%": stock,
    }).dropna()
    monthly = month_end_nav(daily)
    windows = period_windows(monthly)

    # Standard four-period result table.
    rows = []
    for key, (start, end) in windows.items():
        for col in daily.columns:
            met = standard_metrics(monthly[col], daily[col], start, end)
            met.update(detailed_mdd_dates(daily[col], start, end))
            met["Period"] = key
            met["Strategy"] = col
            rows.append(met)
    summary = pd.DataFrame(rows)
    summary = summary[[
        "Period", "Strategy", "Start", "End", "Months", "Final_Multiple", "Final_Asset_USD",
        "Cumulative_Return", "CAGR", "Annualized_Vol", "MDD", "Sharpe_rf0", "MDD_Source",
        "Max_Recovery_Months", "Max_Recovery_Days", "MDD_Peak", "MDD_Trough", "MDD_Recovery",
        "Max_Recovery_Start", "Max_Recovery_End",
    ]]
    summary.to_csv(OUT / "summary_four_periods.csv", index=False, encoding="utf-8-sig")

    # Book verification comparison.
    b = summary[(summary["Period"] == "book_validation") & (summary["Strategy"] == "60/40 비용전")].iloc[0]
    book_compare = pd.DataFrame([
        {"Metric": "Final_Asset_USD", "Book": BOOK_REPORTED["Final_Asset_USD"], "Backtest": b["Final_Asset_USD"], "Difference": b["Final_Asset_USD"] - BOOK_REPORTED["Final_Asset_USD"]},
        {"Metric": "CAGR", "Book": BOOK_REPORTED["CAGR"], "Backtest": b["CAGR"], "Difference": b["CAGR"] - BOOK_REPORTED["CAGR"]},
        {"Metric": "MDD", "Book": BOOK_REPORTED["MDD"], "Backtest": b["MDD"], "Difference": b["MDD"] - BOOK_REPORTED["MDD"]},
        {"Metric": "Sharpe", "Book": BOOK_REPORTED["Sharpe"], "Backtest": b["Sharpe_rf0"], "Difference": b["Sharpe_rf0"] - BOOK_REPORTED["Sharpe"]},
    ])
    book_compare.to_csv(OUT / "book_verification.csv", index=False, encoding="utf-8-sig")

    sens = cost_sensitivity(levels, windows)
    sens.to_csv(OUT / "cost_sensitivity.csv", index=False, encoding="utf-8-sig")

    robust = actual_etf_robustness(levels)
    robust.to_csv(OUT / "actual_etf_overlap_check.csv", index=False, encoding="utf-8-sig")

    # Save reduced chart data plus full daily drawdown inputs for reproducibility.
    monthly.to_csv(OUT / "monthly_nav_full.csv", encoding="utf-8-sig")
    daily.to_csv(OUT / "daily_nav_full.csv.gz", compression="gzip")
    if len(net5_trades):
        net5_trades.to_csv(OUT / "rebalance_trades_5bp.csv", index=False, encoding="utf-8-sig")

    write_plotly_html(monthly, daily, windows)

    metadata = {
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE_MONTH_END.date().isoformat(),
        "initial_capital_usd": INITIAL_CAPITAL,
        "allocation": {"SP500": STOCK_WEIGHT, "IEF": BOND_WEIGHT},
        "rebalance": "annual, before first valuation/business day return of each calendar year",
        "base_cost_bps_per_gross_traded_dollar": BASE_COST_BPS,
        "cost_scenarios_bps": COST_SCENARIOS_BPS,
        "risk_free_rate_for_sharpe": RISK_FREE_RATE,
        "metrics": {
            "CAGR_Sharpe_Vol": "monthly NAV",
            "MDD_Recovery": "daily NAV",
        },
        "sources": {
            "SP500": POFO_SP500,
            "IEF": POFO_IEF,
            "actual_overlap": ["data/etf_us/SPY.csv", "data/etf_us/IEF.csv"],
        },
        "proxy_start": levels.index[0].date().isoformat(),
        "proxy_end": levels.index[-1].date().isoformat(),
        "notes": [
            "Pre-ETF history is a backfilled total-return proxy; it is not executable SPY/IEF history before fund inception.",
            "Taxes are excluded.",
            "Initial deployment trading cost is excluded; annual rebalancing costs are modeled.",
            "September 2026 is excluded because it is incomplete as of 2026-09-17.",
        ],
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    assumptions = f"""# 60/40 backtest assumptions\n\n- Attached-book rule: 60% US stocks / 40% US intermediate Treasuries; annual rebalance.\n- Initial capital: $10,000.\n- Complete-data cutoff: 2026-08-31 (September 2026 excluded as incomplete on 2026-09-17).\n- Long proxy: pofo S&P 500 total-return series + pofo IEF/VFITX intermediate-Treasury backfill; daily from the common 1962 start.\n- Rebalance timing: before the first valuation/business-day return of each calendar year.\n- Gross result: no trading cost.\n- Net base: 5 bp per dollar of gross traded notional at annual rebalance; 0/5/15 bp sensitivity.\n- Taxes: excluded.\n- Sharpe risk-free rate: 0% to match the attached standard template default and facilitate book comparison.\n- CAGR/Sharpe/annualized volatility: monthly NAV.\n- MDD/max recovery: daily NAV.\n- Actual-instrument robustness check: repository SPY and IEF adjusted-close overlap from IEF inception onward.\n\n## Important limitation\n\nThe book's 1970~2021 result necessarily uses pre-ETF backfills. Different historical bond proxies, dividend timing, rebalance date, and Sharpe convention can produce nontrivial differences. The actual SPY/IEF overlap check is therefore reported separately.\n"""
    (OUT / "ASSUMPTIONS.md").write_text(assumptions, encoding="utf-8")

    print("=== FOUR PERIODS ===")
    print(summary.to_string(index=False))
    print("\n=== BOOK VERIFICATION ===")
    print(book_compare.to_string(index=False))
    print("\n=== ACTUAL ETF OVERLAP CHECK ===")
    print(robust.to_string(index=False))
    print("\n=== COST SENSITIVITY ===")
    print(sens.to_string(index=False))


if __name__ == "__main__":
    main()
