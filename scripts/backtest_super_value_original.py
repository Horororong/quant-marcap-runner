from __future__ import annotations

from pathlib import Path
import json, re, math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICE_DIR = ROOT / "data/krx_equities/yearly"
FULL_DIR = ROOT / "data/financials/full_history"
RECENT_DIR = ROOT / "data/financials/recent_batches"
OUT = ROOT / "results/super_value_original"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 10_000_000.0
TOP_N = 20
ROUND_TRIP_COST = {"gross":0.0, "min":0.002, "base":0.005, "conservative":0.01}

FLOW_METRICS = {"revenue","net_income","operating_cashflow"}

def num(x):
    if pd.isna(x): return np.nan
    s = str(x).strip().replace(",", "")
    if s in {"","-","nan","None"}: return np.nan
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in {"","-",".","-."}: return np.nan
    try:
        v = float(s)
        return -abs(v) if neg else v
    except Exception:
        return np.nan

def metric_and_priority(row):
    sj = str(row.get("sj_div","")).upper()
    aid = str(row.get("account_id","")).lower()
    nm = re.sub(r"\s+","",str(row.get("account_nm","")))
    if sj == "BS":
        if aid.endswith("_equity") or aid == "ifrs-full_equity":
            return "equity", 0
        if nm in {"자본총계","자본합계","자기자본"}:
            return "equity", 1
    if sj in {"IS","CIS"}:
        if aid.endswith("_revenue") or aid == "ifrs-full_revenue":
            return "revenue", 0
        if nm in {"매출액","매출","영업수익","수익(매출액)","영업수익합계"}:
            return "revenue", 1
        if aid.endswith("_profitloss") or aid == "ifrs-full_profitloss":
            return "net_income", 0
        if nm in {"당기순이익","분기순이익","반기순이익","당기순손익","분기순손익","반기순손익"}:
            return "net_income", 1
    if sj == "CF":
        if "cashflowsfromusedinoperatingactivities" in aid:
            return "operating_cashflow", 0
        if nm in {"영업활동현금흐름","영업활동으로인한현금흐름","영업활동에의한현금흐름"}:
            return "operating_cashflow", 1
    return "", 99

def read_csv_selected(path, source):
    if source == "full":
        cols = ["_stock_code","_requested_year","_period","_fs_div_requested","_filing_date",
                "rcept_no","fs_div","sj_div","account_id","account_nm","thstrm_amount","thstrm_add_amount"]
        rename = {"_stock_code":"stock_code","_requested_year":"year","_period":"period",
                  "_fs_div_requested":"fs_req","_filing_date":"filing_date"}
    else:
        cols = ["stock_code","requested_year","period","filing_date","rcept_no","fs_div",
                "sj_div","account_id","account_nm","thstrm_amount","thstrm_add_amount"]
        rename = {"requested_year":"year"}
    try:
        df = pd.read_csv(path, usecols=lambda c: c in cols, low_memory=False, compression="gzip")
    except Exception:
        return pd.DataFrame()
    df = df.rename(columns=rename)
    needed = ["stock_code","year","period","filing_date","sj_div","account_id","account_nm","thstrm_amount"]
    if any(c not in df.columns for c in needed):
        return pd.DataFrame()
    df["stock_code"] = df["stock_code"].astype(str).str.replace(".0","",regex=False).str.zfill(6)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)
    df["period"] = df["period"].astype(str).str.upper()
    df["filing_date"] = pd.to_datetime(df["filing_date"].astype(str).str.slice(0,8), format="%Y%m%d", errors="coerce")
    if "fs_div" not in df.columns:
        df["fs_div"] = df.get("fs_req","")
    df["fs_div"] = df["fs_div"].fillna(df.get("fs_req","")).astype(str).str.upper()
    mp = df.apply(metric_and_priority, axis=1, result_type="expand")
    df["metric"] = mp[0]; df["priority"] = mp[1]
    df = df[df["metric"] != ""].copy()
    if df.empty: return df
    df["amount"] = df["thstrm_amount"].map(num)
    if "thstrm_add_amount" in df.columns:
        df["add_amount"] = df["thstrm_add_amount"].map(num)
    else:
        df["add_amount"] = np.nan
    return df[["stock_code","year","period","filing_date","fs_div","metric","priority","amount","add_amount"]]

