from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"proxy_long"/"raw"
OUT=ROOT/"results"/"all_weather_long"; OUT.mkdir(parents=True,exist_ok=True)
START=pd.Timestamp("2000-12-01")
INITIAL=10000.0
ONE_WAY_COST=0.0005
TARGET=pd.Series({"SPY":.12,"EFA":.12,"EEM":.12,"DBC":.07,"GLD":.07,"EDV":.18,"LTPZ":.18,"LQD":.07,"EMLC":.07},dtype=float)
YF_SYMBOLS=["SPY","EFA","EEM","DBC","GLD","EDV","LTPZ","LQD","EMLC","VGTSX","VEIEX","PCRIX","VIPSX","VFICX","FNMIX","^SPGSCI"]
LTPZ_DURATION=18.79
VIPSX_DURATION=6.50
BASE_TIPS_MULT=LTPZ_DURATION/VIPSX_DURATION

def load_yf(symbols):
    out={}
    for symbol in symbols:
        print("download",symbol)
        df=yf.download(symbol,start=START.strftime("%Y-%m-%d"),auto_adjust=False,actions=False,progress=False,threads=False)
        if df.empty:
            print("WARN empty",symbol); continue
        if isinstance(df.columns,pd.MultiIndex):
            if symbol in df.columns.get_level_values(-1):
                df=df.xs(symbol,axis=1,level=-1)
            else:
                df.columns=[c[0] if isinstance(c,tuple) else c for c in df.columns]
        col="Adj Close" if "Adj Close" in df.columns else "Close"
        s=pd.to_numeric(df[col],errors="coerce").dropna()
        s.index=pd.to_datetime(s.index).tz_localize(None).normalize()
        s=s[~s.index.duplicated(keep="last")].sort_index()
        if len(s):
            out[symbol]=s
            print(symbol,s.index.min().date(),s.index.max().date(),len(s))
    return out

def load_csv_series(path,value_col):
    df=pd.read_csv(path)
    df["Date"]=pd.to_datetime(df["Date"],errors="coerce")
    df[value_col]=pd.to_numeric(df[value_col],errors="coerce")
    s=df.dropna(subset=["Date",value_col]).set_index("Date")[value_col].sort_index()
    s.index=pd.to_datetime(s.index).normalize()
    return s[~s.index.duplicated(keep="last")]

def pct_return(price,master):
    return price.reindex(master).pct_change(fill_method=None)

def splice(primary,proxy):
    x=proxy.copy()
    valid=primary.dropna()
    if valid.empty: return x
    first=valid.index[0]
    x.loc[first:]=primary.loc[first:]
    return x

def rf_from_dtb3(master):
    raw=load_csv_series(RAW/"US_3M_TBILL.csv","Value").reindex(master).ffill(limit=10)
    if raw.isna().any(): raise RuntimeError("DTB3 unresolved gaps")
    ret=pd.Series(0.0,index=master)
    for i in range(1,len(master)):
        days=max(1,(master[i]-master[i-1]).days); y=float(raw.iloc[i-1])/100
        ret.iloc[i]=(1+y)**(days/365.2425)-1
    return ret

def zero_coupon_return(master,maturity_years=25.0):
    y20=load_csv_series(RAW/"US_20Y_YIELD.csv","Value").reindex(master)
    y30=load_csv_series(RAW/"US_30Y_YIELD.csv","Value").reindex(master)
    y=pd.concat([y20,y30],axis=1).mean(axis=1,skipna=True).ffill(limit=10)/100
    if y.isna().any(): raise RuntimeError("zero-coupon yield gaps")
    r=pd.Series(0.0,index=master)
    for i in range(1,len(master)):
        days=max(1,(master[i]-master[i-1]).days)
        yp=float(y.iloc[i-1]); yc=float(y.iloc[i])
        t0=maturity_years; t1=max(t0-days/365.2425,.01)
        p0=(1+yp/2)**(-2*t0); p1=(1+yc/2)**(-2*t1)
        r.iloc[i]=p1/p0-1
    return r

def broad_tips_to_long(vipsx_ret,rf,mult):
    return rf+mult*(vipsx_ret-rf)

def commodity_pre_dbc(yfdata,master,rf):
    spot=pct_return(yfdata["^SPGSCI"],master) if "^SPGSCI" in yfdata else pd.Series(np.nan,index=master)
    out=spot.fillna(0.0)+rf
    if "PCRIX" in yfdata:
        pr=pct_return(yfdata["PCRIX"],master); valid=pr.dropna()
        if len(valid): out.loc[valid.index[0]:]=pr.loc[valid.index[0]:]
    return out

