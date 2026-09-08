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
OUT = ROOT / "results" / "kang_k_allweather_original"
OUT.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2000-01-31")
TODAY = pd.Timestamp.today().normalize()
END = (TODAY.replace(day=1) - pd.Timedelta(days=1)).normalize()
INITIAL_KRW = 10_000_000.0
ONE_WAY_COST = 0.0010

ASSETS = ["미국주식", "한국주식", "금", "한국10년국채", "미국10년국채"]

# 강환국 '한국형 올웨더' 원본(정적) 비중
STATIC_W = pd.Series({
    "미국주식": 0.175,
    "한국주식": 0.175,
    "금": 0.15,
    "한국10년국채": 0.25,
    "미국10년국채": 0.25,
})

# 강환국 개선안: 11~4월 주식 +7.5%p씩, 채권 -7.5%p씩 / 5~10월 반대
WINTER_W = pd.Series({
    "미국주식": 0.25,
    "한국주식": 0.25,
    "금": 0.15,
    "한국10년국채": 0.175,
    "미국10년국채": 0.175,
})
SUMMER_W = pd.Series({
    "미국주식": 0.10,
    "한국주식": 0.10,
    "금": 0.15,
    "한국10년국채": 0.325,
    "미국10년국채": 0.325,
})

ETF = {
    "미국주식": "360750.KS",    # TIGER 미국S&P500
    "한국주식": "294400.KS",    # KOSEF/KIWOOM 200TR
    "금": "132030.KS",          # KODEX 골드선물(H)
    "한국10년국채": "148070.KS",# KOSEF/KIWOOM 국고채10년
    "미국10년국채": "305080.KS",# TIGER 미국채10년선물
}


def setup_korean_font():
    names = [f.name for f in font_manager.fontManager.ttflist if "NanumGothic" in f.name]
    if names:
        rcParams["font.family"] = "NanumGothic"
    rcParams["axes.unicode_minus"] = False


def fred(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    d = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    v = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    return pd.Series(v.values, index=d, name=series_id).dropna().sort_index()


def yf_close(ticker: str, start="1999-10-01", adjusted=True) -> pd.Series:
    end = (END + pd.offsets.MonthEnd(1) + pd.Timedelta(days=10)).date().isoformat()
    try:
        df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False, threads=False)
        if df.empty:
            return pd.Series(dtype=float, name=ticker)
        if isinstance(df.columns, pd.MultiIndex):
            key = ("Adj Close", ticker) if adjusted and ("Adj Close", ticker) in df.columns else ("Close", ticker)
            if key in df.columns:
                s = df[key]
            else:
                level = "Adj Close" if adjusted else "Close"
                s = df.xs(level, level=0, axis=1).iloc[:, 0]
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


def ret(price: pd.Series) -> pd.Series:
    return price.pct_change(fill_method=None)


def par_bond_price(yield_decimal: float, coupon_rate: float, maturity_years: int) -> float:
    n = maturity_years * 2
    r = yield_decimal / 2.0
    c = 100.0 * coupon_rate / 2.0
    if abs(r) < 1e-12:
        return 100.0 + c * n
    return c * (1.0 - (1.0 + r) ** (-n)) / r + 100.0 * (1.0 + r) ** (-n)


def synthetic_bond_monthly(yield_pct: pd.Series, maturity_years=10) -> pd.Series:
    months = pd.date_range(START - pd.offsets.MonthEnd(1), END, freq="ME")
    y = yield_pct.resample("ME").last().reindex(months).ffill() / 100.0
    out = pd.Series(index=months, dtype=float)
    out.iloc[0] = 0.0
    for i in range(1, len(months)):
        y0, y1 = float(y.iloc[i-1]), float(y.iloc[i])
        # Constant-maturity approximation: a fresh par bond at prior yield, repriced one month later.
        px = par_bond_price(y1, y0, maturity_years)
        coupon_month = 100.0 * y0 / 12.0
        out.iloc[i] = (px + coupon_month) / 100.0 - 1.0
    return out


def splice_returns(proxy: pd.Series, ticker: str, label: str):
    etf_px = month_last(yf_close(ticker, adjusted=True))
    etf_ret = ret(etf_px)
    out = proxy.copy()
    common = out.index.intersection(etf_ret.dropna().index)
    first = None
    if len(common):
        out.loc[common] = etf_ret.loc[common]
        first = common.min()
        print(f"{label}: proxy -> {ticker} from {first.date()}")
    else:
        print(f"WARN {label}: no ETF overlap; proxy only")
    return out, first


