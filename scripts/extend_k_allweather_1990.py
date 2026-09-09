from __future__ import annotations

from pathlib import Path
import math
import re
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "k_allweather_1990"
OUT.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("1990-01-31")
EARLY_END = pd.Timestamp("1999-12-31")
INITIAL = 10_000_000.0
COST = 0.001  # 10bp per traded notional

LATEST_FILE = ROOT / "results" / "k_allweather_v3" / "asset_returns_monthly.csv"
KANG_FILE = ROOT / "results" / "kang_k_allweather_original" / "asset_returns_monthly.csv"

LATEST_W = pd.Series({
    "미국주식": 0.24, "한국주식": 0.08, "중국주식": 0.08, "인도주식": 0.08,
    "금": 0.19, "미국30년국채": 0.14, "한국30년국채": 0.14, "현금성자산": 0.05,
})

KANG_STATIC = pd.Series({
    "미국주식": 0.175, "한국주식": 0.175, "금": 0.15,
    "한국10년국채": 0.25, "미국10년국채": 0.25,
})
KANG_WINTER = pd.Series({
    "미국주식": 0.25, "한국주식": 0.25, "금": 0.15,
    "한국10년국채": 0.175, "미국10년국채": 0.175,
})
KANG_SUMMER = pd.Series({
    "미국주식": 0.10, "한국주식": 0.10, "금": 0.15,
    "한국10년국채": 0.325, "미국10년국채": 0.325,
})
KR_WINTER = pd.Series({
    "미국주식": 0.175, "한국주식": 0.25, "금": 0.15,
    "한국10년국채": 0.2125, "미국10년국채": 0.2125,
})
KR_SUMMER = pd.Series({
    "미국주식": 0.175, "한국주식": 0.10, "금": 0.15,
    "한국10년국채": 0.2875, "미국10년국채": 0.2875,
})


def fred(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    dt = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    val = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    return pd.Series(val.values, index=dt, name=series_id).dropna().sort_index()


def month_last(s: pd.Series) -> pd.Series:
    return s.sort_index().resample("ME").last() if not s.empty else s


def yf_close(ticker: str, start="1989-11-01", end="2000-02-15") -> pd.Series:
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False, threads=False)
    if df.empty:
        raise RuntimeError(f"Yahoo data unavailable: {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        if ("Adj Close", ticker) in df.columns:
            s = df[("Adj Close", ticker)]
        else:
            s = df.xs("Adj Close", level=0, axis=1).iloc[:, 0]
    else:
        s = df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return pd.to_numeric(s, errors="coerce").dropna()


def par_price(y1: float, coupon: float, maturity_years: int) -> float:
    n = maturity_years * 2
    r = y1 / 2.0
    c = 100.0 * coupon / 2.0
    if abs(r) < 1e-12:
        return 100.0 + c * n
    return c * (1.0 - (1.0 + r) ** (-n)) / r + 100.0 * (1.0 + r) ** (-n)


def synthetic_bond(yield_pct: pd.Series, maturity_years: int, months: pd.DatetimeIndex) -> pd.Series:
    y = month_last(yield_pct).reindex(months).ffill() / 100.0
    out = pd.Series(index=months, dtype=float)
    out.iloc[0] = 0.0
    for i in range(1, len(months)):
        y0, y1 = float(y.iloc[i - 1]), float(y.iloc[i])
        p = par_price(y1, y0, maturity_years)
        out.iloc[i] = (p + 100.0 * y0 / 12.0) / 100.0 - 1.0
    return out


def china_monthly_index() -> pd.Series:
    # Public monthly Shanghai Composite history. Jan-1991 is the first monthly observation.
    url = "https://www.forecasts.org/data/data/shangcompM.htm"
    txt = requests.get(url, timeout=30).text
    pat = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2})\s+([0-9]+(?:\.[0-9]+)?)", re.I)
    month_no = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
    rows = []
    for mon, yy, value in pat.findall(txt):
        year = 1900 + int(yy) if int(yy) >= 90 else 2000 + int(yy)
        if 1991 <= year <= 1999:
            rows.append((pd.Timestamp(year=year, month=month_no[mon.title()], day=1) + pd.offsets.MonthEnd(0), float(value)))
    if len(rows) < 90:
        # HTML can contain tags between cells; fallback through read_html.
        for tab in pd.read_html(url):
            flat = tab.astype(str).agg(" ".join, axis=1)
            for line in flat:
                m = pat.search(line)
                if m:
                    mon, yy, value = m.groups()
                    year = 1900 + int(yy) if int(yy) >= 90 else 2000 + int(yy)
                    if 1991 <= year <= 1999:
                        rows.append((pd.Timestamp(year=year, month=month_no[mon.title()], day=1) + pd.offsets.MonthEnd(0), float(value)))
    s = pd.Series(dict(rows)).sort_index()
    if s.index.duplicated().any():
        s = s[~s.index.duplicated(keep="first")]
    if s.loc["1991":"1999"].shape[0] < 100:
        raise RuntimeError(f"Shanghai monthly history insufficient: {s.shape[0]} observations")
    return s


