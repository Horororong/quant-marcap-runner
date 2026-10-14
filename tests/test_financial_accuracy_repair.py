"""Focused safety tests; run with the existing verified offline kit Python."""
import json,os,sys,tempfile,types,unittest
from pathlib import Path
from decimal import Decimal
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.legacy_native_financials import decimal_amount,parse_native,select_verified,backtest_usable,financial_account
def fixture(account='당기순이익(손실)',amount='1,234',unit='천원',end='2007.06.30',prior='9,999'):
 return f"""<DOCUMENT><COVER>사업연도 2007년01월01일부터 2007년06월30일까지</COVER><P>4. 재무제표</P>
 <P>손익계산서</P><TABLE><TR><TD>제12기반기 2007.01.01부터 {end}까지 제11기반기 2006.01.01부터2006.06.30까지</TD></TR>
 <TR><TD>단위:{unit}</TD></TR></TABLE><TABLE><TR><TH>과목</TH><TH>제12기반기</TH><TH>제11기반기</TH></TR>
 <TR><TD>{account}</TD><TD>{amount}</TD><TD>{prior}</TD></TR></TABLE></DOCUMENT>"""
class NumericSafety(unittest.TestCase):
 def test_alternative_profit_loss_stays_positive(self):
  self.assertEqual(decimal_amount('1,234','당기순이익(손실)','net_income'),Decimal(1234))
 def test_actual_negative_stays_negative(self):
  for token in ['(1,234)','(-)1,234','(-1,234)','△1,234','(△1,234)','-1,234']:
   self.assertEqual(decimal_amount(token,'당기순이익(손실)','net_income'),Decimal(-1234),token)
  self.assertEqual(decimal_amount('1,234','당기순손실','net_income'),Decimal(-1234))
 def test_no_invalid_grouping_or_merged_value(self):
  for token in ['7,205,734,7733','12,34','1,2342,345','5,678 20','1 (주석2)','1.5%','-','']:
   self.assertIsNone(decimal_amount(token),token)
 def test_zero_is_real_money(self):self.assertEqual(decimal_amount('0'),Decimal(0))
 def test_shared_explicit_negative_prefix(self):
  from scripts.legacy_financial_fields import parse_number
  self.assertEqual(parse_number('(-)1,234'),-1234)
 def test_terminal_note_alias_preserves_loss(self):
  self.assertEqual(financial_account('Ⅰ.매출액(주석 2, 3)','IS')[0],'revenue')
  self.assertEqual(financial_account('당기순이익(손실)','IS')[0],'net_income')
  self.assertEqual(financial_account('순매출액','IS')[0],'revenue')
