from pathlib import Path
import math

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "proxy_long" / "raw"
ETF = ROOT / "data" / "etf_us"
DERIVED = ROOT / "data" / "proxy_long" / "derived"
RESULTS = ROOT / "results" / "permanent_portfolio_long"

START_DATE = pd.Timestamp("1970-01-02")
END_DATE = pd.Timestamp("2026-08-19")
INITIAL_CAPITAL = 10_000.0
TARGET_WEIGHT = 0.25
TRADING_COST_RATE = 0.0  # baseline requested result: gross of trading costs

ASSETS = ["STOCK", "LONG_TREASURY", "GOLD", "TBILL"]


def load_csv(path: Path, date_col="Date") -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise RuntimeError(f"Missing {date_col} in {path}")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col).drop_duplicates(date_col)
    return df.set_index(date_col)


def load_etf_adj_close(ticker: str) -> pd.Series:
    df = load_csv(ETF / f"{ticker}.csv")
    if "Adj Close" not in df.columns:
        raise RuntimeError(f"Adj Close missing for {ticker}")
    s = pd.to_numeric(df["Adj Close"], errors="coerce").dropna()
    if s.empty:
        raise RuntimeError(f"No valid Adj Close for {ticker}")
    return s


def build_master_calendar() -> pd.DatetimeIndex:
    sp = load_csv(RAW / "SP500_PRICE.csv")
    if "Close" not in sp.columns:
        raise RuntimeError("SP500_PRICE.csv missing Close")
    idx = sp.loc[START_DATE:END_DATE].index
    if len(idx) == 0 or idx[0] != START_DATE:
        raise RuntimeError(f"S&P calendar does not start at {START_DATE.date()}")
    if idx[-1] != END_DATE:
        raise RuntimeError(
            f"S&P calendar ends {idx[-1].date()}, expected {END_DATE.date()}"
        )
    return idx


def build_stock_proxy(master: pd.DatetimeIndex) -> pd.Series:
    """S&P 500 daily price return + Shiller monthly dividend cash, then SPY Adj Close."""
    sp = load_csv(RAW / "SP500_PRICE.csv")
    close = pd.to_numeric(sp["Close"], errors="coerce").reindex(master)
    if close.isna().any():
        raise RuntimeError("Missing S&P 500 closes on master calendar")

    sh = load_csv(RAW / "SHILLER_SP500_MONTHLY.csv")
    div = pd.to_numeric(sh["DividendAnnualized"], errors="coerce")
    div_by_month = {d.to_period("M"): v for d, v in div.dropna().items()}

    ret = close.pct_change()
    # Shiller D is a 12-month dividend total interpolated monthly; D/12 is the
    # approximate dividend cash for the month. Credit it on the last US trading
    # day of each month so daily price movements remain observable for MDD.
    month_last = pd.Series(master, index=master).groupby(master.to_period("M")).max()
    for period, pay_date in month_last.items():
        if pay_date == master[0] or period not in div_by_month:
            continue
        prev_date = master[master.get_loc(pay_date) - 1]
        dividend_cash = float(div_by_month[period]) / 12.0
        ret.loc[pay_date] = (close.loc[pay_date] + dividend_cash) / close.loc[prev_date] - 1.0

    spy = load_etf_adj_close("SPY")
    spy_ret = spy.pct_change().reindex(master)
    use = spy_ret.notna()
    ret.loc[use] = spy_ret.loc[use]
    ret.iloc[0] = 0.0
    return ret.rename("STOCK")


def load_yield(name: str, master: pd.DatetimeIndex) -> pd.Series:
    df = load_csv(RAW / name)
    return pd.to_numeric(df["Value"], errors="coerce").reindex(master)


def bond_price_from_yield(yield_decimal: float, coupon_rate: float) -> float:
    """Price a par-style 20y nominal bond with semiannual coupons, face=100."""
    n = 40
    r = yield_decimal / 2.0
    c = 100.0 * coupon_rate / 2.0
    if abs(r) < 1e-12:
        return 100.0 + c * n
    discount = 1.0 + r
    coupons = c * (1.0 - discount ** (-n)) / r
    principal = 100.0 * discount ** (-n)
    return coupons + principal