def build_early_panels() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    months_ext = pd.date_range(pd.Timestamp("1989-12-31"), EARLY_END, freq="ME")
    months = months_ext[1:]

    usdkrw = month_last(fred("DEXKOUS")).reindex(months_ext).ffill()
    cnyusd = month_last(fred("DEXCHUS")).reindex(months_ext).ffill()
    inrusd = month_last(fred("DEXINUS")).reindex(months_ext).ffill()
    fx_usd = usdkrw.pct_change(fill_method=None)
    cnykrw = usdkrw / cnyusd
    inrkrw = usdkrw / inrusd
    fx_cny = cnykrw.pct_change(fill_method=None)
    fx_inr = inrkrw.pct_change(fill_method=None)

    # U.S. equity total-return proxy: Vanguard 500 Index mutual fund, unhedged to KRW.
    vfinx = month_last(yf_close("VFINX")).reindex(months_ext).ffill()
    us_local = vfinx.pct_change(fill_method=None)
    us = ((1 + us_local) * (1 + fx_usd) - 1).reindex(months)

    # Korea: OECD broad share-price monthly return (price return).
    kr = (fred("SPASTT01KRM657N").reindex(months_ext, method="ffill") / 100.0).reindex(months)

    # India: OECD broad share-price monthly price return + INR/KRW FX.
    india_local = (fred("SPASTT01INM657N").reindex(months_ext, method="ffill") / 100.0)
    india = ((1 + india_local) * (1 + fx_inr) - 1).reindex(months)

    # KRW cash: 3M interbank from 1991; 1990 uses IMF discount rate as explicit fallback.
    kr3m = month_last(fred("IR3TIB01KRM156N")).reindex(months_ext)
    disc = month_last(fred("INTDSRKRM193N")).reindex(months_ext).ffill()
    rate = kr3m.combine_first(disc).ffill() / 100.0
    cash = pd.Series(index=months_ext, dtype=float)
    cash.iloc[0] = 0.0
    for i in range(1, len(months_ext)):
        days = (months_ext[i] - months_ext[i - 1]).days
        cash.iloc[i] = (1 + float(rate.iloc[i - 1])) ** (days / 365.2425) - 1
    cash = cash.reindex(months)

    # China: actual market only from 1991 monthly series; before Feb-1991 keep this sleeve in KRW cash.
    china_idx = china_monthly_index().reindex(months_ext)
    china_local = china_idx.pct_change(fill_method=None)
    china = ((1 + china_local) * (1 + fx_cny) - 1).reindex(months)
    china.loc[:pd.Timestamp("1991-01-31")] = cash.loc[:pd.Timestamp("1991-01-31")]
    if china.loc[pd.Timestamp("1991-02-28"):].isna().any():
        raise RuntimeError(f"China early missing months: {china[china.isna()].index.tolist()}")

    # Gold spot USD, unhedged to KRW.
    gold_usd = month_last(fred("GOLDPMGBD228NLBM")).reindex(months_ext).ffill()
    gold = (gold_usd * usdkrw).pct_change(fill_method=None).reindex(months)

    # U.S. long bond: 30Y Treasury constant-maturity yield for 1990s, priced as 30Y par bond, unhedged.
    us30_local = synthetic_bond(fred("GS30"), 30, months_ext)
    us30 = ((1 + us30_local) * (1 + fx_usd) - 1).reindex(months)
    us10_local = synthetic_bond(fred("GS10"), 10, months_ext)
    us10 = ((1 + us10_local) * (1 + fx_usd) - 1).reindex(months)

    # Korea long-bond early proxy: OECD housing-bond yield (monthly from 1987), flat-curve priced.
    # It is a long-ish domestic bond proxy, not a claim that 10Y/30Y KTBs existed in 1990.
    kr_long_y = fred("IRLOHO01KRM156N")
    kr10 = synthetic_bond(kr_long_y, 10, months_ext).reindex(months)
    kr30 = synthetic_bond(kr_long_y, 30, months_ext).reindex(months)

    latest = pd.concat([
        us.rename("미국주식"), kr.rename("한국주식"), china.rename("중국주식"), india.rename("인도주식"),
        gold.rename("금"), us30.rename("미국30년국채"), kr30.rename("한국30년국채"), cash.rename("현금성자산")
    ], axis=1).reindex(months)

    kang = pd.concat([
        us.rename("미국주식"), kr.rename("한국주식"), gold.rename("금"),
        kr10.rename("한국10년국채"), us10.rename("미국10년국채")
    ], axis=1).reindex(months)

    for name, p in [("latest_early", latest), ("kang_early", kang)]:
        miss = p.isna().sum()
        if miss.any():
            raise RuntimeError(f"{name} unresolved missing: {miss[miss>0].to_dict()}")

    return latest, kang, cash