def load_financial_raw(dataset):
    parts=[]
    if dataset == "2016_2019":
        for y in [2016,2017,2018]:
            for p in ["Q1","H1","Q3","FY"]:
                for fs in ["CFS","OFS"]:
                    for f in sorted(FULL_DIR.glob(f"dart_full_{y}_{p}_{fs}_*.csv.gz")):
                        x=read_csv_selected(f,"full")
                        if len(x): parts.append(x)
    elif dataset == "2024_2026":
        for f in sorted(RECENT_DIR.glob("dart_recent_*.csv.gz")):
            x=read_csv_selected(f,"recent")
            if len(x):
                x=x[x["year"].isin([2024,2025,2026])]
                if len(x): parts.append(x)
    if not parts:
        raise RuntimeError(f"No financial rows for {dataset}")
    x=pd.concat(parts, ignore_index=True)
    x=x.dropna(subset=["filing_date"])
    # prefer standardized account rows
    key=["stock_code","year","period","fs_div","metric","filing_date"]
    x=x.sort_values(key+["priority"]).drop_duplicates(key,keep="first")
    return x

def build_quarter_factors(raw):
    # One chosen report per stock/year/period/fs/metric: latest filing, best account.
    # Prefer CFS if that stock-period has it; OFS otherwise.
    raw=raw.copy()
    raw["fs_pref"]=raw["fs_div"].map({"CFS":0,"OFS":1}).fillna(2)
    key0=["stock_code","year","period","metric"]
    # If multiple filings exist, retain all first; PIT logic later must not use future amendments.
    # For quarterly construction, use each latest available report by period. Historical API generally
    # exposes the final filing; filing_date gate below remains conservative.
    best=(raw.sort_values(key0+["fs_pref","filing_date","priority"])
             .drop_duplicates(key0,keep="first"))
    # Better: if CFS exists at all choose CFS, else OFS.
    # Above ordering already does this; earliest filing chosen within fs to reduce amendment look-ahead.
    piv={}
    for metric in ["revenue","net_income","operating_cashflow","equity"]:
        g=best[best.metric==metric].copy()
        piv[metric]=g

    # Build per stock/year using sequential cumulative-flow logic.
    rows=[]
    stocks_years=best[["stock_code","year"]].drop_duplicates()
    for stock, year in stocks_years.itertuples(index=False):
        sub=best[(best.stock_code==stock)&(best.year==year)]
        flow_q={}
        flow_filing={}
        for metric in FLOW_METRICS:
            m=sub[sub.metric==metric].set_index("period")
            prev_cum=np.nan
            for period in ["Q1","H1","Q3","FY"]:
                if period not in m.index:
                    continue
                r=m.loc[period]
                if isinstance(r,pd.DataFrame): r=r.iloc[0]
                amt=float(r["amount"]) if pd.notna(r["amount"]) else np.nan
                add=float(r["add_amount"]) if pd.notna(r["add_amount"]) else np.nan
                if period=="Q1":
                    cum=add if pd.notna(add) else amt
                    q=cum
                elif period in {"H1","Q3"}:
                    if pd.notna(add):
                        cum=add
                        q=cum-prev_cum if pd.notna(prev_cum) else amt
                    else:
                        q=amt
                        cum=(prev_cum+q) if pd.notna(prev_cum) and pd.notna(q) else np.nan
                else: # FY
                    cum=amt
                    q=cum-prev_cum if pd.notna(cum) and pd.notna(prev_cum) else np.nan
                qname={"Q1":"Q1","H1":"Q2","Q3":"Q3","FY":"Q4"}[period]
                flow_q[(metric,qname)]=q
                flow_filing[(metric,qname)]=pd.Timestamp(r["filing_date"])
                if pd.notna(cum): prev_cum=cum

        for report_period,qname in [("Q1","Q1"),("H1","Q2"),("Q3","Q3"),("FY","Q4")]:
            eq=sub[(sub.metric=="equity")&(sub.period==report_period)]
            if eq.empty: continue
            er=eq.iloc[0]
            vals={m:flow_q.get((m,qname),np.nan) for m in FLOW_METRICS}
            if any(pd.isna(vals[m]) for m in FLOW_METRICS): continue
            equity=float(er["amount"]) if pd.notna(er["amount"]) else np.nan
            if pd.isna(equity): continue
            fdates=[pd.Timestamp(er["filing_date"])] + [flow_filing[(m,qname)] for m in FLOW_METRICS if (m,qname) in flow_filing]
            available=max(fdates)
            rows.append({"stock_code":stock,"year":year,"quarter":qname,"available_date":available,
                         "equity":equity,**vals})
    out=pd.DataFrame(rows)
    if out.empty: raise RuntimeError("No standardized quarter factors")
    qend={"Q1":"03-31","Q2":"06-30","Q3":"09-30","Q4":"12-31"}
    out["quarter_end"]=pd.to_datetime(out["year"].astype(str)+"-"+out["quarter"].map(qend))
    return out.sort_values(["stock_code","available_date","quarter_end"])