class StructureSafety(unittest.TestCase):
 def rows(self,t):return select_verified(parse_native(t)['candidates'])
 def test_exact_units_and_dates(self):
  for unit,mult in [('원',1),('천원',1000),('백만원',1000000)]:
   row=self.rows(fixture(unit=unit))[0]
   self.assertEqual(Decimal(row['amount_krw']),Decimal(1234*mult));self.assertEqual(row['period_end'],'2007-06-30')
   self.assertEqual(row['period_start'],'2007-01-01');self.assertFalse(row['backtest_eligible'])
 def test_dash_never_falls_back(self):
  for missing in ['-','']:
   self.assertEqual(self.rows(fixture(amount=missing)),[])
 def test_old_statement_never_relabelled_current(self):self.assertEqual(self.rows(fixture(end='2006.12.31')),[])
 def test_unknown_unit_is_not_published(self):self.assertEqual(self.rows(fixture(unit='')),[])
 def test_segment_is_not_whole_company(self):self.assertEqual(self.rows(fixture().replace('4. 재무제표','부문별 재무현황')),[])
 def test_unheaded_value_is_not_verified(self):self.assertEqual(self.rows('<TABLE><TR><TD>당기순이익</TD><TD>123</TD></TR></TABLE>'),[])
 def test_ambiguous_conflict_withheld(self):
  one=self.rows(fixture())[0];other={**one,'amount_krw':'999'}
  self.assertEqual(select_verified([one,other]),[])
 def test_three_month_and_cumulative_separate(self):
  t=fixture().replace('<TH>제12기반기</TH>','<TH COLSPAN="2">제12기반기</TH>').replace('<TR><TD>당기순이익(손실)</TD>','<TR><TD></TD><TD>3개월</TD><TD>누적</TD><TD></TD></TR><TR><TD>당기순이익(손실)</TD>').replace('<TD>1,234</TD>','<TD>234</TD><TD>1,234</TD>')
  p=parse_native(t);c=p['candidates'];self.assertEqual({r['measurement_basis']for r in c},{'three_month','cumulative'})
  q=next(x for x in c if x['measurement_basis']=='three_month');self.assertEqual(q['period_start'],'2007-04-01')
  self.assertEqual(self.rows(t)[0]['measurement_basis'],'cumulative')
 def test_cfs_is_separate(self):
  r=self.rows(fixture().replace('손익계산서','연결손익계산서'))[0];self.assertEqual(r['scope'],'CFS')
 def test_point_in_time_default_closed(self):
  r={**self.rows(fixture())[0],'rcept_no':'20070814000001','document_sha256':'f'*64}
  self.assertFalse(backtest_usable(r,'2007-08-15',{}))
  e={'identity_verified':True,'correction_chain_verified':True,'publication_verified':True,'rcept_no':r['rcept_no'],'document_sha256':r['document_sha256'],'available_date':'2007-08-14'}
  self.assertFalse(backtest_usable(r,'2007-08-14',e));self.assertTrue(backtest_usable(r,'2007-08-15',e))
  self.assertFalse(backtest_usable(r,'2007-08-13',e))
  self.assertFalse(backtest_usable({**r,'rcept_no':''},'2007-08-15',e))
class CollectorSafety(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # No network-only dependency is installed in the fixed kit. This stub forbids
  # HTTP and does not replace any financial calculation/selection/storage.
  try:import requests
  except ModuleNotFoundError:
   m=types.ModuleType('requests')
   def forbidden(*args,**kwargs):raise AssertionError('HTTP forbidden')
   m.get=m.Session=forbidden;m.Timeout=type('Timeout',(Exception,),{});m.ConnectionError=type('ConnectionError',(Exception,),{});sys.modules['requests']=m
  cls.directory=tempfile.TemporaryDirectory();cls.cwd=Path.cwd();os.chdir(cls.directory.name)
  from scripts import backfill_dart_legacy_2000_2014 as collector
  cls.subject=collector;os.chdir(cls.cwd)
 @classmethod
 def tearDownClass(cls):cls.directory.cleanup()
 def test_month_end_and_invalid_dates(self):
  import pandas as pd
  for label,expected in [('반기보고서 (2007.06)','2007-06-30'),('사업보고서 (2008.02)','2008-02-29'),('반기보고서 (2007.06.15)','2007-06-15')]:
   self.assertEqual(str(self.subject.infer_report_fields(label,pd.Timestamp('2007-08-14'))['period_end'].date()),expected)
  self.assertTrue(pd.isna(self.subject.infer_report_fields('반기보고서 (2007.02.30)',pd.Timestamp('2007-08-14'))['period_end']))
 def test_unverified_values_never_enter_normalized_input(self):
  with tempfile.TemporaryDirectory()as t:
   from unittest.mock import patch
   with patch.object(self.subject,'NORM_DIR',Path(t)/'normalized'),patch.object(self.subject,'REVIEW_DIR',Path(t)/'review'):
    r={**select_verified(parse_native(fixture())['candidates'])[0],'fiscal_year':2007,'rcept_no':'20070814000001','document_sha256':'f'*64}
    self.subject.append_normalized([r])
    self.assertFalse((Path(t)/'normalized').exists());self.assertTrue((Path(t)/'review/legacy_metrics_2007.csv.gz').exists())
if __name__=='__main__':unittest.main(verbosity=2)
