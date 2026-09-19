from __future__ import annotations

from pathlib import Path
import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "strategy7"
RAW = ROOT / "data" / "proxy_long" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

TITLE = "Strategy 7 - KOSPI absolute momentum"
INITIAL_CAPITAL = 10_000_000.0
RF_ANNUAL = 0.0
BOOK_START = pd.Timestamp("1987-01-31")
BOOK_END = pd.Timestamp("2021-12-31")
STANDARD_2001 = pd.Timestamp("2001-01-31")
STANDARD_2021 = pd.Timestamp("2021-01-31")
MAIN_SWITCH_COST = 0.0010   # total cost per full regime switch (10 bp)
CONSERVATIVE_SWITCH_COST = 0.0020  # 20 bp
INITIAL_ENTRY_COST = 0.0005  # 5 bp one-way initial entry
FRED_HOUSING_5Y = "IRLOHO01KRM156N"
FRED_GOVT_GENERIC = "INTGSBKRM193N"

RUN_AT = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
LAST_COMPLETE_MONTH = (RUN_AT.to_period("M") - 1).to_timestamp("M")


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def fred_download(series_id: str, out_name: str) -> pd.DataFrame:
    """Load a verified cached FRED series first; refresh only if absent."""
    p = RAW / out_name
    if p.exists():
        cached = pd.read_csv(p, encoding="utf-8-sig")
        if {"Date", "Value"}.issubset(cached.columns):
            cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce")
            cached["Value"] = pd.to_numeric(cached["Value"], errors="coerce")
            cached = cached.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date")
            if cached["Value"].notna().sum() >= 12:
                return cached

    headers = {"User-Agent": "Mozilla/5.0 quant-research-backtest/1.0"}
    last_exc = None

    # 1) Static table page: parse DATE/VALUE rows from the HTML table.
    static_url = f"https://fred.stlouisfed.org/data/{series_id}"
    try:
        r = requests.get(static_url, timeout=(15, 75), headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        for tr in soup.find_all("tr"):
            cells = [x.get_text(" ", strip=True) for x in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            dt = pd.to_datetime(cells[0], errors="coerce")
            val = pd.to_numeric(cells[1], errors="coerce")
            if pd.notna(dt) and pd.notna(val):
                rows.append((dt, float(val)))
        if len(rows) >= 12:
            df = pd.DataFrame(rows, columns=["Date", "Value"])
            df = df.sort_values("Date").drop_duplicates("Date")
            p = RAW / out_name
            df.to_csv(p, index=False, encoding="utf-8-sig")
            return df
    except Exception as exc:
        last_exc = exc

    # 2) Fallback: graph CSV with a constrained date range and retries.
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd=1986-12-01&coed={LAST_COMPLETE_MONTH.date()}"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=(15, 90), headers=headers)
            r.raise_for_status()
            p = RAW / out_name
            p.write_bytes(r.content)
            df = pd.read_csv(p)
            if df.shape[1] < 2:
                raise RuntimeError(f"Unexpected FRED payload for {series_id}")
            df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Value"})
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date")
            if df["Value"].notna().sum() < 12:
                raise RuntimeError(f"Insufficient FRED observations for {series_id}")
            return df
        except Exception as exc:
            last_exc = exc
            time.sleep(4 * (attempt + 1))

    raise RuntimeError(f"FRED download failed after static+CSV attempts: {series_id}") from last_exc


def month_end_series_from_daily(df: pd.DataFrame, value_col: str) -> pd.Series:
    x = df.copy()
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    x[value_col] = pd.to_numeric(x[value_col], errors="coerce")
    x = x.dropna(subset=["Date", value_col]).sort_values("Date")
    x = x[x["Date"] <= LAST_COMPLETE_MONTH]
    s = x.set_index("Date")[value_col]
    m = s.groupby(s.index.to_period("M")).last()
    m.index = m.index.to_timestamp("M")
    return m.astype(float)


def build_kospi_monthly_long() -> tuple[pd.Series, dict]:
    kospi = load_csv(ROOT / "data" / "indices" / "KOSPI.csv")
    exact = month_end_series_from_daily(kospi, "Close")

    oecd = load_csv(ROOT / "data" / "proxy_long" / "raw" / "OECD_KR_SHARE_PRICE_MONTHLY.csv")
    oecd["Date"] = pd.to_datetime(oecd.iloc[:, 0], errors="coerce")
    oecd["Value"] = pd.to_numeric(oecd.iloc[:, 1], errors="coerce")
    oecd = oecd.dropna(subset=["Date", "Value"]).sort_values("Date")
    oecd_s = oecd.set_index("Date")["Value"]
    oecd_s.index = oecd_s.index.to_period("M").to_timestamp("M")

    overlap = oecd_s.index.intersection(exact.index)
    if len(overlap) < 12:
        raise RuntimeError("Insufficient OECD/KOSPI overlap")
    corr = float(oecd_s.loc[overlap].pct_change().corr(exact.loc[overlap].pct_change()))

    splice_month = exact.index.min()
    if splice_month not in oecd_s.index:
        nearest = oecd_s.index[oecd_s.index <= splice_month]
        if len(nearest) == 0:
            raise RuntimeError("No OECD value available for KOSPI splice")
        ref_month = nearest[-1]
        # scale using the first exact month and nearest OECD month, preserving OECD return path
        scale = exact.loc[splice_month] / oecd_s.loc[ref_month]
    else:
        ref_month = splice_month
        scale = exact.loc[splice_month] / oecd_s.loc[splice_month]

    pre = oecd_s[oecd_s.index < splice_month] * scale
    long_s = pd.concat([pre, exact]).sort_index()
    long_s = long_s[~long_s.index.duplicated(keep="last")]
    long_s = long_s.loc[:"%04d-%02d-%02d" % (LAST_COMPLETE_MONTH.year, LAST_COMPLETE_MONTH.month, LAST_COMPLETE_MONTH.day)]

    diag = {
        "exact_start": str(exact.index.min().date()),
        "exact_end": str(exact.index.max().date()),
        "oecd_start": str(oecd_s.index.min().date()),
        "oecd_end": str(oecd_s.index.max().date()),
        "splice_month": str(splice_month.date()),
        "oecd_exact_overlap_monthly_return_corr": corr,
    }
    return long_s, diag


def par_bond_5y_one_month_return(y0_pct: float, y1_pct: float) -> float:
    """Approximate one-month total return of a rolling 5y par bond.

    At t0, buy a 5y semiannual-coupon bond at par with coupon=y0.
    One month later reprice the same cash flows at y1 with 59 months remaining.
    Dirty-price change captures carry + yield move. This is a documented proxy,
    not an exact Korean 5y total-return index.
    """
    y0 = float(y0_pct) / 100.0
    y1 = float(y1_pct) / 100.0
    if not np.isfinite(y0) or not np.isfinite(y1) or y0 <= -0.95 or y1 <= -0.95:
        return np.nan
    freq = 2
    face = 100.0
    coupon = face * y0 / freq
    t0_times = np.arange(1, 5 * freq + 1, dtype=float) / freq
    cash = np.full(len(t0_times), coupon, dtype=float)
    cash[-1] += face

    # t0 price should be par (allow floating-point noise)
    p0 = np.sum(cash / (1.0 + y0 / freq) ** (freq * t0_times))
    t1_times = t0_times - 1.0 / 12.0
    p1 = np.sum(cash / (1.0 + y1 / freq) ** (freq * t1_times))
    return float(p1 / p0 - 1.0)


def build_bond_monthly_proxy() -> tuple[pd.Series, pd.Series, dict]:
    housing = fred_download(FRED_HOUSING_5Y, "KR_HOUSING_BOND_5Y_YIELD.csv")

    h = housing.dropna(subset=["Value"]).copy()
    h["Month"] = h["Date"].dt.to_period("M").dt.to_timestamp("M")
    hy = h.groupby("Month")["Value"].last().sort_index()
    syn_ret = pd.Series(index=hy.index, dtype=float)
    for i in range(1, len(hy)):
        syn_ret.iloc[i] = par_bond_5y_one_month_return(hy.iloc[i - 1], hy.iloc[i])
    syn_ret.name = "synthetic_5y_housing_bond"

    etf = load_csv(ROOT / "data" / "etf_kr" / "302190_TIGER중장기국채.csv")
    etf_m = month_end_series_from_daily(etf, "Adj Close")
    etf_ret = etf_m.pct_change()
    etf_ret.name = "tiger_3_10y_govt"

    # Main practical proxy: historical 5y housing-bond synthetic until the ETF
    # has a full prior month, then investable 3-10y government-bond ETF.
    first_etf_ret = etf_ret.first_valid_index()
    if first_etf_ret is None:
        raise RuntimeError("No valid ETF bond return")
    # Reindex to the union before assignment so the ETF extends the proxy
    # beyond the historical housing-bond-yield series endpoint.
    main = syn_ret.reindex(syn_ret.index.union(etf_ret.index)).sort_index()
    etf_idx = etf_ret.index[etf_ret.index >= first_etf_ret]
    main.loc[etf_idx] = etf_ret.loc[etf_idx]
    main = main.sort_index()
    main.name = "bond_main_proxy"

    overlap = syn_ret.dropna().index.intersection(etf_ret.dropna().index)
    overlap = overlap[(overlap >= pd.Timestamp("2018-08-31")) & (overlap <= pd.Timestamp("2023-12-31"))]
    if len(overlap) > 6:
        corr = float(syn_ret.loc[overlap].corr(etf_ret.loc[overlap]))
        syn_vol = float(syn_ret.loc[overlap].std(ddof=1) * np.sqrt(12))
        etf_vol = float(etf_ret.loc[overlap].std(ddof=1) * np.sqrt(12))
        mean_diff = float((syn_ret.loc[overlap] - etf_ret.loc[overlap]).mean() * 12)
    else:
        corr = syn_vol = etf_vol = mean_diff = np.nan

    diag = {
        "housing_yield_start": str(hy.index.min().date()),
        "housing_yield_end": str(hy.index.max().date()),
        "etf_start": str(etf_m.index.min().date()),
        "etf_end": str(etf_m.index.max().date()),
        "main_proxy_etf_return_start": str(first_etf_ret.date()),
        "overlap_months": int(len(overlap)),
        "synthetic_vs_etf_return_corr": corr,
        "synthetic_annualized_vol": syn_vol,
        "etf_annualized_vol": etf_vol,
        "synthetic_minus_etf_ann_mean_return": mean_diff,
        "generic_govt_yield_start": None,
        "generic_govt_yield_end": None,
    }
    return main, syn_ret, diag


def prepare_daily_assets() -> pd.DataFrame:
    k = load_csv(ROOT / "data" / "indices" / "KOSPI.csv")
    b = load_csv(ROOT / "data" / "etf_kr" / "302190_TIGER중장기국채.csv")
    for df in (k, b):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.sort_values("Date", inplace=True)
    k["Close"] = pd.to_numeric(k["Close"], errors="coerce")
    k["Open"] = pd.to_numeric(k["Open"], errors="coerce")
    for c in ["Open", "Close", "Adj Close"]:
        b[c] = pd.to_numeric(b[c], errors="coerce")
    b["AdjFactor"] = b["Adj Close"] / b["Close"]
    b["AdjOpen"] = b["Open"] * b["AdjFactor"]

    kd = k.set_index("Date")[["Open", "Close"]].rename(columns={"Open": "KOpen", "Close": "KClose"})
    bd = b.set_index("Date")[["AdjOpen", "Adj Close"]].rename(columns={"Adj Close": "BAdjClose"})
    d = kd.join(bd, how="inner").dropna()
    d = d[d.index <= LAST_COMPLETE_MONTH]
    return d


def daily_strategy_returns(daily: pd.DataFrame, monthly_position: pd.Series, switch_cost: float) -> pd.DataFrame:
    d = daily.copy()
    month_map = monthly_position.copy()
    month_map.index = month_map.index.to_period("M")

    periods = d.index.to_period("M")
    d["Pos"] = [month_map.get(p, np.nan) for p in periods]
    d = d.dropna(subset=["Pos"]).copy()
    d["Pos"] = d["Pos"].astype(bool)

    prev_kclose = d["KClose"].shift(1)
    prev_bclose = d["BAdjClose"].shift(1)
    stock_cc = d["KClose"] / prev_kclose - 1.0
    bond_cc = d["BAdjClose"] / prev_bclose - 1.0
    stock_overnight = d["KOpen"] / prev_kclose - 1.0
    bond_overnight = d["AdjOpen"] / prev_bclose - 1.0
    stock_intraday = d["KClose"] / d["KOpen"] - 1.0
    bond_intraday = d["BAdjClose"] / d["AdjOpen"] - 1.0

    pos = d["Pos"]
    prev_pos = pos.shift(1)
    prev_pos_bool = prev_pos.fillna(False).astype(bool)
    switch = (pos != prev_pos) & prev_pos.notna()

    gross = pd.Series(np.nan, index=d.index, dtype=float)
    same_stock = (~switch) & pos
    same_bond = (~switch) & (~pos)
    gross.loc[same_stock] = stock_cc.loc[same_stock]
    gross.loc[same_bond] = bond_cc.loc[same_bond]

    s2b = switch & (~pos) & prev_pos_bool
    b2s = switch & pos & (~prev_pos_bool)
    gross.loc[s2b] = (1.0 + stock_overnight.loc[s2b]) * (1.0 + bond_intraday.loc[s2b]) - 1.0
    gross.loc[b2s] = (1.0 + bond_overnight.loc[b2s]) * (1.0 + stock_intraday.loc[b2s]) - 1.0

    net = gross.copy()
    net.loc[switch & net.notna()] = (1.0 + net.loc[switch & net.notna()]) * (1.0 - switch_cost) - 1.0
    benchmark = stock_cc

    out = pd.DataFrame({"StrategyGross": gross, "StrategyNet": net, "KOSPI": benchmark, "PositionStock": pos.astype(int)})
    return out.dropna(subset=["StrategyGross", "StrategyNet", "KOSPI"])


def apply_monthly_cost(ret: pd.Series, position: pd.Series, switch_cost: float) -> pd.Series:
    x = ret.copy()
    p = position.reindex(x.index)
    switch = p.ne(p.shift(1)) & p.shift(1).notna()
    x.loc[switch] = (1.0 + x.loc[switch]) * (1.0 - switch_cost) - 1.0
    first = x.first_valid_index()
    if first is not None:
        x.loc[first] = (1.0 + x.loc[first]) * (1.0 - INITIAL_ENTRY_COST) - 1.0
    return x


def build_strategy_returns(kospi_price: pd.Series, bond_main: pd.Series, bond_syn: pd.Series):
    idx = kospi_price.index
    sma10 = kospi_price.rolling(10, min_periods=10).mean()
    signal = (kospi_price >= sma10)
    position = signal.shift(1)  # prior month-end signal drives current month holdings
    equity_ret = kospi_price.pct_change()

    aligned = pd.DataFrame({
        "KPrice": kospi_price,
        "EquityRet": equity_ret,
        "BondMain": bond_main.reindex(idx),
        "BondSynthetic": bond_syn.reindex(idx),
        "SignalAtMonthEnd": signal.astype(float),
        "PositionStock": position.astype(float),
    })

    gross_main = pd.Series(np.where(position == 1.0, equity_ret, aligned["BondMain"]), index=idx, dtype=float)
    gross_book = pd.Series(np.where(position == 1.0, equity_ret, aligned["BondSynthetic"]), index=idx, dtype=float)

    # Daily exact-ish execution is available once the investable bond ETF exists.
    daily_assets = prepare_daily_assets()
    daily_gross = daily_strategy_returns(daily_assets, position, 0.0)
    daily_net10 = daily_strategy_returns(daily_assets, position, MAIN_SWITCH_COST)
    daily_net20 = daily_strategy_returns(daily_assets, position, CONSERVATIVE_SWITCH_COST)

    # Aggregate complete daily months and replace monthly main-proxy returns.
    def monthly_compound(s: pd.Series) -> pd.Series:
        m = (1.0 + s).groupby(s.index.to_period("M")).prod() - 1.0
        m.index = m.index.to_timestamp("M")
        return m

    dg_m = monthly_compound(daily_gross["StrategyGross"])
    dn10_m = monthly_compound(daily_net10["StrategyNet"])
    dn20_m = monthly_compound(daily_net20["StrategyNet"])

    # Use only full months after ETF inception; August 2018 is first full month.
    daily_full_start = pd.Timestamp("2018-08-31")
    replace_idx = dg_m.index[dg_m.index >= daily_full_start]
    gross_main.loc[replace_idx] = dg_m.loc[replace_idx]

    net10 = apply_monthly_cost(gross_main, position, MAIN_SWITCH_COST)
    net20 = apply_monthly_cost(gross_main, position, CONSERVATIVE_SWITCH_COST)
    # Replace ETF-era net returns with split-day daily execution.
    repl10 = dn10_m.index[dn10_m.index >= daily_full_start]
    repl20 = dn20_m.index[dn20_m.index >= daily_full_start]
    net10.loc[repl10] = dn10_m.loc[repl10]
    net20.loc[repl20] = dn20_m.loc[repl20]

    out = pd.DataFrame({
        "StrategyGross": gross_main,
        "StrategyNet10bp": net10,
        "StrategyNet20bp": net20,
        "BookProxyGross": gross_book,
        "KOSPI": equity_ret,
        "PositionStock": position,
    })

    # Valid strategy months require selected asset return. KOSPI benchmark is retained.
    return out, daily_gross, daily_net10, daily_net20, aligned


def nav_from_returns(ret: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    x = ret.loc[(ret.index >= start) & (ret.index <= end)].dropna().astype(float)
    if x.empty:
        raise RuntimeError(f"No returns for {start}~{end}")
    return (1.0 + x).cumprod()


def drawdown(nav: pd.Series) -> pd.Series:
    return nav / np.maximum.accumulate(np.r_[1.0, nav.to_numpy()])[1:] - 1.0


def recovery_days(nav: pd.Series, baseline_date: pd.Timestamp | None = None) -> tuple[int, float]:
    s = nav.astype(float).sort_index()
    if baseline_date is None:
        if len(s) >= 2:
            med = float(np.median(np.diff(s.index.values).astype("timedelta64[D]").astype(int)))
        else:
            med = 1.0
        baseline_date = (s.index[0].to_period("M") - 1).to_timestamp("M") if med >= 20 else s.index[0] - pd.offsets.BDay(1)

    peak = 1.0
    peak_date = pd.Timestamp(baseline_date)
    underwater_start = None
    longest = 0
    for dt, val in s.items():
        if val >= peak:
            if underwater_start is not None:
                longest = max(longest, (dt - underwater_start).days)
                underwater_start = None
            peak = float(val)
            peak_date = pd.Timestamp(dt)
        elif underwater_start is None:
            underwater_start = peak_date
    if underwater_start is not None:
        longest = max(longest, (s.index[-1] - underwater_start).days)
    return int(longest), round(longest / 30.4375, 1)


def metrics(monthly_ret: pd.Series, start: pd.Timestamp, end: pd.Timestamp, risk_nav: pd.Series | None = None, risk_source: str = "monthly_fallback") -> dict:
    r = monthly_ret.loc[(monthly_ret.index >= start) & (monthly_ret.index <= end)].dropna().astype(float)
    if r.empty:
        raise RuntimeError("No monthly returns in metrics window")
    nav = (1.0 + r).cumprod()
    years = len(r) / 12.0
    final = float(nav.iloc[-1])
    cagr = final ** (1.0 / years) - 1.0
    vol = float(r.std(ddof=1) * np.sqrt(12)) if len(r) >= 2 else np.nan
    mrf = (1.0 + RF_ANNUAL) ** (1 / 12) - 1
    ex = r - mrf
    sharpe = float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)) if len(ex) >= 2 and ex.std(ddof=1) > 0 else np.nan

    if risk_nav is None:
        rnav = nav
        source = "monthly_fallback"
        base = (r.index[0].to_period("M") - 1).to_timestamp("M")
    else:
        rnav = risk_nav
        source = risk_source
        base = rnav.index[0] - pd.offsets.BDay(1)

    dd = drawdown(rnav)
    rec_days, rec_months = recovery_days(rnav, base)
    return {
        "start": str(r.index[0].date()),
        "end": str(r.index[-1].date()),
        "months": int(len(r)),
        "CAGR": cagr,
        "CumulativeReturn": final - 1.0,
        "AnnualizedVol": vol,
        "MDD": float(dd.min()),
        "MDD_source": source,
        "Sharpe": sharpe,
        "MaxRecoveryDays": rec_days,
        "MaxRecoveryMonths": rec_months,
        "FinalMultiple": final,
        "FinalAssetKRW": final * INITIAL_CAPITAL,
    }


def daily_nav_for_window(daily_ret: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series | None:
    x = daily_ret.loc[(daily_ret.index >= start.to_period("M").start_time) & (daily_ret.index <= end.to_period("M").end_time)].dropna()
    if x.empty:
        return None
    # Require first and last month coverage and no long data gaps.
    if x.index[0].to_period("M") != start.to_period("M") or x.index[-1].to_period("M") != end.to_period("M"):
        return None
    if x.index[0].day > 7:
        return None
    if (x.index[-1].to_period("M").end_time.normalize() - x.index[-1]).days > 7:
        return None
    gaps = pd.Series(x.index[1:] - x.index[:-1])
    if len(gaps) and (gaps.dt.days > 7).any():
        return None
    return (1.0 + x).cumprod()


def period_rows(monthly_returns: pd.DataFrame, daily_net10: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, label: str):
    rows = []
    daily_map = {
        "StrategyGross": daily_net10["StrategyGross"],
        "StrategyNet10bp": daily_net10["StrategyNet"],
        "KOSPI": daily_net10["KOSPI"],
    }
    for col in ["StrategyGross", "StrategyNet10bp", "KOSPI"]:
        risk_nav = daily_nav_for_window(daily_map[col], start, end)
        source = "daily" if risk_nav is not None else "monthly_fallback"
        m = metrics(monthly_returns[col], start, end, risk_nav, source)
        m.update({"period": label, "series": col})
        rows.append(m)
    return rows


def save_chart_data(monthly_returns: pd.DataFrame, daily_net10: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, key: str):
    cols = ["StrategyNet10bp", "KOSPI"]
    m = monthly_returns.loc[(monthly_returns.index >= start) & (monthly_returns.index <= end), cols].dropna(how="any")
    nav = (1.0 + m).cumprod()
    chart = pd.DataFrame({
        "Date": nav.index,
        "Strategy": nav["StrategyNet10bp"],
        "KOSPI": nav["KOSPI"],
        "StrategyLog2": np.log2(nav["StrategyNet10bp"]),
        "KOSPILog2": np.log2(nav["KOSPI"]),
    })
    chart.to_csv(OUT / f"chart_{key}_monthly.csv", index=False, encoding="utf-8-sig")

    # Drawdown: daily when full daily coverage exists, otherwise monthly fallback.
    s_daily = daily_nav_for_window(daily_net10["StrategyNet"], start, end)
    b_daily = daily_nav_for_window(daily_net10["KOSPI"], start, end)
    if s_daily is not None and b_daily is not None:
        dd = pd.DataFrame({
            "Date": s_daily.index.intersection(b_daily.index),
        })
        dd = dd.set_index("Date")
        dd["StrategyDD"] = drawdown(s_daily.reindex(dd.index)) * 100.0
        dd["KOSPIDDD"] = drawdown(b_daily.reindex(dd.index)) * 100.0
        dd = dd.reset_index()
        risk_source = "daily"
    else:
        dd = pd.DataFrame({
            "Date": nav.index,
            "StrategyDD": drawdown(nav["StrategyNet10bp"]).to_numpy() * 100.0,
            "KOSPIDDD": drawdown(nav["KOSPI"]).to_numpy() * 100.0,
        })
        risk_source = "monthly_fallback"
    dd.to_csv(OUT / f"chart_{key}_drawdown.csv", index=False, encoding="utf-8-sig")
    return risk_source, len(chart), len(dd)


def main():
    kospi_price, kdiag = build_kospi_monthly_long()
    bond_main, bond_syn, bdiag = build_bond_monthly_proxy()

    # Keep enough warm-up history for 10-month SMA, but performance starts in 1987.
    common_start = max(kospi_price.index.min(), bond_main.index.min())
    common_end = min(kospi_price.index.max(), bond_main.index.max(), LAST_COMPLETE_MONTH)
    kospi_price = kospi_price.loc[:common_end]

    rets, daily_gross, daily_net10, daily_net20, aligned = build_strategy_returns(kospi_price, bond_main, bond_syn)

    # 2018+ daily net10 is the standard risk source when full period coverage exists.
    daily10 = daily_net10.copy()

    longest_start = BOOK_START
    periods = {
        "book_validation": (BOOK_START, BOOK_END),
        "from_2001": (STANDARD_2001, common_end),
        "from_2021": (STANDARD_2021, common_end),
        "longest": (longest_start, common_end),
    }

    metric_rows = []
    for key, (s, e) in periods.items():
        if key == "book_validation":
            # Book-period comparison uses the concept-matched synthetic 5y proxy,
            # while the standard main series remains the investable hybrid.
            for col in ["BookProxyGross", "StrategyGross", "StrategyNet10bp", "KOSPI"]:
                risk_nav = None
                risk_source = "monthly_fallback"
                if col in ["StrategyGross", "StrategyNet10bp", "KOSPI"]:
                    dcol = {"StrategyGross": "StrategyGross", "StrategyNet10bp": "StrategyNet", "KOSPI": "KOSPI"}[col]
                    risk_nav = daily_nav_for_window(daily10[dcol], s, e)
                    if risk_nav is not None:
                        risk_source = "daily"
                m = metrics(rets[col], s, e, risk_nav, risk_source)
                m.update({"period": key, "series": col})
                metric_rows.append(m)
        else:
            metric_rows.extend(period_rows(rets, daily10, s, e, key))

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(OUT / "metrics.csv", index=False, encoding="utf-8-sig")

    # Book figures from the user's source notes for direct gap analysis.
    book_reference = {
        "Strategy": {"FinalMultiple": 87.5, "CAGR": 0.142, "MDD": -0.291, "Sharpe": 0.64},
        "KOSPI": {"FinalMultiple": 10.6, "CAGR": 0.073, "MDD": -0.712, "Sharpe": 0.18},
    }
    book_rows = []
    for series, refkey in [("BookProxyGross", "Strategy"), ("KOSPI", "KOSPI")]:
        obs = metrics_df[(metrics_df["period"] == "book_validation") & (metrics_df["series"] == series)].iloc[0]
        ref = book_reference[refkey]
        book_rows.append({
            "series": series,
            "our_final_multiple": obs["FinalMultiple"],
            "book_final_multiple": ref["FinalMultiple"],
            "our_CAGR": obs["CAGR"],
            "book_CAGR": ref["CAGR"],
            "our_MDD": obs["MDD"],
            "book_MDD": ref["MDD"],
            "our_Sharpe": obs["Sharpe"],
            "book_Sharpe": ref["Sharpe"],
        })
    pd.DataFrame(book_rows).to_csv(OUT / "book_comparison.csv", index=False, encoding="utf-8-sig")

    # Cost sensitivity for the three non-book standard windows.
    cost_rows = []
    for key in ["from_2001", "from_2021", "longest"]:
        s, e = periods[key]
        for col, cost in [("StrategyGross", 0.0), ("StrategyNet10bp", MAIN_SWITCH_COST), ("StrategyNet20bp", CONSERVATIVE_SWITCH_COST)]:
            m = metrics(rets[col], s, e)
            cost_rows.append({"period": key, "series": col, "switch_cost": cost, **m})
    pd.DataFrame(cost_rows).to_csv(OUT / "cost_sensitivity.csv", index=False, encoding="utf-8-sig")

    # Regime statistics.
    pos = rets["PositionStock"].loc[BOOK_START:common_end].dropna()
    switches = int(pos.ne(pos.shift(1)).sum() - 1) if len(pos) else 0
    stock_share = float(pos.mean()) if len(pos) else np.nan
    regime = {
        "months": int(len(pos)),
        "stock_month_share": stock_share,
        "bond_month_share": 1.0 - stock_share if np.isfinite(stock_share) else np.nan,
        "regime_switches": max(0, switches),
        "switches_per_year": max(0, switches) / (len(pos) / 12.0) if len(pos) else np.nan,
    }

    # One-month extra lag robustness: deliberately more conservative timing.
    lagged_position = rets["PositionStock"].shift(1)
    eqr = kospi_price.pct_change().reindex(rets.index)
    lag_ret = pd.Series(np.where(lagged_position == 1.0, eqr, bond_main.reindex(rets.index)), index=rets.index, dtype=float)
    lag_ret = apply_monthly_cost(lag_ret, lagged_position, MAIN_SWITCH_COST)
    robust_rows = []
    for key in ["from_2001", "from_2021", "longest"]:
        s, e = periods[key]
        try:
            robust_rows.append({"period": key, "variant": "extra_1m_lag", **metrics(lag_ret, s, e)})
        except Exception as exc:
            robust_rows.append({"period": key, "variant": "extra_1m_lag", "error": str(exc)})
    pd.DataFrame(robust_rows).to_csv(OUT / "timing_robustness.csv", index=False, encoding="utf-8-sig")

    # Save strategy monthly audit data.
    audit = aligned.join(rets[["StrategyGross", "StrategyNet10bp", "StrategyNet20bp", "BookProxyGross", "KOSPI"]], how="left")
    audit = audit.loc[BOOK_START:common_end]
    audit.index.name = "Date"
    audit.to_csv(OUT / "monthly_audit.csv", encoding="utf-8-sig")

    # Save daily audit data after ETF inception.
    daily_out = daily10.copy()
    daily_out.index.name = "Date"
    daily_out.to_csv(OUT / "daily_nav_inputs_2018plus.csv", encoding="utf-8-sig")

    # 9-chart data (3 periods x cumulative/log2/drawdown).
    chart_meta = {}
    for key in ["from_2001", "from_2021", "longest"]:
        s, e = periods[key]
        chart_meta[key] = {}
        source, n_month, n_dd = save_chart_data(rets, daily10, s, e, key)
        chart_meta[key] = {"risk_source": source, "monthly_points": n_month, "drawdown_points": n_dd}

    summary = {
        "title": TITLE,
        "run_at_utc": RUN_AT.isoformat(),
        "last_complete_month": str(LAST_COMPLETE_MONTH.date()),
        "initial_capital_krw": INITIAL_CAPITAL,
        "signal_rule": "At month-end, KOSPI close >= 10-month SMA => stock; else bond. Prior month-end signal drives next month.",
        "execution_rule": "No same-close signal execution. ETF-era switches are modeled on the first common trading day using old-asset close-to-open + new-asset open-to-close. Pre-ETF proxy period uses next-month return with prior-month signal (monthly boundary approximation).",
        "main_bond_proxy": "1987-07/2018-07 synthetic rolling 5y national-housing-bond return from FRED/OECD yield; from 2018-08 TIGER 3-10y government bond ETF adjusted return.",
        "book_proxy": "Synthetic rolling 5y national-housing-bond return throughout book period where available.",
        "cost_assumptions": {
            "gross": 0.0,
            "base_total_switch_cost": MAIN_SWITCH_COST,
            "conservative_total_switch_cost": CONSERVATIVE_SWITCH_COST,
            "initial_entry_cost": INITIAL_ENTRY_COST,
        },
        "periods": {k: [str(v[0].date()), str(v[1].date())] for k, v in periods.items()},
        "data_diagnostics": {"kospi": kdiag, "bond": bdiag},
        "regime": regime,
        "charts": chart_meta,
        "limitations": [
            "Exact Korean 5-year government-bond total-return index is not available in the project repository.",
            "1987-1995 KOSPI uses an OECD share-price proxy scaled into the exact KOSPI series; it is not an exact KRX month-end history.",
            "Historical 5y bond returns before ETF availability are reconstructed from monthly average 5y national-housing-bond yields; this is a proxy, not an official total-return index.",
            "Pre-ETF execution is monthly and cannot exactly isolate the first-session close-to-open gap.",
            "KOSPI is a price index, so dividends are excluded unless the source index itself includes them.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()
