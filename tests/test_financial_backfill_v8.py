"""Generic appendix boundaries, never receipt/company-specific golden logic."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('financial_fixtures',ROOT/'tests/test_financial_accuracy_repair.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from scripts.legacy_native_financials import parse_native,select_verified
from scripts.legacy_parser_migration import require_explicit_migration,ParserMigrationRequired
class Appendix(unittest.TestCase):
 def rows(self,section,**kwargs):return select_verified(parse_native(m.fixture(**kwargs).replace('4. 재무제표',section))['candidates'])
 def test_current_primary_appendix_is_explicit(self):
  for section in ['XI. 부속명세서','Ⅺ. 부속명세서','ⅩⅠ. 부속명세서','XI. 부속명세서 1. 재무제표 및 주석 가. 재무제표','XI. 재무제표 등','Ⅺ. 재무제표 등','ⅩⅠ. 재무제표 등']:
   r=self.rows(section)[0];self.assertEqual(r['amount_krw'],'1234000');self.assertEqual(r['period_end'],'2007-06-30');self.assertFalse(r['backtest_eligible'])
 def test_later_notes_and_segments_stay_closed(self):
  for section in ['XI. 부속명세서 주석','XI. 부속명세서 부문별재무현황','XI. 부속명세서 합병전후','XI. 재무제표 등 주석','XI. 재무제표 등 부문별재무현황']:
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
  self.assertEqual(r['fiscal_year'],2007);self.assertEqual(r['fiscal_year_evidence'],'original_annual_report_end')
  self.assertEqual(r['period_start'],'2007-01-01');self.assertEqual(r['period_end'],'2007-06-30')
 def test_unused_correction_template_is_not_a_correction_notice(self):
  t=m.fixture().replace('<DOCUMENT>','<DOCUMENT><INSERTION><COMMENT>정정문서 작성시</COMMENT><LIBRARYLIST>정정신고(보고).LCommon</LIBRARYLIST></INSERTION>')
  p=parse_native(t);self.assertFalse(p['correction_file']);self.assertTrue(select_verified(p['candidates']))
 def test_actual_correction_inside_insertion_remains_a_correction(self):
  t=m.fixture().replace('<DOCUMENT>','<DOCUMENT><INSERTION><COMMENT>정정문서 작성시</COMMENT><CORRECTION><TITLE>정정신고(보고)</TITLE></CORRECTION></INSERTION>')
  self.assertTrue(parse_native(t)['correction_file'])
 def test_interim_fiscal_year_is_not_guessed_from_current_company_end_month(self):
  r=select_verified(parse_native(m.fixture())['candidates'])[0]
  self.assertIsNone(r['fiscal_year']);self.assertEqual(r['fiscal_year_evidence'],'UNVERIFIED_INTERIM_FISCAL_YEAR')
class Migration(unittest.TestCase):
 def test_old_classifications_and_quarantine_do_not_implicitly_requeue(self):
  for status in ['PARSED_4F','PARSED_PARTIAL','SOURCE_GAP','NO_METRICS','ERROR']:
   original=[dict(rcept_no='synthetic',parser_version='old',status=status,attempt_count=3)]
   with self.assertRaisesRegex(ParserMigrationRequired,'PARSER_MIGRATION_REQUIRED'):require_explicit_migration(original,'new')
   self.assertEqual(original[0]['attempt_count'],3);self.assertEqual(original[0]['status'],status)
 def test_current_receipt_and_transport_only_history_are_not_new_migrations(self):
  require_explicit_migration([],'new')
  require_explicit_migration([dict(rcept_no='a',parser_version='old',status='NO_DOCUMENT')],'new')
  require_explicit_migration([dict(rcept_no='a',parser_version='old',status='PARSED_4F'),dict(rcept_no='a',parser_version='new',status='PARSED_PARTIAL')],'new')
 def test_upgrade_guard_runs_before_requests_and_coverage_finally(self):
  import ast,types
  src=(ROOT/'scripts/backfill_super_value_fast.py').read_text();fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef)and n.name=='legacy_fast')
  def stop():raise ParserMigrationRequired('PARSER_MIGRATION_REQUIRED')
  def forbidden(*a,**kw):raise AssertionError('No collection or coverage mutation on rejected upgrade')
  env=dict(LEGACY_LIMIT=2000,legacy=types.SimpleNamespace(check_parser_migration=stop,new_control=forbidden,write_coverage=forbidden))
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual-wrapper-upgrade-guard>','exec'),env)
  with self.assertRaises(ParserMigrationRequired):env['legacy_fast']()
if __name__=='__main__':unittest.main(verbosity=2)