def load_prices(start,end):
    ys=range(pd.Timestamp(start).year,pd.Timestamp(end).year+1)
    parts=[]
    cols=["Date","Code","Name","Market","Close","ChangesRatio","Marcap","Amount"]
    for y in ys:
        p=PRICE_DIR/f"marcap-{y}.parquet"
        if not p.exists(): raise FileNotFoundError(p)
        x=pd.read_parquet(p, columns=cols)
        x["Date"]=pd.to_datetime(x["Date"]).dt.normalize()
        x=x[(x.Date>=pd.Timestamp(start))&(x.Date<=pd.Timestamp(end))]
        x["Code"]=x["Code"].astype(str).str.zfill(6)
        x["Market"]=x["Market"].astype(str).str.upper()
        x=x[x.Market.isin(["KOSPI","KOSDAQ"])]
        if len(x): parts.append(x)
    out=pd.concat(parts,ignore_index=True)
    out=out.sort_values(["Date","Code"]).drop_duplicates(["Date","Code"],keep="last")
    return out

def signal_dates(prices):
    dates=pd.DatetimeIndex(sorted(prices.Date.unique()))
    result=[]
    for y in sorted(set(dates.year)):
        for m in [4,10]:
            ds=dates[(dates.year==y)&(dates.month==m)]
            if len(ds): result.append(pd.Timestamp(ds.max()))
    return result

def select_at_signal(prices, factors, sig, n=20):
    cs=prices[prices.Date==sig][["Code","Name","Market","Marcap","Amount"]].copy()
    cs["Marcap"]=pd.to_numeric(cs["Marcap"],errors="coerce")
    cs["Amount"]=pd.to_numeric(cs["Amount"],errors="coerce")
    # Signal-close information only: securities already halted/non-trading at the
    # signal close are not considered executable candidates.
    cs=cs[(cs.Marcap>0)&(cs.Amount>0)].copy()
    f=factors[factors.available_date<=sig].copy()
    f=f.sort_values(["stock_code","available_date","quarter_end"]).drop_duplicates("stock_code",keep="last")
    x=cs.merge(f,left_on="Code",right_on="stock_code",how="inner")
    for col in ["net_income","equity","operating_cashflow","revenue"]:
        x[col]=pd.to_numeric(x[col],errors="coerce")
    x=x.dropna(subset=["net_income","equity","operating_cashflow","revenue","Marcap"])
    x["EY"]=4*x.net_income/x.Marcap
    x["BY"]=x.equity/x.Marcap
    x["CFY"]=4*x.operating_cashflow/x.Marcap
    x["SY"]=4*x.revenue/x.Marcap
    for c in ["EY","BY","CFY","SY"]:
        x=x[np.isfinite(x[c])]
    for c in ["EY","BY","CFY","SY"]:
        x[c+"_rank"]=x[c].rank(ascending=False,method="average")
    x["avg_rank"]=x[[c+"_rank" for c in ["EY","BY","CFY","SY"]]].mean(axis=1)
    x=x.sort_values(["avg_rank","Code"]).head(n).copy()
    x["signal_date"]=sig
    return x

