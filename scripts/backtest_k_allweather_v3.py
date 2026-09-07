from __future__ import annotations

from pathlib import Path
import math
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "k_allweather_v3"
OUT.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2000-01-31")
# Use the last completed calendar month to avoid a partial-month 2026 observation.
TODAY = pd.Timestamp.today().normalize()
END = (TODAY.replace(day=1) - pd.Timedelta(days=1)).normalize()
INITIAL_KRW = 10_000_000.0
ONE_WAY_COST = 0.0010  # 10bp per traded notional sensitivity

ASSETS = [
    "미국주식", "한국주식", "중국주식", "인도주식",
    "금", "미국30년국채", "한국30년국채", "현금성자산"
]

WEIGHTS = {
    "성장형": {"미국주식":0.24,"한국주식":0.08,"중국주식":0.08,"인도주식":0.08,"금":0.19,"미국30년국채":0.14,"한국30년국채":0.14,"현금성자산":0.05},
    "중립형": {"미국주식":0.20,"한국주식":0.067,"중국주식":0.067,"인도주식":0.066,"금":0.16,"미국30년국채":0.12,"한국30년국채":0.12,"현금성자산":0.20},
    "안정형": {"미국주식":0.15,"한국주식":0.05,"중국주식":0.05,"인도주식":0.05,"금":0.12,"미국30년국채":0.09,"한국30년국채":0.09,"현금성자산":0.40},
}

ETF_TICKERS = {
    "미국주식": "379800.KS",      # KODEX 미국S&P500
    "한국주식": "294400.KS",      # KIWOOM 200TR
    "중국주식": "283580.KS",      # KODEX 차이나CSI300
    "인도주식": "453810.KS",      # KODEX 인도Nifty50
    "금": "411060.KS",            # ACE KRX금현물
    "미국30년국채": "464470.KS",  # PLUS 미국채30년액티브
    "한국30년국채": "385560.KS",  # RISE KIS국고채30년Enhanced
    "현금성자산": "497880.KS",    # SOL CD금리&머니마켓액티브
}


def setup_korean_font():
    candidates = [f.fname for f in font_manager.fontManager.ttflist if "NanumGothic" in f.name]
    if candidates:
        rcParams["font.family"] = "NanumGothic"
    rcParams["axes.unicode_minus"] = False


