from __future__ import annotations

import io, json, math, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"super_value_available"
OUT.mkdir(parents=True,exist_ok=True)
HF_TREE="https://huggingface.co/api/datasets/eddmpython/dartlab-data/tree/main/dart/finance?recursive=false&expand=false&limit=1000"
HF_RAW="https://huggingface.co/datasets/eddmpython/dartlab-data/resolve/main/dart/finance/{code}.parquet"
TOP_N=20
INITIAL=10_000_000.0
ASOF=pd.Timestamp("2026-09-23")

def norm(s):
    return re.sub(r"[^0-9a-z가-힣]","",str(s or "").lower())

def num(x):
    if x is None or (isinstance(x,float) and np.isnan(x)): return np.nan
    s=str(x).strip().replace(",","")
    if s in {"","-","--","nan","None"}: return np.nan
    neg=s.startswith("(") and s.endswith(")")
    if neg: s=s[1:-1]
    try:
        v=float(s); return -v if neg else v
    except: return np.nan

def list_hf_codes():
    url=HF_TREE
    codes=set()
    while url:
        r=requests.get(url,timeout=120); r.raise_for_status()
        for x in r.json():
            p=x.get("path","")
            m=re.search(r"/([0-9A-Z]{6})\.parquet$",p)
            if m: codes.add(m.group(1))
        link=r.headers.get("Link","")
        m=re.search(r'<([^>]+)>; rel="next"',link)
        url=m.group(1) if m else None
    return codes

def load_krx(start,end):
    chunks=[]
    for y in range(pd.Timestamp(start).year,pd.Timestamp(end).year+1):
        p=ROOT/f"data/krx_equities/yearly/marcap-{y}.parquet"
        x=pd.read_parquet(p)
        use=[c for c in ["Date","Code","Name","Market","Close","Volume","Amount","Marcap","ChangesRatio","Change"] if c in x.columns]
        x=x[use].copy()
        x["Date"]=pd.to_datetime(x["Date"]).dt.normalize()
        x["Code"]=x["Code"].astype(str).str.zfill(6)
        x["Market"]=x["Market"].astype(str).str.upper()
        x=x[x["Market"].isin(["KOSPI","KOSDAQ"])]
        if "Change" not in x.columns:
            x["Change"]=pd.to_numeric(x["ChangesRatio"],errors="coerce")/100.0
        else:
            x["Change"]=pd.to_numeric(x["Change"],errors="coerce")
        for c in ["Close","Volume","Amount","Marcap"]:
            x[c]=pd.to_numeric(x[c],errors="coerce")
        chunks.append(x)
    z=pd.concat(chunks,ignore_index=True)
    return z[(z["Date"]>=pd.Timestamp(start))&(z["Date"]<=pd.Timestamp(end))].sort_values(["Date","Code"]).drop_duplicates(["Date","Code"])

def last_td(panel,y,m):
    s=panel[(panel.Date.dt.year==y)&(panel.Date.dt.month==m)].Date
    return pd.Timestamp(s.max()) if len(s) else None

def target_row_mask(x):
    sj=x["sj_div"].fillna("").astype(str).str.upper()
    aid=x["account_id"].fillna("").astype(str).str.lower()
    nm=x["account_nm"].fillna("").astype(str).str.replace(r"\s+","",regex=True)
    return (
      ((sj=="BS")&(aid.str.contains("equity",regex=False)|nm.isin(["자본총계","자본합계","자기자본","총자본"]))) |
      (sj.isin(["IS","CIS"])&(aid.str.contains("revenue",regex=False)|nm.isin(["매출액","매출","영업수익","수익","수익(매출액)","영업수익합계"]))) |
      (sj.isin(["IS","CIS"])&(aid.str.contains("profitloss",regex=False)|nm.isin(["당기순이익","당기순이익(손실)","분기순이익","분기순이익(손실)","반기순이익","반기순이익(손실)","연결당기순이익","당기순손익","분기순손익","반기순손익"]))) |
      ((sj=="CF")&(aid.str.contains("cashflowsfromusedinoperatingactivities",regex=False)|nm.isin(["영업활동현금흐름","영업활동으로인한현금흐름","영업활동으로부터의현금흐름","영업활동에의한현금흐름"])))
    )

