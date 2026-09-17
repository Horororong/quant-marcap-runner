from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

AS_OF = pd.Timestamp('2026-09-18')
END = pd.Timestamp('2026-08-31')
INITIAL = 10_000.0
W_STOCK, W_BOND = 0.60, 0.40
BASE_COST_BPS = 5.0
BOOK_START, BOOK_END = pd.Timestamp('1970-01-01'), pd.Timestamp('2021-12-31')
OUT = Path('results/60_40_book_v2'); OUT.mkdir(parents=True, exist_ok=True)
POFO_SP500='https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/SP500.csv'
POFO_IEF='https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/IEF.csv'

def remote(url, name):
    d=pd.read_csv(url, comment='#'); d['date']=pd.to_datetime(d['date']); d['close']=pd.to_numeric(d['close'], errors='coerce')
    return d.dropna().drop_duplicates('date').set_index('date')['close'].sort_index().rename(name)

def local(path,name):
    d=pd.read_csv(path); d['Date']=pd.to_datetime(d['Date']); col='Adj Close' if 'Adj Close' in d.columns else 'Close'; d[col]=pd.to_numeric(d[col],errors='coerce')
    return d.dropna(subset=['Date',col]).drop_duplicates('Date').set_index('Date')[col].sort_index().rename(name)

def stitch(proxy, actual, end):
    idx=pd.bdate_range(proxy.index.min(), end)
    p=proxy.reindex(idx).ffill(); a=actual.reindex(idx).ffill()
    first=actual.index.min()
    if first > end: return p.loc[:end]
    scale=float(p.loc[first])/float(a.loc[first])
    out=p.copy(); out.loc[first:]=a.loc[first:]*scale
    return out.loc[:end]

def levels_hybrid():
    spx=remote(POFO_SP500,'stock_proxy'); iefp=remote(POFO_IEF,'bond_proxy')
    spy=local('data/etf_us/SPY.csv','SPY'); ief=local('data/etf_us/IEF.csv','IEF')
    s=stitch(spx,spy,END); b=stitch(iefp,ief,END)
    x=pd.concat([s.rename('Stock'),b.rename('Bond')],axis=1).dropna()
    if x.index[-1] < END: raise RuntimeError(f'data ends early: {x.index[-1]}')
    return x, spy.index.min(), ief.index.min()

def simulate(levels,cost_bps=0.0):
    r=levels.pct_change().fillna(0.0); sv,bv=W_STOCK,W_BOND; nav=[]; trades=[]; prev_year=levels.index[0].year
    for i,(dt,row) in enumerate(r.iterrows()):
        if i>0 and dt.year!=prev_year:
            pre=sv+bv; ts,tb=pre*W_STOCK,pre*W_BOND; gross=abs(ts-sv)+abs(tb-bv); cost=gross*cost_bps/10000.0; post=pre-cost
            sv,bv=post*W_STOCK,post*W_BOND; trades.append((dt,gross/pre,cost)); prev_year=dt.year
        if i>0: sv*=1+row['Stock']; bv*=1+row['Bond']
        nav.append((dt,sv+bv))
    s=pd.Series(dict(nav)).sort_index(); s/=s.iloc[0]
    return s,pd.DataFrame(trades,columns=['Date','GrossTurnover','CostNAV'])

def stock100(stock):
    s=stock/stock.iloc[0]; return s.rename('S&P500 100%')

def month_end(s):
    m=s.groupby(s.index.to_period('M')).tail(1).copy(); m.index=m.index.to_period('M').to_timestamp('M'); return m.loc[:END]

def rebase(s,start,end):
    x=s.loc[(s.index>=start)&(s.index<=end)].copy(); pos=s.index.searchsorted(x.index[0]); base=s.iloc[pos-1] if pos>0 else 1.0; return x/base

def recovery(nav):
    s=nav.astype(float); peak=1.0; peak_date=s.index[0]-pd.offsets.BDay(1); uw=None; best=0; best_s=None; best_e=None
    for dt,v in s.items():
        if v>=peak:
            if uw is not None:
                days=(dt-uw).days
                if days>best: best,best_s,best_e=days,uw,dt
                uw=None
            peak=float(v); peak_date=dt
        elif uw is None: uw=peak_date
    if uw is not None:
        days=(s.index[-1]-uw).days
        if days>best: best,best_s,best_e=days,uw,None
    return best, best/30.4375, best_s, best_e

def metrics(full_daily,start,end):
    d=rebase(full_daily,start.to_period('M').start_time,end.to_period('M').end_time)
    m=month_end(full_daily); m=rebase(m,start.to_period('M').to_timestamp('M'),end.to_period('M').to_timestamp('M'))
    prior=m.index[0]-pd.offsets.MonthEnd(1); ret=pd.concat([pd.Series([1.0],index=[prior]),m]).pct_change().dropna(); years=len(ret)/12
    final=float(m.iloc[-1]); cagr=final**(1/years)-1; vol=float(ret.std(ddof=1)*np.sqrt(12)); sharpe=float(ret.mean()/ret.std(ddof=1)*np.sqrt(12))
    dd=d/d.cummax()-1; trough=dd.idxmin(); peak=d.loc[:trough].idxmax(); peakv=float(d.loc[peak]); aft=d.loc[trough:]; rec=aft[aft>=peakv]; recdt=rec.index[0] if len(rec) else pd.NaT
    rd,rm,rs,re=recovery(d)
    return dict(Start=m.index[0].date().isoformat(),End=m.index[-1].date().isoformat(),Months=len(ret),Final_Multiple=final,Final_Asset_USD=final*INITIAL,Cumulative_Return=final-1,CAGR=cagr,Annualized_Vol=vol,MDD=float(dd.min()),Sharpe_rf0=sharpe,MDD_Source='daily',Max_Recovery_Days=int(rd),Max_Recovery_Months=round(rm,1),MDD_Peak=peak.date().isoformat(),MDD_Trough=trough.date().isoformat(),MDD_Recovery=(recdt.date().isoformat() if pd.notna(recdt) else 'UNRECOVERED'),Max_Recovery_Start=(rs.date().isoformat() if rs is not None else ''),Max_Recovery_End=(re.date().isoformat() if re is not None else 'UNRECOVERED'))