def fred(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    s = pd.to_numeric(df[val_col], errors="coerce")
    out = pd.Series(s.values, index=df[date_col], name=series_id).dropna().sort_index()
    return out


def yf_close(ticker: str, start="1999-11-01", end=None, adjusted=True) -> pd.Series:
    if end is None:
        end = (END + pd.offsets.MonthEnd(1) + pd.Timedelta(days=7)).date().isoformat()
    try:
        df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False, threads=False)
        if df.empty:
            return pd.Series(dtype=float, name=ticker)
        if isinstance(df.columns, pd.MultiIndex):
            # yfinance may return ('Adj Close', ticker)
            if adjusted and ("Adj Close", ticker) in df.columns:
                s = df[("Adj Close", ticker)]
            elif ("Close", ticker) in df.columns:
                s = df[("Close", ticker)]
            else:
                s = df.xs("Adj Close" if adjusted else "Close", level=0, axis=1).iloc[:, 0]
        else:
            col = "Adj Close" if adjusted and "Adj Close" in df.columns else "Close"
            s = df[col]
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return pd.to_numeric(s, errors="coerce").dropna().rename(ticker)
    except Exception as e:
        print(f"WARN yfinance {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def month_last(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    return s.sort_index().resample("ME").last().loc[:END]


def returns_from_price(price: pd.Series) -> pd.Series:
    return price.pct_change(fill_method=None)


def splice_returns(base_ret: pd.Series, etf_ticker: str, label: str) -> tuple[pd.Series, pd.Timestamp | None]:
    etf = month_last(yf_close(etf_ticker, adjusted=True))
    if etf.empty:
        print(f"WARN {label}: ETF {etf_ticker} unavailable, using proxy only")
        return base_ret.copy(), None
    etf_ret = returns_from_price(etf)
    out = base_ret.copy()
    common = etf_ret.dropna().index.intersection(out.index)
    if len(common):
        out.loc[common] = etf_ret.loc[common]
        first = common.min()
        print(f"{label}: switched to {etf_ticker} from {first.date()}")
        return out, first
    return out, None


def par_bond_price(yield_decimal: float, coupon_rate: float, maturity_years: int) -> float:
    n = maturity_years * 2
    r = yield_decimal / 2.0
    c = 100.0 * coupon_rate / 2.0
    if abs(r) < 1e-12:
        return 100.0 + c * n
    return c * (1.0 - (1.0 + r) ** (-n)) / r + 100.0 * (1.0 + r) ** (-n)


def synthetic_bond_monthly(yield_pct: pd.Series, maturity_years: int) -> pd.Series:
    y = yield_pct.resample("ME").last().ffill().loc[START - pd.offsets.MonthEnd(1):END] / 100.0
    ret = pd.Series(index=y.index, dtype=float)
    ret.iloc[0] = 0.0
    for i in range(1, len(y)):
        y0, y1 = float(y.iloc[i-1]), float(y.iloc[i])
        price = par_bond_price(y1, y0, maturity_years)
        coupon_month = 100.0 * y0 / 12.0
        ret.iloc[i] = (price + coupon_month) / 100.0 - 1.0
    return ret.rename(f"SYN_BOND_{maturity_years}Y")


def build_panel() -> tuple[pd.DataFrame, pd.Series, dict]:
    months = pd.date_range(START - pd.offsets.MonthEnd(1), END, freq="ME")

    # FX: KRW per USD, CNY per USD, INR per USD -> KRW per local currency.
    usdkrw = month_last(fred("DEXKOUS")).reindex(months).ffill()
    cnyusd = month_last(fred("DEXCHUS")).reindex(months).ffill()
    inrusd = month_last(fred("DEXINUS")).reindex(months).ffill()
    cnykrw = usdkrw / cnyusd
    inrkrw = usdkrw / inrusd

    switch_dates = {}

    # US stock total return proxy: SPY adjusted close in USD, unhedged to KRW.
    spy = month_last(yf_close("SPY", adjusted=True)).reindex(months).ffill()
    us_stock_proxy = returns_from_price(spy * usdkrw)
    us_stock, switch_dates["미국주식"] = splice_returns(us_stock_proxy, ETF_TICKERS["미국주식"], "미국주식")

    # Korea stock: KOSPI200 price before KODEX200, then KODEX200 adjusted, then KIWOOM200TR.
    ks200 = month_last(yf_close("^KS200", adjusted=False)).reindex(months)
    kodex200 = month_last(yf_close("069500.KS", adjusted=True)).reindex(months)
    kr_price = ks200.copy()
    kr_price.loc[kodex200.notna()] = kodex200.loc[kodex200.notna()]
    kr_price = kr_price.ffill()
    kr_stock_proxy = returns_from_price(kr_price)
    kr_stock, switch_dates["한국주식"] = splice_returns(kr_stock_proxy, ETF_TICKERS["한국주식"], "한국주식")

    # China: Shanghai Composite before CSI300 availability; currency-unhedged to KRW.
    shcomp = month_last(yf_close("000001.SS", adjusted=False)).reindex(months)
    csi300 = month_last(yf_close("000300.SS", adjusted=False)).reindex(months)
    china_local = shcomp.copy()
    china_local.loc[csi300.notna()] = csi300.loc[csi300.notna()]
    china_local = china_local.ffill()
    china_proxy = returns_from_price(china_local * cnykrw)
    china, switch_dates["중국주식"] = splice_returns(china_proxy, ETF_TICKERS["중국주식"], "중국주식")

    # India: Sensex fallback before Nifty50 availability; currency-unhedged to KRW.
    sensex = month_last(yf_close("^BSESN", adjusted=False)).reindex(months)
    nifty = month_last(yf_close("^NSEI", adjusted=False)).reindex(months)
    india_local = sensex.copy()
    india_local.loc[nifty.notna()] = nifty.loc[nifty.notna()]
    india_local = india_local.ffill()
    india_proxy = returns_from_price(india_local * inrkrw)
    india, switch_dates["인도주식"] = splice_returns(india_proxy, ETF_TICKERS["인도주식"], "인도주식")

    # Gold: LBMA PM USD spot from FRED, unhedged to KRW.
    gold_usd = month_last(fred("GOLDPMGBD228NLBM")).reindex(months).ffill()
    gold_proxy = returns_from_price(gold_usd * usdkrw)
    gold, switch_dates["금"] = splice_returns(gold_proxy, ETF_TICKERS["금"], "금")

    # US long Treasury: synthetic 20Y before TLT, then TLT adjusted; all unhedged to KRW.
    us20y = fred("GS20")
    us_bond_syn = synthetic_bond_monthly(us20y, 20).reindex(months).fillna(0.0)
    tlt = month_last(yf_close("TLT", adjusted=True)).reindex(months)
    tlt_ret = returns_from_price(tlt)
    us_bond_usd_ret = us_bond_syn.copy()
    us_bond_usd_ret.loc[tlt_ret.notna()] = tlt_ret.loc[tlt_ret.notna()]
    # Combine local bond return with FX return exactly: (1+r_bond)*(1+r_fx)-1.
    fx_ret = returns_from_price(usdkrw)
    us_bond_proxy = (1.0 + us_bond_usd_ret) * (1.0 + fx_ret) - 1.0
    us_bond, switch_dates["미국30년국채"] = splice_returns(us_bond_proxy, ETF_TICKERS["미국30년국채"], "미국30년국채")

    # Korea 30Y: pre-ETF proxy from OECD 10Y benchmark yield, priced as a flat-curve 30Y par bond.
    # This is the largest historical approximation because Korean 30Y government bonds / Enhanced ETF did not exist in 2000.
    kr10y = fred("IRLTLT01KRM156N")
    kr_bond_proxy = synthetic_bond_monthly(kr10y, 30).reindex(months).fillna(0.0)
    kr_bond, switch_dates["한국30년국채"] = splice_returns(kr_bond_proxy, ETF_TICKERS["한국30년국채"], "한국30년국채")

    # KRW cash: 3M interbank rate accrued monthly, then exact SOL ETF when available.
    kr3m = fred("IR3TIB01KRM156N").resample("ME").last().reindex(months).ffill() / 100.0
    cash_ret = pd.Series(index=months, dtype=float)
    cash_ret.iloc[0] = 0.0
    for i in range(1, len(months)):
        days = (months[i] - months[i-1]).days
        cash_ret.iloc[i] = (1.0 + float(kr3m.iloc[i-1])) ** (days / 365.2425) - 1.0
    cash, switch_dates["현금성자산"] = splice_returns(cash_ret, ETF_TICKERS["현금성자산"], "현금성자산")

    panel = pd.concat([
        us_stock.rename("미국주식"), kr_stock.rename("한국주식"), china.rename("중국주식"), india.rename("인도주식"),
        gold.rename("금"), us_bond.rename("미국30년국채"), kr_bond.rename("한국30년국채"), cash.rename("현금성자산")
    ], axis=1).reindex(months)

    panel = panel.loc[START:END]
    # Do not silently drop missing data.
    miss = panel.isna().sum()
    if miss.any():
        print("Missing counts before conservative fill:")
        print(miss[miss > 0])
        # Only very short holes are filled with 0 monthly return after surrounding series were ffilled.
        # This prevents a single exchange-calendar mismatch from killing the whole run.
        if (miss > 2).any():
            raise RuntimeError(f"Material unresolved missing data: {miss[miss > 2].to_dict()}")
        panel = panel.fillna(0.0)

    rf = cash.reindex(panel.index).fillna(0.0)
    return panel, rf, switch_dates


def backtest(asset_ret: pd.DataFrame, weights: dict[str,float], rebalance: str, cost_rate: float):
    w = pd.Series(weights, dtype=float).reindex(ASSETS)
    assert abs(w.sum() - 1.0) < 1e-9
    sleeves = INITIAL_KRW * w.copy()
    nav = pd.Series(index=asset_ret.index, dtype=float)
    pret = pd.Series(index=asset_ret.index, dtype=float)
    nav_prev = INITIAL_KRW
    turnovers = []

    for i, dt in enumerate(asset_ret.index):
        # Rebalance at the beginning of the month: January for annual, every month for monthly.
        do_rebal = (rebalance == "monthly") or (rebalance == "annual" and dt.month == 1)
        if do_rebal:
            before = float(sleeves.sum())
            target = before * w
            traded = float((target - sleeves).abs().sum())
            turnover = traded / before if before else 0.0
            cost = traded * cost_rate
            sleeves = target.copy()
            if cost > 0:
                sleeves *= (before - cost) / before
            turnovers.append(turnover)

        sleeves *= (1.0 + asset_ret.loc[dt, ASSETS])
        nav_now = float(sleeves.sum())
        nav.loc[dt] = nav_now
        pret.loc[dt] = nav_now / nav_prev - 1.0
        nav_prev = nav_now

    return nav, pret, turnovers


def recovery_months(nav: pd.Series) -> int:
    peak = nav.cummax()
    dd = nav / peak - 1.0
    longest = cur = 0
    for x in dd:
        if x < -1e-12:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return int(longest)


def calc_metrics(nav, ret, rf, turnovers):
    years = len(ret) / 12.0
    final = float(nav.iloc[-1])
    cagr = (final / INITIAL_KRW) ** (1.0 / years) - 1.0
    vol = float(ret.std(ddof=1) * math.sqrt(12.0))
    dd = nav / nav.cummax() - 1.0
    mdd = float(dd.min())
    excess = ret - rf.reindex(ret.index).fillna(0.0)
    sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(12.0)) if excess.std(ddof=1) > 0 else np.nan
    downside = ret[ret < 0].std(ddof=1)
    sortino = float((ret.mean() - rf.mean()) / downside * math.sqrt(12.0)) if downside and downside > 0 else np.nan
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    ann = (1.0 + ret).groupby(ret.index.year).prod() - 1.0
    return {
        "시작": nav.index[0].date().isoformat(),
        "종료": nav.index[-1].date().isoformat(),
        "초기자산_원": INITIAL_KRW,
        "최종자산_원": final,
        "누적수익률": final / INITIAL_KRW - 1.0,
        "CAGR": cagr,
        "연환산변동성": vol,
        "MDD": mdd,
        "최대손실회복기간_개월": recovery_months(nav),
        "Sharpe_현금초과": sharpe,
        "Sortino": sortino,
        "Calmar": calmar,
        "월간승률": float((ret > 0).mean()),
        "최악연도": int(ann.idxmin()),
        "최악연도수익률": float(ann.min()),
        "최고연도": int(ann.idxmax()),
        "최고연도수익률": float(ann.max()),
        "평균리밸런싱회전율": float(np.mean(turnovers)) if turnovers else 0.0,
    }


