"""Actual browser/current subperiod analysis and one changed-period engine run."""
import argparse,hashlib,importlib.util,json,select,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-store',type=Path,required=True);p.add_argument('--source-proof',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);store=out/'store';source=json.loads(a.source_proof.read_text());runs={r['name']:r['id']for r in source['runs']}
 ids=[runs['json_same_top1'],runs['research_momentum_top3_2020']];before={}
 for jid in ids:
  shutil.copytree(a.source_store/'runs'/jid,store/'runs'/jid);(store/'jobs').mkdir(exist_ok=True);shutil.copy2(a.source_store/'jobs'/str(jid+'.json'),store/'jobs'/str(jid+'.json'))
  for f in (a.source_store/'runs'/jid).rglob('*'):
   if f.is_file():before[str(f.relative_to(a.source_store))]=digest(f)
 with(out/'server-stderr.log').open('w')as err:
  server=subprocess.Popen([sys.executable,'-I',str(ROOT/'scripts/research_web.py'),'--store',str(store),'--port','0'],cwd=ROOT,stdout=subprocess.PIPE,stderr=err,text=True)
  try:
   if not select.select([server.stdout],[],[],30)[0]:raise RuntimeError('SERVER_START_TIMEOUT')
   line=server.stdout.readline()
   if not line:raise RuntimeError((out/'server-stderr.log').read_text())
   ready=json.loads(line)
   with(out/'browser.log').open('w')as log:
    try:subprocess.run(['node',str(ROOT/'scripts/verify_research_periods.cjs'),ready['url'],str(out/'browser')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
    except(subprocess.CalledProcessError,subprocess.TimeoutExpired):log.flush();print((out/'browser.log').read_text()[-10000:],file=sys.stderr);raise
  finally:server.terminate();server.wait(timeout=10)
 proof=json.loads((out/'browser/verification.json').read_text());original=store/'runs'/proof['source_run']/'run';analysis=store/'runs'/proof['analysis_id']/'run';rerun=store/'runs'/proof['rerun_id']/'run'
 assert digest(original/'artifacts/daily_nav.csv')==digest(analysis/'artifacts/daily_nav.csv')
 assert not(analysis/'artifacts/target_weights.csv').exists(),'Analysis must not create engine trades'
 manifest=json.loads((analysis/'report/chat_manifest_CURRENT.json').read_text());selected=manifest['periods']['selection']
 assert selected['actual_start']=='2024-06-03'and selected['ending_asset_date']=='2024-10-31'
 assert selected['baseline_date']=='2024-05-31'
 import pandas as pd
 nav=pd.read_csv(rerun/'artifacts/daily_nav.csv');assert nav.Date.iloc[0]=='2019-12-02'and nav.Date.iloc[-1]=='2020-12-30'
 assert(nav.loc[nav.Date.lt('2020-05-04'),'NAV_Gross']==1).all(),'New run must begin in cash, no copied prior holdings'
 preflight=json.loads((rerun/'preflight.json').read_text());assert '2019'in json.dumps(preflight)and'2020'in json.dumps(preflight)
 path=ROOT/'docs/research/stage15-research-environment-20261017/verify_research_nav.py';spec=importlib.util.spec_from_file_location('independent_period_book',path);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 independent=oracle.verify(rerun,out/'independent-rerun')
 for relative,sha in before.items():assert digest(a.source_store/relative)==sha and digest(store/relative)==sha
 result=dict(status='PASS_REAL_PERIOD_WORKSPACE',browser=proof,source_nav_unchanged=digest(analysis/'artifacts/daily_nav.csv'),
  source_backtests_preserved_files=len(before),analysis_engine_executions=0,new_backtest_executions=1,independent_rerun=independent,
  canonical_analysis_baseline=selected['baseline_date'],new_executable_period='momentum3-1 top3 2019-12-02..2020-12-30',source_HTTP=0,investment_approved=False)
 (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['browser','independent_rerun']},ensure_ascii=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