def metric_priority(row):
    sj=str(row.get("sj_div","") or "").upper(); aid=norm(row.get("account_id","")); nm=norm(row.get("account_nm",""))
    if sj=="BS" and ("equity" in aid or nm in {"자본총계","총자본","자본합계","자기자본"}): return "equity",0 if ("equity" in aid or nm=="자본총계") else 2
    if sj in {"IS","CIS"} and ("revenue" in aid or nm in {"매출액","영업수익","수익","수익매출액","매출"}): return "revenue",(0 if ("revenue" in aid or nm=="매출액") else 2)+(0 if sj=="IS" else 1)
    if sj in {"IS","CIS"} and ("profitloss" in aid or nm in {"당기순이익","당기순이익손실","분기순이익","분기순이익손실","반기순이익","반기순이익손실","연결당기순이익","당기순손익","분기순손익","반기순손익"}): return "net_income",(0 if "profitloss" in aid else 2)+(0 if sj=="IS" else 1)
    if sj=="CF" and ("cashflowsfromusedinoperatingactivities" in aid or nm in {"영업활동현금흐름","영업활동으로인한현금흐름","영업활동으로부터의현금흐름","영업활동에의한현금흐름"}): return "ocf",0 if "cashflowsfromusedinoperatingactivities" in aid else 2
    return None,99

def fetch_code(code):
    try:
        r=requests.get(HF_RAW.format(code=code),timeout=120)
        if r.status_code!=200: return code,None,"HTTP"+str(r.status_code)
        x=pd.read_parquet(io.BytesIO(r.content))
        if "collect_status" in x.columns:
            x=x[x["collect_status"].fillna("").astype(str).str.lower()=="collected"]
        req=["rcept_no","reprt_code","bsns_year","sj_div","account_id","account_nm","thstrm_amount","thstrm_add_amount","fs_div"]
        for c in req:
            if c not in x.columns: x[c]=np.nan
        x["stock_code"]=code
        x["filing_date"]=pd.to_datetime(x["rcept_no"].astype(str).str[:8],format="%Y%m%d",errors="coerce")
        x["period"]=x["reprt_code"].astype(str).map({"11013":"Q1","11012":"H1","11014":"Q3","11011":"FY"})
        x["year"]=pd.to_numeric(x["bsns_year"],errors="coerce")
        x=x[x["period"].notna() & x["year"].between(2018,2025,inclusive="both") & (x["filing_date"]<=ASOF)]
        x=x[target_row_mask(x)].copy()
        if x.empty: return code,pd.DataFrame(),None
        return code,x[["stock_code","filing_date","rcept_no","fs_div","period","year","sj_div","account_id","account_nm","thstrm_amount","thstrm_add_amount"]],None
    except Exception as e:
        return code,None,repr(e)

def snapshots(raw):
    rows=[]
    if raw is None or raw.empty: return pd.DataFrame()
    for (code,fs,year,period,rcept,fdate),g in raw.groupby(["stock_code","fs_div","year","period","rcept_no","filing_date"],dropna=False):
        cand=[]
        for _,r in g.iterrows():
            m,p=metric_priority(r)
            if not m: continue
            cand.append((m,p,num(r.get("thstrm_amount")),num(r.get("thstrm_add_amount"))))
        if not cand: continue
        rec={"Code":str(code).zfill(6),"fs_div":str(fs),"year":int(year),"period":period,"rcept_no":str(rcept),"filing_date":pd.Timestamp(fdate)}
        c=pd.DataFrame(cand,columns=["metric","priority","current","cumulative"])
        for m in ["equity","revenue","net_income","ocf"]:
            z=c[c.metric==m].copy()
            if z.empty:
                rec[m+"_current"]=np.nan; rec[m+"_cum"]=np.nan; continue
            z["has"]=z[["current","cumulative"]].notna().any(axis=1).astype(int)
            z=z.sort_values(["has","priority"],ascending=[False,True])
            b=z.iloc[0]; rec[m+"_current"]=b.current; rec[m+"_cum"]=b.cumulative
        rows.append(rec)
    return pd.DataFrame(rows)

