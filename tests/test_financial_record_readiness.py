import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from financial_record_readiness import assess,select_asof,binding,first_usable_close
class RecordReadiness(unittest.TestCase):
 def fixture(self,receipt='original',published='2010-03-31',rank=0):
  row=dict(rcept_no=receipt,document_sha256='SYNTHETIC_ARCHIVE',source_member=receipt+'.xml',source_member_sha256='SYNTHETIC_MEMBER',metric='equity',scope='OFS',period_start='',period_end='2009-12-31',measurement_basis='instant',corp_code='SYNTHETIC',stock_code='000001',amount_krw=100,structural_status='PASS',backtest_eligible=False)
  a=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=['explicit synthetic number control']),publication=dict(verdict='PASS',date=published,evidence=['synthetic publication']),version_relationship=dict(verdict='PASS',chain_id='SYNTHETIC_CHAIN',version_rank=rank,asof_closed_through='2010-05-03',evidence=['synthetic explicit correction relationship']),historical_security_mapping=dict(verdict='PASS',stock_code='000001',**{'from':'2010-01-01','through':'2010-12-31'},evidence=['synthetic historical mapping']))
  cal=dict(verdict='PASS',evidence=['SYNTHETIC_CALENDAR_NOT_REAL_CERTIFICATE'],coverage_start='2010-03-30',coverage_end='2010-05-03',sessions=['2010-03-30','2010-03-31','2010-04-01','2010-04-02','2010-04-30','2010-05-03'])
  return dict(row=row,attestation=a),cal
 def test_next_session_close_separate_from_clock_execution_and_investment(self):
  r,c=self.fixture();self.assertFalse(assess(r['row'],'2010-03-31',r['attestation'],c)['research_record_ready'])
  out=assess(r['row'],'2010-04-01',r['attestation'],c);self.assertTrue(out['research_record_ready']);self.assertFalse(out['investment_approved']);self.assertFalse(r['row']['backtest_eligible']);self.assertEqual(out['exact_publication_time'],'UNVERIFIED')
 def test_late_attachment_never_uses_parent_receipt_date(self):
  r,c=self.fixture('attachment','2010-04-30');self.assertEqual(assess(r['row'],'2010-04-30',r['attestation'],c)['dimensions']['signal_availability'],'FAIL');self.assertEqual(first_usable_close('2010-04-30',c),'2010-05-03')
 def test_correction_before_after_and_no_fallback_from_bad_current_value(self):
  old,c=self.fixture();new,_=self.fixture('correction','2010-04-02',1);new['row']['amount_krw']=200;new['attestation']['binding']=binding(new['row'])
  self.assertEqual(select_asof([old,new],'2010-04-01',c)['selected']['amount_krw'],100)
  self.assertEqual(select_asof([old,new],'2010-04-30',c)['selected']['amount_krw'],200)
  new['attestation']['financial_accuracy']['verdict']='UNVERIFIED';out=select_asof([old,new],'2010-04-30',c);self.assertIsNone(out['selected']);self.assertEqual(out['reason'],'LATEST_VERSION_NOT_READY_NO_STALE_FALLBACK')
 def test_same_day_correction_uses_explicit_version_order_only(self):
  a,c=self.fixture();b,_=self.fixture('correction','2010-03-31',1)
  self.assertEqual(select_asof([a,b],'2010-03-31',c)['status'],'UNAVAILABLE');self.assertEqual(select_asof([a,b],'2010-04-01',c)['selected']['rcept_no'],'correction')
  b['attestation']['version_relationship']['version_rank']=0;self.assertIsNone(select_asof([a,b],'2010-04-01',c)['selected'])
 def test_no_current_master_weekday_or_unbounded_chain_certification(self):
  for dim in ['financial_accuracy','publication','version_relationship','historical_security_mapping']:
   r,c=self.fixture();r['attestation'][dim]['evidence']=[];self.assertFalse(assess(r['row'],'2010-04-01',r['attestation'],c)['research_record_ready'])
  r,c=self.fixture();c['verdict']='UNVERIFIED';self.assertIsNone(first_usable_close('2010-03-31',c));r['attestation']['version_relationship']['asof_closed_through']='2010-03-31';self.assertIsNone(select_asof([r],'2010-04-01',c)['selected'])
 def test_exact_field_member_hash_binding_and_period_scope_required(self):
  r,c=self.fixture();r['row']['source_member_sha256']='changed';self.assertFalse(assess(r['row'],'2010-04-01',r['attestation'],c)['research_record_ready'])
  r,c=self.fixture();other=copy.deepcopy(r);other['row']['scope']='CFS'
  with self.assertRaises(ValueError):select_asof([r,other],'2010-04-01',c)
 def test_amount_unit_or_issuer_change_invalidates_numeric_attestation(self):
  for field,value in [('amount_krw',999),('unit','천원'),('corp_code','OTHER'),('stock_code','000002')]:
   r,c=self.fixture();r['row'][field]=value;self.assertFalse(assess(r['row'],'2010-04-01',r['attestation'],c)['research_record_ready'])
 def test_non_session_cannot_be_a_close_signal(self):
  r,c=self.fixture();self.assertFalse(assess(r['row'],'2010-04-03',r['attestation'],c)['research_record_ready'])
 def test_closed_first_session_interval_and_separate_signal_proof(self):
  r,c=self.fixture();c['coverage_end']='2010-04-01';c['sessions']=['2010-03-31','2010-04-01']
  self.assertEqual(assess(r['row'],'2010-04-30',r['attestation'],c)['dimensions']['signal_availability'],'UNVERIFIED')
  c['additional_verified_sessions']={'2010-04-30':dict(verdict='PASS',evidence=['SYNTHETIC independent actual signal-market response'])}
  self.assertEqual(assess(r['row'],'2010-04-30',r['attestation'],c)['dimensions']['signal_availability'],'PASS')
  c['verdict']='UNVERIFIED';self.assertEqual(assess(r['row'],'2010-03-31',r['attestation'],c)['dimensions']['signal_availability'],'FAIL')
if __name__=='__main__':unittest.main()
