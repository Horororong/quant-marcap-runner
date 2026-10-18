"""Fresh shared-engine validation and HONEST full-request blocking evidence.

This is orchestration/audit only; no factor backtester or metric calculator.
CI success certifies these assertions, never NAV for a blocked full request.
"""
import argparse,csv,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import pandas as pd
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(HOME),str(HOME.parent/'stage15-research-environment-20261017')]
from verify_real_spinoff import verify as real_spin
from verify_div2021 import verify as real_div
from verify_research_nav import verify as ledger
from test_research_workbench import REQUEST


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def validate(out):
 out.mkdir(parents=True,exist_ok=False);commands=[]
 def command(name,args,expected=0):
  start=time.monotonic()
  with (out/(name+'.log')).open('xb') as f:q=subprocess.run([sys.executable,'-I',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
  commands.append(dict(name=name,args=args,exit_code=q.returncode,expected_exit=expected,seconds=round(time.monotonic()-start,3),log_sha256=sha(out/(name+'.log'))));write(out/'commands.json',commands);print(name,q.returncode,flush=True)
  assert q.returncode==expected,(name,q.returncode,expected,'Exact failure log preserved; no unchanged retry')
 frozen=json.loads((HOME/'frozen_baseline.json').read_bytes())
 for name,pin in frozen['files'].items():assert (ROOT/name).stat().st_size==pin['bytes'] and sha(ROOT/name)==pin['sha256'],('FROZEN_EVIDENCE_CHANGED',name)
 declared=json.loads((HOME/'predeclaration.json').read_bytes())
 for pin in declared['strategies']:assert sha(ROOT/pin['path'])==pin['sha256'],('PREDECLARED_INPUT_CHANGED',pin['path'])
 revision=json.loads((HOME/'source_revision.json').read_bytes())
 for pin in [revision['parent'],revision['new_fact_file'],revision['original_fact_file_preserved'],*revision['strategies']]:assert sha(ROOT/pin['path'])==pin['sha256']
 old_spec=json.loads((ROOT/revision['parent']['path']).read_bytes());new_spec=json.loads((ROOT/revision['strategies'][0]['path']).read_bytes())
 for key in old_spec:
  if key not in ['strategy_id','name','title','description','metadata','research']:assert old_spec[key]==new_spec[key],('SOURCE_REVISION_CHANGED_RULES',key)
 source_count=0
 acquisition_gaps=[]
 for folder in sorted(p.name for p in HOME.glob('evidence*') if (p/'state.json').is_file()):
  state=json.loads((HOME/folder/'state.json').read_bytes());assert state['retries']==0
  if state['errors']:
   assert folder=='evidence_historical' and state['errors']==[dict(reason='ValueError',detail='NO_RETURNED_CANDIDATES')]
   acquisition_gaps.append(dict(folder=folder,errors=state['errors'],requests=state['requests'],status='UNVERIFIED_NOT_ABSENCE_PROOF'))
  for pin in state['responses']:
   p=HOME/folder/pin['file'];assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'];source_count+=1
 for name in ['test_event_deferred_execution.py','test_research_spinoff.py','test_execution_scheduling.py','test_stock_dividend_execution.py','test_stock_dividend_research.py','test_annual_selected_preparation.py','test_research_planned_readiness.py','test_cash_share_exchange.py','test_research_workbench.py','test_krx_technical_factor_adapter.py']:
  command(name,['-c',"import runpy,sys;sys.path.insert(0,'scripts');runpy.run_path('scripts/"+name+"',run_name='__main__')"])
 command('generated_contracts',['-c',"import runpy,sys;sys.path.insert(0,'scripts');sys.argv=['scripts/export_strategy_dsl_contract.py','--check'];runpy.run_path(sys.argv[0],run_name='__main__')"])
 real=real_spin(out/'actual_lg_lx_component')
 skt=real_spin(out/'actual_skt_square_component','017670')
 dividends=real_div(out/'actual_dividend2021_component')
 # A FULL prior successful two-year multi-stock experiment. Explicit new model
 # must not alter its numeric outputs; not a reduced substitute for2019–2025.
 original=ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json'
 spec=json.loads(original.read_bytes());spec['execution'].update(nontradable_policy='defer_full_rebalance_events_v1',data_loading='annual_selected_projection');write(out/'component_original.json',spec)
 for name,korean in [('event_contract_original_full2019_2020',False),('korean_original_full2019_2020',True)]:
  args=['scripts/research_workbench.py','run','--report-periods','config/reports/research_2019_2020.json','--output-dir',str(out/name)]
  args+=['--request',REQUEST,'--research-model-from',str(out/'component_original.json'),'--execution-contract-from',str(out/'component_original.json')] if korean else ['--strategy',str(out/'component_original.json')]
  command(name,args)
 pins=json.loads((HOME.parent/'stage15-research-environment-20261017/numeric_manifest.json').read_bytes())
 regression=[]
 for rel in ['artifacts/daily_nav.csv','report/metrics_CURRENT.csv','report/daily_nav_canonical.csv']:
  p=out/'event_contract_original_full2019_2020'/rel;pin=pins['original/'+rel]
  assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],('ORIGINAL_NUMERIC_REGRESSION',rel)
  assert p.read_bytes()==(out/'korean_original_full2019_2020'/rel).read_bytes(),('KOREAN_NUMERIC_DIFFERS',rel)
  regression.append(dict(file=rel,comparison='EXACT_FROZEN_BYTES',**pin))
 for rel in ['target_weights.csv','decile_membership.csv']:
  pin=json.loads((HOME.parent/'stage16-continuous-research-20261018/regression_baseline.json').read_bytes())['files']['original/artifacts/'+rel]
  p=out/'event_contract_original_full2019_2020/artifacts'/rel
  assert sha(p)==pin['sha256'] and p.stat().st_size==pin['bytes']
 # All factor values/selections and target weights are exact; Korean identifiers
 # can differ in their registered factor-name label only.
 left=out/'event_contract_original_full2019_2020';right=out/'korean_original_full2019_2020'
 assert (left/'artifacts/target_weights.csv').read_bytes()==(right/'artifacts/target_weights.csv').read_bytes()
 a=pd.read_csv(left/'artifacts/decile_membership.csv',dtype={'Code':str});b=pd.read_csv(right/'artifacts/decile_membership.csv',dtype={'Code':str});pd.testing.assert_frame_equal(a,b.rename(columns={'factor_rank__Marcap':'factor_rank__size'}),check_exact=True)
 model_ledger=ledger(left,out/'original_independent')
 # Exact original technical lookback/factor selection, with only observation
 # loading changed AFTER full population ranking. Old engine policy retained.
 m=json.loads((ROOT/'config/strategies/research_momentum_top3_2020.json').read_bytes());m['execution'].update(data_loading='annual_selected_projection',nontradable_policy='defer_full_rebalance_events_v1');write(out/'projection_momentum.json',m)
 command('projected_momentum_full2020',['scripts/research_workbench.py','run','--strategy',str(out/'projection_momentum.json'),'--report-periods','config/reports/research_2019_2020.json','--output-dir',str(out/'projected_momentum_full2020')])
 for rel in ['artifacts/daily_nav.csv','report/metrics_CURRENT.csv','report/daily_nav_canonical.csv']:
  p=out/'projected_momentum_full2020'/rel;pin=pins['momentum2020/'+rel]
  assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],('TECHNICAL_PROJECTION_REGRESSION',rel)
  regression.append(dict(file='momentum2020/'+rel,comparison='EXACT_FROZEN_BYTES',**pin))
 # Complete requested periods, all portfolios, original predeclared inputs.
 # Any source/event failure blocks that request; other requests still execute.
 requests=[];incidents=[]
 for pin in declared['strategies']+revision['strategies']:
  path=ROOT/pin['path'];name=path.stem
  command(name,['scripts/research_workbench.py','run','--strategy',str(path),'--report-periods','config/reports/research_continuous_2025.json','--output-dir',str(out/name)],3)
  run=out/name;status=json.loads((run/'run_status.json').read_bytes());audit=json.loads((run/'preflight.json').read_bytes());assert status['status']=='data_gap' and not status['nav_ready'] and not status['report_ready']
  for issue in audit['issues']:incidents.append(dict(strategy=name,**issue))
  requests.append(dict(strategy=name,period=audit['requested_period'],status=status['status'],nav_ready=False,report_ready=False,issue_count=len(audit['issues']),diagnostic_only_count=sum(bool(x.get('diagnostic_only')) for x in audit['issues']),first_blocker=audit['first_blocker'],preflight_sha256=sha(run/'preflight.json'),planned_codes=len(audit['planned_selected_codes']),sessions=audit['observed_sessions'],full_preflight_in_ci_artifact=name+'/preflight.json'))
  if '2019_2025_event' in name:
   assert not any(i['kind']=='held_return_reference_gap' and i['security']=='003550' and i['date']=='2021-05-27' for i in audit['issues']),'LG parent/child not actually reconciled'
   assert {'383800','402340'}.issubset(audit['observation_codes_with_verified_successors'])
   assert not any(i['kind']=='held_return_reference_gap' and i['security']=='017670' and i['date']=='2021-11-29' for i in audit['issues'])
 # Prove original strict order remains blocked at LG's original scheduled day.
 command('original_strict_2019_2025',['scripts/research_workbench.py','run','--strategy','config/strategies/research_size_deciles_2019_2025_v1.json','--report-periods','config/reports/research_continuous_2025.json','--output-dir',str(out/'original_strict_2019_2025')],3)
 old=json.loads((out/'original_strict_2019_2025/preflight.json').read_bytes())['first_blocker'];assert (old['kind'],old['security'],old['date'])==('planned_trade_not_tradable','003550','2021-05-03')
 fields=['strategy','incident_id','portfolio','kind','classification','verdict','security','date','affected_through','occurrences','previous_date','previous_close','close','exchange_return','effective_comparison_return','difference_bps','basis','origin_signal','diagnostic_only']
 with (out/'requested_incidents.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader();writer.writerows(incidents)
 # Cost/turnover aggregation is ledger audit, not a second metric owner.
 trades=pd.read_csv(left/'artifacts/execution_trades.csv');dollar=pd.read_csv(out/'original_independent/independent_daily_ledger.csv')
 totals=dollar.groupby(['portfolio','book'],as_index=False).trading_cost.sum();totals.to_csv(out/'original_trading_cost_totals.csv',index=False)
 turn=trades.groupby(['decile','cost_scenario'],as_index=False)[['buy_turnover','sell_turnover','one_way_turnover','net_buy_turnover','net_sell_turnover']].sum();turn.to_csv(out/'original_turnover_totals.csv',index=False)
 comparison=[]
 for label,path in [('original_deciles_2019_2020',left/'report/metrics_CURRENT.csv'),('momentum_top3_2020',out/'projected_momentum_full2020/report/metrics_CURRENT.csv'),('size_top1_2024',HOME.parent/'stage15-research-environment-20261017/results/size2024_metrics_CURRENT.csv'),('size_top1_2019_2025',HOME.parent/'stage16-continuous-research-20261018/results/size2019_2025_metrics_CURRENT.csv'),('size_top1_deferred_2001_2025',HOME.parent/'long-execution-20261018/results/long2001_2025/metrics_CURRENT.csv')]:
  frame=pd.read_csv(path);frame.insert(0,'experiment',label);frame['metric_owner']='CURRENT only; original values copied without recalculation';frame['scope']='RESEARCH_ONLY; no cash-dividend total return or investment certification';comparison.append(frame)
 pd.concat(comparison,ignore_index=True).to_csv(out/'available_comparison_CURRENT.csv',index=False)
 write(out/'numeric_regression.json',regression)
 summary=dict(status='PASS_COMMON_IMPLEMENTATION_WITH_FULL_REQUESTS_BLOCKED',investment_approved=False,github_sha=os.getenv('GITHUB_SHA'),ci_run_id=os.getenv('GITHUB_RUN_ID'),python=sys.executable,frozen_evidence_files=len(frozen['files']),new_official_responses=source_count,source_requests_this_validation=0,actual_lg_lx=real,actual_skt_square=skt,actual_2021_dividends=dividends,source_acquisition_gaps=acquisition_gaps,original_two_year_independent=model_ledger,korean_original_nav_targets_metrics_exact=True,technical_projection_numeric_exact=True,original_strict_blocker=old,requested_strategies=requests,commands=commands,limitations=['No full requested multi-security NAV accepted; all source blockers retained','No cash-dividend total returns or distribution-tax/broker-account certification','2026 official holiday/index access demonstrated separately; raw original calendars/index stores not changed','No new collection in final validation'])
 write(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='commands'},ensure_ascii=False));return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();validate(a.output)