def build_asset_returns(yfdata,tips_mult,em_pre_mode):
    if "SPY" not in yfdata: raise RuntimeError("SPY download failed")
    master=yfdata["SPY"].loc[yfdata["SPY"].index>=START].index
    rf=rf_from_dtb3(master)
    def rr(sym):
        return pct_return(yfdata[sym],master) if sym in yfdata else pd.Series(np.nan,index=master)
    r=pd.DataFrame(index=master)
    r["SPY"]=rr("SPY")
    r["EFA"]=splice(rr("EFA"),rr("VGTSX"))
    r["EEM"]=splice(rr("EEM"),rr("VEIEX"))
    r["DBC"]=splice(rr("DBC"),commodity_pre_dbc(yfdata,master,rf))
    gold_px=load_csv_series(RAW/"GOLD_LBMA_PM_USD.csv","Close")
    r["GLD"]=splice(rr("GLD"),pct_return(gold_px,master))
    r["EDV"]=splice(rr("EDV"),zero_coupon_return(master,25.0))
    if "VIPSX" not in yfdata: raise RuntimeError("VIPSX required")
    r["LTPZ"]=splice(rr("LTPZ"),broad_tips_to_long(rr("VIPSX"),rf,tips_mult))
    r["LQD"]=splice(rr("LQD"),rr("VFICX"))
    if em_pre_mode=="fnmix": em_proxy=rr("FNMIX")
    elif em_pre_mode=="cash": em_proxy=rf.copy()
    else: raise ValueError(em_pre_mode)
    r["EMLC"]=splice(rr("EMLC"),em_proxy)
    r=r.loc[r.index>=pd.Timestamp("2000-12-29")].copy()
    r.iloc[0]=r.iloc[0].fillna(0.0)
    missing=r.isna().sum()
    if (missing>0).any():
        raise RuntimeError("unresolved proxy return gaps: "+str({c:int(v) for c,v in missing.items() if v>0}))
    return r,{"tips_duration_multiplier":tips_mult,"em_pre_mode":em_pre_mode,"data_end":r.index.max().date().isoformat(),"source_start":r.index.min().date().isoformat()}

def simulate(returns,cost_rate):
    dates=returns.index; sleeves=TARGET*INITIAL; nav=INITIAL
    rows=[{"Date":dates[0],"NAV":nav,"Return":0.0,"Turnover":0.0,"TradedFraction":0.0,"Cost":0.0}]
    for i in range(1,len(dates)):
        dt=dates[i]; prev=nav
        sleeves=sleeves*(1+returns.loc[dt,TARGET.index]); nav=float(sleeves.sum())
        turnover=traded_fraction=cost=0.0
        if dt.year!=dates[i-1].year:
            tgt=TARGET*nav
            traded_fraction=float((tgt-sleeves).abs().sum()/nav)
            turnover=.5*traded_fraction
            cost=nav*traded_fraction*cost_rate
            nav-=cost; sleeves=TARGET*nav
        rows.append({"Date":dt,"NAV":nav,"Return":nav/prev-1,"Turnover":turnover,"TradedFraction":traded_fraction,"Cost":cost})
    return pd.DataFrame(rows).set_index("Date")

def max_recovery(nav):
    peak=float(nav.iloc[0]); peak_date=nav.index[0]; active=peak_date
    max_days=0; max_peak=peak_date; max_rec=pd.NaT
    for dt,val in nav.iloc[1:].items():
        v=float(val)
        if v>=peak:
            days=(dt-active).days
            if days>max_days: max_days,max_peak,max_rec=days,active,dt
            peak,active=v,dt
    if float(nav.iloc[-1])<peak:
        days=(nav.index[-1]-active).days
        if days>max_days: max_days,max_peak,max_rec=days,active,pd.NaT
    return max_days,max_days/30.4375,max_peak.date().isoformat(),"" if pd.isna(max_rec) else max_rec.date().isoformat()

def metrics(nav):
    nav=nav.dropna().astype(float)
    monthly=nav.resample("ME").last()
    mret=monthly.pct_change().dropna()
    years=len(mret)/12
    cagr=(float(monthly.iloc[-1])/float(monthly.iloc[0]))**(1/years)-1 if years>0 else np.nan
    vol=float(mret.std(ddof=1)*math.sqrt(12)) if len(mret)>1 else np.nan
    sharpe=float(mret.mean()/mret.std(ddof=1)*math.sqrt(12)) if len(mret)>1 and mret.std(ddof=1)>0 else np.nan
    dd=nav/nav.cummax()-1
    mdays,mmonths,pdate,rdate=max_recovery(nav)
    return {"start":nav.index.min().date().isoformat(),"end":nav.index.max().date().isoformat(),"final_asset":float(nav.iloc[-1]),"cum_return":float(nav.iloc[-1]/nav.iloc[0]-1),"cagr":cagr,"ann_vol_monthly":vol,"mdd_daily":float(dd.min()),"mdd_date":dd.idxmin().date().isoformat(),"max_recovery_days":mdays,"max_recovery_months":mmonths,"max_recovery_peak":pdate,"max_recovery_date":rdate,"sharpe_monthly_rf0":sharpe}

