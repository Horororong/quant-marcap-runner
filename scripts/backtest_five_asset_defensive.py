from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "etf_us"
OUT_DIR = ROOT / "results" / "five_asset_defensive"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = ["SPY", "IEF", "TLT", "GLD", "DBC"]
TARGET = pd.Series({"SPY": 0.30, "IEF": 0.15, "TLT": 0.40, "GLD": 0.075, "DBC": 0.075}, dtype=float)
INITIAL_CAPITAL = 10_000.0
ONE_WAY_COST = 0.0005  # 5bp per traded notional (~10bp round trip)
TRADING_DAYS = 252


def load_adj_close() -> pd.DataFrame:
    series = {}
    for ticker in TICKERS:
        path = DATA_DIR / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path, parse_dates=["Date"])
        df = df.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date").set_index("Date")
        if "Adj Close" not in df.columns:
            raise RuntimeError(f"Adj Close missing for {ticker}")
        s = pd.to_numeric(df["Adj Close"], errors="coerce").dropna()
        if s.empty:
            raise RuntimeError(f"No valid Adj Close for {ticker}")
        series[ticker] = s.rename(ticker)

    prices = pd.concat(series.values(), axis=1, join="inner").dropna()
    if prices.empty:
        raise RuntimeError("No common ETF history")
    if (prices <= 0).any().any():
        raise RuntimeError("Non-positive adjusted close detected")
    return prices


def first_trading_days(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.year).first().tolist())


def simulate(asset_returns: pd.DataFrame, cost_rate: float) -> pd.DataFrame:
    dates = asset_returns.index
    weights = TARGET.copy()
    nav = INITIAL_CAPITAL
    rebalance_dates = first_trading_days(dates)
    rows = [{"Date": dates[0], "NAV": nav, "Return": 0.0, "Turnover": 0.0, "Cost": 0.0}]

    for dt in dates[1:]:
        r = asset_returns.loc[dt]
        nav_prev = nav
        nav *= 1.0 + float((weights * r).sum())

        drifted = weights * (1.0 + r)
        drifted = drifted / drifted.sum()
        turnover = 0.0
        cost = 0.0

        if dt in rebalance_dates:
            traded_fraction = float((drifted - TARGET).abs().sum())
            turnover = 0.5 * traded_fraction
            cost = nav * traded_fraction * cost_rate
            nav -= cost
            weights = TARGET.copy()
        else:
            weights = drifted

        rows.append({"Date": dt, "NAV": nav, "Return": nav / nav_prev - 1.0, "Turnover": turnover, "Cost": cost})

    return pd.DataFrame(rows).set_index("Date")


def max_drawdown_stats(nav: pd.Series):
    running_max = nav.cummax()
    dd = nav / running_max - 1.0
    trough = dd.idxmin()
    mdd = float(dd.loc[trough])
    peak = nav.loc[:trough].idxmax()
    peak_value = float(nav.loc[peak])
    future = nav.loc[trough:]
    recovered = future[future >= peak_value]
    recovery = recovered.index[0] if len(recovered) else pd.NaT
    recovery_days = (recovery - peak).days if pd.notna(recovery) else np.nan

    longest = 0
    peak_date = nav.index[0]
    peak_val = float(nav.iloc[0])
    for dt, val in nav.iloc[1:].items():
        val = float(val)
        if val >= peak_val:
            longest = max(longest, (dt - peak_date).days)
            peak_date = dt
            peak_val = val
    if float(nav.iloc[-1]) < peak_val:
        longest = max(longest, (nav.index[-1] - peak_date).days)

    return dd, mdd, peak, trough, recovery, recovery_days, longest


def metrics(nav: pd.Series, rf_daily: pd.Series | None = None) -> dict:
    nav = nav.dropna()
    ret = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0
    ann_vol = float(ret.std(ddof=1) * math.sqrt(TRADING_DAYS))

    dd, mdd, peak, trough, recovery, recovery_days, longest = max_drawdown_stats(nav)

    if rf_daily is None:
        excess = ret
    else:
        p, rf = ret.align(rf_daily, join="inner")
        excess = p - rf
    sharpe = np.nan
    if len(excess) > 1 and excess.std(ddof=1) > 0:
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS))

    downside = excess[excess < 0]
    sortino = np.nan
    if len(excess) and len(downside):
        downside_dev = math.sqrt(float((downside.pow(2).sum()) / len(excess)))
        if downside_dev > 0:
            sortino = float(excess.mean() / downside_dev * math.sqrt(TRADING_DAYS))

    calmar = np.nan if mdd == 0 else float(cagr / abs(mdd))

    monthly = nav.resample("ME").last().pct_change().dropna()
    monthly_win_rate = float((monthly > 0).mean()) if len(monthly) else np.nan
    avg_win = monthly[monthly > 0].mean()
    avg_loss = monthly[monthly < 0].mean()
    monthly_payoff = np.nan if pd.isna(avg_loss) or avg_loss == 0 else float(avg_win / abs(avg_loss))

    annual = nav.resample("YE").last().pct_change().dropna()
    worst_year = int(annual.idxmin().year) if len(annual) else np.nan
    worst_year_return = float(annual.min()) if len(annual) else np.nan

    return {
        "start_date": nav.index[0].date().isoformat(),
        "end_date": nav.index[-1].date().isoformat(),
        "initial_asset_usd": float(nav.iloc[0]),
        "final_asset_usd": float(nav.iloc[-1]),
        "wealth_multiple": float(nav.iloc[-1] / nav.iloc[0]),
        "cumulative_return": float(nav.iloc[-1] / nav.iloc[0] - 1.0),
        "cagr": float(cagr),
        "annualized_volatility": ann_vol,
        "mdd": mdd,
        "mdd_peak_date": peak.date().isoformat(),
        "mdd_date": trough.date().isoformat(),
        "mdd_recovery_date": recovery.date().isoformat() if pd.notna(recovery) else "",
        "mdd_peak_to_recovery_days": recovery_days,
        "max_time_under_water_days": int(longest),
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "monthly_win_rate": monthly_win_rate,
        "monthly_payoff_ratio": monthly_payoff,
        "worst_year": worst_year,
        "worst_year_return": worst_year_return,
    }


