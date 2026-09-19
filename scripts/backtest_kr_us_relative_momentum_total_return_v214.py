from __future__ import annotations
from pathlib import Path
import math, requests
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"kr_us_relative_momentum_total_return_v214"
RAW=ROOT/"data"/"proxy_long"/"raw"
OUT.mkdir(parents=True,exist_ok=True); RAW.mkdir(parents=True,exist_ok=True)
AS_OF=pd.Timestamp("2026-09-19")
END=pd.Timestamp("2026-08-31")
INITIAL=10000.0
SWITCH_COST=0.0010
ENTRY_COST=0.0005

def fred(series):
    url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    r=requests.get(url,timeout=60); r.raise_for_status()
    p=RAW/f"{series}.csv"; p.write_bytes(r.content)
    df=pd.read_csv(p)
    s=pd.Series(pd.to_numeric(df.iloc[:,1],errors="coerce").values,index=pd.to_datetime(df.iloc[:,0]),name=series).dropna()
    return s.sort_index().loc[:END]

def read_adj(path):
    df=pd.read_csv(ROOT/path,parse_dates=["Date"]).set_index("Date").sort_index()
    return pd.to_numeric(df["Adj Close"],errors="coerce").dropna().loc[:END]

def read_fx():
    df=pd.read_csv(ROOT/"data/fx/USDKRW.csv",parse_dates=["Date"]).set_index("Date").sort_index()
    return pd.to_numeric(df["Close"],errors="coerce").dropna().loc[:END]

def month_end(s):
    x=s.dropna().resample("ME").last()
    x.index=x.index.to_period("M").to_timestamp("M")
    return x

def first_common_date(a,b,period):
    ai=a.loc[a.index.to_period("M")==period]
    bi=b.loc[b.index.to_period("M")==period]
    c=ai.index.intersection(bi.index)
    return None if len(c)==0 else c[0]

def build_daily(a,b,a_name,b_name):
    ma,mb=month_end(a),month_end(b)
    px=pd.concat([ma.rename(a_name),mb.rename(b_name)],axis=1).dropna()
    mom=px/px.shift(12)-1
    win=pd.Series(np.where(mom[a_name]>mom[b_name],a_name,b_name),index=px.index,name="Winner").where(mom.notna().all(axis=1))
    events=[]
    for sig,asset in win.dropna().items():
        d=first_common_date(a,b,sig.to_period("M")+1)
        if d is not None and d<=END: events.append((pd.Timestamp(d),asset,pd.Timestamp(sig)))
    events=sorted(events,key=lambda z:z[0])
    if not events: raise RuntimeError("no events")
    start=events[0][0]
    cal=a.index.union(b.index); cal=cal[(cal>=start)&(cal<=END)].sort_values()
    aa=a.reindex(cal).ffill(); bb=b.reindex(cal).ffill()
    amap={d:(asset,sig) for d,asset,sig in events}
    nav_g=1.0; nav_n=1.0; asset=None; prev_a=None; prev_b=None
    rows=[]; sw=[]
    for d in cal:
        va=float(aa.loc[d]); vb=float(bb.loc[d])
        if asset is not None:
            if asset==a_name and prev_a is not None and prev_a>0: f=va/prev_a
            elif asset==b_name and prev_b is not None and prev_b>0: f=vb/prev_b
            else: f=1.0
            nav_g*=f; nav_n*=f
        if d in amap:
            new,sig=amap[d]
            if asset is None:
                asset=new; nav_n*=1-ENTRY_COST
                sw.append({"Date":d,"From":"","To":asset,"SignalDate":sig,"CostRate":ENTRY_COST})
            elif new!=asset:
                old=asset; nav_n*=1-SWITCH_COST; asset=new
                sw.append({"Date":d,"From":old,"To":asset,"SignalDate":sig,"CostRate":SWITCH_COST})
        if asset is not None:
            rows.append((d,nav_g,nav_n,asset))
        prev_a,prev_b=va,vb
    out=pd.DataFrame(rows,columns=["Date","Strategy_Gross","Strategy_Net","Position"]).set_index("Date")
    idx=out.index
    ba=aa.reindex(idx)/float(aa.reindex(idx).iloc[0])
    bb2=bb.reindex(idx)/float(bb.reindex(idx).iloc[0])
    out[a_name]=ba; out[b_name]=bb2
    return out,pd.DataFrame(sw),px,mom,win

