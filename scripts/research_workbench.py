"""Research entry point; controlled Korean -> existing DSL/check/run/CURRENT.

No strategy engine, return adjustment or performance calculation lives here.
Unsupported syntax is rejected completely, never approximately translated.
"""
import argparse,json,re,hashlib,tempfile,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parent))

WORKBENCH_CONTRACT={
 'version':'3','entrypoint':'scripts/research_workbench.py',
 'commands':['capabilities','inventory','examples','translate','check','run','issues'],
 'korean_input':'exact labeled Korean clauses separated by semicolon; unknown/missing/duplicate clauses rejected',
 'required_clauses':['기간','시장','팩터','포트폴리오','리밸런싱','체결','비용','벤치마크'],
 'optional_clauses':['필터'],'translation':'registered factor/direction aliases and strict StrategySpec only',
 'readiness':'shared planned preflight v2: annual complete signal cross-sections, resolved schedule prefix before a failed order, selected cohorts and pending rights; later fallback exposures explicitly diagnostic; engine liquidity/NAV still mandatory',
 'execution':'run_checked_strategy -> PROJECT -> CURRENT; no alternative backtester/calculator',
 'opt_in_execution':'--execution-contract-from a validated predeclared DSL adds only explicit nontradable_policy/data_loading to Korean input; never changes its lag, price or selections',
 'certification':'RESEARCH_ONLY; neither inventory metadata, model assumptions nor software success is PIT approval'}
ROOT=Path(__file__).resolve().parents[1]

def korean_spec(text,*,research=None,execution_contract=None,capital=10000000):
 from strategy_dsl_aliases import resolve_factor_alias
 from strategy_dsl import StrategySpec
 fields={}
 for clause in text.split(';'):
  pair=clause.strip().split(':',1)
  if len(pair)!=2 or not all(x.strip() for x in pair):raise ValueError('지원 문법: 항목:내용; 항목:내용. 미해석 구절: '+clause)
  k,v=[x.strip() for x in pair]
  if k in fields:raise ValueError('중복 항목: '+k)
  fields[k]=v
 required=set(WORKBENCH_CONTRACT['required_clauses']);allowed=required|{'필터'}
 if set(fields)-allowed:raise ValueError('미지원 항목: '+','.join(sorted(set(fields)-allowed)))
 if required-set(fields):raise ValueError('누락 항목: '+','.join(sorted(required-set(fields))))
 def match(pattern,key):
  m=re.fullmatch(pattern,fields[key])
  if not m:raise ValueError('미지원 '+key+' 표현: '+fields[key])
  return m
 dates=match(r'(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})','기간').groups()
 names={'코스피':'KOSPI','코스닥':'KOSDAQ','코스피200':'KOSPI200','코스닥150':'KOSDAQ150'}
 markets=[]
 for token in re.split(r'[,·+]',fields['시장']):
  if token.strip() not in ['코스피','코스닥']:raise ValueError('미지원 주식시장: '+token)
  markets.append(names[token.strip()])
 factor,direction=match(r'(.+)\s+(낮은|높은)','팩터').groups();resolved=resolve_factor_alias(factor,direction)
 portfolio={'selection':'deciles','weighting':'equal'} if fields['포트폴리오']=='10분위' else {'selection':'top_n','weighting':'equal','number_of_positions':int(match(r'상위\s*(\d+)개','포트폴리오')[1])}
 months=[int(x) for x in match(r'(\d+(?:,\d+)*)월말','리밸런싱')[1].split(',')]
 lag=int(match(r'(\d+)거래일뒤종가','체결')[1])
 costs={};cost_names={'수수료':'commission_bps','매도세':'sell_tax_bps','스프레드':'spread_bps','슬리피지':'slippage_bps'}
 for item in fields['비용'].split(','):
  m=re.fullmatch(r'(수수료|매도세|스프레드|슬리피지)(\d+(?:\.\d+)?)bp',item.strip())
  if not m or m[1] in costs:raise ValueError('미지원/중복 비용 표현: '+item)
  costs[m[1]]=float(m[2])
 if set(costs)!=set(cost_names):raise ValueError('비용 네 항목을 모두 명시해야 합니다')
 filters=[]
 if '필터' in fields:
  m=match(r'시가총액(>=|<=)(\d+(?:\.\d+)?)(조원|억원|원)','필터');amount=Decimal(m[2])*{'조원':10**12,'억원':10**8,'원':1}[m[3]]
  filters=[dict(field='Marcap',op='gte' if m[1]=='>=' else 'lte',value=float(amount))]
 if fields['벤치마크'] not in names:raise ValueError('미지원 벤치마크: '+fields['벤치마크'])
 raw=dict(schema_version='1.0',strategy_id='korean_'+hashlib.sha256(text.encode()).hexdigest()[:16],title='RESEARCH_ONLY · '+text,
  asset_class='kr_equity',universe=dict(markets=markets,require_tradable_on_signal=True,filters=filters),
  factors=[dict(name=resolved['field'],source=resolved['source'],field=resolved['field'],direction=resolved['direction'],weight=1.)],
  portfolio=portfolio,rebalance=dict(frequency='months',months=months,trading_day='last'),execution=dict(lag_sessions=lag,price='next_close'),
  cost_scenarios={'zero':{},'fixed_cost':{cost_names[k]:v for k,v in costs.items()}},
  period=dict(start=dates[0],end=dates[1],book_start=dates[0],book_end=dates[1],as_of_date=dates[1]),initial_capital=capital,
  benchmark=dict(source='index',symbol=names[fields['벤치마크']]),
  metadata=dict(classification='RESEARCH_ONLY',investment_use_allowed=False,official_PIT_certified=False,
   source_korean_request=text,benchmark_return_basis='price_index_without_distributions',
   scope='historical observed universe, price/market-cap/technical research; cash dividends and full legal history not certified'))
 if research is not None:raw['research']=research
 if execution_contract is not None:
  if set(execution_contract)-{'nontradable_policy','data_loading'}:raise ValueError('Execution model file may add only explicit opt-in policy/preparation; Korean lag/price remain unchanged')
  raw['execution'].update(execution_contract)
 return StrategySpec.from_dict(raw)

