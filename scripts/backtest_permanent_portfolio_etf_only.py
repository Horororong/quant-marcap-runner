from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "etf_us"
PROXY_PATH = ROOT / "data" / "proxy_long" / "derived" / "permanent_portfolio_asset_returns_daily.csv"
OUT_DIR = ROOT / "results" / "permanent_portfolio_etf_only"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = ["SPY", "TLT", "GLD", "BIL"]
TARGET = pd.Series(0.25, index=TICKERS, dtype=float)
INITIAL_CAPITAL = 10_000.0
ONE_WAY_COST = 0.0005  # 5bp per traded notional; ~10bp round trip
TRADING_DAYS = 252


def load_adj_close() -> pd.DataFrame:
    series = {}
    for ticker in TICKERS:
        path = DATA_DIR / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path, parse_dates=["Date"])
        if "Adj Close" not in df.columns:
            raise ValueError(f"Adj Close missing: {ticker}")
        s = pd.to_numeric(df["Adj Close"], errors="coerce")
        s.index = df["Date"]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        series[ticker] = s.rename(ticker)
    prices = pd.concat(series.values(), axis=1, join="inner").dropna()
    if prices.empty:
        raise RuntimeError("No common ETF history")
    if (prices <= 0).any().any():
        raise ValueError("Non-positive adjusted close detected")
    return prices


def first_trading_days(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.year).first().tolist())


def simulate(asset_returns: pd.DataFrame, cost_rate: float) -> pd.DataFrame:
    dates = asset_returns.index
    rebalance_dates = first_trading_days(dates)
    weights = TARGET.copy()
    nav = INITIAL_CAPITAL
    rows = []

    # First common date is the allocation date; no same-close return is claimed.
    rows.append({"Date": dates[0], "NAV": nav, "Return": 0.0, "Turnover": 0.0, "Cost": 0.0, **{f"W_{k}": weights[k] for k in TICKERS}})

    for dt in dates[1:]:
        r = asset_returns.loc[dt]
        port_ret = float((weights * r).sum())
        nav *= (1.0 + port_ret)

        gross_weights = weights * (1.0 + r)
        gross_weights = gross_weights / gross_weights.sum()
        turnover = 0.0
        cost = 0.0

        if dt in rebalance_dates:
            turnover = float(0.5 * (gross_weights - TARGET).abs().sum())
            # sum(abs(delta weights)) = 2 * one-way turnover; cost applies to traded notional.
            traded_notional_fraction = float((gross_weights - TARGET).abs().sum())
            cost = nav * traded_notional_fraction * cost_rate
            nav -= cost
            weights = TARGET.copy()
        else:
            weights = gross_weights

        rows.append({"Date": dt, "NAV": nav, "Return": nav / rows[-1]["NAV"] - 1.0, "Turnover": turnover, "Cost": cost, **{f"W_{k}": weights[k] for k in TICKERS}})

    out = pd.DataFrame(rows).set_index("Date")
    return out


def drawdown_stats(nav: pd.Series):
    peak = nav.cummax()
    dd = nav / peak - 1.0
    mdd_date = dd.idxmin()
    mdd = float(dd.loc[mdd_date])
    peak_date = nav.loc[:mdd_date].idxmax()
    peak_value = float(nav.loc[peak_date])
    future = nav.loc[mdd_date:]
    recovered = future[future >= peak_value]
    recovery_date = recovered.index[0] if len(recovered) else pd.NaT
    recovery_days = (recovery_date - peak_date).days if pd.notna(recovery_date) else np.nan

    # Longest completed time-under-water spell.
    longest = 0
    current_peak_date = nav.index[0]
    current_peak_value = float(nav.iloc[0])
    for dt, value in nav.iloc[1:].items():
        value = float(value)
        if value >= current_peak_value:
            longest = max(longest, (dt - current_peak_date).days)
            current_peak_date = dt
            current_peak_value = value
    if float(nav.iloc[-1]) < current_peak_value:
        longest = max(longest, (nav.index[-1] - current_peak_date).days)
    return dd, mdd, mdd_date, peak_date, recovery_date, recovery_days, longest