def dd_recovery(nav, baseline_date):
    s=nav.dropna()
    aug=pd.concat([pd.Series([1.0],index=[baseline_date]),s])
    run=aug.cummax(); dd=aug/run-1
    mdd=float(dd.min()); md=pd.Timestamp(dd.idxmin())
    peak=float(aug.iloc[0]); pd0=aug.index[0]; uw=None; longest=0; lp=None; lr=None
    for dt,v in aug.iloc[1:].items():
        v=float(v)
        if v>=peak:
            if uw is not None:
                days=(dt-uw).days
                if days>longest: longest=days; lp=uw; lr=dt
                uw=None
            peak=v; pd0=dt
        elif uw is None: uw=pd0
    if uw is not None:
        days=(aug.index[-1]-uw).days
        if days>longest: longest=days; lp=uw; lr=pd.NaT
    return dd,mdd,md,longest,lp,lr

def slice_rebase(df,start):
    pos=df.index.searchsorted(pd.Timestamp(start))
    if pos>=len(df): return None,None
    first=df.index[pos]; base=df.iloc[pos-1] if pos>0 else None
    cols=[c for c in df.columns if c!="Position"]
    x=df.loc[first:END,cols].copy()
    for c in cols:
        den=float(base[c]) if base is not None else float(x[c].iloc[0])
        x[c]=x[c]/den
    bdate=base.name if base is not None else first-pd.offsets.BDay(1)
    return x,pd.Timestamp(bdate)

def metrics(df,switches,test,starts):
    rows=[]
    for period,st in starts:
        x,bdate=slice_rebase(df,st)
        if x is None or len(x)<30: continue
        monthly=x.resample("ME").last()
        for c in x.columns:
            vals=monthly[c].dropna()
            ext=pd.concat([pd.Series([1.0],index=[vals.index[0]-pd.offsets.MonthEnd(1)]),vals])
            r=ext.pct_change().dropna(); years=len(r)/12
            final=float(vals.iloc[-1]); vol=float(r.std(ddof=1)*math.sqrt(12))
            sh=float(r.mean()/r.std(ddof=1)*math.sqrt(12)) if r.std(ddof=1)>0 else np.nan
            dd,mdd,mdd_date,days,pk,rec=dd_recovery(x[c],bdate)
            rows.append({"test":test,"period":period,"series":c,"start":vals.index[0].date().isoformat(),"end":vals.index[-1].date().isoformat(),
             "final_multiple":final,"final_asset":final*INITIAL,"cagr":final**(1/years)-1,"annualized_volatility":vol,"sharpe_rf0":sh,
             "mdd":mdd,"mdd_date":mdd_date.date().isoformat(),"MDD_source":"daily","max_recovery_days":int(days),
             "max_recovery_months":days/30.4375,"max_recovery_peak":"" if pk is None else pd.Timestamp(pk).date().isoformat(),
             "max_recovery_date":"" if pd.isna(rec) else pd.Timestamp(rec).date().isoformat()})
        sw=switches[(switches["Date"]>=pd.Timestamp(st))&(switches["Date"]<=END)&(switches["From"]!="")]
        yrs=max((x.index[-1]-bdate).days/365.2425,1e-9)
        rows.append({"test":test,"period":period,"series":"TURNOVER","start":x.index[0].date().isoformat(),"end":x.index[-1].date().isoformat(),
                     "switch_count":int(len(sw)),"switches_per_year":len(sw)/yrs,"annualized_two_way_notional_turnover":2*len(sw)/yrs})
        monthly.to_csv(OUT/f"chart_wealth_{test}_{period}.csv",index_label="Date")
        ddf=pd.DataFrame({c:x[c]/x[c].cummax()-1 for c in x.columns})
        ddf.resample("ME").min().to_csv(OUT/f"chart_drawdown_{test}_{period}.csv",index_label="Date")
    return rows