def inventory(root):
 import pyarrow.parquet as pq
 import pandas as pd
 years=[]
 for p in sorted((root/'data/krx_equities/yearly').glob('marcap-*.parquet')):
  row=dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,status='METADATA_ONLY_NOT_CERTIFIED')
  try:
   f=pq.ParquetFile(p);row.update(rows=f.metadata.num_rows,columns=f.schema_arrow.names)
   col=f.schema_arrow.names.index('Date');bounds=[f.metadata.row_group(i).column(col).statistics for i in range(f.num_row_groups)]
   valid=[s for s in bounds if s and s.has_min_max]
   row.update(observed_date_min=str(min(s.min for s in valid)) if valid else None,observed_date_max=str(max(s.max for s in valid)) if valid else None)
  except Exception as e:row.update(status='UNVERIFIED',error={'type':type(e).__name__,'message':str(e)})
  years.append(row)
 benchmarks=[]
 for symbol in ['KOSPI','KOSDAQ','KOSPI200','KOSDAQ150']:
  p=root/f'data/indices/{symbol}.csv';row=dict(symbol=symbol,path=str(p.relative_to(root)),exists=p.exists(),return_basis='price_index_without_distributions')
  if p.exists():
   try:
    d=pd.read_csv(p,usecols=['Date'])['Date'];row.update(rows=len(d),first=str(d.min()),last=str(d.max()))
   except Exception as e:row['error']=type(e).__name__
  benchmarks.append(row)
 extension_file=root/'config/research/official_source_extensions_v1.json'
 extensions=json.loads(extension_file.read_bytes()) if extension_file.exists() else None
 return dict(contract=WORKBENCH_CONTRACT,price_panels=years,benchmarks=benchmarks,
  append_only_source_revision=dict(path=str(extension_file.relative_to(root)),registry=extensions,scope='Declared append-only source metadata, separately from immutable base-file dates; per-request SHA/source/session validation is still mandatory') if extensions else None,
  scope='metadata inventory only; no legal listing, event completeness, PIT or execution certification',
  technical='registered lookbacks require preceding source years and exact per-code sessions; existing provider/preflight validates each strategy',
  dart='financial PIT/availability/corrections/historical mapping remain existing operating gate requirements; file existence is not approval',investment_approved=False)

