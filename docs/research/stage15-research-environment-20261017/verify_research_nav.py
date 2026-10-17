"""Independent validation oracle: raw prices + units/rights/cash, no engine calls.

This is a test/audit, never a strategy executor or performance calculator.
Selection/targets are separately checked invariant against the original DSL;
only quantity accounting and pre-cost turnover/post-cost allocation are audited.
"""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]

def verify(run,output):
 spec=json.loads((run/'strategy_normalized.json').read_text());model=spec['research']
 facts=json.loads((ROOT/model['event_file']).read_text())['events']
 actual=pd.read_csv(run/'artifacts/daily_nav.csv',index_col='Date',parse_dates=True);dates=actual.index
 targets={d.name:pd.read_csv(d/'target_weights.csv',index_col=0,parse_dates=True) for d in (run/'artifacts').glob('D[0-9][0-9]')}
 if not targets:targets={'top_n':pd.read_csv(run/'artifacts/target_weights.csv',index_col=0,parse_dates=True)}
 used=sorted({c for w in targets.values() for c in w if w[c].ne(0).any()})
 rows=[]
 for year in range(dates.min().year,dates.max().year+1):
  x=pd.read_parquet(ROOT/f'data/krx_equities/yearly/marcap-{year}.parquet',columns=['Date','Code','Close'])
  x['Code']=x['Code'].astype(str).str.zfill(6);rows.append(x[x.Code.isin(used)])
 panel=pd.concat(rows);px=panel.pivot(index='Date',columns='Code',values='Close').reindex(index=dates,columns=used)
 def known(e):return next((s for s in dates if s>pd.Timestamp(e['publication_date'])),None)
 records=[];event_rows=[]
 for label,w in sorted(targets.items()):
  codes=[c for c in w if w[c].ne(0).any()];w=w[codes];prices=px[codes]
  schedule={dates[dates.get_loc(dt)+spec['execution']['lag_sessions']]:row for dt,row in w.iterrows() if dates.get_loc(dt)+spec['execution']['lag_sessions']<len(dates)}
  books=[('Gross',{})]+[('Net_'+name,c) for name,c in spec['cost_scenarios'].items()]
  for book,cost in books:
   shares={c:0. for c in codes};cash=spec['initial_capital'];claims={}
   for dt,p in prices.iterrows():
    for fact in facts:
     c=fact['security'];eid=fact['event_id']
     if c not in shares:continue
     if dt==pd.Timestamp(fact['ex_date']):claims[eid]={'q':shares[c]*float(fact['rate']),'security':c,'state':'conditional','value':0.}
     if eid not in claims:continue
     claim=claims[eid];dec=fact['decision'];listing=fact['listing']
     if dec and known(dec['evidence']) is not None and dt>=max(pd.Timestamp(dec['actual_date']),known(dec['evidence'])):
      claim['state']='approved' if dec['approved'] else 'cancelled'
     if listing:
      listed=next((s for s in dates if s>=pd.Timestamp(listing['date'])),None)
      settle=None if listed is None or dates.get_loc(listed)+model['settlement_lag_sessions']>=len(dates) else dates[dates.get_loc(listed)+model['settlement_lag_sessions']]
      if dt==settle:
       assert claim['state']=='approved';shares[c]+=claim['q'];claim['state']='released'
     # After release it remains released; repeated historical approval above
     # must not restore a settled claim on later sessions.
     if claim.get('released'):claim['state']='released'
     if claim['state']=='released':claim['released']=True
     multiplier=model['conditional_fraction'] if claim['state']=='conditional' else 1.
     claim['value']=claim['q']*p[c]*multiplier if claim['state'] in ['conditional','approved'] else 0.
    illiquid=sum(c['value'] for c in claims.values());stock={c:shares[c]*p[c] for c in codes if shares[c]};value=cash+sum(stock.values())+illiquid;fee=0.
    if dt in schedule:
     target=schedule[dt];buys=sum(max(float(target[c])*value-stock.get(c,0.),0.) for c in codes);sells=sum(max(stock.get(c,0.)-float(target[c])*value,0.) for c in codes)
     common=sum(cost.get(k,0.) for k in ['commission_bps','spread_bps','slippage_bps','market_impact_bps'])/10000
     fee=buys*common+sells*(common+cost.get('sell_tax_bps',0.)/10000);value-=fee
     new={c:float(target[c])*value/p[c] if target[c] else 0. for c in codes}
     cash-=sum((new[c]-shares[c])*p[c] for c in codes if new[c] or shares[c])+fee;shares=new
     assert cash>=-1e-5,(dt,label,book,cash)
    col='NAV_'+('' if label=='top_n' else label+'_')+book
    # PROJECT publishes an index starting at1; the independent ledger is KRW.
    # Convert the unit explicitly, never change either input NAV or tolerance.
    engine_value=float(actual.at[dt,col])*spec['initial_capital'];error=value-engine_value
    assert abs(error)<=1e-5,(dt,label,book,value,actual.at[dt,col],error)
    records.append(dict(Date=str(dt.date()),portfolio=label,book=book,expected_nav=value,engine_nav=engine_value,absolute_error=abs(error),cash=cash,rights_value=illiquid,trading_cost=fee))
    for eid,c in claims.items():
     if c['q'] and (str(dt.date()) in [f['ex_date'] for f in facts] or dt in schedule or any(f['listing'] and str(dt.date())==f['listing']['date'] for f in facts)):
      event_rows.append(dict(Date=str(dt.date()),portfolio=label,book=book,event=eid,quantity=c['q'],state=c['state'],rights_value=c['value'],cash=cash))
 output.mkdir(parents=True,exist_ok=False)
 pd.DataFrame(records).to_csv(output/'independent_daily_ledger.csv',index=False);pd.DataFrame(event_rows).to_csv(output/'event_boundaries.csv',index=False)
 result=dict(status='PASS_MODEL_ACCOUNTING',rows=len(records),portfolios=len(targets),sessions=len(dates),max_nav_error=max(r['absolute_error'] for r in records),numerical_tolerance_currency=1e-5,
  scope='raw-price independent quantity/cash validation of explicit continuous pretax model; not historical account/PIT certification',investment_approved=False)
 (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();verify(a.run,a.output)