def standalone(s,name,start):
    s=s.loc[pd.Timestamp(start):END].dropna()
    nav=s/float(s.iloc[0])
    m=nav.resample("ME").last(); r=pd.concat([pd.Series([1.0],index=[m.index[0]-pd.offsets.MonthEnd(1)]),m]).pct_change().dropna()
    years=len(r)/12; dd,mdd,md,days,pk,rec=dd_recovery(nav,nav.index[0]-pd.offsets.BDay(1))
    return {"series":name,"start":nav.index[0].date().isoformat(),"end":nav.index[-1].date().isoformat(),"final_multiple":float(nav.iloc[-1]),
            "cagr":float(nav.iloc[-1])**(1/years)-1,"mdd":mdd,"mdd_date":md.date().isoformat(),"max_recovery_months":days/30.4375}

def main():
    spy=read_adj("data/etf_us/SPY.csv")
    kodex=read_adj("data/etf_kr/069500_KODEX200.csv")
    fx=read_fx()
    korea_usd=fred("NASDAQNQKRT")
    spy_krw=(spy*fx.reindex(spy.index).ffill()).dropna()

    tests=[]
    configs=[
      ("usd_common_tr",korea_usd,spy,"Korea_TR_USD","SPY_TR_USD",[("from_2001",pd.Timestamp("2001-01-01")),("from_2021",pd.Timestamp("2021-01-01"))]),
      ("local_etf_tr",kodex,spy,"KODEX200_TR","SPY_TR_USD",[("from_2007",pd.Timestamp("2007-01-01")),("from_2021",pd.Timestamp("2021-01-01"))]),
      ("krw_investor_tr",kodex,spy_krw,"KODEX200_TR_KRW","SPY_TR_KRW",[("from_2007",pd.Timestamp("2007-01-01")),("from_2021",pd.Timestamp("2021-01-01"))]),
    ]
    for test,a,b,an,bn,starts in configs:
        d,sw,px,mom,win=build_daily(a,b,an,bn)
        d.to_csv(OUT/f"daily_nav_{test}.csv",index_label="Date")
        sw.to_csv(OUT/f"switch_log_{test}.csv",index=False)
        starts2=starts+[("longest",d.index.min())]
        tests.extend(metrics(d,sw,test,starts2))

    pd.DataFrame(tests).to_csv(OUT/"summary_total_return_v214.csv",index=False)

    bench=[
      standalone(spy,"SPY_TR_USD_2001","2001-01-02"),
      standalone(spy,"SPY_TR_USD_1996","1996-01-02"),
      standalone(spy,"SPY_TR_USD_2021","2021-01-04"),
      standalone(spy_krw,"SPY_TR_KRW_2021","2021-01-04"),
      standalone(kodex,"KODEX200_TR_2007","2007-01-29"),
      standalone(kodex,"KODEX200_TR_2021","2021-01-04"),
    ]
    pd.DataFrame(bench).to_csv(OUT/"standalone_benchmarks.csv",index=False)

    meta=pd.DataFrame([{
      "as_of":AS_OF.date().isoformat(),"latest_complete_month":END.date().isoformat(),
      "cost":"5bp one-way; 10bp full country switch; initial entry 5bp",
      "usd_common_tr_kr_source":"FRED NASDAQNQKRT; Nasdaq Korea Total Return Index; USD; 523 components per Nasdaq overview",
      "usd_common_tr_us_source":"SPY Adjusted Close; dividends/splits adjusted; USD",
      "local_etf_tr_kr_source":"KODEX200 Adjusted Close; KRW; starts 2007-01-29",
      "local_etf_tr_us_source":"SPY Adjusted Close; USD; local-currency comparison",
      "krw_investor_us":"SPY Adjusted Close multiplied by USDKRW close",
      "execution":"month-end 12m signal; switch at first common trading day's close next month; return accrues from following observation",
      "important_limitation":"No exact long-history KOSPI TR retrieved from KRX in GitHub Actions; KRX official family confirms KOSPI TR exists, but pykrx query returned empty in this environment."
    }])
    meta.to_csv(OUT/"metadata.csv",index=False)
    print(pd.DataFrame(tests).to_string(index=False))
    print(pd.DataFrame(bench).to_string(index=False))

if __name__=="__main__":
    main()