def check(path,root,diagnose=False):
 from strategy_dsl_preflight import preflight_strategy
 result=preflight_strategy(path,root,inspect_planned=True)
 from research_readiness import BLOCKER_CLASSES
 result['blocker_classes']=BLOCKER_CLASSES
 result['research_certification']=dict(investment_approved=False,account_reconstruction=False,held_return_validation='only actual engine execution can validate selected holdings at1bp')
 if diagnose and result['status']=='ok':
  from strategy_dsl import load_strategy_spec
  from strategy_dsl_runner import load_project_engine
  from krx_history_audit import audit_source_history
  spec=load_strategy_spec(path);engine=load_project_engine(root)
  panel=engine.load_krx_equity_panel(start=spec.period.start,end=spec.period.end,markets=spec.universe.markets,columns=['Date','Code','Market','Close','ChangesRatio'],repo_root=root)
  summary,codes,candidates=audit_source_history(panel,spec.period.start,spec.period.end,spec.universe.markets,root)
  result['full_panel_diagnostics']=summary
  result['full_panel_diagnostics']['not_selected_exposure']=True
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=WORKBENCH_CONTRACT['commands']);p.add_argument('--strategy',type=Path);p.add_argument('--request');p.add_argument('--output',type=Path);p.add_argument('--output-dir',type=Path);p.add_argument('--saved-run',type=Path);p.add_argument('--report-periods',type=Path);p.add_argument('--research-model-from',type=Path);p.add_argument('--execution-contract-from',type=Path);p.add_argument('--diagnose-panel',action='store_true');p.add_argument('--repo-root',type=Path,default=ROOT);a=p.parse_args()
 try:
  contract=None
  if a.execution_contract_from:
   from strategy_dsl import load_strategy_spec
   declared=load_strategy_spec(a.execution_contract_from).execution.to_dict()
   contract={k:v for k,v in declared.items() if k in ['nontradable_policy','data_loading']}
   if not contract:raise ValueError('No explicit execution/preparation contract in source specification')
   if a.command not in ['translate','run'] or not a.request:raise ValueError('--execution-contract-from requires a Korean translate/run request')
  if a.command=='capabilities':
   from export_strategy_dsl_contract import build_capabilities
   result=build_capabilities()
  elif a.command=='inventory':result=inventory(a.repo_root)
  elif a.command=='examples':
   result=json.loads((a.repo_root/'config/research/validated_examples_v1.json').read_text())
  elif a.command=='issues':
   if not a.saved_run:raise ValueError('--saved-run required')
   found={name:json.loads((a.saved_run/name).read_text()) for name in ['readiness_incidents.json','runtime_incident.json'] if (a.saved_run/name).is_file()}
   if not found:raise ValueError('No preserved structured incidents in this run')
   result=dict(status='ok',saved_incidents=found,scope='Exact previous diagnostics only; current inputs must pass fresh preflight before execution',investment_approved=False)
  elif a.command=='translate':
   if not a.request:raise ValueError('--request required')
   model=json.loads(a.research_model_from.read_text())['research'] if a.research_model_from else None
   spec=korean_spec(a.request,research=model,execution_contract=contract);result=dict(status='ok',strategy=spec.to_dict(),strategy_fingerprint=spec.fingerprint(),investment_approved=False)
  elif a.command=='check':
   if not a.strategy:raise ValueError('--strategy required')
   result=check(a.strategy,a.repo_root,a.diagnose_panel)
  else:
   from strategy_dsl_run import run_checked_strategy
   if bool(a.strategy)==bool(a.request):raise ValueError('exactly one of --strategy/--request required')
   if a.strategy:result=run_checked_strategy(a.strategy,a.repo_root,a.output_dir,report_periods=a.report_periods,inspect_planned=True)
   else:
    model=json.loads(a.research_model_from.read_text())['research'] if a.research_model_from else None
    with tempfile.TemporaryDirectory(prefix='korean-dsl-') as temporary:
     f=Path(temporary)/'request.json';f.write_text(json.dumps(korean_spec(a.request,research=model,execution_contract=contract).to_dict(),ensure_ascii=False))
     result=run_checked_strategy(f,a.repo_root,a.output_dir,report_periods=a.report_periods,inspect_planned=True)
  if a.output:
   with a.output.open('x') as stream:json.dump(result['strategy'] if a.command=='translate' else result,stream,ensure_ascii=False,indent=2)
  print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},ensure_ascii=False,indent=2,default=str))
  from strategy_dsl_run import exit_code_for_run
  return exit_code_for_run({'status':result.get('status','ok')})
 except (ValueError,KeyError,TypeError,OSError) as e:
  from strategy_dsl_run import exit_code_for_run
  status='capability_gap' if isinstance(e,(ValueError,KeyError,TypeError)) else 'data_gap'
  print(json.dumps(dict(status=status,error={'type':type(e).__name__,'message':str(e)},investment_approved=False),ensure_ascii=False));return exit_code_for_run({'status':status})
if __name__=='__main__':raise SystemExit(main())