def main():
    levels,spy_start,ief_start=levels_hybrid(); gross,tr0=simulate(levels,0); net,tr5=simulate(levels,BASE_COST_BPS); stock=stock100(levels['Stock'])
    series={'60/40 비용전':gross,'60/40 비용후(5bp)':net,'S&P500 100%':stock}
    windows={'book_validation':(BOOK_START,BOOK_END),'from_2000':(pd.Timestamp('2000-01-01'),END),'from_2021':(pd.Timestamp('2021-01-01'),END),'longest':(levels.index[0].to_period('M').start_time,END)}
    rows=[]
    for pk,(st,en) in windows.items():
        for name,s in series.items():
            q=metrics(s,st,en); q['Period']=pk; q['Strategy']=name; rows.append(q)
    summary=pd.DataFrame(rows); cols=['Period','Strategy','Start','End','Months','Final_Multiple','Final_Asset_USD','Cumulative_Return','CAGR','Annualized_Vol','MDD','Sharpe_rf0','MDD_Source','Max_Recovery_Months','Max_Recovery_Days','MDD_Peak','MDD_Trough','MDD_Recovery','Max_Recovery_Start','Max_Recovery_End']; summary=summary[cols]
    summary.to_csv(OUT/'summary_four_periods.csv',index=False,encoding='utf-8-sig')
    # cost sensitivity
    cr=[]
    for bps in [0,5,15]:
        nav,tr=simulate(levels,bps)
        for pk,(st,en) in windows.items():
            q=metrics(nav,st,en); t=tr[(tr.Date>=st)&(tr.Date<=en)]; cr.append({'Period':pk,'Cost_bps':bps,'CAGR':q['CAGR'],'MDD':q['MDD'],'Final_Asset_USD':q['Final_Asset_USD'],'Avg_Annual_Gross_Turnover':float(t.GrossTurnover.mean()) if len(t) else 0})
    pd.DataFrame(cr).to_csv(OUT/'cost_sensitivity.csv',index=False,encoding='utf-8-sig')
    # actual ETF-only robustness
    etf_start=max(spy_start,ief_start); actual_levels=pd.concat([local('data/etf_us/SPY.csv','Stock'),local('data/etf_us/IEF.csv','Bond')],axis=1,join='inner').dropna().loc[:END]
    anav,_=simulate(actual_levels,0); hnav,_=simulate(levels.reindex(actual_levels.index).ffill().dropna(),0)
    def simple(name,s):
        yrs=(s.index[-1]-s.index[0]).days/365.2425; dd=s/s.cummax()-1; return {'Series':name,'Start':s.index[0].date().isoformat(),'End':s.index[-1].date().isoformat(),'Final_Multiple':float(s.iloc[-1]/s.iloc[0]),'CAGR':float((s.iloc[-1]/s.iloc[0])**(1/yrs)-1),'MDD':float(dd.min())}
    pd.DataFrame([simple('Actual_SPY_IEF',anav),simple('Hybrid_same_dates',hnav)]).to_csv(OUT/'actual_etf_overlap_check.csv',index=False,encoding='utf-8-sig')
    # chart data for chat rendering
    pd.DataFrame(series).to_csv(OUT/'daily_nav_full.csv.gz',compression='gzip')
    pd.DataFrame({k:month_end(v) for k,v in series.items()}).to_csv(OUT/'monthly_nav_full.csv',encoding='utf-8-sig')
    book=summary[(summary.Period=='book_validation')&(summary.Strategy=='60/40 비용전')].iloc[0]
    pd.DataFrame([{'Metric':'Final_Asset_USD','Book':1250000.0,'Backtest':book.Final_Asset_USD},{'Metric':'CAGR','Book':0.098,'Backtest':book.CAGR},{'Metric':'MDD','Book':-0.295,'Backtest':book.MDD},{'Metric':'Sharpe','Book':0.52,'Backtest_rf0':book.Sharpe_rf0}]).to_csv(OUT/'book_verification.csv',index=False,encoding='utf-8-sig')
    meta={'as_of':AS_OF.date().isoformat(),'latest_complete_month':END.date().isoformat(),'book_rule':'SPY 60% + IEF 40%, annual rebalance','stock_proxy_before':spy_start.date().isoformat(),'bond_proxy_before':ief_start.date().isoformat(),'post_inception':'actual ETF adjusted close','proxy_sources':[POFO_SP500,POFO_IEF],'actual_sources':['data/etf_us/SPY.csv','data/etf_us/IEF.csv'],'note':'Sharpe uses rf=0 per attached standard template; book Sharpe definition is not stated in attachment.'}; (OUT/'run_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary.to_string(index=False))
if __name__=='__main__': main()
