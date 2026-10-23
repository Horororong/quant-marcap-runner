import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from legacy_conflict_diagnostics import classify,version_key
class ConflictBoundaries(unittest.TestCase):
 def rows(self):
  a=dict(corp_code='00269612',stock_code='047310',fiscal_year='2009',period='Q3',metric='equity',scope='OFS',statement='BS',period_end='2009-09-01',rcept_no='20091113001332',document_sha256='a'*64,amount_krw='100',unit='원',unit_multiplier='1',report_nm='분기보고서');b={**a,'rcept_no':'20091116000083','document_sha256':'b'*64,'amount_krw':'100000','unit':'천원','unit_multiplier':'1000','report_nm':'[기재정정]분기보고서'};return[a,b]
 def test_exact_scale_is_a_clue_never_repair(self):
  out=classify(self.rows());self.assertIn('EXACT_1000X_SCALE_SIGNATURE',out['reasons']);self.assertIsNone(out['selected']);self.assertEqual(out['economic_values_resolved'],0)
 def test_latest_amendment_never_silently_wins(self):
  rows=self.rows();self.assertEqual(classify(rows)['source_adjudication'],'UNVERIFIED');self.assertIsNone(classify(list(reversed(rows)))['selected'])
 def test_opposite_sign_is_not_absolute_value_normalized(self):
  rows=self.rows();rows[1]['amount_krw']='-100';out=classify(rows);self.assertIn('SIGN_OR_ACCOUNT_DEFINITION_AMBIGUITY',out['reasons']);self.assertEqual(rows[1]['amount_krw'],'-100')
 def test_display_precision_does_not_mean_equal(self):
  rows=self.rows();rows[1]['amount_krw']='101';self.assertIn('WITHIN_SOURCE_DISPLAY_PRECISION_NOT_EQUAL',classify(rows)['reasons'])
 def test_january_fy_not_relabelled_december(self):
  rows=self.rows()
  for r in rows:r.update(period='FY',period_end='2009-01-01')
  out=classify(rows);self.assertFalse(out['target_calendar_period_relevant']);self.assertEqual(out['source_adjudication'],'UNVERIFIED')
 def test_scope_and_duration_are_not_collapsed(self):
  rows=self.rows();rows[1]['scope']='CFS'
  with self.assertRaises(ValueError):classify(rows)
  a=rows[0];self.assertNotEqual(version_key(a),version_key({**a,'measurement_basis':'duration'}));self.assertNotEqual(version_key(a),version_key({**a,'period_start':'2009-01-01'}))
if __name__=='__main__':unittest.main()