def make_charts(navs: pd.DataFrame):
    setup_korean_font()
    # 1) 누적 자산
    plt.figure(figsize=(12,7))
    for c in navs.columns:
        plt.plot(navs.index, navs[c] / 1e6, label=c, linewidth=1.8)
    plt.title("K-올웨더 3종 비교 - 누적 자산")
    plt.ylabel("자산 (백만원)")
    plt.xlabel("연도")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "01_누적자산.png", dpi=180)
    plt.close()

    # 2) 로그2 자산
    plt.figure(figsize=(12,7))
    for c in navs.columns:
        plt.plot(navs.index, np.log2(navs[c] / INITIAL_KRW), label=c, linewidth=1.8)
    plt.axhline(0, linewidth=0.8)
    plt.title("K-올웨더 3종 비교 - 로그2 누적자산")
    plt.ylabel("log2(자산 / 초기자산)  [1 = 2배, 2 = 4배]")
    plt.xlabel("연도")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "02_로그2누적자산.png", dpi=180)
    plt.close()

    # 3) Drawdown
    plt.figure(figsize=(12,7))
    for c in navs.columns:
        dd = navs[c] / navs[c].cummax() - 1.0
        plt.plot(navs.index, dd * 100, label=c, linewidth=1.5)
    plt.title("K-올웨더 3종 비교 - 낙폭(Drawdown)")
    plt.ylabel("고점 대비 낙폭 (%)")
    plt.xlabel("연도")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "03_낙폭.png", dpi=180)
    plt.close()