def load_full_panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    early_latest, early_kang, _ = build_early_panels()
    late_latest = pd.read_csv(LATEST_FILE, index_col=0, parse_dates=True, encoding="utf-8-sig")
    late_kang = pd.read_csv(KANG_FILE, index_col=0, parse_dates=True, encoding="utf-8-sig")
    late_latest = late_latest.loc[late_latest.index >= pd.Timestamp("2000-01-31")]
    late_kang = late_kang.loc[late_kang.index >= pd.Timestamp("2000-01-31")]
    latest = pd.concat([early_latest, late_latest], axis=0).sort_index()
    kang = pd.concat([early_kang, late_kang], axis=0).sort_index()
    if latest.index.min() != START or kang.index.min() != START:
        raise RuntimeError("Start date mismatch")
    return latest, kang


def run_annual(panel: pd.DataFrame, weights: pd.Series, cost=0.0):
    w = weights.reindex(panel.columns)
    sleeves = INITIAL * w
    nav=[]; rr=[]; to=[]; cs=[]
    for i,(dt,r) in enumerate(panel.iterrows()):
        turn=0.0; c=0.0
        if i>0 and dt.month==1:
            before=sleeves.sum(); tgt=before*w; traded=(tgt-sleeves).abs().sum(); c=traded*cost
            sleeves=(before-c)*w; turn=traded/before
        before=sleeves.sum(); sleeves*=1+r; after=sleeves.sum()
        nav.append(after); rr.append(after/before-1); to.append(turn); cs.append(c)
    ix=panel.index
    return pd.Series(nav,index=ix),pd.Series(rr,index=ix),pd.Series(to,index=ix),pd.Series(cs,index=ix)


def season_target(month: int, winter: pd.Series, summer: pd.Series):
    return winter if month in {11,12,1,2,3,4} else summer


def run_seasonal(panel: pd.DataFrame, winter: pd.Series, summer: pd.Series, cost=0.0):
    winter=winter.reindex(panel.columns); summer=summer.reindex(panel.columns)
    sleeves=INITIAL*season_target(panel.index[0].month,winter,summer)
    nav=[]; rr=[]; to=[]; cs=[]
    for i,(dt,r) in enumerate(panel.iterrows()):
        turn=0.0; c=0.0
        if i>0 and dt.month in {5,11}:
            before=sleeves.sum(); w=season_target(dt.month,winter,summer); tgt=before*w
            traded=(tgt-sleeves).abs().sum(); c=traded*cost; sleeves=(before-c)*w; turn=traded/before
        before=sleeves.sum(); sleeves*=1+r; after=sleeves.sum()
        nav.append(after); rr.append(after/before-1); to.append(turn); cs.append(c)
    ix=panel.index
    return pd.Series(nav,index=ix),pd.Series(rr,index=ix),pd.Series(to,index=ix),pd.Series(cs,index=ix)


def run_kr_mintrade(panel: pd.DataFrame, cost=0.0):
    winter=KR_WINTER.reindex(panel.columns); summer=KR_SUMMER.reindex(panel.columns)
    sleeves=INITIAL*winter
    subset=["한국주식","한국10년국채","미국10년국채"]
    nav=[]; rr=[]; to=[]; cs=[]
    for i,(dt,r) in enumerate(panel.iterrows()):
        turn=0.0; c=0.0
        if i>0 and dt.month in {5,11}:
            before=sleeves.sum(); w=season_target(dt.month,winter,summer)
            sub_total=sleeves[subset].sum(); sw=w[subset]/w[subset].sum(); tgt=sub_total*sw
            traded=(tgt-sleeves[subset]).abs().sum(); c=traded*cost
            sleeves.loc[subset]=(sub_total-c)*sw; turn=traded/before
        before=sleeves.sum(); sleeves*=1+r; after=sleeves.sum()
        nav.append(after); rr.append(after/before-1); to.append(turn); cs.append(c)
    ix=panel.index
    return pd.Series(nav,index=ix),pd.Series(rr,index=ix),pd.Series(to,index=ix),pd.Series(cs,index=ix)


