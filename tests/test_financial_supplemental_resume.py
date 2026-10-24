import copy,json,os,sys,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_supplemental_resume as m,financial_limited_resume as old
class Supplemental(unittest.TestCase):
 def setUp(self):
  self.c=json.loads((ROOT/m.CONFIG).read_text());self.original_config=json.loads((ROOT/old.CONFIG).read_text());self.original=old.initial();self.original.update(phase='PAUSED_QUEUE',last_checkpoint='20100331002063',first_review=dict(status='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION'),completed_receipts=['20100331002054','20100331002062','20100331002063'],runs=[dict(run_id='first',day_kst='2026-10-20',reserved_documents=100),dict(run_id='39504052321',day_kst='2026-10-21',reserved_documents=100,resume_segments=[dict(run_id=m.TRIAL,day_kst='2026-10-23',reserved_documents=0)])]);self.b=m.initial(self.c,self.original);self.now=datetime(2026,10,23,16,tzinfo=timezone.utc)
 def check(self,docs=21):return m.check(self.c,self.b,self.original,self.original_config,self.now,docs,m.APPROVAL)
 def first_completed(self,n=21):
  done=self.c['receipts'][:n];self.b['attempts']=[dict(run_id='new1',day_kst='2026-10-24',document_limit=21,http_reserved=42)];self.b['completed_receipts']=done;self.b['phase']='PAUSED';self.original['completed_receipts'].extend(done);self.original['last_checkpoint']=done[-1];self.now=datetime(2026,10,24,16,tzinfo=timezone.utc)
 def test_first_exact_prefix_and_original_ledger_not_mutated(self):
  before=copy.deepcopy(self.original);self.assertEqual(self.check(),self.c['receipts'][:21]);self.assertEqual(before,self.original)
 def test_second_prefix_twenty_and_total_worst_case82(self):
  self.first_completed();self.assertEqual(self.check(20),self.c['receipts'][21:]);self.assertEqual(42+2*len(self.check(20)),82)
 def test_short_first_batch_never_skips_remaining_receipts(self):
  self.first_completed(17);self.assertEqual(self.check(20),self.c['receipts'][17:37])
 def test_daily_limit_shared_with_original_and_supplemental(self):
  self.now=datetime(2026,10,22,23,tzinfo=timezone.utc)
  with self.assertRaisesRegex(ValueError,'ONCE_PER'):self.check()
  self.first_completed();self.now=datetime(2026,10,24,0,tzinfo=timezone.utc)
  with self.assertRaisesRegex(ValueError,'ONCE_PER'):self.check(20)
 def test_strict_order_limits_and_approval_id(self):
  for field,value in [('max_executions',3),('max_HTTP',83),('run_seconds',601),('batch_limits',[22,20]),('maximum_runs_per_KST_day',2),('backtest_eligible',True),('expires_at_utc','2099-01-01T00:00:00+00:00')]:
   c=copy.deepcopy(self.c);c[field]=value
   with self.assertRaises(ValueError):m.validate_approval(c)
  c=copy.deepcopy(self.c);c['receipts'][0],c['receipts'][1]=c['receipts'][1],c['receipts'][0]
  with self.assertRaisesRegex(ValueError,'FROZEN_ORDER'):m.validate_approval(c)
  with self.assertRaisesRegex(ValueError,'EXPLICIT_ID'):m.check(self.c,self.b,self.original,self.original_config,self.now,21,'OTHER')
 def test_original_history_and_financial_gates_unchanged(self):
  self.original['runs'][0]['reserved_documents']=101
  with self.assertRaisesRegex(ValueError,'HISTORY_CHANGED'):self.check()
  self.setUp();self.original['investment_PIT']='6/6'
  with self.assertRaises(ValueError):self.check()
 def test_original_three_not_reset_or_supplemental_injected(self):
  self.original['runs'][-1]['resume_segments']=[];self.b=m.initial(self.c,self.original)
  with self.assertRaisesRegex(ValueError,'THREE_EXECUTIONS'):self.check()
 def test_failure_or_running_lease_blocks_automatic_retry(self):
  for phase in ['RUNNING','HOLD_FAILURE','EXHAUSTED_WITH_PENDING','COMPLETE']:
   self.b['phase']=phase
   with self.assertRaisesRegex(ValueError,'LEASE_OR_FAILURE'):self.check()
 def test_two_attempt_ceiling_even_when_http_remains(self):
  self.b['attempts']=[dict(run_id='a',day_kst='2026-10-20',document_limit=1,http_reserved=2),dict(run_id='b',day_kst='2026-10-21',document_limit=1,http_reserved=2)]
  with self.assertRaisesRegex(ValueError,'EXECUTION_BUDGET'):self.check()
 def test_bad_reservations_or_completed_prefix_rejected(self):
  self.first_completed();self.b['attempts'][0]['http_reserved']=43
  with self.assertRaisesRegex(ValueError,'HTTP_BUDGET'):self.check(20)
  self.setUp();self.b['completed_receipts']=[self.c['receipts'][1]]
  with self.assertRaisesRegex(ValueError,'CHECKPOINT_PREFIX'):self.check()
 def test_already_completed_or_changed_checkpoint_cannot_redownload(self):
  self.original['completed_receipts'].append(self.c['receipts'][0])
  with self.assertRaisesRegex(ValueError,'ALREADY_COLLECTED'):self.check()
  self.setUp();self.original['last_checkpoint']='20100331002054'
  with self.assertRaisesRegex(ValueError,'CHECKPOINT_MISMATCH'):self.check()
 def test_finite_new_window_does_not_change_original_expiry(self):
  self.assertEqual(self.original_config['expires_at_utc'],'2026-10-23T23:59:59+00:00')
  self.first_completed();self.assertEqual(len(self.check(20)),20)
  self.now=datetime(2026,10,25,15,tzinfo=timezone.utc)
  with self.assertRaisesRegex(ValueError,'WINDOW_EXPIRED'):self.check(20)
 def test_zero_collection_green_workflow_never_qualifies(self):
  proof=dict(status='PASS_REAL_TRIAL_PREREQUISITES',run_id=m.TRIAL,new_originals=2,new_candidates=34,HTTP_requests_including_retries=2,normal_exit=True,source_elapsed_seconds=22,duplicate_receipts=0,duplicate_candidates=0,checkpoint_after='20100331002063',documents=[dict(receipt=r,candidate_fields=17,zip_crc='PASS')for r in ['20100331002062','20100331002063']]);m.qualify_trial(proof)
  for key,value in [('new_originals',0),('new_candidates',0),('HTTP_requests_including_retries',5),('HTTP_requests_including_retries',0),('normal_exit',False),('duplicate_candidates',1)]:
   p=copy.deepcopy(proof);p[key]=value
   with self.assertRaises(ValueError):m.qualify_trial(p)
 def test_before_approval_is_rejected_even_if_day_otherwise_qualifies(self):
  self.now=datetime(2026,10,22,22,tzinfo=timezone.utc)
  with self.assertRaisesRegex(ValueError,'BEFORE_APPROVAL'):self.check()
 def test_config_rebound_and_fixed_batch_sizes_block(self):
  self.b['approval_sha256']='changed'
  with self.assertRaisesRegex(ValueError,'REBOUND'):self.check()
  self.setUp()
  with self.assertRaisesRegex(ValueError,'FIXED_SEGMENT'):self.check(22)
 def test_direct_nonmain_entry_rejected_before_any_api(self):
  with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/other','GITHUB_RUN_ATTEMPT':'1'}),patch.object(old,'GitHub')as api:
   with self.assertRaisesRegex(ValueError,'MAIN_FIRST_ATTEMPT_ONLY'):m.run_supplemental(ROOT,ROOT/'unused','schedule','39504052321',21,m.APPROVAL)
   api.assert_not_called()
 def test_coordinator_death_after_lease_retains_budget_and_original_history(self):
  proof=dict(status='PASS_REAL_TRIAL_PREREQUISITES',run_id=m.TRIAL,new_originals=2,new_candidates=34,HTTP_requests_including_retries=2,normal_exit=True,source_elapsed_seconds=22,duplicate_receipts=0,duplicate_candidates=0,checkpoint_after='20100331002063',documents=[dict(receipt=r,candidate_fields=17,zip_crc='PASS')for r in ['20100331002062','20100331002063']],original_runs_sha256=old.sha(old.raw(self.original['runs'])))
  class API:
   def __init__(a):a.files={old.STATE:old.raw(self.original)}
   def head(a):return 'immutable'
   def content(a,path,head):return a.files.get(path)
   def commit(a,files,expected,root,message):
    if a.files[old.STATE]!=expected:raise ValueError('CONCURRENT_STATE')
    a.files.update(files);return 'lease'
  api=API()
  with tempfile.TemporaryDirectory()as t:
   root=Path(t)
   for name,cfg in [(m.CONFIG,self.c),(old.CONFIG,self.original_config)]:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(cfg))
   for name in self.original_config['source_code_sha256']:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
   samples=[dict(rcept_no=r)for r in self.c['receipts']];plan=dict(samples=samples,selection_sha256=old.sha(old.raw(samples)))
   p=root/old.BASE/'runs'/'39504052321'/'selection.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(plan))
   with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/main','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'SYNTHETIC_NEW'}),patch.object(old,'GitHub',return_value=api),patch.object(m,'datetime',SimpleNamespace(now=lambda tz:self.now,fromisoformat=datetime.fromisoformat)),patch('scripts.financial_limited_review.verify_approval'),patch('scripts.check_finite_trial_artifact.verify_remote',return_value=proof),patch.object(old,'run_batch',side_effect=KeyboardInterrupt):
    with self.assertRaises(KeyboardInterrupt):m.run_supplemental(root,root/'output','schedule','39504052321',21,m.APPROVAL)
  leased=json.loads(api.files[m.STATE]);original=json.loads(api.files[old.STATE])
  self.assertEqual(leased['phase'],'RUNNING');self.assertEqual(len(leased['attempts']),1);self.assertEqual(leased['attempts'][0]['http_reserved'],42);self.assertEqual(original['runs'],self.original['runs']);self.assertEqual(original['last_checkpoint'],'20100331002063')
  with self.assertRaisesRegex(ValueError,'PHASE_OR_PARENT'):m.check(self.c,leased,original,self.original_config,self.now,21,m.APPROVAL)
