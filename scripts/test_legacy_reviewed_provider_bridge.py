import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import test_financial_record_readiness as fixtures
from financial_record_readiness import binding
from legacy_reviewed_provider_bridge import bridge,to_account_row
class Bridge(unittest.TestCase):
 def fixture(self):
  r,c=fixtures.RecordReadiness().fixture();r['row'].update(statement='BS',unit='원',unit_multiplier='1',corp_code='00000001');r['attestation']['binding']=binding(r['row']);return r,c
 def test_unattested_v5_confidence_never_grants_provider_input(self):
  r,c=self.fixture();r['row'].update(parser_confidence=1,source_quality='PASS');r['attestation']={};result=bridge([r],'2010-04-01',c);self.assertEqual(result['source_ready_rows'],0)
 def test_same_day_future_and_changed_original_block(self):
  r,c=self.fixture();self.assertEqual(bridge([r],'2010-03-31',c)['source_ready_rows'],0);r['row']['amount_krw']='999';self.assertEqual(bridge([r],'2010-04-01',c)['source_ready_rows'],0)
 def test_attested_annual_and_ytd_have_different_canonical_columns(self):
  r,c=self.fixture();r['row'].update(metric='revenue',statement='IS',measurement_basis='duration',period_start='2009-01-01',period_end='2009-12-31');r['attestation']['binding']=binding(r['row'])
  annual=to_account_row(r['row'],r['attestation']);self.assertEqual(annual['thstrm_amount'],'100');self.assertEqual(annual['thstrm_add_amount'],'')
  r['row']['period_end']='2009-09-30';r['attestation']['binding']=binding(r['row']);ytd=to_account_row(r['row'],r['attestation']);self.assertEqual(ytd['thstrm_add_amount'],'100');self.assertEqual(ytd['thstrm_amount'],'')
 def test_normalized_KRW_is_not_scaled_twice(self):
  r,c=self.fixture();r['row'].update(unit='천원',unit_multiplier='1000',amount_krw='100000');r['attestation']['binding']=binding(r['row']);self.assertEqual(to_account_row(r['row'],r['attestation'])['thstrm_amount'],'100000')
  r['row']['unit_multiplier']='1'
  with self.assertRaises(ValueError):to_account_row(r['row'],r['attestation'])
 def test_existing_snapshot_owner_selected_and_population_stays_blocked(self):
  r,c=self.fixture();out=bridge([r],'2010-04-01',c);self.assertEqual(out['snapshots'].iloc[0].equity_current,100);self.assertFalse(out['engine_population_ready'])
 def test_unknown_period_is_never_calendar_filled(self):
  r,c=self.fixture();r['row'].update(metric='net_income',statement='IS',measurement_basis='duration',period_start='2009-01-01',period_end='2009-12-01')
  with self.assertRaisesRegex(ValueError,'Q3_FY_ONLY'):to_account_row(r['row'],r['attestation'])
 def test_malformed_identifier_is_not_silently_padded(self):
  r,c=self.fixture();r['row']['corp_code']='1'
  with self.assertRaisesRegex(ValueError,'UNVERIFIED_IDENTIFIER'):to_account_row(r['row'],r['attestation'])
if __name__=='__main__':unittest.main()