def run_latest_us30_seasonal(panel: pd.DataFrame, cost=0.0):
    growth=LATEST_W.reindex(panel.columns)
    bond=pd.Series(0.0,index=panel.columns); bond["미국30년국채"]=1.0
    # Match the previous experiment: initialize Growth in January, first switch to US30Y in May.
    sleeves=INITIAL*growth
    nav=[]; rr=[]; to=[]; cs=[]
    for i,(dt,r) in enumerate(panel.iterrows()):
        turn=0.0; c=0.0
        if i>0 and dt.month in {5,11}:
            w=bond if dt.month==5 else growth
            before=sleeves.sum(); tgt=before*w; traded=(tgt-sleeves).abs().sum(); c=traded*cost
            sleeves=(before-c)*w; turn=traded/before
        before=sleeves.sum(); sleeves*=1+r; after=sleeves.sum()
        nav.append(after); rr.append(after/before-1); to.append(turn); cs.append(c)
    ix=panel.index
    return pd.Series(nav,index=ix),pd.Series(rr,index=ix),pd.Series(to,index=ix),pd.Series(cs,index=ix)


def recovery(nav: pd.Series) -> int:
    dd=nav/nav.cummax()-1; cur=best=0
    for v in dd:
        if v < -1e-12: cur += 1; best=max(best,cur)
        else: cur=0
    return best


def metrics(nav, rr, to, costs):
    years=len(rr)/12.0; final=float(nav.iloc[-1]); vol=float(rr.std(ddof=1)*math.sqrt(12))
    mdd=float((nav/nav.cummax()-1).min()); cagr=(final/INITIAL)**(1/years)-1
    sh=float(rr.mean()/rr.std(ddof=1)*math.sqrt(12))
    dn=rr[rr<0].std(ddof=1); sortino=float(rr.mean()/dn*math.sqrt(12)) if pd.notna(dn) and dn>0 else np.nan
    ann=(1+rr).groupby(rr.index.year).prod()-1; reb=to[to>0]
    return {"최종자산_원":final,"누적수익률":final/INITIAL-1,"CAGR":cagr,"연환산변동성":vol,"MDD":mdd,
            "최대손실회복기간_개월":recovery(nav),"Sharpe_rf0":sh,"Sortino_rf0":sortino,"Calmar":cagr/abs(mdd),
            "월간승률":float((rr>0).mean()),"최악연도":int(ann.idxmin()),"최악연도수익률":float(ann.min()),
            "최고연도":int(ann.idxmax()),"최고연도수익률":float(ann.max()),
            "평균리밸런싱회전율":float(reb.mean()) if len(reb) else 0.0,"누적거래비용_원":float(costs.sum())}


def rolling_10y(nav_df: pd.DataFrame):
    rets=nav_df.pct_change(fill_method=None)
    # First month return from initial capital.
    rets.iloc[0]=nav_df.iloc[0]/INITIAL-1
    rows=[]; cgmat={}; mdmat={}
    for c in nav_df.columns:
        rr=rets[c]
        growth=(1+rr).rolling(120).apply(np.prod,raw=True)
        cg=growth**0.1-1
        md=pd.Series(np.nan,index=rr.index)
        vals=rr.to_numpy(float)
        for i in range(119,len(vals)):
            w=np.cumprod(1+vals[i-119:i+1]); w=np.r_[1.0,w]; dd=w/np.maximum.accumulate(w)-1
            md.iloc[i]=dd.min()
        cg=cg.dropna(); md=md.dropna(); cgmat[c]=cg; mdmat[c]=md
        rows.append({"전략":c,"롤링10년_창수":len(cg),"CAGR10Y_평균":cg.mean(),"CAGR10Y_중앙값":cg.median(),
                     "CAGR10Y_최저":cg.min(),"CAGR10Y_최고":cg.max(),"MDD10Y_평균":md.mean(),"MDD10Y_최악":md.min()})
    cgm=pd.DataFrame(cgmat).dropna(); mdm=pd.DataFrame(mdmat).dropna()
    out=pd.DataFrame(rows)
    for i,c in enumerate(out["전략"]):
        out.loc[i,"CAGR10Y_1위비율"]=(cgm.idxmax(axis=1)==c).mean()
        out.loc[i,"MDD10Y_1위비율"]=(mdm.idxmax(axis=1)==c).mean()
    return out, cgm, mdm


