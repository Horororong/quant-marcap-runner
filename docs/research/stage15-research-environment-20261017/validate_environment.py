"""Pinned-kit research E2E; delegates execution, accounting and CURRENT owners.

Expected numeric files are compared byte-for-byte across local and CI. Absolute
paths/run clocks in manifests/HTML are explicitly not deterministic byte pins.
"""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(HOME)]
from test_research_workbench import REQUEST
from verify_research_nav import verify

JOBS=[
 ('original','research_size_deciles_2019_2020_v1.json','research_2019_2020.json'),
 ('haircut90','research_size_deciles_2019_2020_haircut90.json','research_2019_2020.json'),
 ('listing_lag1','research_size_deciles_2019_2020_listing_lag1.json','research_2019_2020.json'),
 ('momentum2020','research_momentum_top3_2020.json','research_2019_2020.json'),
 ('size2024','research_size_top1_2024.json','research_2024.json')]

def main(out,check):
 out.mkdir(parents=True,exist_ok=False)
 results=[]
 def command(name,args):
  start=time.monotonic()
  with (out/(name+'.log')).open('xb') as stream:
   r=subprocess.run([sys.executable,'-I',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
  results.append(dict(name=name,exit_code=r.returncode,seconds=round(time.monotonic()-start,3)))
  (out/'commands.json').write_text(json.dumps(results,indent=2)+'\n')
  print(name,r.returncode,flush=True)
  if r.returncode:raise RuntimeError(name+' failed; see preserved log')
 for name in ['test_stock_dividend_research.py','test_research_workbench.py',
              'test_requested_period_report.py','test_canonical_performance.py',
              'test_strategy_dsl_run.py','test_strategy_dsl_benchmark.py',
              'test_strategy_dsl_aliases.py','test_factor_registry.py',
              'test_krx_technical_factor_adapter.py','test_krx_volatility_factor_adapter.py']:
  command(name,['-c',"import runpy,sys;sys.path.insert(0,'scripts');runpy.run_path('scripts/"+name+"',run_name='__main__')"])
 command('inventory',['scripts/research_workbench.py','inventory','--output',str(out/'inventory.json')])
 command('readiness',['scripts/research_workbench.py','check','--strategy','config/strategies/research_size_deciles_2019_2020_v1.json','--diagnose-panel','--output',str(out/'readiness.json')])
 command('real_event',['docs/research/stage15-research-environment-20261017/real_event_probe.py',str(out/'real_event')])
 accounting={};pins={}
 for name,spec,periods in JOBS:
  run=out/name
  command(name,['scripts/research_workbench.py','run','--strategy','config/strategies/'+spec,'--report-periods','config/reports/'+periods,'--output-dir',str(run)])
  status=json.loads((run/'run_status.json').read_text())
  assert status['status']=='ok' and status['nav_ready'] and status['report_ready'],status
  accounting[name]=verify(run,out/(name+'_independent'))
  for path in ['artifacts/daily_nav.csv','report/metrics_CURRENT.csv','report/daily_nav_canonical.csv']:
   raw=(run/path).read_bytes();pins[name+'/'+path]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 command('korean',['scripts/research_workbench.py','run','--request',REQUEST,'--research-model-from','config/strategies/research_size_deciles_2019_2020_v1.json','--report-periods','config/reports/research_2019_2020.json','--output-dir',str(out/'korean')])
 original=out/'original';translated=out/'korean'
 for path in ['artifacts/daily_nav.csv','artifacts/target_weights.csv','report/metrics_CURRENT.csv']:
  assert (original/path).read_bytes()==(translated/path).read_bytes(),('Korean pipeline differs',path)
 for variant in ['haircut90','listing_lag1']:
  for path in ['target_weights.csv','decile_membership.csv','execution_schedule.csv']:
   assert (original/'artifacts'/path).read_bytes()==(out/variant/'artifacts'/path).read_bytes(),(variant,path)
 (out/'numeric_manifest.json').write_text(json.dumps(pins,indent=2)+'\n')
 if check:
  expected=json.loads((HOME/'numeric_manifest.json').read_text())
  assert pins==expected,'local/CI numeric bytes mismatch'
 summary=dict(status='PASS_RESEARCH_ENVIRONMENT',scope='RESEARCH_ONLY continuous pretax model, not account/PIT certification',investment_use_allowed=False,
  python=sys.executable,github_sha=os.getenv('GITHUB_SHA'),run_id=os.getenv('GITHUB_RUN_ID'),accounting=accounting,
  korean_nav_targets_metrics_bytes_identical=True,sensitivity_selection_timing_invariant=True,numeric_identity_checked=check,
  browser='separate required CI step; local sandbox browser unavailable',commands=len(results))
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--check',action='store_true');a=p.parse_args();main(a.output,a.check)
