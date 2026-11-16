import unittest,tempfile,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from ncav_collection_queue import run,key,classify_response
from ncav_provider import NcavProvider
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=Path(self.t.name)
  self.task=dict(endpoint='fnlttSinglAcntAll.json',corp_code='00123456',bsns_year='2026',reprt_code='11012',fs_div='CFS')
  self.plan=dict(grant_id='SYNTHETIC',valid_from='2026-11-01T00:00:00+00:00',valid_until='2026-11-30T23:59:59+00:00',max_http=5,max_runs=3,tasks=[self.task,self.task,{**self.task,'corp_code':'00999999'}])
  self.now=datetime(2026,11,12,tzinfo=timezone.utc);self.calls=[]
 def dispatch(self,**kwargs):
  def t(task):self.calls.append(task);return dict(status='STORED',body=b'fixture')
  return run(self.plan,self.d,approved=True,transport=kwargs.pop('transport',t),acquire_shared_day=lambda *args:None,now=self.now,seconds=600,max_http=kwargs.pop('max_http',5),**kwargs)
 def test_duplicate_resume_and_completed_skip(self):
  self.assertEqual(self.dispatch(max_http=1)['http'],1)
  self.assertEqual(self.dispatch()['http'],1)
  self.assertEqual(self.dispatch()['http'],0);self.assertEqual(len(self.calls),2)
 def test_forced_interruption_no_duplicate_unknown(self):
  def die(task):self.calls.append(task);raise KeyboardInterrupt()
  with self.assertRaises(KeyboardInterrupt):self.dispatch(transport=die)
  self.dispatch();state=json.loads((self.d/'ledger.json').read_text());self.assertEqual(state['used_http'],2)
  self.assertEqual(state['tasks'][key(self.task)]['status'],'UNKNOWN');self.assertEqual(len(self.calls),2)
 def test_cfs_success_blocks_ofs(self):
  self.plan['tasks']=[self.task,{**self.task,'fs_div':'OFS','depends_on':key(self.task)}]
  self.dispatch();self.assertEqual(len(self.calls),1)
 def test_cfs_no_pair_enables_ofs_same_period(self):
  self.plan['tasks']=[self.task,{**self.task,'fs_div':'OFS','depends_on':key(self.task)}]
  self.dispatch(transport=lambda t:dict(status='NO_PAIR'if t['fs_div']=='CFS'else'STORED',body=b'fixture'))
  self.assertEqual(json.loads((self.d/'ledger.json').read_text())['used_http'],2)
 def test_failure_no_retry_and_no_secret_error_log(self):
  def fail(t):raise RuntimeError('crtfc_key=DO_NOT_PERSIST')
  r=self.dispatch(transport=fail);self.assertEqual(r['status'],'STOP_FAILURE');self.assertNotIn('DO_NOT_PERSIST',(self.d/'ledger.json').read_text())
  self.dispatch();self.assertEqual(json.loads((self.d/'ledger.json').read_text())['used_http'],2)
 def test_budget_scope_and_approval(self):
  self.dispatch(max_http=1);self.plan['max_http']=6
  with self.assertRaises(ValueError):self.dispatch()
  with self.assertRaises(PermissionError):run(self.plan,self.d,approved=False,transport=lambda t:None,acquire_shared_day=lambda *a:None)
 def test_shared_day_rejection_makes_no_source_call(self):
  def denied(*args):raise PermissionError('day already used')
  with self.assertRaises(PermissionError):run(self.plan,self.d,approved=True,transport=lambda t:self.calls.append(t),acquire_shared_day=denied,now=self.now,max_http=5)
  self.assertEqual(self.calls,[])
 def test_time_checkpoint_resumes_only_unrequested(self):
  ticks=iter([0,0,571]);r=self.dispatch(clock=lambda:next(ticks));self.assertEqual(r['status'],'CHECKPOINT_TIME');self.assertEqual(r['http'],1)
  self.dispatch();self.assertEqual(len(self.calls),2)
 def test_saved_response_tamper_does_not_redownload(self):
  self.dispatch(max_http=1);row=next(iter(json.loads((self.d/'ledger.json').read_text())['tasks'].values()));(self.d/row['response_file']).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'Saved response'):self.dispatch()
  self.assertEqual(len(self.calls),1)
 def test_http200_empty_is_not_success(self):
  with self.assertRaises(ValueError):classify_response(self.task,b'{"status":"000","list":[]}')
  self.assertEqual(classify_response(self.task,b'{"status":"013"}')['status'],'NO_DATA')

class ProviderTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);(self.root/'config/sandbox').mkdir(parents=True)
  self.row=dict(corp='00123456',securities=['005930'],rcept_no='20260814000001',fs='CFS',bsns_year='2026',reprt_code='11012',thstrm_nm='2026-06-30',currency='KRW',current_assets='100',total_liabilities='40',ncav='60',admission=None)
 def write(self,rows):
  (self.root/'config/sandbox/ncav_dataset.json').write_text(json.dumps(dict(contract='reviewed-ncav-v1',observations=rows)))
 def admitted(self,receipt,assets,available):
  r={**self.row,'rcept_no':receipt,'current_assets':str(assets),'ncav':str(assets-40)};r['admission']=dict(binding=receipt,available_from=available,proofs={})
  for k in ['accounts','publication','correction_chain','issuer_link','period_unit']:
   p=self.root/(receipt+k+'.json');v=dict(status='reviewed',binding=receipt,observation={k:r[k]for k in ['corp','rcept_no','fs','bsns_year','reprt_code','thstrm_nm','currency','current_assets','total_liabilities']},securities=['005930'],valid_from='2026-01-01',valid_until='2026-12-31T23:59:59',available_from=available,public_at=available,complete_through='2026-12-31T23:59:59',versions=[receipt],capitalization_securities=['005930'],complete_capitalization_universe=True,unit_multiplier='1',period_end='2026-06-30',current_assets=str(assets),total_liabilities='40');p.write_text(json.dumps(v));r['admission']['proofs'][k]=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  return r
 def query(self,date):return NcavProvider(self.root).factor_frame(date,pd.DataFrame([dict(Code='005930',Marcap=200)]),['ncav','ncav_to_market_cap'])
 def test_unverified_values_block(self):
  self.write([self.row])
  with self.assertRaisesRegex(RuntimeError,'PIT_HOLD'):self.query('2026-11-02')
 def test_publication_and_correction_boundaries_synthetic(self):
  a=self.admitted('20260814000001',100,'2026-08-17T00:00:00');b=self.admitted('20260901000001',120,'2026-09-02T00:00:00');self.write([a,b])
  with self.assertRaisesRegex(RuntimeError,'NOT_YET'):self.query('2026-08-14')
  self.assertEqual(self.query('2026-08-17').ncav.iloc[0],60)
  self.assertEqual(self.query('2026-09-02').ncav.iloc[0],80)
  self.assertEqual(self.query('2026-08-20').ncav_to_market_cap.iloc[0],.3)
 def test_share_class_denominator_is_issuer_total(self):
  r=self.admitted('20260814000001',100,'2026-08-17T00:00:00');r['securities']=['005930','005935'];p=Path(r['admission']['proofs']['issuer_link']['path']);v=json.loads(p.read_text());v['securities']=['005930','005935'];v['capitalization_securities']=['005930','005935'];p.write_text(json.dumps(v));r['admission']['proofs']['issuer_link']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.write([r])
  frame=pd.DataFrame([dict(Code='005930',Marcap=200),dict(Code='005935',Marcap=100)])
  result=NcavProvider(self.root).factor_frame('2026-11-02',frame,['ncav_to_market_cap']);self.assertEqual(result.ncav_to_market_cap.tolist(),[.2,.2])
  with self.assertRaisesRegex(RuntimeError,'CLASS_MISSING'):self.query('2026-11-02')
 def test_source_tamper_blocks(self):
  r=self.admitted('20260814000001',100,'2026-08-17T00:00:00');self.write([r]);Path(r['admission']['proofs']['accounts']['path']).write_text('{}')
  with self.assertRaisesRegex(RuntimeError,'EVIDENCE_CHANGED'):self.query('2026-11-02')
if __name__=='__main__':unittest.main()
