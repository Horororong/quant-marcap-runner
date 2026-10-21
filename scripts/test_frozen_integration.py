"""Run exact original frozen inputs; UI-generated equivalent NAV is a separate test."""
import argparse,importlib.util,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 jobs=[('size2024','research_size_top1_2024','research_2024'),('momentum2020','research_momentum_top3_2020','research_2019_2020'),('original','research_size_deciles_2019_2020_v1','research_2019_2020')];commands=[]
 for label,strategy,period in jobs:
  cmd=[sys.executable,'-B','-I',str(ROOT/'scripts/research_workbench.py'),'run','--strategy',str(ROOT/f'config/strategies/{strategy}.json'),'--report-periods',str(ROOT/f'config/reports/{period}.json'),'--output-dir',str(out/label)];start=time.monotonic()
  with(out/(label+'.log')).open('x')as log:result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
  commands.append(dict(label=label,command=cmd,exit_code=result.returncode,seconds=time.monotonic()-start));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  if result.returncode:raise RuntimeError('FROZEN_EXECUTION_FAILED:'+label+'; inspect preserved log before any retry')
 source=ROOT/'docs/research/stage16-continuous-research-20261018/verify_baseline.py';s=importlib.util.spec_from_file_location('frozen_comparator',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
 r=m.verify(out,out/'frozen-regression.json');assert r['exact_files']==130 and r['contract_files']==9
 print(json.dumps({k:v for k,v in r.items()if k!='checks'}))
if __name__=='__main__':main()
