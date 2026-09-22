from __future__ import annotations

from pathlib import Path
import json, os, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from quant_backtest_template_CURRENT import BacktestConfig, run_four_periods, combine_period_payloads

OUT = ROOT / "results" / "strategy8"
OUT.mkdir(parents=True, exist_ok=True)

TITLE = "Strategy 8 - 한미 평균 모멘텀 스코어"
BOOK_START = pd.Timestamp("2005-01-31")
BOOK_END = pd.Timestamp("2021-12-31")
INITIAL_CAPITAL = 10_000_000.0
BASE_TRADE_COST = 0.0010
BASE_ENTRY_COST = 0.0005
MIN_TRADE_COST = 0.0005
MIN_ENTRY_COST = 0.00025
CONS_TRADE_COST = 0.0025
CONS_ENTRY_COST = 0.0010
AS_OF = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
LAST_COMPLETE = (AS_OF.to_period("M") - 1).to_timestamp("M")


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def month_end_from_daily(df: pd.DataFrame, col: str) -> pd.Series:
    x = df.copy()
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.dropna(subset=["Date", col]).sort_values("Date")
    x = x[x["Date"] <= LAST_COMPLETE]
    s = x.set_index("Date")[col]
    m = s.groupby(s.index.to_period("M")).last()
    m.index = m.index.to_timestamp("M")
    return m.astype(float)


def fred_csv(series_id: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, timeout=90, headers={"User-Agent": "quant-strategy8/1.0"})
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Value"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    return df.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date")


def fetch_ecos_20y() -> tuple[pd.DataFrame, str]:
    """Fetch Korean 20Y Treasury daily yields from BOK ECOS.

    ECOS's public sample key effectively truncates long date-range requests.
    In sample-key mode, query one calendar year at a time and paginate within
    each year; then concatenate and de-duplicate.
    """
    key = (os.getenv("ECOS_API_KEY") or "").strip() or "sample"
    base = "https://ecos.bok.or.kr/api/StatisticSearch"
    sess = requests.Session()
    sess.headers.update({"User-Agent": "quant-strategy8/1.0"})

    def fetch_range(start: str, end: str, page_size: int) -> list[dict]:
        def one(a: int, b: int):
            url = f"{base}/{key}/json/kr/{a}/{b}/817Y002/D/{start}/{end}/010220000"
            rr = sess.get(url, timeout=60)
            rr.raise_for_status()
            return rr.json()

        first = one(1, page_size)
        if "StatisticSearch" not in first:
            # No observations in a pre-inception/holiday-only range.
            if "RESULT" in first and first["RESULT"].get("CODE") == "INFO-200":
                return []
            raise RuntimeError(f"ECOS error {start}~{end}: {first}")

        total = int(first["StatisticSearch"]["list_total_count"])
        rows = list(first["StatisticSearch"].get("row", []))
        for a in range(page_size + 1, total + 1, page_size):
            b = min(a + page_size - 1, total)
            js = one(a, b)
            if "StatisticSearch" not in js:
                if rows and "RESULT" in js and js["RESULT"].get("CODE") == "INFO-200":
                    break
                raise RuntimeError(f"ECOS page error {start}~{end} at {a}: {js}")
            page_rows = js["StatisticSearch"].get("row", [])
            if not page_rows:
                break
            rows.extend(page_rows)
            if key == "sample":
                time.sleep(0.005)
        return rows

    rows: list[dict] = []
    if key == "sample":
        # The public sample key truncates long windows around ~100 observations.
        # Query quarter-by-quarter so each request window remains safely below
        # that cap, then concatenate. This is slower but complete and reproducible.
        start_q = pd.Period("2006Q1", freq="Q")
        end_q = LAST_COMPLETE.to_period("Q")
        for q in pd.period_range(start_q, end_q, freq="Q"):
            qs = max(pd.Timestamp("2006-01-01"), q.start_time.normalize())
            qe = min(LAST_COMPLETE, q.end_time.normalize())
            if qs > qe:
                continue
            rows.extend(fetch_range(qs.strftime("%Y%m%d"), qe.strftime("%Y%m%d"), 10))
    else:
        rows = fetch_range("20060101", LAST_COMPLETE.strftime("%Y%m%d"), 1000)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("ECOS 20Y empty")
    df = df[["TIME", "DATA_VALUE"]].copy()
    df.columns = ["Date", "Value"]
    df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna().sort_values("Date").drop_duplicates("Date")
    # Do not invent unavailable tail months. The backtest ends at the latest
    # common month actually supported by all required assets.
    return df, ("ECOS authenticated key" if key != "sample" else "ECOS sample key annual-chunked")