def latest(snap,year,period,signal):
    z=snap[(snap.year==year)&(snap.period==period)&(snap.filing_date<=signal)].copy()
    if z.empty:return z
    z=z.sort_values(["Code","fs_div","filing_date","rcept_no"])
    return z.groupby(["Code","fs_div"],as_index=False).tail(1)

def factors_for_signal(snap,signal):
    y=signal.year; rows=[]
    if signal.month==10:
        q1=latest(snap,y,"Q1",signal); h1=latest(snap,y,"H1",signal)
        m=h1.merge(q1,on=["Code","fs_div"],how="left",suffixes=("_h1","_q1"))
        for _,r in m.iterrows():
            rev=r.get("revenue_current_h1",np.nan); ni=r.get("net_income_current_h1",np.nan)
            if pd.isna(rev): rev=r.get("revenue_cum_h1",np.nan)-r.get("revenue_cum_q1",np.nan)
            if pd.isna(ni): ni=r.get("net_income_cum_h1",np.nan)-r.get("net_income_cum_q1",np.nan)
            oh=r.get("ocf_cum_h1",np.nan); oq=r.get("ocf_cum_q1",np.nan)
            if pd.isna(oh): oh=r.get("ocf_current_h1",np.nan)
            if pd.isna(oq): oq=r.get("ocf_current_q1",np.nan)
            rows.append({"Code":r.Code,"fs_div":r.fs_div,"equity":r.get("equity_current_h1",np.nan),"revenue_q":rev,"net_income_q":ni,"ocf_q":oh-oq if pd.notna(oh) and pd.notna(oq) else np.nan})
    else:
        yy=y-1; q3=latest(snap,yy,"Q3",signal); fy=latest(snap,yy,"FY",signal)
        m=fy.merge(q3,on=["Code","fs_div"],how="left",suffixes=("_fy","_q3"))
        for _,r in m.iterrows():
            rf=r.get("revenue_current_fy",np.nan); nf=r.get("net_income_current_fy",np.nan); of=r.get("ocf_cum_fy",np.nan)
            if pd.isna(rf): rf=r.get("revenue_cum_fy",np.nan)
            if pd.isna(nf): nf=r.get("net_income_cum_fy",np.nan)
            if pd.isna(of): of=r.get("ocf_current_fy",np.nan)
            rq=r.get("revenue_cum_q3",np.nan); nq=r.get("net_income_cum_q3",np.nan); oq=r.get("ocf_cum_q3",np.nan)
            if pd.isna(oq): oq=r.get("ocf_current_q3",np.nan)
            rows.append({"Code":r.Code,"fs_div":r.fs_div,"equity":r.get("equity_current_fy",np.nan),"revenue_q":rf-rq if pd.notna(rf) and pd.notna(rq) else np.nan,"net_income_q":nf-nq if pd.notna(nf) and pd.notna(nq) else np.nan,"ocf_q":of-oq if pd.notna(of) and pd.notna(oq) else np.nan})
    out=pd.DataFrame(rows)
    if out.empty:return out
    out["complete"]=out[["equity","revenue_q","net_income_q","ocf_q"]].notna().all(axis=1)
    out["fsp"]=out.fs_div.map({"CFS":0,"OFS":1}).fillna(9)
    return out.sort_values(["Code","complete","fsp"],ascending=[True,False,True]).groupby("Code",as_index=False).head(1).drop(columns=["complete","fsp"])

def select(panel,signal,factors):
    xs=panel[panel.Date==signal][["Code","Name","Market","Marcap","Amount","Volume","Close"]].copy()
    m=xs.merge(factors,on="Code",how="left")
    valid=m[m.Marcap.gt(0)&m[["equity","revenue_q","net_income_q","ocf_q"]].notna().all(axis=1)].copy()
    for c,src in [("EY","net_income_q"),("BY","equity"),("CFY","ocf_q"),("SY","revenue_q")]:
        mult=1 if c=="BY" else 4
        valid[c]=mult*valid[src]/valid.Marcap
        valid[c+"_rank"]=valid[c].rank(method="average",ascending=False)
    valid["avg_rank"]=valid[[c+"_rank" for c in ["EY","BY","CFY","SY"]]].mean(axis=1)
    valid=valid.sort_values(["avg_rank","Code"]).reset_index(drop=True)
    valid["overall_rank"]=np.arange(1,len(valid)+1)
    sel=valid.head(TOP_N).copy(); sel["signal_date"]=signal; sel["target_weight"]=1/TOP_N
    audit={"signal_date":signal,"cross_section":len(xs),"hf_file_codes_in_xs":int(xs.Code.isin(HF_CODES).sum()),"factor_rows":int(factors.Code.nunique()),"valid_four_factor":len(valid),"factor_coverage":len(valid)/len(xs) if len(xs) else np.nan}
    return sel,audit

