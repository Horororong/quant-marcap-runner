"""Frozen151file baseline; explicit version/preflight evolution, no rebasing pins."""
import hashlib,json,sys
from pathlib import Path
HOME=Path(__file__).resolve().parent

def verify(runs,output):
 m=json.loads((HOME/'regression_baseline.json').read_text());checks=[]
 # Explicit approved owner evolution for additive opt-in contracts and official Samsung split.
 # Frozen archive/numeric pins remain untouched; all other plan fields still exact.
 versions=dict(execution_engine_version='v2-16-exec-9',corporate_action_registry_version='9',dsl_machine_contract_version='29')
 for name,pin in m['files'].items():
  if pin['comparison']!='exact_baseline':continue
  raw=(runs/name).read_bytes();actual=hashlib.sha256(raw).hexdigest()
  if name.endswith('/execution_plan.json') or name.endswith('/preflight.json'):
   prior=(HOME/'baseline_contracts'/name).read_bytes();assert hashlib.sha256(prior).hexdigest()==pin['sha256'],name
   a=json.loads(raw);b=json.loads(prior)
   if name.endswith('/execution_plan.json'):
    assert {k:a[k] for k in versions}==versions,name
    assert {k:v for k,v in a.items() if k not in versions}=={k:v for k,v in b.items() if k not in versions},name
    reason='Only explicit machine/engine/registry contract version fields evolved; all other execution plan values unchanged'
   else:
    assert a['status']=='ok' and a['ready_for_execution'] and not a['issues']
    for key in ['strategy_fingerprint','requested_period','benchmark','factor_sources']:assert a[key]==b[key],(name,key)
    for key in ['actual_start','actual_end','rows']:assert a['krx_panel'][key]==b['krx_panel'][key],(name,key)
    assert all(y['status']=='complete' for y in a['history_coverage_by_year'])
    reason='Planned-readiness v1 replaces source-only research workbench preflight; original inputs/dates/rows/benchmark retained and all planned exposures now inspected'
   checks.append(dict(file=name,status='INTENTIONAL_CONTRACT_EVOLUTION',before_sha256=pin['sha256'],after_sha256=actual,reason=reason))
  else:
   assert len(raw)==pin['bytes'] and actual==pin['sha256'],('REGRESSION',name,pin['sha256'],actual)
   checks.append(dict(file=name,status='EXACT_FROZEN_BYTES',sha256=actual))
 summary=dict(status='PASS_FROZEN_REGRESSION_WITH_EXPLICIT_CONTRACT_EVOLUTION',preserved_archive_files=len(m['files']),exact_files=sum(r['status']=='EXACT_FROZEN_BYTES' for r in checks),contract_files=sum(r['status']=='INTENTIONAL_CONTRACT_EVOLUTION' for r in checks),volatile_envelopes_preserved_only=sum(r['comparison']!='exact_baseline' for r in m['files'].values()),checks=checks)
 output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');return summary
if __name__=='__main__':print(json.dumps({k:v for k,v in verify(Path(sys.argv[1]),Path(sys.argv[2])).items() if k!='checks'}))
