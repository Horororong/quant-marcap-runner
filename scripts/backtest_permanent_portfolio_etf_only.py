from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "etf_us"
RAW_DIR = ROOT / "data" / "proxy_long" / "raw"
OUT_DIR = ROOT / "results" / "permanent_portfolio_etf_only"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = ["SPY", "TLT", "GLD", "BIL"]
TARGET = pd.Series(0.25, index=TICKERS, dtype=float)
INITIAL_CAPITAL = 10_000.0
ONE_WAY_COST = 0.0005  # 5bp per traded notional; ~10bp round trip
TRADING_DAYS = 252


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date")
    return df.set_index("Date")


def load_adj_close() -> pd.DataFrame:
    series = {}
    for ticker in TICKERS:
        df = load_csv(DATA_DIR / f"{ticker}.csv")
        if "Adj Close" not in df.columns:
            raise ValueError(f"Adj Close missing: {ticker}")
        s = pd.to_numeric(df["Adj Close"], errors="coerce").dropna()
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
    weights = TARGET.copy()
    nav = INITIAL_CAPITAL
    rebalance_dates = first_trading_days(dates)
    rows = []
    rows.append({"Date": dates[0], "NAV": nav, "Return": 0.0, "Turnover": 0.0, "Cost": 0.0, **{f"W_{k}": weights[k] for k in TICKERS}})

    for dt in dates[1:]:
        r = asset_returns.loc[dt]
        nav_prev = nav
        nav *= 1.0 + float((weights * r).sum())
        gross_weights = weights * (1.0 + r)
        gross_weights = gross_weights / gross_weights.sum()
        turnover = 0.0
        cost = 0.0

        if dt in rebalance_dates:
            turnover = float(0.5 * (gross_weights - TARGET).abs().sum())
            traded_notional_fraction = float((gross_weights - TARGET).abs().sum())
            cost = nav * traded_notional_fraction * cost_rate
            nav -= cost
            weights = TARGET.copy()
        else:
            weights = gross_weights

        rows.append({"Date": dt, "NAV": nav, "Return": nav / nav_prev - 1.0, "Turnover": turnover, "Cost": cost, **{f"W_{k}": weights[k] for k in TICKERS}})

    return pd.DataFrame(rows).set_index("Date")


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
        p, r = ret.align(rf_daily, join="inner")
        excess = p - r
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


def bond_price_from_yield(yield_decimal: float, coupon_rate: float) -> float:
    n = 40
    r = yield_decimal / 2.0
    c = 100.0 * coupon_rate / 2.0
    if abs(r) < 1e-12:
        return 100.0 + c * n
    discount = 1.0 + r
    coupons = c * (1.0 - discount ** (-n)) / r
    principal = 100.0 * discount ** (-n)
    return coupons + principal


def tbill_return(discount_pct: float, days: int) -> float:
    d = discount_pct / 100.0
    maturity_days = 91.0
    price = 100.0 * (1.0 - d * maturity_days / 360.0)
    hpr = 100.0 / price - 1.0
    return (1.0 + hpr) ** (days / maturity_days) - 1.0