def sell_tax_total(dt):
    dt=pd.Timestamp(dt)
    if dt < pd.Timestamp("2019-06-03"): return 0.0030
    if dt < pd.Timestamp("2021-01-01"): return 0.0025
    if dt < pd.Timestamp("2023-01-01"): return 0.0023
    if dt < pd.Timestamp("2024-01-01"): return 0.0020
    if dt < pd.Timestamp("2025-01-01"): return 0.0018
    if dt < pd.Timestamp("2026-01-01"): return 0.0015
    return 0.0020

def simulate(panel,selections,end,common_bps=21.5):
    dates=pd.DatetimeIndex(sorted(panel.Date.unique()))
    lookup={pd.Timestamp(d):g.set_index("Code") for d,g in panel.groupby("Date")}
    events={}
    for s,sel in selections.items():
        i=dates.searchsorted(s,side="right")
        if i<len(dates): events[pd.Timestamp(dates[i])]=(s,sel)
    start=min(events)
    run=dates[(dates>=start)&(dates<=end)]
    weights={"__CASH__":1.0}; nav=1.0; rows=[]; turns=[]
    for dt in run:
        day=lookup.get(pd.Timestamp(dt)); vals={}; ret=0
        for code,w in weights.items():
            r=0.0 if code=="__CASH__" else (float(day.loc[code,"Change"]) if day is not None and code in day.index and pd.notna(day.loc[code,"Change"]) else 0.0)
            vals[code]=w*max(0,1+r); ret+=w*r
        tot=sum(vals.values()); weights={k:v/tot for k,v in vals.items()} if tot>0 else {"__CASH__":1.0}
        nav*=max(0,1+ret)
        cost=0
        if dt in events:
            sig,sel=events[dt]; target={"__CASH__":0.0}; untrad=[]
            for _,r in sel.iterrows():
                code=r.Code
                trad=day is not None and code in day.index and float(day.loc[code,"Close"])>0 and float(day.loc[code,"Volume"])>0
                if trad: target[code]=1/TOP_N
                else: target["__CASH__"]+=1/TOP_N; untrad.append(code)
            keys=set(weights)|set(target); buy=sell=0
            for k in keys:
                if k=="__CASH__": continue
                old=weights.get(k,0); tar=target.get(k,0)
                buy+=max(tar-old,0); sell+=max(old-tar,0)
            cost=(buy+sell)*(common_bps/10000)+sell*sell_tax_total(dt)
            nav*=1-cost; weights=target
            turns.append({"signal_date":sig,"execution_date":dt,"buy":buy,"sell":sell,"two_way":buy+sell,"cost_fraction":cost,"sell_tax_total":sell_tax_total(dt),"untradable_count":len(untrad)})
        rows.append({"Date":dt,"NAV":nav,"cost_fraction":cost})
    return pd.DataFrame(rows).set_index("Date"),pd.DataFrame(turns)

