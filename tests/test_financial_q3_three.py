"""Offline bounded-source fixtures, never financial/PIT certification."""
import base64,contextlib,copy,gzip,hashlib,importlib.util,io,json,os,subprocess,sys,tempfile,time,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_q3_three as m,financial_q3_source as q,financial_limited_resume as old
from scripts import recover_financial_q3_sources as recovery

def original_states():
 sc=json.loads((ROOT/m.SUPP_CONFIG).read_text());o=old.initial()
 o.update(phase='PAUSED_QUEUE',runs=[dict(run_id='first-fixture',day_kst='2026-10-20',reserved_documents=100),dict(run_id='39504052321',day_kst='2026-10-21',reserved_documents=100,resume_segments=[dict(run_id='39863731314',day_kst='2026-10-23',reserved_documents=0)])],first_review=dict(status='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION'),completed_receipts=['20100331002054','20100331002062','20100331002063']+sc['receipts'][:21],last_checkpoint=sc['receipts'][20])
 s=dict(approval_id='finite41-20261023',approval_sha256=q.sha(q.operating_bytes(sc)),original_runs_sha256=q.sha(q.operating_bytes(o['runs'])),phase='PAUSED',attempts=[dict(run_id='first-supp-fixture',day_kst='2026-10-24',status='COMPLETE',document_limit=21,http_reserved=42)],completed_receipts=sc['receipts'][:21],remaining_receipts=sc['receipts'][21:],financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6')
 return o,s,sc

def page(t):return dict(status='000',page_no=1,page_count=100,total_count=1,total_page=1,list=[dict(corp_code=t['corp'],rcept_no=t['receipt'],report_nm='분기보고서 (2009.09)',rcept_dt=t['receipt'][:8])])
def archive(t):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w')as z:z.writestr(t['receipt']+'.xml','<DOCUMENT><COMPANY-NAME AREGCIK="'+t['corp']+'">'+t['name']+'</COMPANY-NAME></DOCUMENT>')
 return b.getvalue()
def transport(endpoint,params,key,timeout):
 t=next(t for t in q.TARGETS if (t['corp']==params.get('corp_code') if endpoint=='list.json' else t['receipt']==params.get('rcept_no')))
 return 200,json.dumps(page(t)).encode() if endpoint=='list.json' else archive(t)

class API:
 """Durable fake GitHub store for kill/reopen and CAS tests; no network."""
 def __init__(self,home,fail_source=False,kill_marker=False):
  self.home=Path(home);self.home.mkdir(exist_ok=True);self.db=self.home/'fake-remote.json';self.fail_source=fail_source;self.kill_marker=kill_marker
  if not self.db.exists():
   o,s,_=original_states();self.write(dict(files={str(old.STATE):base64.b64encode(old.raw(o)).decode(),str(m.SUPP_STATE):base64.b64encode(old.raw(s)).decode()},blobs={},commits=0))
 def read(self):return json.loads(self.db.read_text())
 def write(self,obj):q.atomic(self.db,obj)
 def head(self):return '0'*40
 def content(self,path,revision):
  d=self.read();v=d['files'].get(str(path));return base64.b64decode(v)if v is not None else None
 def call(self,path,method='GET',body=None):
  if path.startswith('/actions/workflows/') and method=='GET':return dict(workflow_runs=[])
  assert path=='/git/blobs' and method=='POST';b=body['content'].encode();s=old.git_blob_sha(b);d=self.read();d['blobs'][s]=base64.b64encode(b).decode();self.write(d);return dict(sha=s)
 def commit(self,files,expected,root,message,expected_extra=None):
  d=self.read();assert self.content(old.STATE,'head')==expected
  for path,value in (expected_extra or{}).items():
   if str(path) in d['files'] or path in {m.STATE,m.SUPP_STATE}:assert self.content(path,'head')==value
   else:assert (root/path).read_bytes()==value
  source=any(str(p).endswith('.json.gz.b64')for p in files)
  if source and self.fail_source:raise RuntimeError('OFFLINE_SOURCE_PUBLICATION_FAILURE')
  for p,b in files.items():
   d['files'][str(p)]=d['blobs'][b['sha']]if isinstance(b,dict)else base64.b64encode(b).decode()
  d['commits']+=1;self.write(d)
  if source and self.kill_marker:
   (self.home/'FIRST_SOURCE_DURABLE').write_text('synthetic-only')
   while True:time.sleep(0.05)
  return 'f'*40

class Q3(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.home=Path(self.t.name);self.api=API(self.home/'remote');self.env=dict(GITHUB_REF='refs/heads/main',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_ID='OFFLINE_Q3_FIXTURE',GITHUB_SHA='a'*40,SOURCE_CHECKOUT_SHA='b'*40,DART_API_KEY='offline-fixture-not-a-real-key')
  self.now=datetime(2026,10,26,tzinfo=timezone.utc)
 def execute(self,api=None,public=m.PUBLIC):
  with patch.dict(os.environ,self.env),patch('scripts.financial_limited_review.verify_approval'),contextlib.redirect_stdout(io.StringIO()):return m.run_q3(ROOT,self.home/'out',m.APPROVAL,public,api or self.api,transport,self.now)
 def test_full_raw_source_durability_uses6HTTP_and_no_financial_promotion(self):
  before=self.api.content(old.STATE,'head');supp=self.api.content(m.SUPP_STATE,'head')
  self.assertEqual(self.execute(),0);s=json.loads(self.api.content(m.STATE,'head'))
  self.assertEqual(s['HTTP_attempts'],6);self.assertEqual(s['HTTP_responses_observed'],6);self.assertEqual(s['durable_raw_documents'],3);self.assertEqual(s['HTTP_reserved'],12)
  self.assertEqual(s['HTTP_unused'],6);self.assertEqual(s['HTTP_remaining'],0);self.assertEqual(s['executions_remaining'],0)
  self.assertEqual(s['completed_receipts'],[x['receipt']for x in q.TARGETS]);self.assertEqual(s['new_candidates'],0);self.assertEqual(s['new_PIT'],0);self.assertFalse(s['backtest_eligible']);self.assertEqual(s['source_checkout'],'b'*40)
  self.assertEqual(before,self.api.content(old.STATE,'head'));self.assertEqual(supp,self.api.content(m.SUPP_STATE,'head'))
  for receipt,proof in s['source_packs'].items():
   b=base64.b64decode(self.api.read()['blobs'][proof['blob_sha']]);packed=base64.b64decode(b);self.assertEqual(q.sha(packed),proof['compressed_sha256']);files=json.loads(gzip.decompress(packed))['files'];native=next(base64.b64decode(v)for n,v in files.items()if n.endswith('.zip'));t=next(t for t in q.TARGETS if t['receipt']==receipt);self.assertEqual(q.validate_archive(native,t)['ZIP_CRC'],'PASS')
  manifest=json.loads(self.api.content(m.BASE/'runs'/self.env['GITHUB_RUN_ID']/'manifest.json','head'))
  report=recovery.recover(manifest,lambda sha:base64.b64decode(self.api.read()['blobs'][sha]),self.home/'recovered')
  self.assertEqual(report['raw_originals'],3);self.assertEqual(report['DART_HTTP'],0);self.assertEqual(report['new_PIT'],0);self.assertEqual(report['incomplete_receipts'],[])
 def test_second_execution_is_blocked_before_transport(self):
  self.execute()
  with patch.dict(os.environ,self.env),patch.object(q,'live_transport',side_effect=AssertionError('Unexpected source request')):
   with self.assertRaisesRegex(ValueError,'ONE_EXECUTION'):m.run_q3(ROOT,self.home/'second',m.APPROVAL,m.PUBLIC,self.api,now=self.now)
 def test_missing_public_preservation_approval_does_not_lease(self):
  before=self.api.read()
  with self.assertRaisesRegex(ValueError,'PUBLIC_PRESERVATION'):self.execute(public='')
  self.assertEqual(before,self.api.read())
  gate=json.loads((self.home/'out/gate.json').read_text());self.assertEqual(gate['status'],'NO_COLLECTION');self.assertEqual(gate['DART_HTTP'],0)
 def test_wrong_target_order_or_scope_or_limits_rejected(self):
  c=m.expected_config()
  for name,value in [('max_executions',2),('max_HTTP',13),('run_seconds',601),('maximum_runs_per_KST_day',2),('backtest_eligible',True),('max_source_packs',5)]:
   n=copy.deepcopy(c);n[name]=value
   with self.assertRaisesRegex(ValueError,'SCOPE_OR_LIMIT'):m.validate(n,m.initial(n),m.APPROVAL,m.PUBLIC)
  n=copy.deepcopy(c);n['targets'].reverse()
  with self.assertRaises(ValueError):m.validate(n,m.initial(n),m.APPROVAL,m.PUBLIC)
 def test_today_and_FY_priority_are_shared_not_reset_by_runtime(self):
  o,s,c=original_states()
  with self.assertRaisesRegex(ValueError,'ONCE_PER_KST_DAY'):q.gate(o,s,c,[],datetime(2026,10,24,tzinfo=q.KST))
  with self.assertRaisesRegex(ValueError,'FY_APPROVED_WINDOW_PRIORITY'):q.gate(o,s,c,[],datetime(2026,10,25,tzinfo=q.KST))
  self.assertEqual(q.gate(o,s,c,[],datetime(2026,10,26,tzinfo=q.KST)),'OPEN');self.assertEqual(len(s['attempts']),1)
 def test_changed_history_and_failure_hold_are_not_reset(self):
  o,s,c=original_states();o['runs'][0]['day_kst']='2000-01-01'
  with self.assertRaisesRegex(ValueError,'HISTORY_CHANGED'):q.gate(o,s,c,[],self.now)
  o,s,c=original_states();s['phase']='HOLD_FAILURE'
  with self.assertRaisesRegex(ValueError,'FAILURE_HELD'):q.gate(o,s,c,[],self.now)
  o,s,c=original_states()
  with self.assertRaisesRegex(ValueError,'ACTIVE_COLLECTION'):q.gate(o,s,c,[dict(id='other',status='in_progress')],self.now)
 def test_existing_Q3_lease_blocks_FY_even_nextday(self):
  s=m.initial(m.expected_config());s.update(phase='RUNNING',executions_used=1,HTTP_reserved=12,day_kst='2026-10-26');d=self.api.read();d['files'][str(m.STATE)]=base64.b64encode(old.raw(s)).decode();self.api.write(d)
  with self.assertRaisesRegex(ValueError,'LEASE_OR_FAILURE'):old.check_q3_day(self.api,'head',datetime(2026,10,27,tzinfo=q.KST))
 def test_completed_Q3_blocks_same_KST_day_for_FY(self):
  self.execute()
  with self.assertRaisesRegex(ValueError,'ONCE_PER_KST_DAY'):old.check_q3_day(self.api,'head',datetime(2026,10,26,23,tzinfo=q.KST))
 def test_13th_HTTP_and_budget_deadline_are_blocked(self):
  state=dict(HTTP_attempts=12,requests=[]);b=q.Budget(state,self.home/'budget.json')
  with self.assertRaisesRegex(ValueError,'BUDGET_EXHAUSTED'):b.request('x','list.json',{},'fixture',lambda*x:self.fail('HTTP13'))
  state['HTTP_attempts']=0;b.started-=590
  with self.assertRaisesRegex(ValueError,'TIME_BUDGET'):b.request('x','list.json',{},'fixture',lambda*x:self.fail('Past deadline'))
 def test_intent_is_durable_before_transport_and_401_never_retried(self):
  state=dict(HTTP_attempts=0,requests=[]);path=self.home/'budget.json';b=q.Budget(state,path)
  def bad(*args):
   self.assertEqual(json.loads(path.read_text())['HTTP_attempts'],1);raise q.HTTPFailure('SOURCE_HTTP_401')
  with self.assertRaisesRegex(q.HTTPFailure,'401'):b.request('x','list.json',{},'fixture',bad)
  self.assertEqual(state['HTTP_attempts'],1)
 def test_key_echo_refused_without_source_pack(self):
  f=self.home/'metadata';f.mkdir();(f/'test.json').write_text(self.env['DART_API_KEY'])
  with patch.dict(os.environ,self.env):
   with self.assertRaisesRegex(ValueError,'CREDENTIAL_IN_SOURCE'):m.source_pack(self.home)
 def test_compressed_member_with_key_is_refused_before_publication(self):
  receipt=q.TARGETS[0]['receipt'];path=self.home/(receipt+'-'+'a'*64+'.zip')
  with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED)as z:z.writestr(receipt+'.xml',self.env['DART_API_KEY'])
  with patch.dict(os.environ,self.env):
   with self.assertRaisesRegex(ValueError,'CREDENTIAL_IN_ZIP_MEMBER'):m.source_pack(self.home,receipt)
 def test_official_pagination_company_and_duplicates_fail_closed(self):
  t=q.TARGETS[0];p=page(t);p['total_page']=3
  with self.assertRaisesRegex(ValueError,'PAGINATION'):q.validate_page(json.dumps(p).encode(),t,1)
  p=page(t);p['list'][0]['corp_code']='00000000'
  with self.assertRaisesRegex(ValueError,'COMPANY_MISMATCH'):q.validate_page(json.dumps(p).encode(),t,1)
  p=page(t);p['list']*=2;p['total_count']=2
  with self.assertRaisesRegex(ValueError,'DUPLICATE'):q.confirm_receipt([p],t)
  for field,value in [('report_nm','사업보고서 (2009.12)'),('rcept_no','20091116000000'),('rcept_dt','20091115')]:
   p=page(t);p['list'][0][field]=value
   with self.assertRaises(ValueError):q.confirm_receipt([p],t)
 def test_source_error020_is_preserved_as_reason_not_expired_key(self):
  with self.assertRaisesRegex(ValueError,'DART_DOCUMENT_STATUS_020'):q.validate_archive(b'<result><status>020</status></result>',q.TARGETS[0])
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w')as z:z.writestr(q.TARGETS[0]['receipt']+'.xml','<DOCUMENT><COMPANY-NAME AREGCIK="99999999">Wrong fixture issuer</COMPANY-NAME></DOCUMENT>')
  with self.assertRaisesRegex(ValueError,'ISSUER_MISMATCH'):q.validate_archive(b.getvalue(),q.TARGETS[0])
 def test_correction_list_is_evidence_not_PIT_certification(self):
  t=q.TARGETS[0];p=page(t);p['list'].append(dict(p['list'][0],rcept_no='20100201000001',report_nm='[기재정정]분기보고서 (2009.09)'));p['total_count']=2
  d=q.confirm_receipt([p],t);self.assertEqual(len(d['same_period_versions']),2);self.assertEqual(d['PIT'],'UNVERIFIED');self.assertFalse(d['engine_eligible'])
 def test_persistence_failure_never_advances_remote_source_checkpoint(self):
  api=API(self.home/'failed',fail_source=True);self.assertEqual(self.execute(api),2);s=json.loads(api.content(m.STATE,'head'));self.assertEqual(s['completed_receipts'],[]);self.assertEqual(s['phase'],'HOLD_FAILURE');self.assertEqual(s['executions_used'],1)
 def test_existing_cache_is_reused_with_zero_DART_calls(self):
  cache=self.home/'cache';cache.mkdir();out=self.home/'cached';out.mkdir();state=dict(HTTP_attempts=0,requests=[],completed_receipts=[],new_raw_documents=0)
  for t in q.TARGETS:
   p=cache/(t['corp']+'-list1.json');p.write_text(json.dumps(page(t)));q.atomic(p.with_suffix('.proof.json'),dict(params=dict(q.LIST_BASE,corp_code=t['corp'],page_no='1'),endpoint='list.json',sha256=q.sha(p.read_bytes())));p=cache/(t['receipt']+'.zip');p.write_bytes(archive(t));q.atomic(p.with_suffix('.proof.json'),dict(receipt=t['receipt'],sha256=q.sha(p.read_bytes())))
  q.collect(out,q.Budget(state,self.home/'state.json'),lambda*x:self.fail('Cached source fetched again'),'fixture',cache)
  self.assertEqual(state['HTTP_attempts'],0);self.assertEqual(state['new_raw_documents'],0)
 def test_nonmain_and_GitHub_rerun_never_reach_API(self):
  for change in [dict(GITHUB_REF='refs/heads/other'),dict(GITHUB_RUN_ATTEMPT='2')]:
   env=dict(self.env,**change)
   with patch.dict(os.environ,env),patch.object(old,'GitHub')as api:
    with self.assertRaisesRegex(ValueError,'MAIN_FIRST_ATTEMPT'):m.run_q3(ROOT,self.home/'x',m.APPROVAL,m.PUBLIC)
    api.assert_not_called()
 def test_readonly_validation_workflow_does_not_inject_DART_secret(self):
  workflow=(ROOT/'.github/workflows/backfill-dart-legacy-2000-2014.yml').read_text();validation=workflow.split('  q3-validation:')[1]
  self.assertNotIn('secrets.DART_API_KEY',validation);self.assertIn('contents: read',validation);self.assertIn('git rev-parse HEAD',validation);self.assertNotIn('pip install',validation)
 def test_actual_SIGKILL_preserves_one_lease_completed_source_and_offline_reopen(self):
  home=self.home/'killed';home.mkdir();env=dict(os.environ,**self.env,Q3_FIXTURE_HOME=str(home),Q3_FIXTURE_ROOT=str(ROOT))
  code='''import importlib.util,os,sys
from pathlib import Path
from unittest.mock import patch
r=Path(os.environ["Q3_FIXTURE_ROOT"]);sys.path.insert(0,str(r));s=importlib.util.spec_from_file_location("fixture",r/"tests/test_financial_q3_three.py");t=importlib.util.module_from_spec(s);s.loader.exec_module(t);h=Path(os.environ["Q3_FIXTURE_HOME"])
with patch('scripts.financial_limited_review.verify_approval'):t.m.run_q3(r,h/"out",t.m.APPROVAL,t.m.PUBLIC,t.API(h/"remote",kill_marker=True),t.transport,t.datetime(2026,10,26,tzinfo=t.timezone.utc))
'''
  p=subprocess.Popen([sys.executable,'-I','-c',code],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  try:
   deadline=time.monotonic()+15
   while not(home/'remote/FIRST_SOURCE_DURABLE').exists():
    if p.poll()is not None:self.fail('Fixture coordinator stopped before durable source')
    if time.monotonic()>deadline:self.fail('Fixture coordinator did not reach durable source')
    time.sleep(.02)
   p.kill();p.wait(timeout=5);self.assertEqual(p.returncode,-9)
  finally:
   if p.poll()is None:p.kill();p.wait(timeout=5)
   p.stderr.close()
  api=API(home/'remote');state=json.loads(api.content(m.STATE,'head'));self.assertEqual(state['HTTP_attempts'],4);self.assertEqual(state['executions_used'],1);self.assertEqual(state['phase'],'RUNNING');self.assertEqual(state['completed_receipts'],[q.TARGETS[0]['receipt']])
  proof=state['source_packs'][q.TARGETS[0]['receipt']];b=base64.b64decode(api.read()['blobs'][proof['blob_sha']]);packed=base64.b64decode(b);self.assertEqual(q.sha(packed),proof['compressed_sha256']);files=json.loads(gzip.decompress(packed))['files'];raw=next(base64.b64decode(v)for n,v in files.items()if n.endswith('.zip'));self.assertEqual(q.validate_archive(raw,q.TARGETS[0])['ZIP_CRC'],'PASS')
  with patch.dict(os.environ,self.env):
   with self.assertRaisesRegex(ValueError,'ONE_EXECUTION'):m.run_q3(ROOT,home/'restart',m.APPROVAL,m.PUBLIC,api,lambda*x:self.fail('Completed source redownloaded'),self.now)
 def test_extra_state_CAS_guard_checks_before_creating_a_tree(self):
  from unittest.mock import Mock
  api=object.__new__(old.GitHub);api.head=lambda:'0'*40;api.content=lambda p,h:b'original' if p==old.STATE else b'other-budget';api.call=Mock(side_effect=AssertionError('Unexpected mutation'))
  with self.assertRaisesRegex(ValueError,'EXTRA_LEASE_OR_INPUT'):api.commit({},b'original',ROOT,'offline',expected_extra={m.STATE:b'expected-budget'})
  api.call.assert_not_called()
 def test_soft_deadline_saves_a_normal_stop_but_does_not_free_execution(self):
  with patch.object(q.Budget,'request',side_effect=ValueError('TIME_BUDGET_CHECKPOINT_SAVED')):
   self.assertEqual(self.execute(),2)
  s=json.loads(self.api.content(m.STATE,'head'));self.assertTrue(s['normal_exit']);self.assertEqual(s['phase'],'STOPPED_TIME_BUDGET');self.assertEqual(s['executions_used'],1);self.assertEqual(s['HTTP_attempts'],0)
 def test_shared_transport_has_no_redirect_following(self):
  from scripts import dart_http
  self.assertIsNone(dart_http.NoRedirect().redirect_request(None,None,None,None,None,None))
 def test_recovery_refuses_corrupt_compressed_hash(self):
  self.execute();manifest=json.loads(self.api.content(m.BASE/'runs'/self.env['GITHUB_RUN_ID']/'manifest.json','head'));next(iter(manifest['source_packs'].values()))['compressed_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'COMPRESSED_HASH'):recovery.recover(manifest,lambda sha:base64.b64decode(self.api.read()['blobs'][sha]),self.home/'bad-recovery')
 def test_recovery_never_overwrites_an_existing_directory(self):
  self.execute();manifest=json.loads(self.api.content(m.BASE/'runs'/self.env['GITHUB_RUN_ID']/'manifest.json','head'));out=self.home/'original';out.mkdir();p=out/'baseline.txt';p.write_text('unchanged')
  with self.assertRaises(FileExistsError):recovery.recover(manifest,lambda sha:base64.b64decode(self.api.read()['blobs'][sha]),out)
  self.assertEqual(p.read_text(),'unchanged')

if __name__=='__main__':unittest.main(verbosity=2)
