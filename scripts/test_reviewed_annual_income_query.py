"""Synthetic query boundaries, separate from actual source review evidence."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import test_financial_record_readiness as fixtures
from financial_record_readiness import binding
from reviewed_annual_income_query import inspect_annual_income_asof
class AnnualQuery(unittest.TestCase):
 def fixture(self,*args):
  r,c=fixtures.RecordReadiness().fixture(*args);r['row'].update(metric='revenue',statement='IS',scope='OFS',measurement_basis='duration',period_start='2009-01-01',period_end='2009-12-31',unit='원',unit_multiplier='1');r['attestation']['binding']=binding(r['row']);return r,c
 def test_source_gate_before_provider_and_annual_not_quarterly(self):
  r,c=self.fixture()
  for d in ['2010-03-30','2010-03-31']:self.assertIsNone(inspect_annual_income_asof([r],d,c)['value'])
  out=inspect_annual_income_asof([r],'2010-04-01',c);self.assertEqual(out['value']['annual_amount_krw'],100);self.assertIsNone(out['value']['quarterly_amount']);self.assertFalse(out['strategy_population_ready'])
 def test_both_supported_concepts_and_sign_preserved(self):
  for metric in ['revenue','net_income']:
   r,c=self.fixture();r['row'].update(metric=metric,amount_krw='-100');r['attestation']['binding']=binding(r['row']);self.assertEqual(inspect_annual_income_asof([r],'2010-04-01',c)['value']['annual_amount_krw'],-100)
 def test_unsupported_scope_units_and_instant_are_not_guessed(self):
  for k,v in [('scope','CFS'),('unit','천원'),('metric','ocf'),('measurement_basis','instant')]:
   r,c=self.fixture();r['row'][k]=v;r['attestation']['binding']=binding(r['row'])
   with self.assertRaisesRegex(ValueError,'ONLY_ATTESTED'):inspect_annual_income_asof([r],'2010-04-01',c)
 def test_quarter_multiyear_and_future_periods_block(self):
  for start,end,reason in [('2009-01-01','2009-09-30','NOT_A_CALENDAR_FY'),('2008-01-01','2009-12-31','NOT_A_CALENDAR_FY'),('2011-01-01','2011-12-31','ACCOUNTING_PERIOD_AFTER_PUBLICATION')]:
   r,c=self.fixture();r['row'].update(period_start=start,period_end=end);r['attestation']['binding']=binding(r['row'])
   with self.assertRaisesRegex(ValueError,reason):inspect_annual_income_asof([r],'2010-04-01',c)
 def test_nonfinite_or_altered_source_never_becomes_value(self):
  r,c=self.fixture();r['row']['amount_krw']='changed';self.assertIsNone(inspect_annual_income_asof([r],'2010-04-01',c)['value'])
  r['attestation']['binding']=binding(r['row'])
  with self.assertRaisesRegex(ValueError,'NONFINITE'):inspect_annual_income_asof([r],'2010-04-01',c)
 def test_synthetic_correction_and_no_stale_fallback(self):
  old,c=self.fixture();new,_=self.fixture('SYNTHETIC_CORRECTION','2010-04-02',1);new['row']['amount_krw']='200';new['attestation']['binding']=binding(new['row'])
  self.assertEqual(inspect_annual_income_asof([old,new],'2010-04-01',c)['value']['annual_amount_krw'],100)
  self.assertEqual(inspect_annual_income_asof([old,new],'2010-04-30',c)['value']['annual_amount_krw'],200)
  new['attestation']['financial_accuracy']['verdict']='UNVERIFIED';self.assertIsNone(inspect_annual_income_asof([old,new],'2010-04-30',c)['value'])
if __name__=='__main__':unittest.main()