def build_long_treasury_proxy(master: pd.DatetimeIndex) -> pd.Series:
    y20 = load_yield("US_20Y_YIELD.csv", master)
    y10 = load_yield("US_10Y_YIELD.csv", master)
    y30 = load_yield("US_30Y_YIELD.csv", master)

    gap = (master >= pd.Timestamp("1987-01-01")) & (master <= pd.Timestamp("1993-09-30"))
    estimated = (y10 + y30) / 2.0
    y20.loc[gap & y20.isna()] = estimated.loc[gap & y20.isna()]

    # Normal market holidays/missing observations use the last available yield.
    # A hard cap prevents silently bridging another long historical gap.
    y20 = y20.ffill(limit=10)
    if y20.isna().any():
        missing = y20[y20.isna()].index[:5].strftime("%Y-%m-%d").tolist()
        raise RuntimeError(f"Unresolved 20Y yield gaps, examples: {missing}")

    y = y20 / 100.0
    ret = pd.Series(index=master, dtype=float, name="LONG_TREASURY")
    ret.iloc[0] = 0.0
    for i in range(1, len(master)):
        prev = master[i - 1]
        cur = master[i]
        y_prev = float(y.loc[prev])
        y_cur = float(y.loc[cur])
        # Constant-maturity approximation: yesterday's 20y par bond is repriced
        # at today's 20y yield; accrued coupon is included; then the sleeve rolls
        # back to a fresh 20y par exposure for the next interval.
        price = bond_price_from_yield(y_cur, y_prev)
        days = (cur - prev).days
        accrued_coupon = 100.0 * y_prev * days / 365.25
        ret.loc[cur] = (price + accrued_coupon) / 100.0 - 1.0

    tlt = load_etf_adj_close("TLT")
    tlt_ret = tlt.pct_change().reindex(master)
    use = tlt_ret.notna()
    ret.loc[use] = tlt_ret.loc[use]
    return ret


def build_gold_proxy(master: pd.DatetimeIndex) -> pd.Series:
    gold = load_csv(RAW / "GOLD_LBMA_PM_USD.csv")
    close = pd.to_numeric(gold["Close"], errors="coerce").reindex(master).ffill(limit=10)
    ret = close.pct_change(fill_method=None).rename("GOLD")

    # GLD is the investable series once it exists. Apply the ETF handoff first,
    # then validate gaps. This avoids falsely failing because the auxiliary
    # LBMA file may stop updating after GLD is already available.
    gld = load_etf_adj_close("GLD")
    gld_ret = gld.pct_change().reindex(master)
    use = gld_ret.notna()
    ret.loc[use] = gld_ret.loc[use]
    ret.iloc[0] = 0.0

    if ret.isna().any():
        missing = ret[ret.isna()].index[:5].strftime("%Y-%m-%d").tolist()
        raise RuntimeError(f"Unresolved gold proxy gaps, examples: {missing}")
    return ret


def tbill_daily_return_from_discount_rate(discount_pct: float, days: int) -> float:
    """Convert 3m T-bill bank-discount quote to an approximate holding return."""
    d = discount_pct / 100.0
    maturity_days = 91.0
    price = 100.0 * (1.0 - d * maturity_days / 360.0)
    if price <= 0:
        raise RuntimeError(f"Invalid T-bill price from discount rate {discount_pct}")
    hpr_91d = 100.0 / price - 1.0
    return (1.0 + hpr_91d) ** (days / maturity_days) - 1.0


def build_tbill_proxy(master: pd.DatetimeIndex):
    raw = load_yield("US_3M_TBILL.csv", master).ffill(limit=10)
    if raw.isna().any():
        raise RuntimeError("Unresolved 3M T-bill gaps on master calendar")

    proxy_ret = pd.Series(index=master, dtype=float, name="TBILL")
    proxy_ret.iloc[0] = 0.0
    for i in range(1, len(master)):
        days = (master[i] - master[i - 1]).days
        proxy_ret.iloc[i] = tbill_daily_return_from_discount_rate(float(raw.iloc[i - 1]), days)

    # Keep the pure T-bill rate proxy separately for Sharpe risk-free returns.
    rf_ret = proxy_ret.copy().rename("RF_RETURN")

    bil = load_etf_adj_close("BIL")
    bil_ret = bil.pct_change().reindex(master)
    use = bil_ret.notna()
    proxy_ret.loc[use] = bil_ret.loc[use]
    return proxy_ret, rf_ret


def build_asset_returns(master: pd.DatetimeIndex) -> pd.DataFrame:
    stock = build_stock_proxy(master)
    bond = build_long_treasury_proxy(master)
    gold = build_gold_proxy(master)
    cash, rf = build_tbill_proxy(master)
    out = pd.concat([stock, bond, gold, cash, rf], axis=1)
    if out[ASSETS + ["RF_RETURN"]].isna().any().any():
        raise RuntimeError("Final asset-return panel contains missing values")
    return out