def fetch_pykrx_yield(kind: str, start: str, end: str) -> tuple[pd.Series, str]:
    """Fetch KRX OTC Treasury yields through pykrx in annual chunks."""
    cache_name = "KR_" + ("10Y" if "10년" in kind else "20Y") + "_KOFIA_YIELD.csv"
    cache = ROOT / "data" / "proxy_long" / "raw" / cache_name

    if cache.exists():
        x = load_csv(cache)
        if {"Date", "Value"}.issubset(x.columns):
            x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
            x["Value"] = pd.to_numeric(x["Value"], errors="coerce")
            s = x.dropna(subset=["Date", "Value"]).sort_values("Date").drop_duplicates("Date").set_index("Date")["Value"]
            if len(s) > 100 and s.index.max() >= pd.Timestamp("2025-12-01"):
                return s.loc[:LAST_COMPLETE], "repo_cache_pykrx"

    from pykrx import bond

    pieces = []
    y0, y1 = int(start[:4]), int(end[:4])
    for year in range(y0, y1 + 1):
        s0 = max(start, f"{year}0101")
        e0 = min(end, f"{year}1231")
        try:
            df = bond.get_otc_treasury_yields(s0, e0, kind)
            if df is not None and not df.empty:
                col = "수익률" if "수익률" in df.columns else df.columns[0]
                z = pd.to_numeric(df[col], errors="coerce")
                z.index = pd.to_datetime(z.index, errors="coerce")
                pieces.append(z.dropna())
        except Exception:
            pass
        time.sleep(0.08)

    if not pieces:
        raise RuntimeError(f"pykrx returned no data for {kind}")

    s = pd.concat(pieces).sort_index()
    s = s[~s.index.duplicated(keep="last")].dropna()
    s = s[s.index <= LAST_COMPLETE]
    pd.DataFrame({"Date": s.index, "Value": s.values}).to_csv(cache, index=False, encoding="utf-8-sig")
    return s, "pykrx KRX OTC treasury yield"


def bond_price_par(yield_decimal: float, coupon_rate: float, maturity_years: float) -> float:
    freq = 2
    n = int(round(maturity_years * freq))
    r = yield_decimal / freq
    c = 100.0 * coupon_rate / freq
    if abs(r) < 1e-12:
        return 100.0 + c * n
    d = 1.0 + r
    return c * (1.0 - d ** (-n)) / r + 100.0 * d ** (-n)


def synth_returns_from_yield(y: pd.Series, maturity_years: float = 20.0) -> pd.Series:
    """Approximate one-period total return of a rolling par Treasury.

    At t0, buy a semiannual-coupon bond at par with coupon=y(t0).
    At t1, reprice the same bond after elapsed time reduces remaining maturity.
    """
    y = y.dropna().sort_index().astype(float) / 100.0
    out = pd.Series(index=y.index, dtype=float)
    if len(out):
        out.iloc[0] = np.nan

    face, freq = 100.0, 2
    base_times = np.arange(1, int(round(maturity_years * freq)) + 1, dtype=float) / freq

    for i in range(1, len(y)):
        prev, cur = y.index[i - 1], y.index[i]
        y0, y1 = float(y.iloc[i - 1]), float(y.iloc[i])
        if min(y0, y1) <= -0.95:
            continue

        coupon = face * y0 / freq
        cash = np.full(len(base_times), coupon, dtype=float)
        cash[-1] += face
        p0 = float(np.sum(cash / (1.0 + y0 / freq) ** (freq * base_times)))

        elapsed = max((cur - prev).days / 365.2425, 1.0 / 365.2425)
        t1 = base_times - elapsed
        paid = float(cash[t1 <= 0].sum())
        remain = t1 > 0
        p1 = float(np.sum(cash[remain] / (1.0 + y1 / freq) ** (freq * t1[remain])))
        out.iloc[i] = (paid + p1) / p0 - 1.0
    return out


