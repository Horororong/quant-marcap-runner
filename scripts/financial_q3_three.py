"""One approved Q3 source run on the existing GitHub collector path.

This prepares public preservation only behind a separate explicit dispatch ID.
No API key export, candidate certification, financial publication, or FY reset.
"""
import base64,gzip,io,json,os,re,signal,sys,time,zipfile
from datetime import datetime
from pathlib import Path
from scripts import financial_limited_resume as old
from scripts import financial_q3_source as src

CONFIG=Path('config/financial_q3_three_v1.json')
STATE=Path('data/status/dart_q3_three_v1.json')
SUPP_STATE=Path('data/status/dart_legacy_supplemental_41_v1.json')
SUPP_CONFIG=Path('config/financial_supplemental_41_v1.json')
BASE=Path('data/financials/legacy_2000_2014/quality_v9/q3_three_v1')
APPROVAL='q3-three-company-20261024'
PUBLIC='q3-three-public-preservation-20261024'

def expected_config():
 return dict(contract='q3-fixed-source-v1',approval_id=APPROVAL,max_executions=1,max_HTTP=12,run_seconds=600,maximum_runs_per_KST_day=1,targets=src.TARGETS,metadata=src.LIST_BASE,requires_public_preservation_id=PUBLIC,max_source_pack_compressed_bytes=12*1024*1024,max_source_packs=4,automatic_financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',collection_only_no_semantic_or_PIT_promotion=True)

def initial(config):
 return dict(contract=config['contract'],approval_id=APPROVAL,approval_sha256=old.sha(old.raw(config)),phase='APPROVED_NOT_STARTED',executions_used=0,HTTP_attempts=0,HTTP_reserved=0,requests=[],completed_receipts=[],new_raw_documents=0,source_packs={},financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6')

def validate(config,budget,approval,public):
 if config!=expected_config():raise ValueError('Q3_FIXED_SCOPE_OR_LIMIT_CHANGED')
 if approval!=APPROVAL:raise ValueError('Q3_EXPLICIT_COLLECTION_ID_REQUIRED')
 if public!=PUBLIC:raise ValueError('Q3_PUBLIC_SOURCE_PRESERVATION_APPROVAL_REQUIRED')
 if budget.get('contract')!=config['contract']or budget.get('approval_id')!=APPROVAL or budget.get('approval_sha256')!=old.sha(old.raw(config)):raise ValueError('Q3_APPROVAL_BINDING_CHANGED')
 if budget.get('executions_used')!=0 or budget.get('HTTP_attempts')!=0 or budget.get('phase')!='APPROVED_NOT_STARTED':raise ValueError('Q3_ONE_EXECUTION_ALREADY_USED_NO_AUTOMATIC_RETRY')
 if budget.get('financial_publication')!='HOLD' or budget.get('backtest_eligible')is not False or budget.get('investment_PIT')!='0/6':raise ValueError('Q3_FINANCIAL_GATE_CHANGED')

def source_pack(folder,receipt=None):
 """Public originals only after explicit approval; never preserve a key/URL."""
 files={}
 patterns=['metadata/*.json']+([receipt+'-*',receipt+'-official.json']if receipt else[])
 for pattern in patterns:
  for p in sorted(folder.glob(pattern)):
   if not p.is_file():continue
   raw=p.read_bytes()
   for name in ['DART_API_KEY','GH_TOKEN']:
    secret=os.getenv(name,'')
    if secret and secret.encode()in raw:raise ValueError('CREDENTIAL_IN_SOURCE_PACK_REFUSED')
    if secret and p.suffix=='.zip':
     with zipfile.ZipFile(io.BytesIO(raw))as z:
      if any(secret.encode()in z.read(i)for i in z.infolist()if not i.is_dir()):raise ValueError('CREDENTIAL_IN_ZIP_MEMBER_REFUSED')
   files[str(p.relative_to(folder))]=base64.b64encode(raw).decode()
 raw=json.dumps(dict(files=files),sort_keys=True,separators=(',',':')).encode();packed=gzip.compress(raw,mtime=0)
 if len(packed)>12*1024*1024:raise ValueError('Q3_SOURCE_PACK_STORAGE_CAP')
 entries=[dict(path=n,bytes=len(base64.b64decode(b)),sha256=old.sha(base64.b64decode(b)))for n,b in files.items()]
 return packed,dict(compressed_sha256=old.sha(packed),compressed_bytes=len(packed),files=entries,financial_certification='UNVERIFIED',PIT='UNVERIFIED',engine_eligible=False)

class HardDeadline(BaseException):pass
def deadline_handler(*unused):raise HardDeadline('Q3_600_SECONDS_EXHAUSTED_LEASE_REMAINS_HELD')

def run_q3(root,out,approval,public,api=None,transport=None,now=None):
 if os.getenv('GITHUB_REF')!='refs/heads/main' or os.getenv('GITHUB_RUN_ATTEMPT','1')!='1':raise ValueError('MAIN_FIRST_ATTEMPT_ONLY')
 if not sys.flags.isolated or sys.prefix==sys.base_prefix:raise ValueError('ISOLATED_FIXED_KIT_VENV_REQUIRED')
 begin=time.monotonic();prior_handler=signal.signal(signal.SIGALRM,deadline_handler);signal.setitimer(signal.ITIMER_REAL,600)
 try:return _run(root,out,approval,public,api,transport,now,begin)
 except Exception as e:
  if not (out/'Q3_STATE.json').exists():
   out.mkdir(parents=True,exist_ok=True)
   reason=str(e)if isinstance(e,ValueError)else str(e)if re.fullmatch(r'GITHUB_HTTP_\d{3}',str(e))else type(e).__name__
   old.atomic(out/'gate.json',dict(status='NO_COLLECTION',reason=reason,execution_consumed=0,DART_HTTP=0,financial_publication='HOLD'))
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,prior_handler)

def _run(root,out,approval,public,api,transport,now,begin):
 config=json.loads((root/CONFIG).read_text())
 # Explicit publication authority is checked before any network call or lease.
 if config!=expected_config()or approval!=APPROVAL or public!=PUBLIC:raise ValueError('Q3_COLLECTION_OR_PUBLIC_PRESERVATION_NOT_APPROVED')
 if not os.getenv('DART_API_KEY'):raise ValueError('Q3_DART_SECRET_MISSING_NO_LEASE')
 api=api or old.GitHub();head=api.head();original_bytes=api.content(old.STATE,head);original=json.loads(original_bytes)
 supp_bytes=api.content(SUPP_STATE,head);supp=json.loads(supp_bytes);sc=json.loads((root/SUPP_CONFIG).read_text())
 operating=json.loads((root/old.CONFIG).read_text());old.check_contract(operating,original)
 from scripts.financial_supplemental_resume import validate_approval
 validate_approval(sc)
 for name,pin in operating['source_code_sha256'].items():
  if old.sha((root/name).read_bytes())!=pin:raise ValueError('UNAPPROVED_SOURCE_OWNER:'+name)
 previous=api.content(STATE,head);state=json.loads(previous)if previous else initial(config)
 validate(config,state,approval,public)
 if previous is not None:raise ValueError('Q3_EXISTING_DURABLE_LEDGER_NO_RESTART')
 now=now or datetime.now(old.UTC)
 # Same existing ledger history and KST daily rule; the workflow concurrency
 # group serializes FY and Q3. Active/failure phases are checked by this guard.
 active=[]
 for workflow in ['backfill-dart-legacy-2000-2014.yml','backfill-dart-legacy-quarterly.yml']:
  runs=api.call('/actions/workflows/'+workflow+'/runs?per_page=20')['workflow_runs']
  active.extend(dict(id=r['id'],status=r['status'])for r in runs if str(r['id'])!=os.environ['GITHUB_RUN_ID']and r['status']in {'queued','in_progress','waiting','pending'})
 src.gate(original,supp,sc,active,now)
 old.check_q3_day(api,head,now,q3_mode=True)
 from scripts.financial_limited_review import verify_approval
 verify_approval(root,original)
 run_id=os.environ['GITHUB_RUN_ID'];out.mkdir(parents=True,exist_ok=False)
 checkout=os.getenv('SOURCE_CHECKOUT_SHA','')
 if not re.fullmatch('[0-9a-f]{40}',checkout):raise ValueError('ACTUAL_CHECKOUT_SHA_REQUIRED_NO_LEASE')
 state.update(phase='RUNNING',executions_used=1,HTTP_reserved=12,run_id=run_id,day_kst=old.local_day(now),started_at_utc=old.stamp(),public_preservation_approval=public,source_checkout=checkout,dispatch_SHA=os.getenv('GITHUB_SHA','UNVERIFIED'),original_runs_sha256=old.sha(old.raw(original['runs'])),original_state_sha256=old.sha(original_bytes),supplemental_state_sha256=old.sha(supp_bytes))
 originals_fingerprint=old.sha(original_bytes);supp_fingerprint=old.sha(supp_bytes)
 extra={SUPP_STATE:supp_bytes}
 for p in [CONFIG,SUPP_CONFIG,Path('scripts/financial_q3_three.py'),Path('scripts/financial_q3_source.py'),Path('.github/workflows/backfill-dart-legacy-2000-2014.yml')]:extra[p]=(root/p).read_bytes()
 last=[previous];manifest={'classification':'RESEARCH_ONLY','approval_id':APPROVAL,'raw_data_publication_requires':PUBLIC,'source_packs':{},'automatic_financial_publication':'HOLD','PIT':'UNVERIFIED','engine_eligible':False}
 def persist(files=None,message='Checkpoint bounded Q3 source intent; HOLD [skip ci]'):
  packed=old.raw(state);old.atomic(out/'Q3_STATE.json',state)
  guarded=dict(extra);guarded[STATE]=last[0]
  payload={STATE:packed};payload.update(files or{})
  commit=api.commit(payload,original_bytes,root,message,expected_extra=guarded)
  last[0]=packed;old.atomic(out/'LATEST_PERSISTENCE.json',dict(commit=commit,state_sha256=old.sha(packed)))
  return commit
 persist(message='Lease one approved Q3 source execution/12HTTP; HOLD [skip ci]')
 b=src.Budget(state,out/'Q3_STATE.json',persist=persist,reserve_seconds=120);b.started=begin
 def preserve(receipt=None):
  packed,proof=source_pack(out,receipt);encoded=base64.b64encode(packed).decode()+'\n'
  blob=api.call('/git/blobs','POST',dict(content=encoded,encoding='utf-8'))
  if blob['sha']!=old.git_blob_sha(encoded.encode()):raise ValueError('Q3_SOURCE_BLOB_HASH_MISMATCH')
  key=receipt or'metadata';manifest['source_packs'][key]=dict(proof,blob_sha=blob['sha'])
  state['source_packs'][key]=dict(blob_sha=blob['sha'],compressed_sha256=proof['compressed_sha256'])
  if len(state['source_packs'])>4:raise ValueError('Q3_PACK_COUNT_CAP')
  files={BASE/'runs'/run_id/(key+'.json.gz.b64'):dict(sha=blob['sha']),BASE/'runs'/run_id/'manifest.json':old.raw(manifest)}
  persist(files,'Preserve approved Q3 original/metadata and hashes; HOLD [skip ci]')
 def after_raw(target,archive,proof):
  # The source is remotely referenced in the SAME commit as this completed ID.
  # A kill before that CAS leaves it pending, not falsely completed.
  preserve(target['receipt'])
 try:
  src.collect(out,b,transport or src.live_transport,os.environ['DART_API_KEY'],root/BASE/'cache',after_raw)
  state.update(phase='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW',normal_exit=True,stop_reason='FIXED_THREE_SOURCE_COMPLETE')
 except Exception as e:
  reason=str(e)if isinstance(e,(ValueError,src.HTTPFailure))or re.fullmatch(r'GITHUB_HTTP_\d{3}',str(e))else type(e).__name__
  # The last committed raw IDs are authoritative if a per-document publication
  # failed. Do not promote merely local ZIPs to completed remote documents.
  committed=json.loads(last[0]);state['completed_receipts']=committed['completed_receipts'];state['source_packs']=committed['source_packs']
  manifest['uploaded_uncommitted_blob_hints']={k:v for k,v in manifest['source_packs'].items()if k not in committed['source_packs']}
  manifest['source_packs']={k:v for k,v in manifest['source_packs'].items()if k in committed['source_packs']}
  timed=reason.startswith('TIME_BUDGET')
  state.update(phase='STOPPED_TIME_BUDGET'if timed else'HOLD_FAILURE',normal_exit=timed,stop_reason=reason)
  if (out/'metadata').is_dir() and b.remaining()>90:
   try:preserve()
   except Exception:state['metadata_preservation']='FAILED_LEASE_HELD_NO_AUTOMATIC_RETRY'
 state.update(finished_at_utc=old.stamp(),elapsed_seconds=time.monotonic()-begin,remaining_receipts=[x['receipt']for x in src.TARGETS if x['receipt']not in state['completed_receipts']],durable_raw_documents=len(state['completed_receipts']),HTTP_unused=max(0,12-state['HTTP_attempts']),HTTP_remaining=0,executions_remaining=0,HTTP_responses_observed=sum(x.get('HTTP_status')is not None for x in state['requests']),new_candidates=0,new_semantic_PASS=0,new_PIT=0,new_engine_eligible=0)
 manifest.update(state=state,original_state_sha256=originals_fingerprint,supplemental_state_sha256=supp_fingerprint)
 final=persist({BASE/'runs'/run_id/'manifest.json':old.raw(manifest)},'Finish bounded Q3 source run; financial publication HOLD [skip ci]')
 # No raw body/URL/key is printed. RUNNING/failed final commits stay held.
 print(json.dumps(dict(status=state['phase'],commit=final,HTTP_attempts_charged=state['HTTP_attempts'],HTTP_responses_observed=state['HTTP_responses_observed'],new_raw_documents=state['new_raw_documents'],completed_receipts=state['completed_receipts'],remaining_receipts=state['remaining_receipts'],new_candidates=0,new_PIT=0,financial_publication='HOLD')))
 return 0 if state['phase']=='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW'else 2
