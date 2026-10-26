"""Business outcome reporting only. Never dispatches or reads a DART secret."""
import argparse,base64,json,os,subprocess
from pathlib import Path
from datetime import datetime,timezone
PATHS={'original':'data/status/dart_legacy_limited_resume_v1.json','supplemental':'data/status/dart_legacy_supplemental_41_v1.json','q3':'data/status/dart_q3_three_v1.json'}
def snapshot():
 repo=os.environ['GITHUB_REPOSITORY'];states={}
 for key,path in PATHS.items():
  p=subprocess.run(['gh','api',f'repos/{repo}/contents/{path}?ref=main'],capture_output=True,text=True)
  if p.returncode:
   if '404' in p.stderr:states[key]=None;continue
   raise RuntimeError('GitHub state read failed; no credential output')
  states[key]=json.loads(base64.b64decode(json.loads(p.stdout)['content']))
 return {'observed_at':datetime.now(timezone.utc).isoformat(),'states':states}
def read(path):return json.loads(path.read_text())if path.exists()else None
def observe(before,after,source,step):
 b=before.get('states',{});a=after.get('states',{});old=b.get('original')or{};new=a.get('original')or{}
 gate=read(source/'gate.json');q=read(source/'Q3_STATE.json');summary=read(source/'limited_summary.json')or read(source/'summary.json');started=(source/'reservation.json').exists()or bool(q and q.get('executions_used'))or bool(summary)
 known_before=set(old.get('completed_receipts',[]));new_raw=None;http=None;candidates=0;reason='No source completion evidence';normal=False
 if q:
  prior=b.get('q3')or{};new_raw=max(0,q.get('durable_raw_documents',len(q.get('completed_receipts',[])))-prior.get('durable_raw_documents',0));http=q.get('HTTP_attempts');reason=q.get('stop_reason',q.get('phase'));normal=q.get('normal_exit')is True
 elif summary:
  originals={c['rcept_no']for c in summary.get('collection',[])if c.get('source_status')=='DURABLE'and c.get('archives')}
  new_raw=len(originals-known_before);candidates=summary.get('candidate_fields',0);reason=summary.get('run_status',{}).get('stop_reason','Processed source batch');normal=step=='success'
  attempts=(a.get('supplemental')or{}).get('attempts',[])
  current=[x for x in attempts if x.get('run_id')==os.getenv('GITHUB_RUN_ID')]
  if len(current)==1:http=current[0].get('HTTP_requests_observed')
 elif gate:new_raw=0;http=0;reason=gate.get('reason',gate.get('phase','Gate stopped before source collection'))
 if 'states' not in before or not before.get('states'):
  new_raw = 0 if gate and not started else None
 if gate and not started:status='NO_COLLECTION'
 elif step=='failure':status='COLLECTION_FAILED'if started else'PROCESS_FAILED_BEFORE_COLLECTION'
 elif normal and new_raw and new_raw>0:status='RAW_COLLECTED_PENDING_REVIEW'
 elif summary and normal:status='PROCESSED_NO_NEW_RAW'
 elif started:status='INCOMPLETE_OR_UNCONFIRMED'
 else:status='NO_COLLECTION_OR_UNCONFIRMED'
 return {'schema':'collection-outcome-v1','workflow_invocation':'received','process_started':step in ('success','failure'),'process_finished':step in ('success','failure'),'process_step_outcome':step,'collection_started':started,'collection_status':status,'reason':reason,'new_raw_originals':new_raw,'source_HTTP_observed':http,'new_candidates_extracted':candidates,'checkpoint_before':old.get('last_checkpoint'),'checkpoint_after':new.get('last_checkpoint'),'checkpoint_moved':old.get('last_checkpoint')!=new.get('last_checkpoint') if 'last_checkpoint'in old and 'last_checkpoint'in new else None,'semantic_verification':'NOT_RUN_IN_COLLECTION_WORKFLOW','new_semantic_PASS':0,'PIT_verification':'NOT_RUN_IN_COLLECTION_WORKFLOW','new_PIT':0,'new_engine_eligible':0,'financial_publication':'HOLD','automatic_followup_dispatched':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path);p.add_argument('--before',type=Path);p.add_argument('--source-output',type=Path);p.add_argument('--output',type=Path);p.add_argument('--step-outcome',default='skipped');args=p.parse_args()
 if args.snapshot:args.snapshot.write_text(json.dumps(snapshot(),ensure_ascii=False,indent=2));return
 # A missing before snapshot is explicit unknown evidence, never zero progress.
 before=read(args.before)or {'states':{}};after=snapshot();result=observe(before,after,args.source_output,args.step_outcome)
 args.output.mkdir(parents=True,exist_ok=True);(args.output/'collection_outcome.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(args.output/'after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
 text='### Collection business outcome: '+result['collection_status']+'\n\n'+ '\n'.join(f'- {k}: {v}'for k,v in result.items())+'\n'
 if os.getenv('GITHUB_STEP_SUMMARY'):
  with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a')as f:f.write(text)
 if os.getenv('GITHUB_OUTPUT'):
  with Path(os.environ['GITHUB_OUTPUT']).open('a')as f:f.write('collection_status='+result['collection_status']+'\n')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