class WindowRenewal(unittest.TestCase):
 setUp=Supplemental.setUp
 first_completed=Supplemental.first_completed
 def test_owner_renewal_allows_only_remaining20_on26_without_rebinding(self):
  self.first_completed();window=json.loads((ROOT/m.WINDOW).read_text());before=copy.deepcopy((self.c,self.b,self.original));now=datetime(2026,10,26,0,tzinfo=old.KST)
  self.assertEqual(m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL,window),self.c['receipts'][21:])
  self.assertEqual(before,(self.c,self.b,self.original));self.assertEqual(sum(x['http_reserved']for x in self.b['attempts']),42)
  with self.assertRaisesRegex(ValueError,'WINDOW_EXPIRED'):m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL)
 def test_new_window_cannot_expand_budget_dates_or_rebind_approval(self):
  self.first_completed();w=json.loads((ROOT/m.WINDOW).read_text());now=datetime(2026,10,26,tzinfo=old.KST)
  for field,value in [('remaining_FY_HTTP',41),('remaining_FY_executions',2),('Q3_HTTP',13),('fy_expires_at_utc','2099-01-01T00:00:00+00:00'),('original_approval_sha256','0'*64),('automatic_scheduling',True)]:
   bad=copy.deepcopy(w);bad[field]=value
   with self.assertRaisesRegex(ValueError,'BINDING_CHANGED'):m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL,bad)
  for now,reason in [(datetime(2026,10,25,23,59,59,tzinfo=old.KST),'NOT_OPEN'),(datetime(2026,10,27,tzinfo=old.KST),'WINDOW_EXPIRED')]:
   with self.assertRaisesRegex(ValueError,reason):m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL,w)
 def test_renewal_keeps_expiry_boundary_and_failure_hold(self):
  self.first_completed();w=json.loads((ROOT/m.WINDOW).read_text());now=datetime(2026,10,26,23,59,59,tzinfo=old.KST)
  self.assertEqual(len(m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL,w)),20)
  self.b['phase']='HOLD_FAILURE'
  with self.assertRaisesRegex(ValueError,'FAILURE_HELD'):m.check(self.c,self.b,self.original,self.original_config,now,20,m.APPROVAL,w)
 def test_remaining_runtime_leases40_preserves_history_and_binds_window(self):
  self.first_completed();self.now=datetime(2026,10,26,tzinfo=old.KST)
  w=json.loads((ROOT/m.WINDOW).read_text());proof=dict(status='PASS_REAL_TRIAL_PREREQUISITES',run_id=m.TRIAL,new_originals=2,new_candidates=34,HTTP_requests_including_retries=2,normal_exit=True,source_elapsed_seconds=22,duplicate_receipts=0,duplicate_candidates=0,checkpoint_after='20100331002063',documents=[dict(receipt=r,candidate_fields=17,zip_crc='PASS')for r in ['20100331002062','20100331002063']],original_runs_sha256=old.sha(old.raw(self.original['runs'])))
  class API:
   def __init__(a):a.files={old.STATE:old.raw(self.original),m.STATE:old.raw(self.b),Path('data/status/dart_q3_three_v1.json'):old.raw(dict(contract='q3-fixed-source-v1',approval_id='q3-three-company-20261024',executions_used=1,HTTP_reserved=12,HTTP_attempts=6,financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',phase='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW',day_kst='2026-10-25')),m.WINDOW:(ROOT/m.WINDOW).read_bytes(),m.CONFIG:(ROOT/m.CONFIG).read_bytes()}
   def head(a):return 'immutable'
   def content(a,path,head):return a.files.get(path)
   def commit(a,files,expected,root,message,expected_extra=None):
    if a.files[old.STATE]!=expected:raise ValueError('CONCURRENT_STATE')
    for path,data in (expected_extra or {}).items():
     if a.files.get(path)!=data:raise ValueError('WINDOW_CAS_GUARD')
    a.files.update(files);return 'lease'
  api=API();before=copy.deepcopy(self.original['runs'])
  with tempfile.TemporaryDirectory()as t:
   root=Path(t)
   for name in [m.CONFIG,m.WINDOW,old.CONFIG]:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
   for name in self.original_config['source_code_sha256']:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
   samples=[dict(rcept_no=r)for r in self.c['receipts']];plan=dict(samples=samples,selection_sha256=old.sha(old.raw(samples)))
   p=root/old.BASE/'runs'/'39504052321'/'selection.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(plan))
   with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/main','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'OFFLINE_RENEWAL'}),patch.object(old,'GitHub',return_value=api),patch.object(m,'datetime',SimpleNamespace(now=lambda tz:self.now,fromisoformat=datetime.fromisoformat)),patch('scripts.financial_limited_review.verify_approval'),patch('scripts.check_finite_trial_artifact.verify_remote',return_value=proof),patch.object(old,'run_batch',side_effect=KeyboardInterrupt):
    with self.assertRaises(KeyboardInterrupt):m.run_supplemental(root,root/'out','schedule','39504052321',20,m.APPROVAL)
  b=json.loads(api.files[m.STATE]);o=json.loads(api.files[old.STATE])
  self.assertEqual(o['runs'],before);self.assertEqual(b['approval_sha256'],self.b['approval_sha256']);self.assertEqual([x['http_reserved']for x in b['attempts']],[42,40]);self.assertEqual(b['attempts'][1]['receipts'],self.c['receipts'][21:]);self.assertEqual(o['last_checkpoint'],'20100331002116')
  self.assertEqual(json.loads(api.files[old.BASE/'runs'/'OFFLINE_RENEWAL'/'selection.json'])['window_renewal'],w)
if __name__=='__main__':unittest.main(verbosity=2)