def month_end_yield(df: pd.DataFrame) -> pd.Series:
    x = df.copy().dropna(subset=["Date", "Value"]).sort_values("Date")
    s = x.set_index("Date")["Value"].astype(float)
    m = s.groupby(s.index.to_period("M")).last()
    m.index = m.index.to_timestamp("M")
    return m


def wealth_from_returns(r: pd.Series, base: float = 1.0) -> pd.Series:
    r = r.sort_index().astype(float).fillna(0.0)
    return base * (1.0 + r).cumprod()


def splice_return_series(pre_ret: pd.Series, post_price: pd.Series) -> pd.Series:
    post_ret = post_price.pct_change()
    first = post_ret.first_valid_index()
    idx = pre_ret.index.union(post_ret.index).sort_values()
    out = pre_ret.reindex(idx)
    if first is not None:
        use = post_ret.index[post_ret.index >= first]
        out.loc[use] = post_ret.loc[use]
    return out.sort_index()


def build_assets() -> tuple[pd.DataFrame, dict]:
    spy = month_end_from_daily(load_csv(ROOT / "data/etf_us/SPY.csv"), "Adj Close")
    spy_ret = spy.pct_change()
    spy_idx = wealth_from_returns(spy_ret.dropna())

    u20 = load_csv(ROOT / "data/proxy_long/raw/US_20Y_YIELD.csv")
    u10 = load_csv(ROOT / "data/proxy_long/raw/US_10Y_YIELD.csv")
    u30 = load_csv(ROOT / "data/proxy_long/raw/US_30Y_YIELD.csv")
    for d in (u20, u10, u30):
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        d["Value"] = pd.to_numeric(d["Value"], errors="coerce")
    y20 = month_end_yield(u20)
    y10 = month_end_yield(u10)
    y30 = month_end_yield(u30)
    allm = y20.index.union(y10.index).union(y30.index).sort_values()
    y20 = y20.reindex(allm)
    y10 = y10.reindex(allm)
    y30 = y30.reindex(allm)
    gap = (allm >= pd.Timestamp("1987-01-31")) & (allm <= pd.Timestamp("1993-09-30"))
    y20.loc[gap & y20.isna()] = ((y10 + y30) / 2).loc[gap & y20.isna()]
    y20 = y20.ffill(limit=2)
    us_syn = synth_returns_from_yield(y20.dropna(), 20.0)
    tlt = month_end_from_daily(load_csv(ROOT / "data/etf_us/TLT.csv"), "Adj Close")
    us_bond_ret = splice_return_series(us_syn, tlt)
    us_bond_idx = wealth_from_returns(us_bond_ret.dropna())

    k200 = month_end_from_daily(load_csv(ROOT / "data/indices/KOSPI200.csv"), "Close")
    k200_ret = k200.pct_change()
    kodex = month_end_from_daily(load_csv(ROOT / "data/etf_kr/069500_KODEX200.csv"), "Adj Close")
    kr_eq_ret = splice_return_series(k200_ret, kodex)
    kr_eq_idx = wealth_from_returns(kr_eq_ret.dropna())

    # Korean government-bond leg.
    # The 20Y KTB did not exist in 2005. Use the repo-local 5Y yield
    # reconstruction only before the first ECOS 20Y observation, then
    # reconstruct a true-duration 20Y constant-maturity return from ECOS.
    kr_bridge = load_csv(ROOT / "data/proxy_long/raw/KR_HOUSING_BOND_5Y_YIELD.csv")
    kr_bridge["Date"] = pd.to_datetime(kr_bridge["Date"], errors="coerce")
    kr_bridge["Value"] = pd.to_numeric(kr_bridge["Value"], errors="coerce")
    y_bridge = month_end_yield(kr_bridge)

    ecos, ecos_status = fetch_ecos_20y()
    y_kr20 = month_end_yield(ecos)

    bridge_ret = synth_returns_from_yield(y_bridge.loc[:LAST_COMPLETE], 5.0)
    kr20_ret = synth_returns_from_yield(y_kr20.loc[:LAST_COMPLETE], 20.0)
    first_kr20_ret = kr20_ret.first_valid_index()
    if first_kr20_ret is None:
        raise RuntimeError("No valid ECOS Korean 20Y return after reconstruction")

    kr_bond_ret = pd.concat([
        bridge_ret[bridge_ret.index < first_kr20_ret],
        kr20_ret[kr20_ret.index >= first_kr20_ret],
    ]).sort_index()
    kr_bond_ret = kr_bond_ret[~kr_bond_ret.index.duplicated(keep="last")]
    kr_bond_idx = wealth_from_returns(kr_bond_ret.dropna())
    kr_bond_mode = "repo KR 5Y bridge before 20Y inception -> ECOS KR 20Y actual-duration synthetic return"
    kr10_source = "not_used"
    kr20_source = ecos_status
    pykrx_err = None
    ecos_err = None

    idx = spy_idx.index.intersection(us_bond_idx.index).intersection(kr_eq_idx.index).intersection(kr_bond_idx.index)
    idx = idx[idx <= LAST_COMPLETE]
    prices = pd.DataFrame({
        "SPY": spy_idx.reindex(idx),
        "US_LONG_BOND": us_bond_idx.reindex(idx),
        "KODEX200_PROXY": kr_eq_idx.reindex(idx),
        "KR_20Y_PROXY": kr_bond_idx.reindex(idx),
    }).dropna()

    diag = {
        "requested_last_complete_month": str(LAST_COMPLETE.date()),
        "actual_common_data_end": str(prices.index.max().date()),
        "spy_raw_start": str(spy.index.min().date()),
        "tlt_raw_start": str(tlt.index.min().date()),
        "kospi200_start": str(k200.index.min().date()),
        "kodex200_repo_start": str(kodex.index.min().date()),
        "kr_bridge_yield_start": str(y_bridge.index.min().date()),
        "kr20_source": kr20_source,
        "kr_bond_mode": kr_bond_mode,
        "kr20_yield_start": str(y_kr20.index.min().date()),
        "kr20_yield_end": str(y_kr20.index.max().date()),
        "kr20_return_start": str(first_kr20_ret.date()),
        "ecos_status": ecos_status,
        "common_price_start": str(prices.index.min().date()),
        "common_price_end": str(prices.index.max().date()),
    }
    return prices, diag


