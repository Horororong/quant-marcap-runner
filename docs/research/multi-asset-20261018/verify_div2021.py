"""Independent units/rights/cash oracle for two newly evidenced actual dividends.

Explicit component allocations and actual quotes; NOT a factor strategy, a
shortened long backtest, or a claim of cash-dividend total return/tax approval.
"""
import argparse,hashlib,json,sys,base64,io,zipfile,importlib.util
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];HOME=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'scripts'))
from strategy_dsl import StrategySpec
from strategy_dsl_runner import load_project_engine,engine_inputs
from stock_dividend_research import load_strategy_actions


def verify(out):
 out.mkdir(parents=True,exist_ok=False)
 source=ROOT/'config/strategies/research_size_deciles_2019_2025_event_deferred_v2.json';raw=json.loads(source.read_bytes())
 raw['period']=dict(start='2021-12-01',end='2022-04-29',book_start='2021-12-01',book_end='2022-04-29',as_of_date='2022-04-29');spec=StrategySpec.from_dict(raw)
 # Verify original transported ZIPs and source text. Legacy XML filenames
 # contain CP949 HTML. The existing safe source decoder/parser is retained.
 s=importlib.util.spec_from_file_location('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py');safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)
 state=json.loads((HOME/'evidence_div2021/state.json').read_bytes());source_assertions=[]
 for pin in state['responses']:
  file=HOME/'evidence_div2021'/pin['file'];b=file.read_bytes();assert len(b)==pin['bytes'] and hashlib.sha256(b).hexdigest()==pin['sha256']
  if pin.get('storage_encoding')=='base64':
   original=base64.b64decode(b,validate=False);assert len(original)==pin['raw_bytes'] and hashlib.sha256(original).hexdigest()==pin['raw_sha256'];members,text=safe.inspect_archive(original,'')
   joined=' '.join(text.values());assert all(x in joined for x in (['0.02','2021-12-31'] if '202112' in file.name else ['주식배당','2022-03-25']))
   assert all(x['format']=='HTML' for x in members)
   source_assertions.append(dict(file=pin['file'],raw_sha256=pin['raw_sha256'],format='CP949 HTML despite XML suffix; not forced XML',members=members))
 frames=[pd.read_parquet(ROOT/f'data/krx_equities/yearly/marcap-{year}.parquet',columns=['Date','Code','Close','Volume','ChangesRatio']) for year in [2021,2022]]
 panel=pd.concat(frames);panel=panel[panel.Date.between('2021-12-01','2022-04-29')&panel.Code.isin(['068270','091990'])]
 dates=pd.DatetimeIndex(panel.Date.unique()).sort_values();px=panel.pivot(index='Date',columns='Code',values='Close').reindex(index=dates);vol=panel.pivot(index='Date',columns='Code',values='Volume').reindex_like(px);refs=panel.pivot(index='Date',columns='Code',values='ChangesRatio').reindex_like(px)/100
 target=pd.DataFrame([[.6,.4],[0,1],[.5,.5],[0,0]],columns=px.columns,index=pd.to_datetime(['2021-12-27','2022-01-31','2022-02-28','2022-04-25']))
 e=load_project_engine(ROOT);_,costs,execution=engine_inputs(spec,e);events=load_strategy_actions(ROOT,spec,start=dates[0],end=dates[-1],asset_codes=set(px.columns));assert len(events)==2
 results={name:e.simulate_target_weight_portfolio(px,target,initial_capital=spec.initial_capital,tradable_mask=px.notna()&vol.gt(0),source_volumes=vol,reference_returns=refs,corporate_action_events=events,execution_assumptions=execution,cost_assumptions=cost) for name,cost in costs.items()}
 facts=[f for f in json.loads((ROOT/spec.research['event_file']).read_bytes())['events'] if f['ex_date']=='2021-12-29'];records=[];entitlements=[]
 # Signal dates need not be exchange sessions (Jan31 is a Lunar New Year
 # holiday). Independently find the first OBSERVED later session, matching
 # the explicit next-session-close contract, never an invented weekday.
 schedule={dates[dates.searchsorted(d,side='right')]:w for d,w in target.iterrows()}
 for book,cost,key in [('Gross',{},'zero')]+[('Net_'+name,raw['cost_scenarios'][name],name) for name in costs]:
  shares=dict.fromkeys(px.columns,0.);cash=float(spec.initial_capital);rights={}
  for day,p in px.iterrows():
   for fact in facts:
    code=fact['security']
    if day==pd.Timestamp(fact['ex_date']):rights[code]=dict(q=shares[code]*float(fact['rate']),state='conditional',value=0.);entitlements.append(dict(book=book,security=code,quantity=rights[code]['q']))
    if code not in rights:continue
    claim=rights[code]
    if claim['state']!='released' and day>pd.Timestamp(fact['decision']['evidence']['publication_date']):claim['state']='approved'
    if day==pd.Timestamp(fact['listing']['date']):shares[code]+=claim['q'];claim['state']='released'
    claim['value']=claim['q']*p[code] if claim['state']!='released' else 0.
   illiquid=sum(c['value'] for c in rights.values());stock={c:shares[c]*p[c] for c in px};value=cash+sum(stock.values())+illiquid;fee=0.
   if day in schedule:
    w=schedule[day];liquid=cash+sum(stock.values());desired={c:w[c]*liquid for c in px};common=sum(cost.get(k,0) for k in ['commission_bps','spread_bps','slippage_bps'])/10000
    fee=sum(max(desired[c]-stock[c],0)*common+max(stock[c]-desired[c],0)*(common+cost.get('sell_tax_bps',0)/10000) for c in px)
    new={c:w[c]*(liquid-fee)/p[c] for c in px};cash-=sum((new[c]-shares[c])*p[c] for c in px)+fee;shares=new;value=cash+sum(shares[c]*p[c] for c in px)+illiquid
   r=results[key];label='Gross' if book=='Gross' else 'Net';actual=float(r['daily_nav'].at[day,label])*spec.initial_capital;weights=r['weights' if book=='Gross' else 'net_weights']
   assert abs(value-actual)<=1e-5,(book,day,value,actual);assert abs(cash-float(weights.at[day,'Cash'])*actual)<=1e-5;assert abs(illiquid-float(weights.at[day,'StockDividendIlliquid'])*actual)<=1e-5;assert cash>=-1e-5
   for c in px:assert abs(shares[c]-float(weights.at[day,c])*actual/p[c])<=1e-7
   records.append(dict(book=book,Date=str(day.date()),expected_value=value,engine_value=actual,error=abs(value-actual),cash=cash,rights_value=illiquid,trading_cost=fee,**{'shares_'+c:shares[c] for c in px}))
  for day in pd.to_datetime(['2022-03-28','2022-04-22']):assert r['trades'].at[day,'cost_fraction']==0.
 pd.DataFrame(records).to_csv(out/'independent_ledger.csv',index=False);pd.DataFrame(entitlements).to_csv(out/'entitlements.csv',index=False)
 summary=dict(status='PASS_TWO_NEW_DIVIDENDS_ACTUAL_PRICE_MODEL_ACCOUNTING',events=2,sessions=len(dates),book_days=len(records),max_nav_error_currency=max(r['error'] for r in records),tolerance_currency=1e-5,source_fact_sha256=spec.research['event_sha256'],source_assertions=source_assertions,investment_approved=False,scope='Explicit continuous liquid-target component; not a full-period factor result, integer broker account, cash distribution total return or tax/PIT certification')
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='source_assertions'}));return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();verify(a.output)