def simulate(prices, factors, start, end, label):
    px=prices[(prices.Date>=pd.Timestamp(start))&(prices.Date<=pd.Timestamp(end))].copy()
    cal=pd.DatetimeIndex(sorted(px.Date.unique()))
    sigs=[d for d in signal_dates(px) if d>=pd.Timestamp(start) and d<=pd.Timestamp(end)]
    events=[]
    sels=[]
    for sig in sigs:
        pos=cal.searchsorted(sig)
        if pos+1>=len(cal): continue
        ex=cal[pos+1]
        sel=select_at_signal(px,factors,sig,TOP_N)
        trade_cs=px[px.Date==ex][["Code","Close","Amount"]].copy()
        trade_cs["Close"]=pd.to_numeric(trade_cs["Close"],errors="coerce")
        trade_cs["Amount"]=pd.to_numeric(trade_cs["Amount"],errors="coerce")
        tradeable=set(trade_cs.loc[(trade_cs.Close>0)&(trade_cs.Amount>0),"Code"])
        sel["exec_tradeable"]=sel["Code"].isin(tradeable)
        if len(sel)<TOP_N:
            print(f"WARN {label} {sig.date()} only {len(sel)} selected")
        if len(sel)<10:
            print(f"SKIP {label} {sig.date()} insufficient cross-section")
            continue
        sel["execution_date"]=ex
        sels.append(sel)
        events.append((ex,sel))
    if not events: raise RuntimeError(f"No rebalance events {label}")

    first_ex=events[0][0]
    cal=cal[(cal>=first_ex)&(cal<=pd.Timestamp(end))]
    ret=px.pivot(index="Date",columns="Code",values="ChangesRatio").reindex(cal)
    ret=ret.apply(pd.to_numeric,errors="coerce")/100.0
    last_obs=px.groupby("Code")["Date"].max().to_dict()

    variants={k:{"nav":1.0,"w":{}} for k in ROUND_TRIP_COST}
    rec=[]
    event_map={d:s for d,s in events}
    delist_events=0
    for i,d in enumerate(cal):
        for k,st in variants.items():
            if st["w"] and i>0:
                rs={}
                for code,w in list(st["w"].items()):
                    if code=="__CASH__":
                        rv=0.0
                    else:
                        rv=ret.at[d,code] if code in ret.columns else np.nan
                        if pd.isna(rv):
                            lo=last_obs.get(code,pd.Timestamp.max)
                            rv=-1.0 if (lo<d and lo<pd.Timestamp(end)) else 0.0
                            if rv==-1.0 and k=="gross": delist_events+=1
                    rs[code]=float(rv)
                pr=sum(st["w"].get(c,0)*r for c,r in rs.items())
                st["nav"]*=max(0.0,1.0+pr)
                denom=1.0+pr
                if denom>0:
                    st["w"]={c:st["w"][c]*(1+rs[c])/denom for c in st["w"]}
                else:
                    st["w"]={}
            if d in event_map:
                sel=event_map[d]
                codes=list(sel.Code)
                nslots=len(codes)
                tradable_codes=list(sel.loc[sel["exec_tradeable"],"Code"])
                tgt={c:1.0/nslots for c in tradable_codes}
                unavailable=nslots-len(tradable_codes)
                if unavailable:
                    tgt["__CASH__"]=unavailable/nslots
                allc=set(st["w"])|set(tgt)
                turnover=0.5*sum(abs(tgt.get(c,0)-st["w"].get(c,0)) for c in allc)
                if not st["w"]: turnover=1.0
                st["nav"]*=max(0.0,1.0-ROUND_TRIP_COST[k]*turnover)
                st["w"]=tgt
        rec.append({"Date":d,**{k:v["nav"] for k,v in variants.items()}})
    nav=pd.DataFrame(rec).set_index("Date")
    sel=pd.concat(sels,ignore_index=True)
    return nav,sel,delist_events