def metrics(nav: pd.Series, rf_daily: pd.Series | None = None) -> dict:
    nav = nav.dropna()
    ret = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0
    ann_vol = ret.std(ddof=1) * math.sqrt(TRADING_DAYS)
    dd, mdd, mdd_date, peak_date, recovery_date, recovery_days, longest = drawdown_stats(nav)

    if rf_daily is None:
        excess = ret.copy()
    else:
        excess = ret.align(rf_daily, join="inner")[0] - ret.align(rf_daily, join="inner")[1]
    sharpe = np.nan if excess.std(ddof=1) == 0 else excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS)
    downside = excess[excess < 0]
    downside_dev = math.sqrt((downside.pow(2).sum()) / len(excess)) if len(excess) else np.nan
    sortino = np.nan if not downside_dev or np.isnan(downside_dev) else excess.mean() / downside_dev * math.sqrt(TRADING_DAYS)
    calmar = np.nan if mdd == 0 else cagr / abs(mdd)

    monthly = nav.resample("ME").last().pct_change().dropna()
    monthly_win = float((monthly > 0).mean()) if len(monthly) else np.nan
    avg_win = monthly[monthly > 0].mean()
    avg_loss = monthly[monthly < 0].mean()
    payoff = np.nan if pd.isna(avg_loss) or avg_loss == 0 else float(avg_win / abs(avg_loss))

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
        "annualized_volatility": float(ann_vol),
        "mdd": mdd,
        "mdd_date": mdd_date.date().isoformat(),
        "mdd_peak_date": peak_date.date().isoformat(),
        "mdd_recovery_date": recovery_date.date().isoformat() if pd.notna(recovery_date) else "",
        "mdd_peak_to_recovery_days": recovery_days,
        "max_time_under_water_days": int(longest),
        "sharpe_excess_bil_sqrt252": float(sharpe),
        "sortino_excess_bil_sqrt252": float(sortino),
        "calmar": float(calmar),
        "monthly_win_rate": monthly_win,
        "monthly_payoff_ratio": payoff,
        "worst_year": worst_year,
        "worst_year_return": worst_year_return,
    }


def simulate_proxy_overlap(index: pd.DatetimeIndex) -> pd.DataFrame | None:
    if not PROXY_PATH.exists():
        return None
    p = pd.read_csv(PROXY_PATH, parse_dates=["Date"])
    p = p.set_index("Date").sort_index()
    candidates = {
        "SPY": ["STOCK_RETURN", "StockReturn", "stock_return", "STOCK"],
        "TLT": ["LONG_TREASURY_RETURN", "BondReturn", "bond_return", "LONG_TREASURY"],
        "GLD": ["GOLD_RETURN", "GoldReturn", "gold_return", "GOLD"],
        "BIL": ["TBILL_RETURN", "CashReturn", "cash_return", "TBILL"],
    }
    cols = {}
    for ticker, options in candidates.items():
        hit = next((c for c in options if c in p.columns), None)
        if hit is None:
            return None
        cols[ticker] = hit
    r = p[[cols[t] for t in TICKERS]].copy()
    r.columns = TICKERS
    r = r.reindex(index).dropna()
    if r.empty:
        return None
    return simulate(r, 0.0)


def save_chart(nav: pd.Series, spy_nav: pd.Series, name: str):
    fig, ax = plt.subplots(figsize=(12, 6))
    wm = nav / nav.iloc[0]
    spy_wm = spy_nav / spy_nav.iloc[0]
    ax.plot(wm.index, wm.values, linewidth=1.8, label="Permanent Portfolio")
    ax.plot(spy_wm.index, spy_wm.values, linewidth=1.2, label="SPY Buy & Hold")
    ax.set_yscale("log", base=2)
    ymax = max(float(wm.max()), float(spy_wm.max()))
    max_pow = max(0, int(math.ceil(math.log(ymax, 2))))
    ticks = [2 ** i for i in range(0, max_pow + 1)]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{int(t)}x" for t in ticks])
    ax.set_title("Permanent Portfolio Cumulative Wealth (LOG2)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Wealth Multiple")
    ax.grid(True, which="both", linestyle="--", alpha=0.35)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=180)
    plt.close(fig)


