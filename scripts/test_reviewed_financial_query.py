"""Synthetic correction boundaries; not a real-world correction certificate."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import test_financial_record_readiness as fixtures
from financial_record_readiness import binding
from reviewed_financial_query import inspect_equity_asof

class ReviewedQuery(unittest.TestCase):
 def fixture(self,*args):
  r,c=fixtures.RecordReadiness().fixture(*args)
  r['row'].update(unit='원',unit_multiplier='1',statement='BS');r['attestation']['binding']=binding(r['row']);return r,c
 def test_publication_boundary_uses_existing_provider_after_source_gate(self):
  r,c=self.fixture()
  for d in ['2010-03-30','2010-03-31']:
   out=inspect_equity_asof([r],d,c);self.assertIsNone(out['value']);self.assertEqual(out['status'],'UNAVAILABLE')
  out=inspect_equity_asof([r],'2010-04-01',c)
  self.assertEqual(out['value']['equity_current'],100);self.assertFalse(out['strategy_population_ready']);self.assertFalse(out['operating_store_modified'])
 def test_later_correction_never_overwrites_past_and_unverified_current_never_falls_back(self):
  old,c=self.fixture();new,_=self.fixture('SYNTHETIC_CORRECTION','2010-04-02',1)
  new['row']['amount_krw']=200;new['attestation']['binding']=binding(new['row'])
  before=inspect_equity_asof([old,new],'2010-04-01',c);after=inspect_equity_asof([old,new],'2010-04-30',c)
  self.assertEqual(before['value']['equity_current'],100);self.assertEqual(after['value']['equity_current'],200)
  self.assertEqual(before,inspect_equity_asof([old,new],'2010-04-01',c))
  new['attestation']['financial_accuracy']['verdict']='UNVERIFIED'
  held=inspect_equity_asof([old,new],'2010-04-30',c);self.assertIsNone(held['value']);self.assertIn('NO_STALE_FALLBACK',held['reason'])
 def test_unbound_or_unclosed_record_yields_no_provider_value(self):
  for field in ['source_member_sha256','amount_krw','stock_code']:
   r,c=self.fixture();r['row'][field]='CHANGED'
   self.assertIsNone(inspect_equity_asof([r],'2010-04-01',c)['value'])
  r,c=self.fixture();r['attestation']['version_relationship']['asof_closed_through']='2010-03-31'
  self.assertIsNone(inspect_equity_asof([r],'2010-04-01',c)['value'])
 def test_no_annual_profit_or_unit_guessing(self):
  for field,value in [('metric','net_income'),('unit','천원'),('measurement_basis','duration'),('statement','IS'),('scope','UNKNOWN')]:
   r,c=self.fixture();r['row'][field]=value;r['attestation']['binding']=binding(r['row'])
   with self.assertRaisesRegex(ValueError,'ONLY_ATTESTED'):inspect_equity_asof([r],'2010-04-01',c)
 def test_unparseable_audited_amount_never_becomes_zero_or_nan_result(self):
  r,c=self.fixture();r['row']['amount_krw']='not-a-number';r['attestation']['binding']=binding(r['row'])
  with self.assertRaisesRegex(ValueError,'NONFINITE_AUDITED_EQUITY'):inspect_equity_asof([r],'2010-04-01',c)
 def test_future_balance_date_cannot_be_attested_into_an_old_publication(self):
  r,c=self.fixture();r['row']['period_end']='2011-12-31';r['attestation']['binding']=binding(r['row'])
  with self.assertRaisesRegex(ValueError,'ACCOUNTING_PERIOD_AFTER_PUBLICATION'):inspect_equity_asof([r],'2010-04-01',c)

if __name__=='__main__':unittest.main()