def average_momentum_score(prices: pd.DataFrame) -> pd.DataFrame:
    parts = [prices.gt(prices.shift(k)).astype(float) for k in range(1, 13)]
    score = sum(parts) / 12.0
    valid = pd.DataFrame(True, index=prices.index, columns=prices.columns)
    for k in range(1, 13):
        valid &= prices.shift(k).notna()
    return score.where(valid)


def run_portfolio(
    prices: pd.DataFrame,
    trade_cost: float,
    entry_cost: float,
    rebalance_month: int = 1,
    fx_krw: pd.Series | None = None,
) -> tuple[pd.Series, pd.DataFrame, dict]:
    px = prices.copy()
    if fx_krw is not None:
        fx = fx_krw.reindex(px.index).ffill()
        px["SPY"] = px["SPY"] * fx / fx.iloc[0]
        px["US_LONG_BOND"] = px["US_LONG_BOND"] * fx / fx.iloc[0]

    score = average_momentum_score(px)
    asset_ret = px.pct_change()
    candidates = []
    for dt in px.index:
        if dt.month == rebalance_month:
            prev = (dt.to_period("M") - 1).to_timestamp("M")
            if prev in score.index and score.loc[prev].notna().all():
                candidates.append(dt)
    if not candidates:
        raise RuntimeError("No valid annual rebalance after 12m score warm-up")
    start = candidates[0]
    run_idx = px.index[px.index >= start]

    nav = 1.0
    weights = pd.Series(0.0, index=px.columns)
    cash = 1.0
    nav_s = []
    audit = []
    first_entry = True
    traded_total = 0.0
    rebal_count = 0

    for dt in run_idx:
        if dt.month == rebalance_month:
            prev = (dt.to_period("M") - 1).to_timestamp("M")
            if prev in score.index and score.loc[prev].notna().all():
                target = 0.25 * score.loc[prev].astype(float)
                target_cash = float(1.0 - target.sum())
                traded = float((target - weights).abs().sum())
                rate = entry_cost if first_entry else trade_cost
                cost = nav * traded * rate
                nav -= cost
                traded_total += traded
                rebal_count += 1
                weights = target.copy()
                cash = target_cash
                first_entry = False
                audit.append({
                    "Date": dt,
                    "SignalDate": prev,
                    "TradeFraction": traded,
                    "CostRate": rate,
                    "CostNAV": cost,
                    **{f"w_{c}": float(target[c]) for c in target.index},
                    "w_CASH": target_cash,
                })

        r = asset_ret.loc[dt].fillna(0.0)
        sleeve = weights * (1.0 + r)
        gross_factor = float(sleeve.sum() + cash)
        nav *= gross_factor
        if gross_factor <= 0:
            raise RuntimeError("Nonpositive portfolio factor")
        weights = sleeve / gross_factor
        cash = cash / gross_factor
        nav_s.append((dt, nav))

    s = pd.Series(dict(nav_s), name="NAV").sort_index()
    aud = pd.DataFrame(audit)
    stats = {
        "start": str(s.index.min().date()),
        "end": str(s.index.max().date()),
        "rebalances": rebal_count,
        "avg_traded_notional_fraction": traded_total / rebal_count if rebal_count else 0.0,
    }
    return s, aud, stats


