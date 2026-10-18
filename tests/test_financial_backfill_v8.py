"""Generic appendix boundaries, never receipt/company-specific golden logic."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('financial_fixtures',ROOT/'tests/test_financial_accuracy_repair.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from scripts.legacy_native_financials import parse_native,select_verified
class Appendix(unittest.TestCase):
 def rows(self,section,**kwargs):return select_verified(parse_native(m.fixture(**kwargs).replace('4. 재무제표',section))['candidates'])
 def test_current_primary_appendix_is_explicit(self):
  for section in ['XI. 부속명세서','Ⅺ. 부속명세서','ⅩⅠ. 부속명세서','XI. 부속명세서 1. 재무제표 및 주석 가. 재무제표']:
   r=self.rows(section)[0];self.assertEqual(r['amount_krw'],'1234000');self.assertEqual(r['period_end'],'2007-06-30');self.assertFalse(r['backtest_eligible'])
 def test_later_notes_and_segments_stay_closed(self):
  for section in ['XI. 부속명세서 주석','XI. 부속명세서 부문별재무현황','XI. 부속명세서 합병전후']:
   self.assertEqual(self.rows(section),[])
 def test_appendix_does_not_prove_missing_source_contract(self):
  for kwargs in [{'unit':''},{'amount':'-'},{'end':'2006.06.30'}]:self.assertEqual(self.rows('XI. 부속명세서',**kwargs),[])
 def test_index_heading_alone_is_not_a_primary_statement(self):
  self.assertEqual(select_verified(parse_native('<COVER>사업연도2007.01.01부터2007.06.30까지</COVER><P>XI.부속명세서</P><TABLE><TR><TD>당기순이익</TD><TD>1234</TD></TR></TABLE>')['candidates']),[])
 def test_explicit_short_fiscal_year_is_not_a_half_year_report(self):
  # Development A05 establishes the failure, no holdout-specific rule.
  t=m.fixture().replace('<COVER>','<COVER><P>사 업 보 고 서</P>')
  r=select_verified(parse_native(t)['candidates'])[0]
  self.assertEqual(r['period'],'FY');self.assertEqual(r['measurement_basis'],'cumulative')
  self.assertEqual(r['period_start'],'2007-01-01');self.assertEqual(r['period_end'],'2007-06-30')
if __name__=='__main__':unittest.main(verbosity=2)