def metrics(nav,name,start_baseline):
    s=nav.dropna().astype(float)
    monthly=s.resample("ME").last()
    prior=monthly.index[0]-pd.offsets.MonthEnd(1)
    r=pd.concat([pd.Series([1.0],index=[prior]),monthly]).pct_change().dropna()
    if pd.Timestamp(start_baseline).to_period("M")==monthly.index[0].to_period("M") and len(r): stats=r.iloc[1:]
    else: stats=r
    years=(s.index[-1]-pd.Timestamp(start_baseline)).days/365.2425
    cagr=float(s.iloc[-1])**(1/years)-1 if years>0 else np.nan
    vol=float(stats.std(ddof=1)*math.sqrt(12)) if len(stats)>=2 else np.nan
    sh=float(stats.mean()/stats.std(ddof=1)*math.sqrt(12)) if len(stats)>=2 and stats.std(ddof=1)>0 else np.nan
    dd=s/s.cummax()-1
    # recovery
    peak=1.0; peak_date=pd.Timestamp(start_baseline); under=None; longest=0
    for dt,v in s.items():
        if v>=peak:
            if under is not None: longest=max(longest,(pd.Timestamp(dt)-under).days); under=None
            peak=v; peak_date=pd.Timestamp(dt)
        elif under is None: under=peak_date
    if under is not None: longest=max(longest,(s.index[-1]-under).days)
    return {"series":name,"start":s.index[0].date().isoformat(),"end":s.index[-1].date().isoformat(),"final_multiple":float(s.iloc[-1]),"final_asset_krw":float(s.iloc[-1])*INITIAL,"cumulative_return":float(s.iloc[-1]-1),"CAGR":cagr,"annualized_volatility_monthly":vol,"Sharpe_rf0_monthly":sh,"MDD_daily":float(dd.min()),"MDD_date":dd.idxmin().date().isoformat(),"max_recovery_days":int(longest),"max_recovery_months":round(longest/30.4375,1)}

