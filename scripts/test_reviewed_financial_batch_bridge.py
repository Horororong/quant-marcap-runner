import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from financial_record_readiness import binding
from reviewed_financial_batch_bridge import normalise_reviewed,compile_reviewed_batch
import test_financial_record_readiness as fixtures
class BatchBoundaries(unittest.TestCase):
 def fixture(self,stock='000001',corp='00000001'):
  rec,cal=fixtures.RecordReadiness().fixture();row=rec['row'];row.update(stock_code=stock,corp_code=corp,statement='BS',unit='원',unit_multiplier='1');rec['attestation']['binding']=binding(row);rec['attestation']['historical_security_mapping']['stock_code']=stock
  review=dict(verdict='PASS',binding=binding(row),evidence=['SYNTHETIC_TEST_ONLY'],current_period_proved=True,scope_proved=True,unit_sign_proved=True,account_definition_proved=True)
  return dict(row=row,review=review,filing_index_date='2010-03-31',attestation=rec['attestation']),cal
 def test_two_issuers_require_their_own_attestations(self):
  a,c=self.fixture();b,_=self.fixture('000002','00000002');b.pop('attestation');out=compile_reviewed_batch([a,b],'2010-04-01',c);self.assertEqual((out['candidate_rows'],out['candidate_stock_hints']),(2,2));self.assertEqual((out['source_ready_rows'],out['source_ready_stocks']),(1,1));self.assertFalse(out['whole_population_ready'])
 def test_review_cannot_be_copied_to_another_issuer(self):
  a,c=self.fixture();b,_=self.fixture('000002','00000002');b['review']=a['review']
  with self.assertRaisesRegex(ValueError,'BINDING_REQUIRED'):normalise_reviewed(b['row'],b['review'],b['filing_index_date'])
 def test_annual_IS_taxonomy_preserves_amount_and_original(self):
  a,c=self.fixture();a['row'].update(metric='revenue',statement='IS',period_start='2009-01-01',measurement_basis='cumulative');a['review']['binding']=binding(a['row']);before=copy.deepcopy(a['row']);out=normalise_reviewed(a['row'],a['review'],a['filing_index_date']);self.assertEqual(a['row'],before);self.assertEqual(out['canonical_candidate']['thstrm_amount'],'100');self.assertTrue(out['normalization_changed_binding'])
 def test_normalization_never_rebinds_old_PIT_attestation(self):
  a,c=self.fixture();a['row'].update(metric='revenue',statement='IS',period_start='2009-01-01',measurement_basis='cumulative');a['review']['binding']=binding(a['row']);a['attestation']['binding']=binding(a['row']);out=compile_reviewed_batch([a],'2010-04-01',c);self.assertEqual(out['candidate_rows'],1);self.assertEqual(out['source_ready_rows'],0)
 def test_Q3_and_FY_are_separate_partitions(self):
  a,c=self.fixture();b=copy.deepcopy(a);b['row']['period_end']='2009-09-30';b['review']['binding']=binding(b['row']);b.pop('attestation');out=compile_reviewed_batch([a,b],'2010-04-01',c);self.assertEqual(set(out['partitions']),{(2009,'Q3'),(2009,'FY')})
 def test_month_first_period_is_not_filled(self):
  a,c=self.fixture();a['row']['period_end']='2009-12-01';a['review']['binding']=binding(a['row']);out=compile_reviewed_batch([a],'2010-04-01',c);self.assertEqual(out['candidate_rows'],0);self.assertEqual(len(out['held']),1)
 def test_index_OK_or_confidence_is_not_source_review(self):
  a,c=self.fixture();a['review']={'status':'OK','source_quality':'PASS','confidence':1};out=compile_reviewed_batch([a],'2010-04-01',c);self.assertEqual(out['candidate_rows'],0)
 def test_comparative_or_unknown_unit_remains_held(self):
  a,c=self.fixture();a['review']['current_period_proved']=False
  with self.assertRaisesRegex(ValueError,'MEANING_NOT_COMPLETE'):normalise_reviewed(a['row'],a['review'],a['filing_index_date'])
 def test_conflicting_values_are_not_selected_by_input_order(self):
  a,c=self.fixture();b=copy.deepcopy(a);b['row']['amount_krw']='101';b['review']['binding']=binding(b['row']);b.pop('attestation')
  for records in [[a,b],[b,a]]:
   out=compile_reviewed_batch(records,'2010-04-01',c);self.assertEqual(out['candidate_rows'],0);self.assertEqual(out['source_ready_rows'],0);self.assertEqual(len(out['conflicts']),1);self.assertEqual(len(out['held']),2)
if __name__=='__main__':unittest.main()
