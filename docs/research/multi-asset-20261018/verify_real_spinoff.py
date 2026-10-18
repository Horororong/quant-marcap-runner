"""Actual-price multi-security component audit, NOT a shortened strategy run.

Own units + cash oracle uses original quotes and evidence terms. It reads no
engine return, drift, schedule, quantity or fee as an expected value.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from strategy_dsl_runner import load_project_engine
from research_spinoff import load_events,CATALOG


def verify(out,parent="003550"):
 out.mkdir(parents=True,exist_ok=False)
 pth=ROOT/'data/krx_equities/yearly/marcap-2021.parquet'
 panel=pd.read_parquet(pth,columns=['Date','Code','Close','Open','Volume','ChangesRatio'])
 facts=json.loads((ROOT/CATALOG).read_bytes())['events'];fact=next(c for c in facts if c['parent']==parent)
 parent,child=fact['parent'],fact['child'];codes=[parent,child,'005930']
 source_dates=pd.DatetimeIndex(panel.Date.unique()).sort_values();last=source_dates.get_loc(pd.Timestamp(fact['last_trade_date']));listed=source_dates.get_loc(pd.Timestamp(fact['listing_date']))
 dates=source_dates[last-2:listed+5]
 panel=panel[panel.Date.isin(dates)&panel.Code.isin(codes)]
 px=panel.pivot(index='Date',columns='Code',values='Close').reindex(index=dates,columns=codes)
 volumes=panel.pivot(index='Date',columns='Code',values='Volume').reindex_like(px);mask=px.notna()&volumes.gt(0);refs=panel.pivot(index='Date',columns='Code',values='ChangesRatio').reindex_like(px)/100
 events=load_events(ROOT,start=dates[0],end=dates[-1],asset_codes={parent});assert len(events)==1
 # Explicit functional allocations, not a factor strategy or shortened full
 # requested study: buy last pre-halt close, sell at first observed joint fill,
 # then make a new parent purchase that cannot receive an old child entitlement.
 w=pd.DataFrame([[.6,0,.4],[0,0,1],[.5,0,.5]],index=pd.DatetimeIndex([source_dates[last-1],pd.Timestamp(fact['record_date']),source_dates[listed+1]]),columns=codes)
 engine=load_project_engine(ROOT);capital=10000000.
 results={}
 for label,cost in [('zero',{}),('fixed_cost',dict(commission_bps=1.5,sell_tax_bps=15.,spread_bps=3.,slippage_bps=5.))]:
  results[label]=engine.simulate_target_weight_portfolio(px,w,initial_capital=capital,tradable_mask=mask,source_volumes=volumes,reference_returns=refs,corporate_action_events=events,execution_assumptions=engine.ExecutionAssumptions(nontradable_policy='defer_full_rebalance_events_v1'),cost_assumptions=engine.TradingCostAssumptions(**cost))
 rows=[];orders=[]
 arrivals={dates[dates.get_loc(s)+1]:(s,target) for s,target in w.iterrows()}
 for book,cost,key in [('Gross',{},'zero'),('Net_zero',{},'zero'),('Net_fixed_cost',dict(commission_bps=1.5,sell_tax_bps=15.,spread_bps=3.,slippage_bps=5.),'fixed_cost')]:
  cash=capital;shares=dict.fromkeys(codes,0.);pending=None
  for date in dates:
   if str(date.date())==fact['listing_date']:
    old=shares[fact['parent']];shares[fact['parent']]=old*fact['parent_ratio'];shares[fact['child']]+=old*fact['child_ratio']
   holding={c:shares[c]*px.at[date,c] if shares[c] else 0. for c in codes};value=cash+sum(holding.values());fee=0.
   if date in arrivals:
    assert pending is None;pending=arrivals[date]
   if pending:
    signal,target=pending;required={c for c in codes if shares[c] or target[c]}
    if all(mask.at[date,c] and pd.notna(px.at[date,c]) and px.at[date,c]>0 for c in required):
     buy=sum(max(target[c]*value-holding[c],0) for c in codes);sell=sum(max(holding[c]-target[c]*value,0) for c in codes)
     common=sum(cost.get(k,0) for k in ['commission_bps','spread_bps','slippage_bps'])/10000
     fee=buy*common+sell*(common+cost.get('sell_tax_bps',0)/10000)
     new={c:target[c]*(value-fee)/px.at[date,c] if target[c] else 0. for c in codes}
     cash-=sum((new[c]-shares[c])*px.at[date,c] for c in codes if new[c] or shares[c])+fee;shares=new
     value=cash+sum(shares[c]*px.at[date,c] for c in codes if shares[c]);orders.append(dict(book=book,signal_date=str(signal.date()),execution_date=str(date.date())));pending=None
   result=results[key];which='Gross' if book=='Gross' else 'Net';expected=value;actual=float(result['daily_nav'].at[date,which])*capital
   assert abs(actual-expected)<=1e-5,(book,date,expected,actual)
   weights=result['weights' if book=='Gross' else 'net_weights'];assert abs(float(weights.at[date,'Cash'])*actual-cash)<=1e-5
   for c in codes:
    observed=float(weights.at[date,c])*actual/px.at[date,c] if pd.notna(px.at[date,c]) else 0.
    assert abs(observed-shares[c])<=1e-7,(book,date,c,observed,shares[c])
   assert cash>=-1e-5
   rows.append(dict(book=book,Date=str(date.date()),independent_value=value,engine_value=actual,absolute_error=abs(value-actual),cash=cash,trading_cost=fee,**{'quantity_'+c:shares[c] for c in codes}))
  assert pending is None
  own=[r for r in orders if r['book']==book];assert own[1]['execution_date']==fact['listing_date']
  assert [str(d.date()) for d in result['execution_schedule'].execution_date]==[r['execution_date'] for r in own]
 # Actual independent source checks, not ratios reverse-engineered as facts.
 quote=next(e for e in fact['evidence'] if e['role']=='official_quote')
 primary=json.loads((ROOT/quote['path']).read_bytes())['OutBlock_1'];checks=[]
 for code,reference in [(parent,fact['parent_reference']),(child,fact['child_reference'])]:
  row=next(r for r in primary if r['ISU_CD']==code);src=panel[panel.Date.eq(fact['listing_date'])&panel.Code.eq(code)].iloc[0]
  for a,b in [('Close','TDD_CLSPRC'),('Open','TDD_OPNPRC'),('Volume','ACC_TRDVOL'),('ChangesRatio','FLUC_RT')]:assert src[a]==float(row[b])
  diff=abs(float(row['TDD_CLSPRC'])/reference-1-float(row['FLUC_RT'])/100)*10000;assert diff<=1.
  checks.append(dict(security=code,reference=reference,close=float(row['TDD_CLSPRC']),exchange_return=float(row['FLUC_RT'])/100,difference_bps=diff))
 # Both public modes use the same event-aware common execution. Ten buckets
 # receive the same component targets deliberately; this is integration, not
 # a claim that factor deciles chose these three securities.
 from strategy_dsl import StrategySpec
 from strategy_dsl_runner import execute_daily_nav,engine_inputs
 from strategy_dsl_deciles import execute_decile_nav,DECILE_LABELS
 raw=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2025_event_deferred_v1.json').read_bytes())
 raw['period']=dict(start=str(dates[0].date()),end=str(dates[-1].date()),book_start=str(dates[0].date()),book_end=str(dates[-1].date()),as_of_date=str(dates[-1].date()))
 spec=StrategySpec.from_dict(raw);cfg,costs,execution=engine_inputs(spec,engine)
 top=execute_daily_nav(engine,px,w,costs,execution,capital,tradable_mask=mask,corporate_action_events=events,reference_returns=refs,source_volumes=volumes)
 dec=execute_decile_nav(panel,spec,{b:w for b in DECILE_LABELS},engine,events,refs)
 for bucket in DECILE_LABELS:pd.testing.assert_frame_equal(dec['decile_results'][bucket]['daily_nav'],top['daily_nav'],check_exact=True)
 pd.DataFrame(rows).to_csv(out/'independent_ledger.csv',index=False);pd.DataFrame(orders).to_csv(out/'independent_orders.csv',index=False)
 for k,v in results.items():
  v['daily_nav'].to_csv(out/(k+'_daily_nav.csv'));v['trades'].to_csv(out/(k+'_trades.csv'));v['corporate_actions'].to_csv(out/(k+'_actions.csv'),index=False)
 result=dict(parent=parent,child=child,event_date=fact['listing_date'],status='PASS_ACTUAL_PRICE_RESEARCH_COMPONENT',sessions=len(dates),book_days=len(rows),max_error_currency=max(r['absolute_error'] for r in rows),tolerance_currency=1e-5,source_sha256=hashlib.sha256(pth.read_bytes()).hexdigest(),fact_catalog_sha256=hashlib.sha256((ROOT/CATALOG).read_bytes()).hexdigest(),official_price_checks=checks,investment_approved=False,scope='Two-leg simultaneous-listing continuous-quantity component with another real security. Not a full-period factor strategy, integer broker account, dividend total return or investment PIT certification.',pending_sale_no_cash_advance=True,entire_order_waits_for_both_legs=True,original_fixed_lag_unchanged=True,all_ten_buckets_and_top_n_common_results_exact=True)
 (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--parent',default='003550');a=p.parse_args();verify(a.output,a.parent)