def backtest(returns: pd.DataFrame):
    dates = returns.index
    sleeves = pd.Series(INITIAL_CAPITAL * TARGET_WEIGHT, index=ASSETS, dtype=float)
    nav = pd.Series(index=dates, dtype=float)
    nav.iloc[0] = INITIAL_CAPITAL
    turnovers = []

    for i in range(1, len(dates)):
        sleeves *= (1.0 + returns.loc[dates[i], ASSETS])
        nav_before_rebalance = float(sleeves.sum())

        # Annual rebalance at the CLOSE of the first US trading day of the year.
        # The new 25/25/25/25 weights therefore become effective the next day.
        if dates[i].year != dates[i - 1].year:
            target = pd.Series(nav_before_rebalance * TARGET_WEIGHT, index=ASSETS)
            traded = float((target - sleeves).abs().sum())
            turnover = traded / nav_before_rebalance
            cost = traded * TRADING_COST_RATE
            sleeves = target
            if cost:
                sleeves *= (nav_before_rebalance - cost) / nav_before_rebalance
            turnovers.append((dates[i], turnover, cost))

        nav.iloc[i] = float(sleeves.sum())

    portfolio_ret = nav.pct_change().fillna(0.0)
    return nav, portfolio_ret, turnovers


def metrics(nav: pd.Series, portfolio_ret: pd.Series, rf_ret: pd.Series, turnovers):
    start = nav.index[0]
    end = nav.index[-1]
    years = (end - start).days / 365.2425
    final = float(nav.iloc[-1])
    cagr = (final / float(nav.iloc[0])) ** (1.0 / years) - 1.0

    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    mdd = float(drawdown.min())
    mdd_date = drawdown.idxmin()

    excess = (portfolio_ret - rf_ret).iloc[1:]
    sharpe = np.nan
    if excess.std(ddof=1) > 0:
        sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(252.0))

    ann_vol = float(portfolio_ret.iloc[1:].std(ddof=1) * math.sqrt(252.0))
    avg_turnover = float(np.mean([x[1] for x in turnovers])) if turnovers else 0.0

    return {
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "initial_asset_usd": float(nav.iloc[0]),
        "final_asset_usd": final,
        "cagr": cagr,
        "mdd": mdd,
        "mdd_date": mdd_date.date().isoformat(),
        "sharpe_excess_dtb3_sqrt252": sharpe,
        "annualized_volatility": ann_vol,
        "average_annual_rebalance_turnover": avg_turnover,
        "transaction_cost_rate": TRADING_COST_RATE,
        "rebalance_rule": "first US trading day close each year; effective next trading day",
        "stock_proxy": "S&P500 price + Shiller D/12 monthly dividend until SPY Adj Close available",
        "bond_proxy": "synthetic 20Y constant-maturity par bond until TLT Adj Close available",
        "gold_proxy": "LBMA PM USD until GLD Adj Close available",
        "cash_proxy": "DTB3 accrued return until BIL Adj Close available",
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    master = build_master_calendar()
    returns = build_asset_returns(master)
    returns.to_csv(DERIVED / "permanent_portfolio_asset_returns_daily.csv", encoding="utf-8-sig")

    nav, port_ret, turnovers = backtest(returns)
    drawdown = nav / nav.cummax() - 1.0
    daily = pd.DataFrame({
        "NAV": nav,
        "PortfolioReturn": port_ret,
        "Drawdown": drawdown,
        "RiskFreeReturn_DTB3": returns["RF_RETURN"],
    })
    daily.to_csv(RESULTS / "daily_nav.csv", encoding="utf-8-sig")

    summary = metrics(nav, port_ret, returns["RF_RETURN"], turnovers)
    pd.DataFrame([summary]).to_csv(RESULTS / "summary.csv", index=False, encoding="utf-8-sig")

    # Calendar-year return must compound every daily return in the year. Using
    # last NAV / first NAV omits the first trading day's return for years after 1970.
    annual = nav.groupby(nav.index.year).agg(["first", "last"])
    annual["return"] = (1.0 + port_ret).groupby(port_ret.index.year).prod() - 1.0
    annual.index.name = "Year"
    annual.to_csv(RESULTS / "annual_returns.csv", encoding="utf-8-sig")

    print("=== Permanent Portfolio Long Backtest ===")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