def buy_and_hold_nav(price: pd.Series) -> pd.Series:
    s = price.dropna()
    return INITIAL_CAPITAL * s / float(s.iloc[0])


def save_log2_chart(net_nav: pd.Series, spy_nav: pd.Series):
    fig, ax = plt.subplots(figsize=(12, 6))
    wm = net_nav / net_nav.iloc[0]
    spy_wm = spy_nav / spy_nav.iloc[0]
    ax.plot(wm.index, wm.values, linewidth=1.8, label="5-Asset Portfolio")
    ax.plot(spy_wm.index, spy_wm.values, linewidth=1.2, label="SPY Buy & Hold")
    ax.set_yscale("log", base=2)
    ymax = max(float(wm.max()), float(spy_wm.max()))
    max_pow = max(0, int(math.ceil(math.log(ymax, 2))))
    ticks = [2 ** i for i in range(max_pow + 1)]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{int(t)}x" for t in ticks])
    ax.set_title("5-Asset Portfolio Cumulative Wealth (LOG2)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Wealth Multiple")
    ax.grid(True, which="both", linestyle="--", alpha=0.35)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cumulative_wealth_log2.png", dpi=180)
    plt.close(fig)


def save_drawdown_chart(nav: pd.Series):
    dd = nav / nav.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dd.index, dd.values * 100.0, linewidth=1.4)
    ax.set_title("5-Asset Portfolio Drawdown")
    ax.set_xlabel("Year")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, linestyle="--", alpha=0.35)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "drawdown.png", dpi=180)
    plt.close(fig)


def main():
    prices = load_adj_close()
    returns = prices.pct_change(fill_method=None).fillna(0.0)

    gross = simulate(returns, 0.0)
    net = simulate(returns, ONE_WAY_COST)

    # Risk-free proxy for Sharpe/Sortino: BIL if available in repo; otherwise 0.
    bil_path = DATA_DIR / "BIL.csv"
    rf_daily = None
    if bil_path.exists():
        bil = pd.read_csv(bil_path, parse_dates=["Date"]).set_index("Date")
        bil_adj = pd.to_numeric(bil["Adj Close"], errors="coerce").dropna()
        rf_daily = bil_adj.pct_change().reindex(prices.index).fillna(0.0)

    gross_m = metrics(gross["NAV"], rf_daily)
    net_m = metrics(net["NAV"], rf_daily)
    gross_m["scenario"] = "gross_0bp"
    net_m["scenario"] = "net_5bp_each_side"

    gross_reb = gross.loc[gross["Turnover"] > 0, "Turnover"]
    net_reb = net.loc[net["Turnover"] > 0, "Turnover"]
    gross_m["average_annual_rebalance_turnover"] = float(gross_reb.mean()) if len(gross_reb) else 0.0
    net_m["average_annual_rebalance_turnover"] = float(net_reb.mean()) if len(net_reb) else 0.0
    gross_m["total_transaction_cost_usd"] = 0.0
    net_m["total_transaction_cost_usd"] = float(net["Cost"].sum())
    gross_m["one_way_cost_rate"] = 0.0
    net_m["one_way_cost_rate"] = ONE_WAY_COST

    spy_nav = buy_and_hold_nav(prices["SPY"])
    spy_m = metrics(spy_nav, rf_daily)
    spy_m["scenario"] = "SPY_buy_hold"

    pd.DataFrame([gross_m, net_m]).to_csv(OUT_DIR / "summary.csv", index=False)
    pd.DataFrame([gross_m, net_m, spy_m]).to_csv(OUT_DIR / "comparison.csv", index=False)

    daily = pd.DataFrame({
        "NAV_Gross": gross["NAV"],
        "NAV_Net": net["NAV"],
        "Drawdown_Net": net["NAV"] / net["NAV"].cummax() - 1.0,
        "Turnover": net["Turnover"],
        "Cost": net["Cost"],
    })
    daily.to_csv(OUT_DIR / "daily_nav.csv")

    annual = pd.DataFrame({
        "Gross": gross["NAV"].resample("YE").last().pct_change(),
        "Net": net["NAV"].resample("YE").last().pct_change(),
        "SPY": spy_nav.resample("YE").last().pct_change(),
    }).dropna(how="all")
    annual.index = annual.index.year
    annual.index.name = "Year"
    annual.to_csv(OUT_DIR / "annual_returns.csv")

    chart = pd.DataFrame({
        "WealthMultiple_Net": (net["NAV"] / net["NAV"].iloc[0]).resample("ME").last(),
        "Drawdown_Net": (net["NAV"] / net["NAV"].cummax() - 1.0).resample("ME").min(),
        "SPY_WealthMultiple": (spy_nav / spy_nav.iloc[0]).resample("ME").last(),
    }).dropna(how="all")
    chart.to_csv(OUT_DIR / "chart_monthly.csv")

    save_log2_chart(net["NAV"], spy_nav)
    save_drawdown_chart(net["NAV"])

    print(pd.DataFrame([gross_m, net_m, spy_m]).to_string(index=False))


if __name__ == "__main__":
    main()
