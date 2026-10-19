"""Explicit candidate-hash extension of pinned22 runner. Copy into the reference audit directory; all original numeric/period/source/protection controls remain unchanged. CI != financial approval."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def compare_original_controls(audit,baseline,approved):
 import csv
 actual=list(csv.DictReader((audit/'field_comparison.csv').open(newline='')));old=list(csv.DictReader((baseline/'field_comparison.csv').open(newline='')))
 assert len(actual)==len(old)==88
 for a,b in zip(actual,old):
  assert a.keys()==b.keys()
  for key in a:
   if key=='revised_parser':
    assert b[key]==approved['prior_parser_version'] and a[key]==approved['parser_version'],(key,a,b)
   else:assert a[key]==b[key],(key,a,b)
 assert (audit/'summary.json').read_bytes()==(baseline/'summary.json').read_bytes()
 return dict(status='PASS_ALL_FINANCIAL_COLUMNS_IDENTICAL',changed_metadata_column='revised_parser',rows=88,prior_parser=approved['prior_parser_version'],candidate_parser=approved['parser_version'],numeric_period_scope_source_verdict_columns='UNCHANGED',original_golden_files_modified=False)

def main(out,originals,runtime,check,candidate_manifest):
 out.mkdir(parents=True,exist_ok=False);commands=[]
 def run(name,args):
  c=[sys.executable,'-I',*map(str,args)];r=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);(out/(name+'.log')).write_text(r.stdout+r.stderr);commands.append(dict(name=name,command=c,exit_code=r.returncode,log=name+'.log'));(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,(name,r.returncode)
 assert Path(sys.executable).absolute()==(runtime/'.venv/bin/python').absolute()
 run('runtime',[runtime/'scripts/sandbox_runtime.py','verify'])
 freeze=json.loads((HOME/'parser_freeze.json').read_text());approved=json.loads(candidate_manifest.read_text());assert approved['prior_parser_sha256']==freeze['v91_metadata_followup']['parser_sha256'];assert approved['parser_version']=='legacy-v9.2-statement-boundary-guard';assert hashlib.sha256((ROOT/'scripts/legacy_native_financials.py').read_bytes()).hexdigest()==approved['parser_sha256']
 for name,args in [('financial_units',['-m','unittest','discover','-s','tests','-p','test_financial*.py','-v']),('service',['-m','unittest','discover','-s','scripts','-p','test_dart_service_status.py','-v']),('phase',['-m','unittest','discover','-s','scripts','-p','test_fast_backfill_phase*.py','-v']),('source_quality',['-m','unittest','discover','-s','scripts','-p','test_legacy_document_quality.py','-v'])]:run(name,args)
 run('main_patch_apply_and_rollback',[HOME/'candidate_patch_regression.py','--candidate-manifest',candidate_manifest])
 run('pinned_v7',[HOME/'replay.py','--before','--cohort','development','--output',out/'v7'])
 run('reextract_v91',[HOME/'replay.py','--output',out/'v91'])
 run('independent_controls',[HOME/'compare.py','--replay',out/'v91','--output',out/'audit'])
 run('materialize60',[HOME/'materialize60.py','--originals',originals,'--output',out/'originals'])
 run('replay60',[ROOT/'docs/audits/financial-repair-20261014/replay60.py','--original40',out/'originals/original40','--holdout20',out/'originals/holdout20','--runtime',runtime,'--output',out/'replay60'])
 run('independent_original60',[ROOT/'docs/audits/financial-extraction-stage3-20261014/revalidate.py','--original40',out/'originals/original40','--holdout20',out/'originals/holdout20','--replay',out/'replay60','--output',out/'audit60'])
 run('protected_controls',[HOME/'verify_protected.py','--replay',out/'replay60','--audit',out/'audit60','--output',out/'protected.json'])
 run('old_bytes_preserved',[ROOT/'docs/research/stage16-continuous-research-20261018/preserve.py','--originals',originals,'--output',out/'preservation'])
 report=json.loads((out/'audit/summary.json').read_text());assert report['cohorts']['development']['revised_amount_verdict']=={'PASS':28,'UNVERIFIED':4};assert report['cohorts']['holdout']['revised_amount_verdict']=={'PASS':44,'UNVERIFIED':4};assert report['cohorts']['reserve']['revised_amount_verdict']=={'PASS':8}
 assert all('FAIL'not in report['cohorts'][k]['revised_contract_verdict'] for k in report['cohorts'])
 if check:
  delta=compare_original_controls(out/'audit',HOME/'results',approved);(out/'provenance_delta.json').write_text(json.dumps(delta,indent=2)+'\n')
 result=dict(status='PASS_REPRODUCTION_AND_PROTECTION',financial_population_certification='UNVERIFIED',investment_PIT='0/6',published_main_changed=False,protected=json.loads((out/'protected.json').read_text()),independent_audit=report)
 (out/'validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--originals',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--check',action='store_true');p.add_argument('--candidate-manifest',type=Path,required=True);a=p.parse_args();main(a.output,a.originals,a.runtime,a.check,a.candidate_manifest)
