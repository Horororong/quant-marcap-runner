"""Actual-data continuous research checks; reuse DSL, PROJECT, CURRENT and oracle."""
import argparse,json,subprocess,sys,time,hashlib
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'docs/research/stage15-research-environment-20261017'),str(HOME)]
from verify_research_nav import verify as accounting
from verify_baseline import verify as frozen
from test_research_workbench import REQUEST

def main(out,baselines,check):
 assert (baselines/'summary.json').is_file(),'Prerequisite: complete Stage15 regression must finish before this dependent validation'
 assert json.loads((baselines/'summary.json').read_text())['status']=='PASS_RESEARCH_ENVIRONMENT'
 out.mkdir(parents=True,exist_ok=False);commands=[]
 def command(name,args,expected=0):
  t=time.monotonic()
  with (out/(name+'.log')).open('xb') as f:r=subprocess.run([sys.executable,'-I',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
  commands.append(dict(name=name,exit_code=r.returncode,expected_exit=expected,seconds=round(time.monotonic()-t,3)));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(name,r.returncode,flush=True)
  assert r.returncode==expected,(name,r.returncode,expected)
 for name in ['test_corporate_action_reference.py','test_research_planned_readiness.py','test_research_action_scope.py']:
  command(name,['-c',"import runpy,sys;sys.path.insert(0,'scripts');runpy.run_path('scripts/"+name+"',run_name='__main__')"])
 command('primary',['docs/research/stage16-continuous-research-20261018/verify_primary.py'])
 regression=frozen(baselines,out/'frozen_regression.json')
 command('real2021',['docs/research/stage16-continuous-research-20261018/real_lifecycle_probe.py',str(out/'real2021')])
 command('real_kakao',['docs/research/stage16-continuous-research-20261018/real_split_probe.py',str(out/'real_kakao')])
 command('original2019_2025',['scripts/research_workbench.py','run','--strategy','config/strategies/research_size_deciles_2019_2025_v1.json','--report-periods','config/reports/research_continuous_2025.json','--output-dir',str(out/'original2019_2025')],3)
 blockers={}
 p=out/'original2019_2025';r=json.loads((p/'preflight.json').read_text());b=r['first_blocker'];assert (b['kind'],b['security'],b['date'])==('planned_trade_not_tradable','003550','2021-05-03'),b
 assert not json.loads((p/'run_status.json').read_text())['nav_ready'];blockers['original2019_2025']=b
 for name in ['research_original_size_deciles_2001_2025','research_size_top1_2001_2025']:
  command(name,['scripts/research_workbench.py','check','--strategy','config/strategies/'+name+'.json','--output',str(out/(name+'.json'))],3);r=json.loads((out/(name+'.json')).read_text());blockers[name]=r['first_blocker']
 assert blockers['research_original_size_deciles_2001_2025']['kind']=='insufficient_eligible_population'
 assert (blockers['research_size_top1_2001_2025']['security'],blockers['research_size_top1_2001_2025']['date'])==('005930','2018-05-02')
 # 2026 is explicitly separate; no shrinking an input period to obtain success.
 d=json.loads((ROOT/'config/strategies/research_size_top1_2019_2025.json').read_text());d['period']={k:('2026-01-01' if k in ['start','book_start'] else '2026-10-08') for k in d['period']};(out/'input2026.json').write_text(json.dumps(d,ensure_ascii=False))
 command('separate2026',['scripts/research_workbench.py','check','--strategy',str(out/'input2026.json'),'--output',str(out/'readiness2026.json')],3)
 command('issues_lookup',['scripts/research_workbench.py','issues','--saved-run',str(out/'original2019_2025'),'--output',str(out/'saved_issues.json')])
 command('size2019_2025',['scripts/research_workbench.py','run','--strategy','config/strategies/research_size_top1_2019_2025.json','--report-periods','config/reports/research_continuous_2025.json','--output-dir',str(out/'size2019_2025')])
 ledger=accounting(out/'size2019_2025',out/'size2019_2025_independent')
 request=REQUEST.replace('2020-12-31','2025-12-31').replace('시가총액 낮은','시가총액 높은').replace('10분위','상위1개')
 command('korean2019_2025',['scripts/research_workbench.py','run','--request',request,'--research-model-from','config/strategies/research_size_top1_2019_2025.json','--report-periods','config/reports/research_continuous_2025.json','--output-dir',str(out/'korean2019_2025')])
 pins={}
 for name in ['artifacts/daily_nav.csv','artifacts/target_weights.csv','artifacts/selections.csv','report/metrics_CURRENT.csv','report/daily_nav_canonical.csv']:
  raw=(out/'size2019_2025'/name).read_bytes();assert raw==(out/'korean2019_2025'/name).read_bytes(),('Korean differs',name);pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 (out/'numeric_manifest.json').write_text(json.dumps(pins,indent=2)+'\n')
 if check:assert pins==json.loads((HOME/'numeric_manifest.json').read_text()),'new continuous numeric pins differ; never regenerate expected to pass'
 summary=dict(status='PASS_SOFTWARE_AND_AVAILABLE_RESEARCH; ORIGINAL_LONG_DECILES_BLOCKED',investment_approved=False,
  available=['original deciles2019–2020','momentum3-1 top3full2020','size top1full2024','predeclared size top1full2019–2025'],
  ledger=ledger,korean_json_bytes_identical=True,frozen={k:v for k,v in regression.items() if k!='checks'},blockers=blockers,commands=commands,
  scope='Source-panel price/size research, modeled continuous pretax stock rights where used; cash distributions/legal account/PIT not certified; Net means trading costs only')
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='commands'},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--baselines',required=True,type=Path);p.add_argument('--check',action='store_true');a=p.parse_args();main(a.output,a.baselines,a.check)