def build_synthetic_proxy_returns(master: pd.DatetimeIndex) -> pd.DataFrame:
    # STOCK: S&P 500 price + Shiller D/12 monthly dividend; intentionally NO SPY overlay.
    sp = load_csv(RAW_DIR / "SP500_PRICE.csv")
    close = pd.to_numeric(sp["Close"], errors="coerce").reindex(master)
    stock = close.pct_change(fill_method=None)
    sh = load_csv(RAW_DIR / "SHILLER_SP500_MONTHLY.csv")
    div = pd.to_numeric(sh["DividendAnnualized"], errors="coerce")
    div_by_month = {d.to_period("M"): float(v) for d, v in div.dropna().items()}
    month_last = pd.Series(master, index=master).groupby(master.to_period("M")).max()
    for period, pay_date in month_last.items():
        if pay_date == master[0] or period not in div_by_month:
            continue
        loc = master.get_loc(pay_date)
        prev_date = master[loc - 1]
        if pd.notna(close.loc[pay_date]) and pd.notna(close.loc[prev_date]):
            stock.loc[pay_date] = (close.loc[pay_date] + div_by_month[period] / 12.0) / close.loc[prev_date] - 1.0
    stock.iloc[0] = 0.0

    # LONG TREASURY: synthetic 20y constant-maturity par bond; intentionally NO TLT overlay.
    def yfile(name: str):
        d = load_csv(RAW_DIR / name)
        return pd.to_numeric(d["Value"], errors="coerce").reindex(master)

    y20, y10, y30 = yfile("US_20Y_YIELD.csv"), yfile("US_10Y_YIELD.csv"), yfile("US_30Y_YIELD.csv")
    gap = (master >= pd.Timestamp("1987-01-01")) & (master <= pd.Timestamp("1993-09-30"))
    est = (y10 + y30) / 2.0
    y20.loc[gap & y20.isna()] = est.loc[gap & y20.isna()]
    y20 = y20.ffill(limit=10)
    y = y20 / 100.0
    bond = pd.Series(index=master, dtype=float)
    bond.iloc[0] = 0.0
    for i in range(1, len(master)):
        if pd.isna(y.iloc[i - 1]) or pd.isna(y.iloc[i]):
            continue
        prev, cur = master[i - 1], master[i]
        yp, yc = float(y.iloc[i - 1]), float(y.iloc[i])
        price = bond_price_from_yield(yc, yp)
        accrued = 100.0 * yp * (cur - prev).days / 365.25
        bond.iloc[i] = (price + accrued) / 100.0 - 1.0

    # GOLD: LBMA PM USD; intentionally NO GLD overlay.
    gold_df = load_csv(RAW_DIR / "GOLD_LBMA_PM_USD.csv")
    gold_close = pd.to_numeric(gold_df["Close"], errors="coerce").reindex(master).ffill(limit=10)
    gold = gold_close.pct_change(fill_method=None)
    gold.iloc[0] = 0.0

    # CASH: 3m T-bill bank-discount proxy; intentionally NO BIL overlay.
    tb = load_csv(RAW_DIR / "US_3M_TBILL.csv")
    raw = pd.to_numeric(tb["Value"], errors="coerce").reindex(master).ffill(limit=10)
    cash = pd.Series(index=master, dtype=float)
    cash.iloc[0] = 0.0
    for i in range(1, len(master)):
        if pd.isna(raw.iloc[i - 1]):
            continue
        cash.iloc[i] = tbill_return(float(raw.iloc[i - 1]), (master[i] - master[i - 1]).days)

    out = pd.concat([stock.rename("SPY"), bond.rename("TLT"), gold.rename("GLD"), cash.rename("BIL")], axis=1)
    valid = out.notna().all(axis=1)
    if not valid.any():
        raise RuntimeError("No valid synthetic-proxy overlap")
    last_valid = valid[valid].index[-1]
    out = out.loc[:last_valid]
    if out.isna().any().any():
        bad = out[out.isna().any(axis=1)].index[:5].strftime("%Y-%m-%d").tolist()
        raise RuntimeError(f"Synthetic proxy has internal gaps: {bad}")
    return out


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

    spy_nav = INITIAL_CAPITAL * prices["SPY"] / prices["SPY"].iloc[0]
    spy_m = metrics(spy_nav, rf)
    spy_m["scenario"] = "SPY_buy_hold"
    rows = [gross_m, net_m, spy_m]
    pd.DataFrame(rows).to_csv(OUT_DIR / "comparison.csv", index=False, encoding="utf-8-sig")

    # Independent validation: compare raw synthetic proxies against actual ETFs,
    # explicitly WITHOUT the ETF overlays used by the 1970 long-history series.
    synth = build_synthetic_proxy_returns(prices.index)
    common = synth.index.intersection(returns.index)
    synth = synth.reindex(common)
    etf_same = returns.reindex(common)
    etf_same.iloc[0] = 0.0
    synth.iloc[0] = 0.0

    etf_bt = simulate(etf_same, 0.0)
    synth_bt = simulate(synth, 0.0)
    rf_same = etf_same["BIL"]
    etf_same_m = metrics(etf_bt["NAV"], rf_same)
    synth_same_m = metrics(synth_bt["NAV"], rf_same)
    etf_same_m["scenario"] = "actual_ETFs_same_proxy_window"
    synth_same_m["scenario"] = "synthetic_proxies_no_ETF_overlay"
    pd.DataFrame([etf_same_m, synth_same_m]).to_csv(OUT_DIR / "proxy_validation_summary.csv", index=False, encoding="utf-8-sig")

    asset_rows = []
    for t in TICKERS:
        a = etf_same[t].iloc[1:]
        b = synth[t].iloc[1:]
        pair = pd.concat([a.rename("ETF"), b.rename("Proxy")], axis=1).dropna()
        diff = pair["Proxy"] - pair["ETF"]
        asset_rows.append({
            "ticker": t,
            "start_date": pair.index[0].date().isoformat(),
            "end_date": pair.index[-1].date().isoformat(),
            "daily_return_correlation": float(pair.corr().iloc[0, 1]),
            "annualized_tracking_error_proxy_minus_etf": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS)),
            "mean_annualized_return_gap_proxy_minus_etf": float(diff.mean() * TRADING_DAYS),
        })
    pd.DataFrame(asset_rows).to_csv(OUT_DIR / "proxy_validation_assets.csv", index=False, encoding="utf-8-sig")

    save_chart(net["NAV"], spy_nav, "cumulative_wealth_log2.png")
    save_drawdown(net["NAV"], "drawdown.png")

    print(pd.DataFrame(rows)[["scenario", "start_date", "end_date", "cagr", "mdd", "sharpe_excess_bil_sqrt252", "sortino_excess_bil_sqrt252", "calmar", "monthly_win_rate", "monthly_payoff_ratio"]].to_string(index=False))
    print("\nIndependent proxy validation")
    print(pd.DataFrame([etf_same_m, synth_same_m])[["scenario", "start_date", "end_date", "cagr", "mdd", "annualized_volatility"]].to_string(index=False))


if __name__ == "__main__":
    main()