def main():
    latest,kang=load_full_panels()
    latest.to_csv(OUT/"asset_returns_latest_1990.csv",encoding="utf-8-sig")
    kang.to_csv(OUT/"asset_returns_kang_1990.csv",encoding="utf-8-sig")

    builders={
        "최신 K-올웨더 성장형": lambda cost: run_annual(latest,LATEST_W,cost),
        "한국주식만 계절형": lambda cost: run_seasonal(kang,KR_WINTER,KR_SUMMER,cost),
        "강환국 원본 계절형": lambda cost: run_seasonal(kang,KANG_WINTER,KANG_SUMMER,cost),
        "강환국 정적": lambda cost: run_annual(kang,KANG_STATIC,cost),
        "한국주식만 계절형(최소매매)": lambda cost: run_kr_mintrade(kang,cost),
        "5~10월 미국30년채100%": lambda cost: run_latest_us30_seasonal(latest,cost),
    }

    rows=[]; gross_nav={}; gross_ret={}
    for label,cost in [("0bp",0.0),("10bp",COST)]:
        for name,fn in builders.items():
            nav,rr,to,cs=fn(cost); rows.append({"전략":name,"비용":label,**metrics(nav,rr,to,cs)})
            if cost==0:
                gross_nav[name]=nav; gross_ret[name]=rr
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/"summary.csv",index=False,encoding="utf-8-sig")
    nav_df=pd.DataFrame(gross_nav); nav_df.to_csv(OUT/"nav_monthly_0bp.csv",encoding="utf-8-sig")

    # Added-decade and old-sample split, using realized monthly returns inside each subperiod.
    subrows=[]
    for pname,s,e in [("1990~1999","1990-01-31","1999-12-31"),("2000~2026.08","2000-01-31","2026-08-31"),("2021~2026.08","2021-01-31","2026-08-31")]:
        for name,rr in gross_ret.items():
            x=rr.loc[s:e]; wealth=(1+x).cumprod(); n=len(x)
            subrows.append({"기간":pname,"전략":name,"CAGR":wealth.iloc[-1]**(12/n)-1,
                            "MDD":float((wealth/wealth.cummax()-1).min()),"누적수익률":float(wealth.iloc[-1]-1)})
    pd.DataFrame(subrows).to_csv(OUT/"subperiod.csv",index=False,encoding="utf-8-sig")

    roll,cg,md=rolling_10y(nav_df)
    roll.to_csv(OUT/"rolling10y_summary.csv",index=False,encoding="utf-8-sig")
    cg.to_csv(OUT/"rolling10y_cagr.csv",encoding="utf-8-sig")
    md.to_csv(OUT/"rolling10y_mdd.csv",encoding="utf-8-sig")

    notes="""1990 extension assumptions\n- 2000 onward: reuse previously validated repository asset-return panels unchanged.\n- US equity 1990-1999: VFINX adjusted total-return proxy + USD/KRW.\n- Korea equity: OECD broad share-price monthly return (price return).\n- India equity: OECD broad share-price monthly return + INR/KRW.\n- China equity: Shanghai Composite monthly history from 1991; before Feb-1991 the China sleeve remains in KRW cash because the market was not investable for a full prior month.\n- Gold: LBMA PM USD spot + USD/KRW.\n- US30Y early: GS30 yield, synthetic 30Y par-bond return + USD/KRW. US10Y: GS10 similarly.\n- Korea long-bond 1990-1999: OECD Housing Bond yield IRLOHO01KRM156N, priced as flat-curve synthetic 10Y/30Y. This is the largest pre-2000 approximation.\n- KRW cash: 3M interbank from 1991; IMF discount rate fallback for 1990.\n- Foreign assets remain unhedged where the original tested strategy was unhedged.\n- Gross and 10bp per traded-notional sensitivity are reported. Taxes ignored.\n"""
    (OUT/"README.txt").write_text(notes,encoding="utf-8")
    print(summary.to_string(index=False))
    print("\nROLLING10Y\n",roll.to_string(index=False))

if __name__=="__main__":
    main()