def drawdown(s):
    baseline_date=s.index[0]-pd.offsets.BDay(1)
    z=pd.concat([pd.Series([1.0],index=[baseline_date]),s.astype(float)])
    return (z/z.cummax()-1).iloc[1:]

def recovery_days(s):
    peak=1.0; peak_date=s.index[0]-pd.offsets.BDay(1); under=None; longest=0
    for d,v in s.items():
        if v>=peak:
            if under is not None:
                longest=max(longest,(d-under).days); under=None
            peak=v; peak_date=d
        elif under is None:
            under=peak_date
    if under is not None: longest=max(longest,(s.index[-1]-under).days)
    return longest

def metrics(nav,label):
    rows=[]
    monthly=nav.groupby(nav.index.to_period("M")).tail(1)
    for c in nav.columns:
        s=nav[c].astype(float)
        years=(s.index[-1]-s.index[0]).days/365.2425
        cagr=s.iloc[-1]**(1/years)-1 if years>0 and s.iloc[-1]>0 else np.nan
        mr=monthly[c].pct_change().dropna()
        vol=mr.std(ddof=1)*math.sqrt(12) if len(mr)>=2 else np.nan
        sharpe=mr.mean()/mr.std(ddof=1)*math.sqrt(12) if len(mr)>=2 and mr.std(ddof=1)>0 else np.nan
        dd=drawdown(s)
        rows.append({"sample":label,"cost_case":c,"start":s.index[0],"end":s.index[-1],
                     "months":len(mr),"CAGR":cagr,"cum_return":s.iloc[-1]-1,
                     "ann_vol":vol,"MDD":dd.min(),"max_recovery_days":recovery_days(s),
                     "Sharpe_rf0_monthly":sharpe,"final_asset_krw":s.iloc[-1]*INITIAL_CAPITAL})
    return pd.DataFrame(rows)

def run_sample(dataset,start,end,label):
    print(f"LOAD {label} financials")
    raw=load_financial_raw(dataset)
    fac=build_quarter_factors(raw)
    print(f"{label} factors rows={len(fac)} codes={fac.stock_code.nunique()} range={fac.available_date.min()}..{fac.available_date.max()}")
    px=load_prices(start,end)
    nav,sel,delist=simulate(px,fac,start,end,label)
    m=metrics(nav,label)
    return nav,sel,m,fac,delist

def main():
    allm=[]; alls=[]; coverage=[]; navs=[]
    samples=[
      ("2016_2019","2016-09-01","2019-09-30","2016-10~2019-09"),
      ("2024_2026","2024-09-01","2026-09-21","2024-10~2026-09"),
    ]
    for ds,st,en,label in samples:
        nav,sel,m,fac,de=run_sample(ds,st,en,label)
        nav.to_csv(OUT/f"nav_{ds}.csv",encoding="utf-8-sig")
        sel.to_csv(OUT/f"selections_{ds}.csv",index=False,encoding="utf-8-sig")
        fac.to_csv(OUT/f"factors_{ds}.csv",index=False,encoding="utf-8-sig")
        allm.append(m); alls.append(sel)
        coverage.append({"sample":label,"factor_rows":len(fac),"factor_codes":fac.stock_code.nunique(),
                         "factor_min":fac.available_date.min(),"factor_max":fac.available_date.max(),
                         "signals":sel.signal_date.nunique(),"min_eligible_selected":sel.groupby("signal_date").size().min(),
                         "untradeable_execution_slots":int((~sel["exec_tradeable"]).sum()),
                         "delisting_loss_events":de})
    metrics_df=pd.concat(allm,ignore_index=True)
    metrics_df.to_csv(OUT/"metrics.csv",index=False,encoding="utf-8-sig")
    pd.concat(alls,ignore_index=True).to_csv(OUT/"selections_all.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(coverage).to_csv(OUT/"coverage.csv",index=False,encoding="utf-8-sig")
    print("\n=== METRICS ===")
    print(metrics_df.to_string(index=False))
    print("\n=== COVERAGE ===")
    print(pd.DataFrame(coverage).to_string(index=False))

if __name__=="__main__":
    main()