def build_panel():
    months = pd.date_range(START - pd.offsets.MonthEnd(1), END, freq="ME")
    usdkrw = month_last(fred("DEXKOUS")).reindex(months).ffill()
    fx_ret = ret(usdkrw)
    switch = {}

    # US equity: unhedged USD exposure, then exact TIGER S&P500.
    spy = month_last(yf_close("SPY", adjusted=True)).reindex(months).ffill()
    us_proxy = ret(spy * usdkrw)
    us, switch["미국주식"] = splice_returns(us_proxy, ETF["미국주식"], "미국주식")

    # Korea equity: KOSPI200 price proxy -> KOSEF/KIWOOM 200TR ETF.
    ks200 = month_last(yf_close("^KS200", adjusted=False)).reindex(months).ffill()
    kr_proxy = ret(ks200)
    kr, switch["한국주식"] = splice_returns(kr_proxy, ETF["한국주식"], "한국주식")

    # Gold: original uses currency-hedged gold futures ETF.
    # Pre-ETF proxy is COMEX continuous gold futures return WITHOUT USD/KRW FX.
    gc = month_last(yf_close("GC=F", adjusted=True)).reindex(months).ffill()
    if gc.isna().all():
        # fallback: gold spot, still FX-neutral because original gold sleeve is hedged
        gc = month_last(fred("GOLDAMGBD228NLBM")).reindex(months).ffill()
    gold_proxy = ret(gc)
    gold, switch["금"] = splice_returns(gold_proxy, ETF["금"], "금")

    # Korea 10Y: synthetic constant-maturity 10Y -> exact 10Y ETF.
    kr10y_y = fred("IRLTLT01KRM156N")
    kr10_proxy = synthetic_bond_monthly(kr10y_y, 10).reindex(months).fillna(0.0)
    kr10, switch["한국10년국채"] = splice_returns(kr10_proxy, ETF["한국10년국채"], "한국10년국채")

    # US 10Y: synthetic constant-maturity Treasury total return + USD/KRW -> exact TIGER 10Y futures ETF.
    us10y_y = fred("GS10")
    us10_local = synthetic_bond_monthly(us10y_y, 10).reindex(months).fillna(0.0)
    us10_proxy = (1.0 + us10_local) * (1.0 + fx_ret) - 1.0
    us10, switch["미국10년국채"] = splice_returns(us10_proxy, ETF["미국10년국채"], "미국10년국채")

    panel = pd.concat([
        us.rename("미국주식"), kr.rename("한국주식"), gold.rename("금"),
        kr10.rename("한국10년국채"), us10.rename("미국10년국채")
    ], axis=1).reindex(months).loc[START:END]

    miss = panel.isna().sum()
    if miss.any():
        print("Missing counts:", miss[miss > 0].to_dict())
        if (miss > 2).any():
            raise RuntimeError(f"Material missing data: {miss[miss > 2].to_dict()}")
        panel = panel.fillna(0.0)

    return panel, switch


def target_timing(month: int) -> pd.Series:
    return WINTER_W if month in {11, 12, 1, 2, 3, 4} else SUMMER_W


def run_static(panel: pd.DataFrame, cost_rate=0.0):
    sleeves = INITIAL_KRW * STATIC_W
    nav = pd.Series(index=panel.index, dtype=float)
    pret = pd.Series(index=panel.index, dtype=float)
    turnover = pd.Series(0.0, index=panel.index)
    costs = pd.Series(0.0, index=panel.index)

    for i, dt in enumerate(panel.index):
        if i > 0 and dt.month == 1:
            before = sleeves.sum()
            target_vals = before * STATIC_W
            traded = (target_vals - sleeves).abs().sum()
            c = traded * cost_rate
            sleeves = (before - c) * STATIC_W
            turnover.loc[dt] = traded / before
            costs.loc[dt] = c
        before_ret = sleeves.sum()
        sleeves *= (1 + panel.loc[dt])
        after = sleeves.sum()
        pret.loc[dt] = after / before_ret - 1
        nav.loc[dt] = after
    return nav, pret, turnover, costs