def run_static_benchmark(prices: pd.DataFrame, trade_cost: float = 0.0, entry_cost: float = 0.0) -> pd.Series:
    r = prices.pct_change()
    score = average_momentum_score(prices)
    starts = []
    for dt in prices.index:
        if dt.month == 1:
            prev = (dt.to_period("M") - 1).to_timestamp("M")
            if prev in score.index and score.loc[prev].notna().all():
                starts.append(dt)
    start = starts[0]
    idx = prices.index[prices.index >= start]
    nav = 1.0
    w = pd.Series(0.0, index=prices.columns)
    cash = 1.0
    first = True
    vals = []
    for dt in idx:
        if dt.month == 1:
            target = pd.Series(0.25, index=prices.columns)
            tc = entry_cost if first else trade_cost
            traded = float((target - w).abs().sum())
            nav -= nav * traded * tc
            w = target
            cash = 0.0
            first = False
        rr = r.loc[dt].fillna(0.0)
        sleeve = w * (1.0 + rr)
        f = float(sleeve.sum() + cash)
        nav *= f
        w = sleeve / f
        cash = cash / f
        vals.append((dt, nav))
    return pd.Series(dict(vals)).sort_index()


def make_monthly_nav(prices: pd.DataFrame, fx_krw: pd.Series | None = None):
    gross, _, sg = run_portfolio(prices, 0.0, 0.0, 1, fx_krw)
    net, an, sn = run_portfolio(prices, BASE_TRADE_COST, BASE_ENTRY_COST, 1, fx_krw)
    bench = run_static_benchmark(prices, 0.0, 0.0)
    common = gross.index.intersection(net.index).intersection(bench.index)
    nav = pd.DataFrame({
        "전략(비용전)": gross.reindex(common),
        "전략(비용후)": net.reindex(common),
        "정적4자산25%": bench.reindex(common),
    })
    return nav, an, {"gross": sg, "net": sn}