def period_slice(df,start):
    start_ts=pd.Timestamp(start); x=df.loc[df.index>=start_ts].copy()
    if x.empty: raise RuntimeError("empty period "+start)
    pos=df.index.searchsorted(x.index[0])
    base=df.iloc[pos-1] if pos>0 else df.iloc[0]
    for c in ["NAV_Gross","NAV_Net"]: x[c]=x[c]/float(base[c])*INITIAL
    return x

def run_scenario(yfdata,tips_mult,em_pre_mode,label):
    returns,notes=build_asset_returns(yfdata,tips_mult,em_pre_mode)
    gross=simulate(returns,0.0); net=simulate(returns,ONE_WAY_COST)
    daily=pd.DataFrame({"NAV_Gross":gross["NAV"],"NAV_Net":net["NAV"],"Turnover":net["Turnover"],"TradedFraction":net["TradedFraction"],"Cost":net["Cost"]})
    last=daily.index.max()
    if last.normalize()<(last+pd.offsets.MonthEnd(0)).normalize():
        daily=daily.loc[:(last.to_period("M")-1).to_timestamp("M")]
    periods={"from_2001":period_slice(daily,"2001-01-01"),"from_2021":period_slice(daily,"2021-01-01"),"longest":period_slice(daily,daily.index.min().strftime("%Y-%m-%d"))}
    rows=[]
    for p,x in periods.items():
        for col,cost_label in [("NAV_Gross","gross"),("NAV_Net","net_5bp_one_way")]:
            d=metrics(x[col]); d.update({"scenario":label,"period":p,"cost_case":cost_label}); rows.append(d)
    return returns,daily,pd.DataFrame(rows),notes

def main():
    yfdata=load_yf(YF_SYMBOLS)
    required={"SPY","EFA","EEM","DBC","GLD","EDV","LTPZ","LQD","EMLC","VGTSX","VEIEX","VIPSX","VFICX","FNMIX"}
    missing=sorted(required-set(yfdata))
    if missing: raise RuntimeError("missing yfinance symbols: "+str(missing))
    scenarios=[("baseline",BASE_TIPS_MULT,"fnmix"),("tips_unscaled",1.0,"fnmix"),("tips_2_5x",2.5,"fnmix"),("tips_3_0x",3.0,"fnmix"),("em_cash_pre2010",BASE_TIPS_MULT,"cash")]
    all_summary=[]; baseline_daily=None; baseline_returns=None; notes={}
    for label,mult,emmode in scenarios:
        ret,daily,sm,note=run_scenario(yfdata,mult,emmode,label)
        all_summary.append(sm); notes[label]=note
        if label=="baseline": baseline_daily=daily; baseline_returns=ret
    summary=pd.concat(all_summary,ignore_index=True)
    summary.to_csv(OUT/"summary_robustness.csv",index=False)
    baseline_daily.to_csv(OUT/"daily_nav.csv")
    baseline_returns.to_csv(OUT/"asset_returns_daily.csv")
    baseline_daily[["NAV_Gross","NAV_Net"]].resample("ME").last().to_csv(OUT/"monthly_nav.csv")
    cov=[{"symbol":sym,"first":s.index.min().date().isoformat(),"last":s.index.max().date().isoformat(),"rows":len(s)} for sym,s in yfdata.items()]
    pd.DataFrame(cov).sort_values("symbol").to_csv(OUT/"proxy_coverage.csv",index=False)
    proxy_notes={
      "title":"All Weather long proxy backtest",
      "weights":TARGET.to_dict(),
      "rebalance":"first US trading day close each year; effective next trading day",
      "cost":"gross and 5bp one-way per traded notional",
      "book_period":"1926-2019 not reconstructed; TIPS and EM local-currency bonds lack equivalent history. Book 9.24% is reference only.",
      "EFA_pre_inception":"VGTSX total international Adj Close; short 2001 gap only",
      "EEM_pre_inception":"VEIEX EM index fund Adj Close",
      "DBC_pre_inception":"PCRIX Adj Close once available; earlier S&P GSCI spot + DTB3 collateral; earliest segment lacks roll yield",
      "GLD_pre_inception":"LBMA PM USD gold spot",
      "EDV_pre_inception":"synthetic 25y zero-coupon Treasury from DGS20/DGS30 with daily carry and repricing",
      "LTPZ_pre_inception":f"duration-scaled VIPSX; multiplier={BASE_TIPS_MULT:.4f}=18.79/6.50; sensitivity 1.0/2.5/3.0",
      "LQD_pre_inception":"VFICX total-return Adj Close",
      "EMLC_pre_inception":"FNMIX hard-currency EM sovereign bond as imperfect fallback; cash sensitivity also reported; weakest proxy",
      "sources":"Yahoo Finance Adj Close via yfinance; FRED Treasury yields; LBMA gold; existing repo definitions",
      "notes_by_scenario":notes,
    }
    (OUT/"proxy_notes.json").write_text(json.dumps(proxy_notes,ensure_ascii=False,indent=2),encoding="utf-8")
    print(summary.to_string(index=False))

if __name__=="__main__":
    main()