def main():
    global HF_CODES
    panel=load_krx("2019-01-01","2026-09-21")
    signals=[last_td(panel,y,m) for y in range(2019,2027) for m in (4,10)]
    signals=[s for s in signals if s is not None and s<=pd.Timestamp("2026-04-30")]
    needed=set(panel[panel.Date.isin(signals)].Code.astype(str))
    HF_CODES=list_hf_codes()
    fetch=sorted(needed & HF_CODES)
    print(f"HF files={len(HF_CODES)} needed={len(needed)} fetch={len(fetch)}",flush=True)
    chunks=[]; errs=[]
    with ThreadPoolExecutor(max_workers=20) as ex:
        fut={ex.submit(fetch_code,c):c for c in fetch}
        n=0
        for f in as_completed(fut):
            code,x,e=f.result(); n+=1
            if x is not None and not x.empty: chunks.append(x)
            if e: errs.append((code,e))
            if n%250==0: print(f"downloaded {n}/{len(fetch)}",flush=True)
    raw=pd.concat(chunks,ignore_index=True) if chunks else pd.DataFrame()
    snap=snapshots(raw)
    print(f"candidate rows={len(raw)} snapshots={len(snap)} errors={len(errs)}",flush=True)
    selections={}; audits=[]; sels=[]
    for s in signals:
        fac=factors_for_signal(snap,s)
        sel,a=select(panel,s,fac)
        selections[s]=sel; audits.append(a); sels.append(sel)
        print(s.date(),a,flush=True)
    # Cross-check against previously verified 2019-04 local selection
    prev=ROOT/"results"/"super_value_v214"/"selections.csv"
    xcheck={}
    if prev.exists():
        p=pd.read_csv(prev,dtype={"Code":str},parse_dates=["signal_date"])
        p=p[(p.top_n==20)&(p.signal_date==pd.Timestamp("2019-04-30"))]
        h=selections.get(pd.Timestamp("2019-04-30"),pd.DataFrame())
        if len(p) and len(h):
            A=set(p.Code.astype(str).str.zfill(6)); B=set(h.Code.astype(str).str.zfill(6))
            xcheck={"signal":"2019-04-30","overlap":len(A&B),"local_top20":sorted(A),"hf_top20":sorted(B)}
    # extension starts at 2019-10 signal, not the April signal already used in verified run
    ext_sel={s:v for s,v in selections.items() if s>=pd.Timestamp("2019-10-31")}
    nav,turn=simulate(panel,ext_sel,pd.Timestamp("2026-09-21"))
    nav.to_csv(OUT/"hf_extension_nav.csv",encoding="utf-8-sig")
    turn.to_csv(OUT/"hf_extension_turnover.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(OUT/"hf_factor_coverage.csv",index=False,encoding="utf-8-sig")
    pd.concat(sels,ignore_index=True).to_csv(OUT/"hf_selections.csv",index=False,encoding="utf-8-sig")
    (OUT/"hf_crosscheck.json").write_text(json.dumps(xcheck,ensure_ascii=False,indent=2),encoding="utf-8")
    pd.DataFrame(errs,columns=["Code","error"]).to_csv(OUT/"hf_download_errors.csv",index=False,encoding="utf-8-sig")

    # Combine preserved fully-verified 2016-2019 NAV with HF extension.
    old=pd.read_csv(ROOT/"results"/"super_value_v214"/"daily_nav.csv",parse_dates=["Date"]).set_index("Date")
    verified=old["Top20_Base"].loc[:pd.Timestamp("2019-10-31")]
    ext=nav["NAV"].copy()
    # extension NAV starts at 1 and includes first execution cost; rebase to verified terminal NAV.
    composite=pd.concat([verified, ext*float(verified.iloc[-1])])
    composite=composite[~composite.index.duplicated(keep="first")].sort_index()
    composite.name="Top20_AvailableComposite"
    composite.to_csv(OUT/"composite_nav.csv",encoding="utf-8-sig")

    # requested windows: cannot start 2001, so calculate the actually available slice within each requested end.
    rows=[]
    for label,end in [("requested_2001_2021_available_slice",pd.Timestamp("2021-12-31")),("requested_2001_2026_available_slice",pd.Timestamp("2026-09-21"))]:
        z=composite[composite.index<=end]
        rows.append(metrics(z,label,pd.Timestamp("2016-10-31")))
    pd.DataFrame(rows).to_csv(OUT/"requested_window_available_metrics.csv",index=False,encoding="utf-8-sig")

    status=pd.DataFrame([
      {"requested_period":"2001-01-01~2021-12-31","status":"PARTIAL_ONLY","available_performance":"2016-11-01~2021-12-31","unavailable":"2001-01-01~2016-10-31","reason":"PIT four-factor financial statements for the full historical universe are not sufficiently parsed/available before the first verified 2016-10-31 signal."},
      {"requested_period":"2001-01-01~2026-09-21","status":"PARTIAL_ONLY","available_performance":"2016-11-01~2026-09-21","unavailable":"2001-01-01~2016-10-31","reason":"Same pre-2016 PIT financial gap; 2019-10 onward uses the currently available DartLab HF finance archive and is reported with factor-coverage audit."},
      {"requested_period":"2016-11-01~2019-10-31","status":"FULLY_VERIFIED","available_performance":"2016-11-01~2019-10-31","unavailable":"","reason":"Repository DART PIT task coverage complete for every required signal."},
      {"requested_period":"2019-11-01~2026-09-21","status":"AVAILABLE_DATA_EXTENSION","available_performance":"2019-11-01~2026-09-21","unavailable":"","reason":"HF per-code DART finance files used; cross-sectional four-factor coverage is explicitly audited and this segment is not labeled fully complete unless coverage is 100%."},
    ])
    status.to_csv(OUT/"period_status.csv",index=False,encoding="utf-8-sig")

    # simple dashboard
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,subplot_titles=("누적자산","Log2 누적자산","Drawdown"),vertical_spacing=.08)
    s=composite
    fig.add_trace(go.Scatter(x=s.index,y=s*INITIAL,name="가용데이터 복합"),row=1,col=1)
    fig.add_trace(go.Scatter(x=s.index,y=np.log2(s),name="가용데이터 복합",showlegend=False),row=2,col=1)
    fig.add_trace(go.Scatter(x=s.index,y=(s/s.cummax()-1)*100,name="가용데이터 복합",showlegend=False),row=3,col=1)
    fig.update_layout(height=1000,title="슈퍼가치 전략 — 현재 가용 데이터 기준 복합 백테스트",hovermode="x unified")
    fig.write_html(OUT/"interactive_dashboard.html",include_plotlyjs="cdn")

    meta={"data_as_of":"2026-09-23","hf_finance_files":len(HF_CODES),"needed_codes":len(needed),"downloaded_codes":len(fetch),"download_errors":len(errs),"crosscheck":xcheck}
    (OUT/"run_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False),flush=True)
    print(pd.DataFrame(audits).to_string(index=False),flush=True)
    print("XCHECK",xcheck,flush=True)

if __name__=="__main__":
    main()