def manual_metrics(nav: pd.Series, start: str, end: str) -> dict:
    s = nav.loc[pd.Timestamp(start):pd.Timestamp(end)].copy()
    if s.empty:
        return {"error": "no data"}
    pos = nav.index.searchsorted(s.index[0])
    base = float(nav.iloc[pos - 1]) if pos > 0 else 1.0
    x = s / base
    r = pd.concat([pd.Series([1.0], index=[s.index[0] - pd.offsets.MonthEnd(1)]), x]).pct_change().dropna()
    yrs = len(r) / 12.0
    final = float(x.iloc[-1])
    cagr = final ** (1.0 / yrs) - 1.0
    vol = float(r.std(ddof=1) * np.sqrt(12))
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(12)) if r.std(ddof=1) > 0 else np.nan
    dd = x / np.maximum.accumulate(np.r_[1.0, x.values])[1:] - 1.0
    return {
        "start": str(s.index[0].date()),
        "end": str(s.index[-1].date()),
        "months": len(s),
        "CAGR": cagr,
        "CumulativeReturn": final - 1.0,
        "AnnualizedVol": vol,
        "MDD": float(dd.min()),
        "Sharpe": sharpe,
        "FinalMultiple": final,
        "FinalAssetKRW": final * INITIAL_CAPITAL,
    }


