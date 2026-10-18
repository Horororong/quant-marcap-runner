"""Actual offline original replays and independent audits; CI != financial approval."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def main(out,originals,runtime,check):
 out.mkdir(parents=True,exist_ok=False);commands=[]
 def run(name,args):
  c=[sys.executable,'-I',*map(str,args)];r=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);(out/(name+'.log')).write_text(r.stdout+r.stderr);commands.append(dict(name=name,command=c,exit_code=r.returncode,log=name+'.log'));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,(name,r.returncode)
 assert Path(sys.executable).absolute()==(runtime/'.venv/bin/python').absolute()
 run('runtime',[runtime/'scripts/sandbox_runtime.py','verify'])
 freeze=json.loads((HOME/'parser_freeze.json').read_text());assert hashlib.sha256((ROOT/'scripts/legacy_native_financials.py').read_bytes()).hexdigest()==freeze['followup']['parser_sha256']
 for name,args in [('financial_units',['-m','unittest','discover','-s','tests','-p','test_financial*.py','-v']),('service',['-m','unittest','discover','-s','scripts','-p','test_dart_service_status.py','-v']),('phase',['-m','unittest','discover','-s','scripts','-p','test_fast_backfill_phase*.py','-v']),('source_quality',['-m','unittest','discover','-s','scripts','-p','test_legacy_document_quality.py','-v'])]:run(name,args)
 run('main_patch_apply_and_rollback',[HOME/'test_main_proposal.py'])
 run('pinned_v7',[HOME/'replay.py','--before','--cohort','development','--output',out/'v7'])
 run('reextract_v81',[HOME/'replay.py','--output',out/'v81'])
 run('independent_controls',[HOME/'compare.py','--replay',out/'v81','--output',out/'audit'])
 run('materialize60',[HOME/'materialize60.py','--originals',originals,'--output',out/'originals'])
 run('replay60',[ROOT/'docs/audits/financial-repair-20261014/replay60.py','--original40',out/'originals/original40','--holdout20',out/'originals/holdout20','--runtime',runtime,'--output',out/'replay60'])
 run('independent_original60',[ROOT/'docs/audits/financial-extraction-stage3-20261014/revalidate.py','--original40',out/'originals/original40','--holdout20',out/'originals/holdout20','--replay',out/'replay60','--output',out/'audit60'])
 run('protected_controls',[HOME/'verify_protected.py','--replay',out/'replay60','--audit',out/'audit60','--output',out/'protected.json'])
 run('old_bytes_preserved',[ROOT/'docs/research/stage16-continuous-research-20261018/preserve.py','--originals',originals,'--output',out/'preservation'])
 report=json.loads((out/'audit/summary.json').read_text());assert report['cohorts']['development']['v8_amount_verdict']=={'PASS':28,'UNVERIFIED':4};assert report['cohorts']['holdout']['v8_amount_verdict']=={'PASS':20,'UNVERIFIED':28}
 assert all('FAIL'not in report['cohorts'][k]['v8_contract_verdict'] for k in report['cohorts'])
 if check:
  for name in ['field_comparison.csv','summary.json']:assert (out/'audit'/name).read_bytes()==(HOME/'results'/name).read_bytes(),name
 result=dict(status='PASS_REPRODUCTION_AND_PROTECTION',financial_population_certification='UNVERIFIED',investment_PIT='0/6',published_main_changed=False,protected=json.loads((out/'protected.json').read_text()),independent_audit=report)
 (out/'validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--originals',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();main(a.output,a.originals,a.runtime,a.check)
