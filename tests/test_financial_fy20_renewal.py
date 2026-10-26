"""Expiry-only owner renewal: preserve prior used history, guards and frozen20."""
import copy,json,sys,unittest,tempfile,os
from types import SimpleNamespace
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import test_financial_supplemental_resume as fixture
from scripts import financial_supplemental_resume as m,financial_limited_resume as old
class Renewal(unittest.TestCase):
 def setUp(self):
  x=fixture.Supplemental();x.setUp();x.first_completed();self.x=x
  self.x.b['attempts'][0].update(run_id='40024818567',status='COMPLETE')
  self.w=json.loads((ROOT/m.WINDOW).read_text());self.r=json.loads((ROOT/m.RENEWAL).read_text())
  self.now=datetime(2026,10,27,12,tzinfo=old.KST)
 def check(self,r=None):
  x=self.x;return m.check(x.c,x.b,x.original,x.original_config,self.now,20,m.APPROVAL,self.w,self.r if r is None else r)
 def test_exact20_admitted_without_mutation(self):
  before=copy.deepcopy((self.x.c,self.x.b,self.x.original,self.w,self.r))
  self.assertEqual(self.check(),self.x.c['receipts'][21:]);self.assertEqual(before,(self.x.c,self.x.b,self.x.original,self.w,self.r))
 def test_finite_start_expiry_and_old_window_unchanged(self):
  self.assertEqual(self.w['fy_expires_at_utc'],'2026-10-26T14:59:59+00:00')
  self.now=datetime(2026,10,27,tzinfo=old.KST)-timedelta(seconds=1)
  with self.assertRaisesRegex(ValueError,'NOT_OPEN'):self.check()
  self.now=datetime(2026,10,28,23,59,59,tzinfo=old.KST);self.assertEqual(len(self.check()),20)
  self.now+=timedelta(seconds=1)
  with self.assertRaisesRegex(ValueError,'EXPIRED'):self.check()
 def test_no_implicit_renewal(self):
  with self.assertRaisesRegex(ValueError,'EXPIRED'):m.validate_window(self.x.c,self.w,self.now,'fy')
 def test_renewal_changes_fail_closed(self):
  for field,value in [('expires_at_utc','2099-01-01T00:00:00+00:00'),('remaining_HTTP',41),('remaining_executions',2),('maximum_runs_per_KST_day',2),('automatic_dispatch',True),('investment_PIT','6/6'),('original_approval_sha256','bad')]:
   r=copy.deepcopy(self.r);r[field]=value
   with self.assertRaisesRegex(ValueError,'NOT_APPROVED'):self.check(r)
  r=copy.deepcopy(self.r);r['remaining_receipts'].reverse()
  with self.assertRaises(ValueError):self.check(r)
 def test_prior_window_binding_and_no_Q3_extension(self):
  self.w['fy_expires_at_utc']='2099-01-01T00:00:00+00:00'
  with self.assertRaisesRegex(ValueError,'BINDING_CHANGED'):self.check()
  self.w=json.loads((ROOT/m.WINDOW).read_text())
  with self.assertRaisesRegex(ValueError,'CANNOT_EXTEND_Q3'):m.validate_window(self.x.c,self.w,self.now,'q3',self.r)
 def test_used_history_failure_and_replay_remain_blocked(self):
  for field,value in [('run_id','other'),('status','STOPPED'),('http_reserved',40)]:
   b=copy.deepcopy(self.x.b);self.x.b['attempts'][0][field]=value
   with self.assertRaisesRegex(ValueError,'USED_HISTORY_CHANGED'):self.check()
   self.x.b=b
  self.x.b['attempts'].append(copy.deepcopy(self.x.b['attempts'][0]))
  with self.assertRaises(ValueError):self.check()
 def test_same_day_and_Q3_shared_day(self):
  self.x.b['attempts'][0]['day_kst']='2026-10-27'
  with self.assertRaisesRegex(ValueError,'ONCE_PER_KST_DAY'):self.check()
  class API:
   def content(a,path,head):return old.raw(dict(contract='q3-fixed-source-v1',approval_id='q3-three-company-20261024',executions_used=1,HTTP_reserved=12,HTTP_attempts=6,financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',phase='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW',day_kst='2026-10-27'))
  with self.assertRaisesRegex(ValueError,'ONCE_PER_KST_DAY'):old.check_q3_day(API(),'head',self.now)
 def test_runtime_binds_addendum_to_lease(self):
  outer=self;self=self.x;self.now=outer.now
  w=json.loads((ROOT/m.WINDOW).read_text());proof=dict(status='PASS_REAL_TRIAL_PREREQUISITES',run_id=m.TRIAL,new_originals=2,new_candidates=34,HTTP_requests_including_retries=2,normal_exit=True,source_elapsed_seconds=22,duplicate_receipts=0,duplicate_candidates=0,checkpoint_after='20100331002063',documents=[dict(receipt=r,candidate_fields=17,zip_crc='PASS')for r in ['20100331002062','20100331002063']],original_runs_sha256=old.sha(old.raw(self.original['runs'])))
  class API:
   def __init__(a):a.files={old.STATE:old.raw(self.original),m.STATE:old.raw(self.b),Path('data/status/dart_q3_three_v1.json'):old.raw(dict(contract='q3-fixed-source-v1',approval_id='q3-three-company-20261024',executions_used=1,HTTP_reserved=12,HTTP_attempts=6,financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',phase='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW',day_kst='2026-10-25')),m.WINDOW:(ROOT/m.WINDOW).read_bytes(),m.CONFIG:(ROOT/m.CONFIG).read_bytes(),m.RENEWAL:(ROOT/m.RENEWAL).read_bytes()}
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
   for name in [m.CONFIG,m.WINDOW,m.RENEWAL,old.CONFIG]:
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
  outer.assertEqual(json.loads(api.files[old.BASE/'runs'/'OFFLINE_RENEWAL'/'selection.json'])['expiry_addendum'],outer.r)
if __name__=='__main__':unittest.main()