def save_drawdown(nav: pd.Series, name: str):
    dd = nav / nav.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dd.index, dd.values * 100.0, linewidth=1.4)
    ax.set_title("Permanent Portfolio Drawdown")
    ax.set_xlabel("Year")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, linestyle="--", alpha=0.35)
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=180)
    plt.close(fig)


def main():
    prices = load_adj_close()
    returns = prices.pct_change().fillna(0.0)
    rf = returns["BIL"].copy()

    gross = simulate(returns, 0.0)
    net = simulate(returns, ONE_WAY_COST)

    gross_m = metrics(gross["NAV"], rf)
    net_m = metrics(net["NAV"], rf)
    gross_m["scenario"] = "gross_0bp"
    net_m["scenario"] = "net_5bp_each_side"
    gross_m["average_annual_rebalance_turnover"] = float(gross.loc[gross["Turnover"] > 0, "Turnover"].mean())
    net_m["average_annual_rebalance_turnover"] = float(net.loc[net["Turnover"] > 0, "Turnover"].mean())
    gross_m["total_transaction_cost_usd"] = 0.0
    net_m["total_transaction_cost_usd"] = float(net["Cost"].sum())
    gross_m["one_way_cost_rate"] = 0.0
    net_m["one_way_cost_rate"] = ONE_WAY_COST

    pd.DataFrame([gross_m, net_m]).to_csv(OUT_DIR / "summary.csv", index=False, encoding="utf-8-sig")

    combined = pd.DataFrame({
        "NAV_Gross": gross["NAV"],
        "NAV_Net": net["NAV"],
        "Drawdown_Net": net["NAV"] / net["NAV"].cummax() - 1.0,
        "Turnover": net["Turnover"],
        "Cost": net["Cost"],
    })
    combined.to_csv(OUT_DIR / "daily_nav.csv", encoding="utf-8-sig")

    monthly = pd.DataFrame({
        "WealthMultiple_Net": (net["NAV"] / net["NAV"].iloc[0]).resample("ME").last(),
        "Drawdown_Net": (net["NAV"] / net["NAV"].cummax() - 1.0).resample("ME").min(),
    })
    monthly.to_csv(OUT_DIR / "chart_monthly.csv", encoding="utf-8-sig")

    annual = pd.DataFrame({
        "Gross": gross["NAV"].resample("YE").last().pct_change(),
        "Net": net["NAV"].resample("YE").last().pct_change(),
    }).dropna(how="all")
    annual.index = annual.index.year
    annual.index.name = "Year"
    annual.to_csv(OUT_DIR / "annual_returns.csv", encoding="utf-8-sig")

    # SPY benchmark over the exact same common ETF period.
    spy_nav = INITIAL_CAPITAL * prices["SPY"] / prices["SPY"].iloc[0]
    spy_m = metrics(spy_nav, rf)
    spy_m["scenario"] = "SPY_buy_hold"

    # Same-period long-proxy cross-check if the derived asset return file exposes known columns.
    rows = [gross_m, net_m, spy_m]
    proxy_bt = simulate_proxy_overlap(prices.index)
    if proxy_bt is not None:
        proxy_nav = proxy_bt["NAV"].reindex(prices.index).dropna()
        proxy_rf = rf.reindex(proxy_nav.index).fillna(0.0)
        proxy_m = metrics(proxy_nav, proxy_rf)
        proxy_m["scenario"] = "long_proxy_same_period_gross"
        rows.append(proxy_m)
    pd.DataFrame(rows).to_csv(OUT_DIR / "comparison.csv", index=False, encoding="utf-8-sig")

    save_chart(net["NAV"], spy_nav, "cumulative_wealth_log2.png")
    save_drawdown(net["NAV"], "drawdown.png")

    print(pd.DataFrame(rows)[["scenario", "start_date", "end_date", "cagr", "mdd", "sharpe_excess_bil_sqrt252", "sortino_excess_bil_sqrt252", "calmar", "monthly_win_rate", "monthly_payoff_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