def main():
    prices, diag = build_assets()
    monthly, audit, portstats = make_monthly_nav(prices)
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    monthly = monthly.loc[:LAST_COMPLETE]
    DATA_END = monthly.index.max()

    cfg = BacktestConfig(
        title=TITLE,
        initial_capital=INITIAL_CAPITAL,
        risk_free_rate=0.0,
        book_start=str(BOOK_START.date()),
        book_end=str(BOOK_END.date()),
        expected_end=DATA_END.strftime("%Y-%m"),
        standard_end_year=DATA_END.year,
        as_of_date=AS_OF.strftime("%Y-%m-%d"),
    )
    results = run_four_periods(monthly, cfg, daily_nav=None)

    rows = []
    for key, res in results.items():
        m = res["metrics"].reset_index()
        m.insert(0, "period", key)
        rows.append(m)
    metrics = pd.concat(rows, ignore_index=True)
    metrics.to_csv(OUT / "metrics.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(OUT / "monthly_nav.csv", encoding="utf-8-sig")
    audit.to_csv(OUT / "rebalance_audit_base.csv", index=False, encoding="utf-8-sig")

    variants = {
        "gross": run_portfolio(prices, 0, 0)[0],
        "min_5bp": run_portfolio(prices, MIN_TRADE_COST, MIN_ENTRY_COST)[0],
        "base_10bp": run_portfolio(prices, BASE_TRADE_COST, BASE_ENTRY_COST)[0],
        "conservative_25bp": run_portfolio(prices, CONS_TRADE_COST, CONS_ENTRY_COST)[0],
    }
    windows = {
        "book_validation": ("2005-01-31", "2021-12-31"),
        "from_2001": ("2001-01-31", str(DATA_END.date())),
        "from_2021": ("2021-01-31", str(DATA_END.date())),
        "longest": (str(monthly.index.min().date()), str(DATA_END.date())),
    }
    cost_rows = []
    for p, (a, b) in windows.items():
        for name, s in variants.items():
            cost_rows.append({"period": p, "variant": name, **manual_metrics(s, a, b)})
    pd.DataFrame(cost_rows).to_csv(OUT / "cost_sensitivity.csv", index=False, encoding="utf-8-sig")

    timing = []
    timing_book = []
    for m in range(1, 13):
        s, _, _ = run_portfolio(prices, BASE_TRADE_COST, BASE_ENTRY_COST, m)
        timing.append({"rebalance_month": m, **manual_metrics(s, "2001-01-31", str(DATA_END.date()))})
        timing_book.append({"rebalance_month": m, **manual_metrics(s, "2005-01-31", "2021-12-31")})
    timing_df = pd.DataFrame(timing)
    timing_df.to_csv(OUT / "timing_sensitivity.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(timing_book).to_csv(OUT / "timing_sensitivity_book.csv", index=False, encoding="utf-8-sig")

    oos = manual_metrics(variants["base_10bp"], "2022-01-31", str(DATA_END.date()))

    fxdf = load_csv(ROOT / "data/fx/USDKRW_FRED_LONG.csv")
    fxdf["Date"] = pd.to_datetime(fxdf["Date"], errors="coerce")
    fxdf["DEXKOUS"] = pd.to_numeric(fxdf["DEXKOUS"], errors="coerce")
    fxs = fxdf.dropna().set_index("Date")["DEXKOUS"]
    fxm = fxs.groupby(fxs.index.to_period("M")).last()
    fxm.index = fxm.index.to_timestamp("M")
    krw_nav, _, _ = make_monthly_nav(prices, fxm)
    krw_base = krw_nav["전략(비용후)"]
    krw_sens = {p: manual_metrics(krw_base, a, b) for p, (a, b) in windows.items()}

    payloads = [results[k]["chat_payload"] for k in ("from_2001", "from_2021", "longest")]
    dashboard = combine_period_payloads(*payloads)
    (OUT / "chat_dashboard_payload.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    bm = metrics[(metrics.period == "book_validation") & (metrics["전략"] == "전략(비용후)")].iloc[0].to_dict()
    book_compare = {
        "book_reference": {"CAGR": 0.08, "MDD": -0.07},
        "our_proxy_base_cost": {"CAGR": float(bm["CAGR"]), "MDD": float(bm["MDD"]), "MDD_source": bm["MDD_source"]},
        "gap": {"CAGR_pctpt": (float(bm["CAGR"]) - 0.08) * 100, "MDD_pctpt": (float(bm["MDD"]) + 0.07) * 100},
    }

    summary = {
        "title": TITLE,
        "run_at_utc": AS_OF.isoformat(),
        "last_complete_month": str(DATA_END.date()),
        "source_rule": {
            "assets": ["SPY", "TLT/US long Treasury", "KODEX200/KOSPI200 proxy", "Korean 20Y Treasury proxy"],
            "momentum": "For each asset, compare current month-end wealth/price with 1..12 months ago; score = positive comparisons/12.",
            "target_weight": "Each risky asset = 25% * score; residual = 0%-return cash.",
            "rebalance": "Annual; Dec month-end signal, next January holding month. No same-close execution.",
        },
        "implementation": {
            "primary_convention": "book-style native-currency return mixing; no FX translation in primary result",
            "cash_return": "0% (literal residual cash; no BIL substitution)",
            "cost_base": "5bp first entry; 10bp per traded notional at annual rebalance; taxes and FX conversion fees excluded",
            "risk_metrics": "monthly fallback because exact daily Korean 20Y total-return index is unavailable",
            "us_bond_extension": "synthetic 20Y constant-maturity from Treasury yields before TLT, then TLT Adj Close",
            "kr_equity_extension": "KOSPI200 price index before repo KODEX200 history, then KODEX200 Adj Close",
            "kr_bond_extension": "Before the first Korean 20Y observation, the repo-local 5Y yield series is used only as an explicit bridge and repriced at 5Y duration. From ECOS 20Y availability onward, the 20Y final-quotation yield is repriced at 20Y duration and the RETURN series are spliced. This avoids a false maturity-transition return; it is still not an official total-return index.",
        },
        "diagnostics": diag,
        "portfolio_stats": portstats,
        "book_comparison": book_compare,
        "oos_2022_to_latest": oos,
        "krw_translation_sensitivity": krw_sens,
        "timing_sensitivity": {
            p: {
                "CAGR_min": float(g.CAGR.min()),
                "CAGR_median": float(g.CAGR.median()),
                "CAGR_max": float(g.CAGR.max()),
                "MDD_min": float(g.MDD.min()),
                "MDD_median": float(g.MDD.median()),
                "MDD_max": float(g.MDD.max()),
            }
            for p, g in timing_df.groupby("period")
        },
        "limitations": [
            "Exact KR_GOVT_20Y_TR remains missing in the repository registry. From 20Y inception onward this run uses BOK ECOS 20Y Treasury yields to reconstruct the return of a rolling 20Y par bond, so it remains a reconstructed proxy rather than an official total-return index.",
            "Korean 20Y Treasury yield history begins in 2006, so 2005 book start necessarily uses a bridge proxy.",
            "Repository KODEX200 adjusted-price history starts in 2007, so earlier Korean-equity months use KOSPI200 price index.",
            "Primary book-style result mixes native-currency returns because the source rule does not specify FX treatment; KRW-translated sensitivity is reported separately.",
            "The standard windows end at the latest common month actually available across all four required assets; unavailable tail months are not fabricated.",
            "MDD/recovery are monthly fallback and can understate intramonth drawdowns.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
