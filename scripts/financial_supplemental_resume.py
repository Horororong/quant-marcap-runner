"""One explicit41-document supplemental approval; original3-run ledger is immutable.

Manual dispatch only. Reservations cover worst-case retry HTTP. Source/PIT
contracts are shared with the deployed collector; no new financial values publish.
"""
import copy,json,os
from datetime import datetime
from pathlib import Path
from scripts import financial_limited_resume as old
CONFIG=Path('config/financial_supplemental_41_v1.json')
STATE=Path('data/status/dart_legacy_supplemental_41_v1.json')
APPROVAL='finite41-20261023'
ORDER_SHA='7bfafadb83322a9c7e2d358fd3c0f9331784b7597770c133ed83fb3e78283904'
TRIAL='39863731314'

def approval_hash(c):return old.sha(old.raw(c))
def validate_approval(c):
 if c['approval_id']!=APPROVAL or c['contract']!='supplemental-finite-source-v1':raise ValueError('SUPPLEMENTAL_APPROVAL_ID')
 expected=dict(max_executions=2,batch_limits=[21,20],max_HTTP=82,max_HTTP_per_document=2,document_seconds=90,run_seconds=600,maximum_runs_per_KST_day=1,parent_run='39504052321',trial_run=TRIAL,automatic_financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6')
 if any(c.get(k)!=v for k,v in expected.items()):raise ValueError('SUPPLEMENTAL_PROTECTED_LIMIT_CHANGED')
 rs=c['receipts']
 if len(rs)!=41 or len(set(rs))!=41 or rs!=sorted(rs)or old.sha(('\n'.join(rs)+'\n').encode())!=ORDER_SHA:raise ValueError('SUPPLEMENTAL_FROZEN_ORDER')
 if c['expires_at_utc']!='2026-10-25T14:59:59+00:00':raise ValueError('SUPPLEMENTAL_FINITE_WINDOW_CHANGED')
 return rs

def initial(c,original):
 return dict(contract=c['contract'],approval_id=APPROVAL,approval_sha256=approval_hash(c),phase='READY',attempts=[],completed_receipts=[],original_runs_sha256=old.sha(old.raw(original['runs'])),financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6')
def check(c,budget,original,operating,now,batch_documents,approval_id):
 rs=validate_approval(c);old.check_contract(operating,original)
 if original.get('contract')!=old.CONTRACT or sum(s['reserved_documents']for s in original['runs'])>300:raise ValueError('SUPPLEMENTAL_ORIGINAL_CONTRACT_OR_RESERVATIONS')
 if approval_id!=APPROVAL:raise ValueError('SUPPLEMENTAL_EXPLICIT_ID_REQUIRED')
 if now>datetime.fromisoformat(c['expires_at_utc']):raise ValueError('SUPPLEMENTAL_WINDOW_EXPIRED')
 if now<datetime.fromisoformat(c['approved_at_utc']):raise ValueError('SUPPLEMENTAL_BEFORE_APPROVAL')
 original_attempts=original['runs']+[s for r in original['runs']for s in r.get('resume_segments',[])]
 if len(original_attempts)!=3 or original_attempts[-1]['run_id']!=TRIAL:raise ValueError('SUPPLEMENTAL_ORIGINAL_THREE_EXECUTIONS_REQUIRED')
 if original['phase']!='PAUSED_QUEUE'or original['runs'][-1]['run_id']!=c['parent_run']:raise ValueError('SUPPLEMENTAL_ORIGINAL_PHASE_OR_PARENT')
 if (original.get('first_review')or{}).get('status')!='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION':raise ValueError('SUPPLEMENTAL_FIRST_REVIEW_REQUIRED')
 if budget['approval_id']!=APPROVAL or budget['approval_sha256']!=approval_hash(c)or budget['contract']!=c['contract']:raise ValueError('SUPPLEMENTAL_REBOUND_APPROVAL')
 if budget['original_runs_sha256']!=old.sha(old.raw(original['runs'])):raise ValueError('SUPPLEMENTAL_ORIGINAL_HISTORY_CHANGED')
 if budget['phase']not in {'READY','PAUSED'}:raise ValueError('SUPPLEMENTAL_LEASE_OR_FAILURE_HELD')
 for k,v in [('financial_publication','HOLD'),('backtest_eligible',False),('investment_PIT','0/6')]:
  if budget.get(k)!=v:raise ValueError('SUPPLEMENTAL_FINANCIAL_GATE')
 attempts=budget['attempts']
 if len(attempts)>=2:raise ValueError('SUPPLEMENTAL_EXECUTION_BUDGET_EXHAUSTED')
 if any(s['day_kst']==old.local_day(now)for s in original_attempts+attempts):raise ValueError('ONCE_PER_KST_DAY')
 if len({s['run_id']for s in attempts})!=len(attempts):raise ValueError('SUPPLEMENTAL_DUPLICATE_EXECUTION')
 complete=budget['completed_receipts']
 if complete!=rs[:len(complete)]or len(complete)!=len(set(complete)):raise ValueError('SUPPLEMENTAL_CHECKPOINT_PREFIX')
 if len(original['completed_receipts'])!=len(set(original['completed_receipts']))or any(r not in original['completed_receipts']for r in complete):raise ValueError('SUPPLEMENTAL_DUPLICATE_OR_MISSING_DURABLE')
 if any(r in original['completed_receipts']for r in rs[len(complete):]):raise ValueError('SUPPLEMENTAL_ALREADY_COLLECTED')
 checkpoint=complete[-1]if complete else'20100331002063'
 if original['last_checkpoint']!=checkpoint:raise ValueError('SUPPLEMENTAL_CHECKPOINT_MISMATCH')
 cap=c['batch_limits'][len(attempts)]
 if batch_documents!=cap:raise ValueError('SUPPLEMENTAL_FIXED_SEGMENT_CAP_REQUIRED')
 selected=rs[len(complete):len(complete)+cap]
 if not selected:raise ValueError('SUPPLEMENTAL_NO_PENDING_SOURCE')
 reserved=sum(s['http_reserved']for s in attempts)
 if reserved+2*len(selected)>82 or any(s['http_reserved']!=2*s['document_limit']for s in attempts):raise ValueError('SUPPLEMENTAL_HTTP_BUDGET_EXHAUSTED')
 return selected

def qualify_trial(proof):
 if proof['status']!='PASS_REAL_TRIAL_PREREQUISITES'or proof['run_id']!=TRIAL or proof['new_originals']!=2 or proof['new_candidates']<=0 or not 2<=proof['HTTP_requests_including_retries']<=4 or not proof['normal_exit']or proof['source_elapsed_seconds']>=600 or proof['duplicate_receipts']or proof['duplicate_candidates']or proof['checkpoint_after']!='20100331002063':raise ValueError('SUPPLEMENTAL_TRIAL_NOT_QUALIFIED')
 if [d['receipt']for d in proof['documents']]!=['20100331002062','20100331002063']or any(d['candidate_fields']<=0 or d['zip_crc']!='PASS'for d in proof['documents']):raise ValueError('SUPPLEMENTAL_TRIAL_DOCUMENTS_INCOMPLETE')

def validate_result(meta,result,out):
 old.validate_result(meta,result,out)
 if result['state']['status']=='NO_DOCUMENT':raise ValueError('SUPPLEMENTAL_SOURCE_UNAVAILABLE_STOP')

def observed_HTTP(batch):
 starts=retries=0
 for p in batch.glob('workers/*/progress.jsonl'):
  for line in p.read_text().splitlines():
   r=json.loads(line);starts+=r['stage']=='http_start';retries+=r['stage']=='http_retry'
 return starts,retries

def run_supplemental(root,out,event,parent_run,batch_documents,approval_id):
 if os.getenv('GITHUB_REF')!='refs/heads/main'or os.getenv('GITHUB_RUN_ATTEMPT','1')!='1':raise ValueError('MAIN_FIRST_ATTEMPT_ONLY')
 api=old.GitHub();head=api.head();original_bytes=api.content(old.STATE,head);original=json.loads(original_bytes);operating=json.loads((root/old.CONFIG).read_text());c=json.loads((root/CONFIG).read_text());previous=api.content(STATE,head);budget=json.loads(previous)if previous else initial(c,original);now=datetime.now(old.UTC)
 try:
  old.check_q3_day(api,head,now)
  if parent_run!=c['parent_run']:raise ValueError('SUPPLEMENTAL_PARENT_REQUIRED')
  selected=check(c,budget,original,operating,now,batch_documents,approval_id)
 except ValueError as e:
  out.mkdir(parents=True,exist_ok=False);old.atomic(out/'gate.json',dict(status='NO_COLLECTION',reason=str(e),approval_id=APPROVAL));print(json.dumps(dict(status='NO_COLLECTION',reason=str(e))));return 0
 for name,expected in operating['source_code_sha256'].items():
  if old.sha((root/name).read_bytes())!=expected:raise ValueError('UNAPPROVED_SOURCE_CODE:'+name)
 from scripts.financial_limited_review import verify_approval
 verify_approval(root,original)
 from scripts.check_finite_trial_artifact import verify_remote
 proof=verify_remote();qualify_trial(proof)
 if proof['original_runs_sha256']!=old.sha(old.raw(original['runs'])):raise ValueError('SUPPLEMENTAL_TRIAL_HISTORY_CHANGED')
 prior=json.loads((root/old.BASE/'runs'/parent_run/'selection.json').read_text());by={s['rcept_no']:s for s in prior['samples']}
 if old.sha(old.raw(prior['samples']))!=prior['selection_sha256']or any(r not in by for r in c['receipts']):raise ValueError('SUPPLEMENTAL_PARENT_SELECTION_CHANGED')
 run_id=os.environ['GITHUB_RUN_ID']
 if run_id in {s['run_id']for s in budget['attempts']}:raise ValueError('SUPPLEMENTAL_RUN_REPLAY')
 plan=dict(prior,run_id=run_id,parent_run_id=parent_run,approval_id=APPROVAL,samples=[by[r]for r in selected],start_checkpoint=original['last_checkpoint'],selection_sha256=old.sha(old.raw([by[r]for r in selected])),frozen41_order_sha256=ORDER_SHA,new_document_reservation=0)
 out.mkdir(parents=True,exist_ok=False);old.atomic(out/'batch_plan.json',plan);old.atomic(out/'trial_qualification.json',proof)
 slot=dict(run_id=run_id,day_kst=old.local_day(now),started_at_utc=old.stamp(),status='RUNNING',document_limit=len(selected),http_reserved=2*len(selected),receipts=selected,completed_receipts=[],new_reservation=0)
 budget['attempts'].append(slot);budget['phase']='RUNNING';original['phase']='RUNNING_SUPPLEMENTAL';leased=old.raw(original)
 reservation=api.commit({old.STATE:leased,STATE:old.raw(budget),old.BASE/'runs'/run_id/'selection.json':old.raw(plan)},original_bytes,root,'Lease explicit finite41 supplemental '+run_id+' [skip ci]');old.atomic(out/'reservation.json',dict(commit=reservation,approval_id=APPROVAL))
 batch=out/'batch';code=1;failure=''
 try:code=old.run_batch(plan['samples'],batch,result_validator=validate_result,document_seconds=90,total_seconds=600,max_documents=len(selected))
 except Exception as e:failure=type(e).__name__+':'+str(e)if isinstance(e,ValueError)else type(e).__name__
 if not(batch/'run_status.json').exists():raise ValueError('SUPPLEMENTAL_NO_DURABLE_STATUS_LEASE_STAYS_HELD')
 summary=old.summarize(batch,plan);old.atomic(out/'summary.json',summary);completed=summary['completed_receipts']
 if completed!=selected[:len(completed)]:raise ValueError('SUPPLEMENTAL_RESULT_CHECKPOINT_PREFIX')
 actual,retries=observed_HTTP(batch)
 if actual>slot['http_reserved']:raise ValueError('SUPPLEMENTAL_HTTP_CONTRACT_BREACH')
 # A missing/failed worker never frees its worst-case reserved HTTP allocation.
 transfers=[]
 from scripts.financial_rollout_transfer import main as transfer
 for i in range(0,len(plan['samples']),20):
  folder=out/f'preserved{i//20:02d}';folder.mkdir();subset={s['rcept_no']for s in plan['samples'][i:i+20]}
  for name in ['native','service-responses','results','collection','quality']:
   for p in(batch/name).glob('*'):
    if any(p.name.startswith(r)for r in subset):dest=folder/name/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
  old.atomic(folder/'selection.json',dict(samples=[s for s in plan['samples'][i:i+20]]));old.atomic(folder/'run_status.json',summary['run_status']);transfer(folder);transfers.append(json.loads((folder/'transfer.json').read_text()))
 budget['completed_receipts'].extend(completed);original['completed_receipts'].extend(completed)
 if completed:original['last_checkpoint']=completed[-1]
 remaining=c['receipts'][len(budget['completed_receipts']):]
 slot.update(status='STOPPED'if code else'COMPLETE',completed_at_utc=old.stamp(),completed_receipts=completed,HTTP_requests_observed=actual,retries_observed=retries,candidate_fields=summary['candidate_fields'],stop_reason=failure or summary['run_status']['stop_reason'],source_elapsed_seconds=summary['run_status']['elapsed_seconds'])
 budget.update(phase='HOLD_FAILURE'if code else'EXHAUSTED_WITH_PENDING'if remaining and len(budget['attempts'])>=2 else'PAUSED'if remaining else'COMPLETE',remaining_receipts=remaining)
 original['phase']='HOLD_SUPPLEMENTAL_FAILURE'if code else'PAUSED_QUEUE'if remaining else'OBSERVATION_COMPLETE'
 if old.sha(old.raw(original['runs']))!=budget['original_runs_sha256']:raise ValueError('SUPPLEMENTAL_ORIGINAL_HISTORY_CHANGED')
 manifest=dict(summary=summary,transfers=transfers,approval_id=APPROVAL,approval_sha256=approval_hash(c),plan_sha256=old.sha(old.raw(plan)),HTTP_requests_observed=actual,http_reserved=slot['http_reserved'],financial_publication='HOLD',code_sha=os.environ['GITHUB_SHA'])
 files={old.STATE:old.raw(original),STATE:old.raw(budget),old.BASE/'runs'/run_id/'manifest.json':old.raw(manifest)};files.update({old.BASE/'runs'/run_id/f'sources{i:02d}.json.gz.b64':dict(sha=t['blob_sha'])for i,t in enumerate(transfers)})
 final=api.commit(files,leased,root,'Preserve finite41 source results '+run_id+'; financial publication HOLD [skip ci]');old.atomic(out/'final_commit.json',dict(sha=final,phase=budget['phase'],checkpoint=original['last_checkpoint']));print(json.dumps(dict(status=budget['phase'],commit=final,new_originals=summary['durable_terminal_documents'],new_candidates=summary['candidate_fields'],HTTP_requests_observed=actual,http_reserved=slot['http_reserved'],checkpoint=original['last_checkpoint'],pending=len(remaining),financial_publication='HOLD')));return code
