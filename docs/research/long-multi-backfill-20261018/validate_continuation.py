"""Offline reproduction; no API, collection, state reset or original mutation."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
import pandas as pd
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];sys.path.insert(0,str(HOME))
from verify_2026_ledger import verify as ledger
from verify_official_sources import verify as official_sources
REQUEST='기간:2026-01-01~2026-10-16;시장:코스피·코스닥;필터:시가총액>=10조원;팩터:시가총액 높은;포트폴리오:상위1개;리밸런싱:4월말;체결:1거래일뒤종가;비용:수수료1.5bp,매도세15bp,스프레드3bp,슬리피지5bp;벤치마크:코스피'
def verify(out,check):
 out.mkdir(parents=True,exist_ok=False);commands=[]
 def command(name,args,expected=0):
  start=time.monotonic();log=out/(name+'.log')
  with log.open('xb') as stream:r=subprocess.run([sys.executable,'-I',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
  commands.append(dict(name=name,args=args,exit_code=r.returncode,expected=expected,seconds=round(time.monotonic()-start,3),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
  (out/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n');print(name,r.returncode,flush=True)
  assert r.returncode==expected,(name,r.returncode,'Preserved log; do not retry without diagnosis')
 for pattern in ['test_fast_backfill_phase*.py','test_dart_service_status.py','test_audited_source_extensions.py']:
  command(pattern,['-m','unittest','discover','-s','scripts','-p',pattern,'-v'])
 source_verification=official_sources()
 (out/'source_verification.json').write_text(json.dumps(source_verification,indent=2)+'\n')
 command('independent_financial',['docs/research/long-multi-backfill-20261018/verify_independent_audit.py','--output',str(out/'financial')])
 assert json.loads((out/'financial/audit_summary.json').read_bytes())==json.loads((HOME/'results/financial_audit/audit_summary.json').read_bytes())
 source='config/strategies/research_size_top1_2026_asof1016_v1.json';report='config/reports/research_continuous_2025.json'
 for label,argument in [('json',['--strategy',source]),('korean',['--request',REQUEST,'--research-model-from',source])]:
  command(label,['scripts/research_workbench.py','run',*argument,'--report-periods',report,'--output-dir',str(out/label)])
  assert json.loads((out/label/'run_status.json').read_bytes())['status']=='ok'
 a=out/'json';b=out/'korean';records={}
 for f in ['artifacts/daily_nav.csv','artifacts/target_weights.csv','report/metrics_CURRENT.csv','report/daily_nav_canonical.csv']:
  raw=(a/f).read_bytes();assert raw==(b/f).read_bytes(),('Korean/JSON mismatch',f)
  records[f]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 left=pd.read_csv(a/'artifacts/selections.csv',dtype={'Code':str});right=pd.read_csv(b/'artifacts/selections.csv',dtype={'Code':str})
 normalized=[c for c in left if c.startswith('factor_rank__')];mapped=[c for c in right if c.startswith('factor_rank__')]
 pd.testing.assert_frame_equal(left,right.rename(columns=dict(zip(mapped,normalized))),check_exact=True)
 original=json.loads((HOME/'numeric2026_manifest.json').read_bytes()) if check else records
 assert original==records,'Never replace old numeric pins to hide regression'
 result=ledger(a,out/'independent_2026')
 # Frozen successful baseline files are immutable; code migrations only are
 # separately recorded and never relax financial/NAV/selection hashes.
 pins=json.loads((ROOT/'docs/research/multi-asset-20261018/frozen_baseline.json').read_bytes())['files']
 for p,pin in pins.items():
  raw=(ROOT/p).read_bytes();assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],p
 for p in ['data/krx_equities/yearly/marcap-2026.parquet','data/indices/KOSPI.csv']:
  registry=json.loads((ROOT/'config/research/official_source_extensions_v1.json').read_bytes());pin=next(x['base'] for x in registry['datasets'] if x['base']['path']==p)
  assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==pin['sha256']
 (out/'numeric_manifest.json').write_text(json.dumps(records,indent=2)+'\n')
 summary=dict(status='PASS_SOFTWARE_AND_RESEARCH_MODEL_NOT_FINANCIAL_OR_INVESTMENT_CERTIFICATION',original_baseline_files=len(pins),existing_original_2026_and_index_unchanged=True,sessions=192,ledger=result,commands=commands,financial_verdicts=json.loads((out/'financial/audit_summary.json').read_bytes()),PIT_certified=0,investment_approved=False,source_requests=0)
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='commands'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();verify(a.output,a.check)