def run_timing(panel: pd.DataFrame, cost_rate=0.0):
    sleeves = INITIAL_KRW * target_timing(panel.index[0].month)
    nav = pd.Series(index=panel.index, dtype=float)
    pret = pd.Series(index=panel.index, dtype=float)
    turnover = pd.Series(0.0, index=panel.index)
    costs = pd.Series(0.0, index=panel.index)

    for i, dt in enumerate(panel.index):
        # 월별 데이터로 10월 말/4월 말 체결을 각각 11월/5월 전체 수익률에 새 비중 적용으로 근사.
        if i > 0 and dt.month in {5, 11}:
            before = sleeves.sum()
            w = target_timing(dt.month)
            target_vals = before * w
            traded = (target_vals - sleeves).abs().sum()
            c = traded * cost_rate
            sleeves = (before - c) * w
            turnover.loc[dt] = traded / before
            costs.loc[dt] = c
        before_ret = sleeves.sum()
        sleeves *= (1 + panel.loc[dt])
        after = sleeves.sum()
        pret.loc[dt] = after / before_ret - 1
        nav.loc[dt] = after
    return nav, pret, turnover, costs


def recovery_months(nav):
    dd = nav / nav.cummax() - 1
    best = cur = 0
    for v in dd:
        if v < -1e-12:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def metrics(nav, ret_, turnover, cost_paid, name):
    years = len(ret_) / 12.0
    final = nav.iloc[-1]
    cagr = (final / INITIAL_KRW) ** (1 / years) - 1
    vol = ret_.std(ddof=1) * math.sqrt(12)
    dd = nav / nav.cummax() - 1
    mdd = dd.min()
    # Sharpe shown with rf=0 because original published summaries typically use raw-return Sharpe conventions inconsistently.
    sharpe0 = ret_.mean() / ret_.std(ddof=1) * math.sqrt(12) if ret_.std(ddof=1) > 0 else np.nan
    downside = ret_[ret_ < 0].std(ddof=1)
    sortino0 = ret_.mean() / downside * math.sqrt(12) if downside and downside > 0 else np.nan
    annual = (1 + ret_).groupby(ret_.index.year).prod() - 1
    reb = turnover[turnover > 0]
    return {
        "전략": name,
        "시작": nav.index[0].date().isoformat(),
        "종료": nav.index[-1].date().isoformat(),
        "초기자산_원": INITIAL_KRW,
        "최종자산_원": final,
        "누적수익률": final / INITIAL_KRW - 1,
        "CAGR": cagr,
        "연환산변동성": vol,
        "MDD": mdd,
        "최대손실회복기간_개월": recovery_months(nav),
        "Sharpe_rf0": sharpe0,
        "Sortino_rf0": sortino0,
        "Calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
        "월간승률": (ret_ > 0).mean(),
        "최악연도": int(annual.idxmin()),
        "최악연도수익률": annual.min(),
        "최고연도": int(annual.idxmax()),
        "최고연도수익률": annual.max(),
        "평균리밸런싱회전율": reb.mean() if len(reb) else 0.0,
        "누적거래비용_원": cost_paid.sum(),
    }


def subperiod_metrics(nav, ret_, end="2022-04-30"):
    n = nav.loc[:end]
    r = ret_.loc[:end]
    years = len(r) / 12.0
    cagr = (n.iloc[-1] / INITIAL_KRW) ** (1 / years) - 1
    mdd = (n / n.cummax() - 1).min()
    return cagr, mdd, n.iloc[-1]


def make_charts(navs):
    setup_korean_font()
    plt.figure(figsize=(12,7))
    for c in navs.columns:
        plt.plot(navs.index, navs[c] / 1e6, label=c, linewidth=1.8)
    plt.title("강환국 K-올웨더 원본 2개 - 누적자산")
    plt.ylabel("자산 (백만원)")
    plt.xlabel("연도")
    plt.grid(alpha=0.25); plt.legend(); plt.tight_layout()
    plt.savefig(OUT / "01_누적자산.png", dpi=180); plt.close()

    plt.figure(figsize=(12,7))
    for c in navs.columns:
        plt.plot(navs.index, np.log2(navs[c] / INITIAL_KRW), label=c, linewidth=1.8)
    ticks = np.arange(0, 5)
    plt.yticks(ticks, ["1배","2배","4배","8배","16배"])
    plt.title("강환국 K-올웨더 원본 2개 - 로그2 누적자산")
    plt.ylabel("초기자산 대비 배수")
    plt.xlabel("연도")
    plt.grid(alpha=0.25); plt.legend(); plt.tight_layout()
    plt.savefig(OUT / "02_로그2_배수축.png", dpi=180); plt.close()

    plt.figure(figsize=(12,7))
    for c in navs.columns:
        dd = navs[c] / navs[c].cummax() - 1
        plt.plot(navs.index, dd * 100, label=c, linewidth=1.6)
    plt.title("강환국 K-올웨더 원본 2개 - 낙폭")
    plt.ylabel("고점 대비 낙폭 (%)")
    plt.xlabel("연도")
    plt.grid(alpha=0.25); plt.legend(); plt.tight_layout()
    plt.savefig(OUT / "03_낙폭.png", dpi=180); plt.close()