def main():
    print(f"Backtest requested window: {START.date()} ~ {END.date()}")
    panel, rf, switches = build_panel()
    panel.to_csv(OUT / "asset_returns_monthly.csv", encoding="utf-8-sig")

    weight_df = pd.DataFrame(WEIGHTS).T[ASSETS]
    weight_df.to_csv(OUT / "weights.csv", encoding="utf-8-sig")

    all_metrics = []
    annual_rets = {}
    annual_navs = {}

    for profile in ["성장형", "중립형", "안정형"]:
        # Primary = annual rebalance, gross.
        nav, ret, turnovers = backtest(panel, WEIGHTS[profile], "annual", 0.0)
        annual_navs[profile] = nav
        annual_rets[profile] = (1.0 + ret).groupby(ret.index.year).prod() - 1.0
        m = calc_metrics(nav, ret, rf, turnovers)
        m.update({"유형":profile,"리밸런싱":"연1회(매년1월)","거래비용":"0bp"})
        all_metrics.append(m)

        # Net cost sensitivity.
        nav_c, ret_c, turns_c = backtest(panel, WEIGHTS[profile], "annual", ONE_WAY_COST)
        m_c = calc_metrics(nav_c, ret_c, rf, turns_c)
        m_c.update({"유형":profile,"리밸런싱":"연1회(매년1월)","거래비용":"10bp/매매금액"})
        all_metrics.append(m_c)

        # Monthly rebalance robustness sensitivity, gross.
        nav_m, ret_m, turns_m = backtest(panel, WEIGHTS[profile], "monthly", 0.0)
        m_m = calc_metrics(nav_m, ret_m, rf, turns_m)
        m_m.update({"유형":profile,"리밸런싱":"매월","거래비용":"0bp"})
        all_metrics.append(m_m)

    navs = pd.DataFrame(annual_navs)
    navs.to_csv(OUT / "nav_monthly_primary_annual_rebalance.csv", encoding="utf-8-sig")
    pd.DataFrame(annual_rets).to_csv(OUT / "annual_returns_primary.csv", encoding="utf-8-sig")

    metrics_df = pd.DataFrame(all_metrics)
    ordered = ["유형","리밸런싱","거래비용","시작","종료","초기자산_원","최종자산_원","누적수익률","CAGR","연환산변동성","MDD","최대손실회복기간_개월","Sharpe_현금초과","Sortino","Calmar","월간승률","최악연도","최악연도수익률","최고연도","최고연도수익률","평균리밸런싱회전율"]
    metrics_df[ordered].to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")

    switch_df = pd.DataFrame({"자산":list(switches.keys()), "실제ETF_전환일":[d.date().isoformat() if d is not None else "미전환" for d in switches.values()], "ETF": [ETF_TICKERS[k] for k in switches.keys()]})
    switch_df.to_csv(OUT / "proxy_to_etf_switches.csv", index=False, encoding="utf-8-sig")

    make_charts(navs)

    notes = f"""K-올웨더 v3 백테스트\n기간: {START.date()} ~ {END.date()} (마지막 완료 월)\n초기자산: 10,000,000원\n기본 리밸런싱: 연 1회, 매년 1월 초 목표비중 복원\n기본 비용: 0bp, 민감도: 거래금액당 10bp\n수익률 빈도: 월간\n\n중요한 장기 프록시 한계\n- 2000년에 현재 ETF들은 존재하지 않았으므로 ETF 상장 전은 지수/금리 프록시 사용. 상장 후에는 가능한 한 실제 국내 ETF 수정주가로 자동 전환.\n- 한국 30년 국채는 2000년부터 동일 상품이 존재하지 않아, 상장 전 구간을 OECD 한국 10년 국채수익률로 30년 만기 평탄수익률곡선(par bond) 프록시를 합성. 실제 RISE KIS국고채30년Enhanced는 30% RP 차입으로 노출을 높이는 구조라 과거 프록시와 완전히 동일하지 않음.\n- 중국/인도 지수의 ETF 상장 전 장기 구간은 가격지수 기반이라 배당 재투자를 완전 반영하지 못할 수 있음. 따라서 장기 CAGR을 다소 보수적으로 추정할 가능성.\n- 중국 CSI300 이전에는 상하이종합, 인도 Nifty50 데이터가 비는 초기 구간에는 Sensex를 사용.\n- MDD/변동성은 월말 관측 기준. 일중/일간 최대 낙폭보다 작게 보일 수 있음.\n"""
    (OUT / "README.txt").write_text(notes, encoding="utf-8")

    primary = metrics_df[(metrics_df["리밸런싱"] == "연1회(매년1월)") & (metrics_df["거래비용"] == "0bp")]
    print("\n=== PRIMARY RESULTS ===")
    print(primary[["유형","최종자산_원","CAGR","연환산변동성","MDD","Sharpe_현금초과","최대손실회복기간_개월"]].to_string(index=False))


if __name__ == "__main__":
    main()
