"""Legacy numeric/source regressions, migrated to the immutable kit's unittest.

v5 loose unheaded values and NaN candidate rows are intentionally rejected by
the source-proved v9 contract. Numeric/loss/alias protections remain executable.
"""
import json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.backfill_dart_legacy_2000_2014 import parse_number,table_candidates,PARSER_VERSION
class LegacyParser(unittest.TestCase):
    def test_negative_symbols(self):
        for token in ['△78,304','▲78,304','Δ78,304','(78,304)']:
            self.assertEqual(parse_number(token),-78304)
    def test_loss_with_explicit_dates_and_current_term_remains_negative(self):
        body='<COVER>사업연도2007년01월01일부터2007년06월30일까지</COVER><P>4. 재무제표</P><P>손익계산서</P><TABLE><TR><TD>제12기반기2007.01.01부터2007.06.30까지</TD></TR><TR><TD>단위:천원</TD></TR></TABLE><TABLE><TR><TH>과목</TH><TH>제12기반기</TH></TR><TR><TD>당기순손실</TD><TD>5,787</TD></TR></TABLE>'
        row=next(r for r in table_candidates(body)if r['metric']=='net_income')
        self.assertEqual(row['amount_reported'],'-5787');self.assertEqual(row['amount_krw'],'-5787000')
    def test_unheaded_loss_never_becomes_proved_current_money(self):
        self.assertEqual(table_candidates('<H2>손익계산서</H2><P>단위:천원</P><TABLE><TR><TD>당기순손실</TD><TD>5,787</TD></TR></TABLE>'),[])
    def test_explicit_current_parser_and_separate_checkpoint_contract(self):
        self.assertEqual(PARSER_VERSION,'legacy-v9.2-statement-boundary-guard')
        from scripts.legacy_parser_migration import require_explicit_migration,ParserMigrationRequired
        with self.assertRaises(ParserMigrationRequired):require_explicit_migration([dict(rcept_no='synthetic',status='PARSED_4F',parser_version='legacy-v5-single-amount')],PARSER_VERSION)
    def test_ambiguous_or_missing_cells_are_not_invented(self):
        for text in ['751,637 22,35416,940','670,000200,0001,500,000','83 15,787 13,418 100','12,34','1.5%','1 (주2)','-','—','–']:
            self.assertTrue(math.isnan(parse_number(text)),text)
    def test_real_source_combined_summary_is_not_current_quarter(self):
        fixture=json.loads((ROOT/'tests/fixtures/legacy_dart/merged_annual_stats_20000515000887.json').read_text())
        self.assertEqual(fixture['rcept_no'],'20000515000887');self.assertIn('751,637 22,35416,940',fixture['source_text']);self.assertEqual(table_candidates(fixture['source_text']),[])
    def test_valid_amounts_and_zero(self):
        for text,want in [('9,573,422',9573422),('104,519,807',104519807),('0',0),('+1,234.50',1234.5)]:self.assertEqual(parse_number(text),want)
    def test_unknown_and_combined_alias_are_not_metrics(self):
        body='<P>단위:천원</P><TABLE><TR><TD>당기순이익</TD><TD>123</TD></TR></TABLE>'
        self.assertFalse(table_candidates(body));self.assertFalse(table_candidates('<H2>손익계산서</H2>'+body.replace('당기순이익','매출액영업이익당기순이익')))
    def test_nonfinite_candidate_is_rejected_instead_of_published_as_nan(self):
        self.assertEqual(table_candidates('<H2>손익계산서</H2><P>단위:백만원</P><TABLE><TR><TD>당기순이익</TD><TD>'+'1'+'0'*308+'</TD></TR></TABLE>'),[])
    def test_parentheses_do_not_double_flip(self):
        for raw,value in [('(-1,170,019,230)',-1170019230),('(-482,479,885)',-482479885),('(△62,175,514)',-62175514)]:self.assertEqual(parse_number(raw),value)
if __name__=='__main__':unittest.main(verbosity=2)