def main():
    panel, switch = build_panel()
    panel.to_csv(OUT / "asset_returns_monthly.csv", encoding="utf-8-sig")
    pd.DataFrame({"proxy_to_etf_switch": switch}).to_csv(OUT / "proxy_to_etf_switches.csv", encoding="utf-8-sig")

    rows = []
    gross_navs = {}
    gross_rets = {}
    for cost_label, cost in [("0bp", 0.0), ("10bp_per_traded_notional", ONE_WAY_COST)]:
        for label, runner in [("강환국 정적 K-올웨더", run_static), ("강환국 계절형 K-올웨더", run_timing)]:
            nav, rr, turnover, costs = runner(panel, cost)
            m = metrics(nav, rr, turnover, costs, label)
            m["거래비용"] = cost_label
            rows.append(m)
            if cost == 0:
                gross_navs[label] = nav
                gross_rets[label] = rr

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")
    nav_df = pd.DataFrame(gross_navs)
    nav_df.to_csv(OUT / "nav_monthly_gross.csv", encoding="utf-8-sig")
    annual = pd.DataFrame({k: (1+v).groupby(v.index.year).prod()-1 for k,v in gross_rets.items()})
    annual.to_csv(OUT / "annual_returns_gross.csv", encoding="utf-8-sig")

    # Replication check against book-derived public summaries (2000.1~2022.4)
    checks=[]
    lit={
        "강환국 정적 K-올웨더": {"문헌_CAGR":0.079, "문헌_MDD":-0.072},
        "강환국 계절형 K-올웨더": {"문헌_CAGR":0.093, "문헌_MDD":-0.075},
    }
    for k in gross_navs:
        cagr, mdd, final = subperiod_metrics(gross_navs[k], gross_rets[k])
        checks.append({"전략":k,"재현_CAGR_2000_2022_04":cagr,"재현_MDD_2000_2022_04":mdd,"재현_최종자산_원":final,**lit[k]})
    pd.DataFrame(checks).to_csv(OUT / "replication_check_2000_2022_04.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame({
        "정적": STATIC_W,
        "계절형_11월~4월": WINTER_W,
        "계절형_5월~10월": SUMMER_W,
    }).to_csv(OUT / "weights.csv", encoding="utf-8-sig")

    make_charts(nav_df)

    readme = f"""강환국 한국형 K-올웨더 원본 2개 재현\n\n기간: {START.date()} ~ {END.date()}\n초기자산: 10,000,000원\n\n1) 정적 K-올웨더\n- 미국주식 17.5%, 한국주식 17.5%, 금 15%, 한국10년국채 25%, 미국10년국채 25%\n- 연 1회, 매년 1월 초 목표비중으로 리밸런싱\n\n2) 계절형 K-올웨더\n- 11~4월: 미국주식 25%, 한국주식 25%, 금 15%, 한국10년국채 17.5%, 미국10년국채 17.5%\n- 5~10월: 미국주식 10%, 한국주식 10%, 금 15%, 한국10년국채 32.5%, 미국10년국채 32.5%\n- 10월 말/4월 말 리밸런싱을 월별 데이터에서 각각 11월/5월 수익률부터 새 비중 적용으로 근사\n\n원본 ETF\n- TIGER 미국S&P500 (360750)\n- KOSEF/KIWOOM 200TR (294400)\n- KODEX 골드선물(H) (132030)\n- KOSEF/KIWOOM 국고채10년 (148070)\n- TIGER 미국채10년선물 (305080)\n\n프록시 한계\n- ETF 상장 전은 자산군 프록시를 사용: SPY*USD/KRW, KOSPI200, COMEX 금선물(환헤지 가정), FRED 10년 금리로 만든 합성 10년채.\n- 미국10년채 프록시는 합성 미국 10년채 수익률과 USD/KRW를 결합. 실제 TIGER 미국채10년선물의 선물 ER 롤 구조와 완전히 같지 않음.\n- 금 프록시는 실제 S&P GSCI Gold TR의 롤/담보수익을 완전히 복제하지 않음.\n- 따라서 2000~ETF 상장 전 성과는 '원본 규칙의 장기 프록시 재현'이며, ETF 실존기간 이후는 실제 ETF 조정종가를 우선 사용.\n"""
    (OUT / "README.txt").write_text(readme, encoding="utf-8")

    print(summary.to_string(index=False))
    print(pd.DataFrame(checks).to_string(index=False))


if __name__ == "__main__":
    main()
