"""Stage3 parser safety boundaries; synthetic examples are not audit evidence."""
import importlib.util,sys,unittest
from pathlib import Path
from decimal import Decimal
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('existing_repair_tests',repo/'tests/test_financial_accuracy_repair.py')
existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
from scripts.legacy_native_financials import parse_native,select_verified,decimal_amount,financial_account
fixture=existing.fixture
def rows(t):return select_verified(parse_native(t)['candidates'])
def cash_statement(amount='1,234',end='2007.06.30',unit='천원',label='1. 당기순이익'):
 return f"""<P>현금흐름표</P><TABLE><TR><TD>제12기반기2007.01.01부터{end}까지제11기반기2006.01.01부터2006.06.30까지</TD></TR><TR><TD>단위:{unit}</TD></TR></TABLE><TABLE><TR><TH>과목</TH><TH>제12기반기</TH><TH>제11기반기</TH></TR><TR><TD>Ⅰ.영업활동으로 인한 현금흐름</TD><TD>9,999</TD><TD>8,888</TD></TR><TR><TD>{label}</TD><TD>{amount}</TD><TD>9,999</TD></TR></TABLE>"""
def with_cash(t,**kwargs):return t.replace('</DOCUMENT>',cash_statement(**kwargs)+'</DOCUMENT>')
class Stage3ProfitTests(unittest.TestCase):
 def test_eps_annotation_leaves_exact_scalar(self):
  t=fixture(account='당기순이익(손실)(기본주당순이익 : 당기 10원 전기 20원')
  r=rows(t)[0];self.assertEqual(r['amount_krw'],'1234000');self.assertEqual(r['statement'],'IS')
 def test_loss_semantics_ignore_positive_eps_annotation(self):
  self.assertEqual(decimal_amount('1,234','당기순손실(기본주당순이익 : 10원','net_income'),Decimal(-1234))
 def test_other_account_in_annotation_is_not_stripped(self):
  self.assertIsNone(financial_account('당기순이익(기본주당순이익10원 매출액123)','IS')[0])
 def test_fused_money_eps_token_is_never_split(self):
  self.assertEqual(rows(fixture(account='당기순이익 기본주당순이익',amount='1,23410원')),[])
  self.assertIsNone(decimal_amount('1,23410원'))
  for token in ['100 200','1,234 20','100\n200','100 200===']:
   self.assertIsNone(decimal_amount(token),token)
 def test_explicit_cash_flow_profit_recovers_unusable_is(self):
  r=rows(with_cash(fixture(account='당기순이익 기본주당순이익',amount='1,23410원')))[0]
  self.assertEqual(r['statement'],'CF');self.assertEqual(r['amount_krw'],'1234000')
  self.assertEqual(r['net_income_source'],'primary_cash_flow_reconciliation')
  self.assertEqual(r['period_start'],'2007-01-01');self.assertEqual(r['period_end'],'2007-06-30')
 def test_cash_flow_does_not_change_proved_is_scalar(self):
  r=rows(with_cash(fixture(),amount='1,234'))[0];self.assertEqual(r['statement'],'IS');self.assertEqual(r['amount_krw'],'1234000')
 def test_cf_prior_period_unknown_unit_and_dash_are_not_fallbacks(self):
  for kwargs in [{'end':'2006.06.30'},{'unit':''},{'amount':'-'}]:
   self.assertFalse(any(r['metric']=='net_income'for r in rows(with_cash(fixture(account='당기순이익 기본주당순이익',amount='1,23410원'),**kwargs))))
 def test_non_profit_cash_flow_is_not_net_income(self):
  self.assertFalse(any(r['metric']=='net_income'for r in rows(with_cash(fixture(account='unknown',amount='-'),label='매출액'))))
 def test_cash_flow_profit_without_operating_reconciliation_is_withheld(self):
  t=with_cash(fixture(account='unknown',amount='-')).replace('Ⅰ.영업활동으로 인한 현금흐름','Ⅱ.투자활동으로 인한 현금흐름')
  self.assertFalse(any(r['metric']=='net_income'for r in rows(t)))
 def test_half_or_current_year_alias_is_exact(self):
  for account in ['반(당)기순이익','반(당)기순이익(손실)','반(당)기순손실']:
   r=rows(fixture(account=account))[0]
   self.assertEqual(r['amount_krw'],'-1234000'if account.endswith('순손실')else'1234000')
 def test_underline_is_terminal_and_does_not_invent_zero(self):
  for suffix in ['===','____','==========']:
   for token,value in [('1,234',1234),('(1,234)',-1234),('△1,234',-1234),('0',0)]:
    self.assertEqual(decimal_amount(token+suffix),Decimal(value))
  for bad in ['123=','123_','1,23===','123=456','123_456','===','___','-===','1,2342,345===','123==___']:
   self.assertIsNone(decimal_amount(bad),bad)
 def test_raw_token_and_normalization_provenance_are_retained(self):
  r=rows(fixture(amount='1,234===='))[0]
  self.assertEqual(r['raw_amount'],'1,234====');self.assertEqual(r['numeric_normalization'],'terminal_underline')
class NetPpeProtectionTests(unittest.TestCase):
 def body(self,net='1,200',gross='2,000',acc='(800)',extra=''):
  return f"""<DOCUMENT><COVER>사업연도2007년01월01일부터2007년06월30일까지</COVER><P>4.재무제표</P><P>대차대조표</P><TABLE><TR><TD>제12기반기2007.06.30현재제11기2006.12.31현재</TD></TR><TR><TD>단위:원</TD></TR></TABLE><TABLE><TR><TH>과목</TH><TH>제12기반기</TH><TH>제11기</TH></TR><TR><TD>Ⅵ. 유형자산</TD><TD>{net}</TD><TD>100</TD></TR><TR><TD>유형자산</TD><TD>{gross}</TD><TD>200</TD></TR><TR><TD>(감가상각누계액)</TD><TD>{acc}</TD><TD>(100)</TD></TR>{extra}</TABLE></DOCUMENT>"""
 def test_net_subtotal_requires_exact_component_equation(self):
  r=rows(self.body())[0];self.assertEqual(r['amount_krw'],'1200')
  self.assertEqual(r['carrying_amount_basis'],'net_of_accumulated_depreciation')
  self.assertEqual(len(r['net_components']),3)
 def test_unproved_gross_net_conflicts_stay_withheld(self):
  for args in [{'net':'1,100'},{'acc':'800'},{'extra':'<TR><TD>손상차손누계액</TD><TD>(100)</TD></TR>'}]:
   self.assertEqual(rows(self.body(**args)),[],args)
 def test_explicit_net_scalar_is_not_lost_when_gross_component_is_missing(self):
  r=rows(self.body(gross='-'))[0]
  self.assertEqual(r['amount_krw'],'1200');self.assertNotIn('net_components',r)
 def test_asset_bond_holding_is_not_issued_debt(self):
  t=self.body().replace('<TR><TD>Ⅵ. 유형자산</TD>', '<TR><TD>자산</TD><TD></TD><TD></TD></TR><TR><TD>3.회사채</TD>')
  self.assertFalse(any(r['metric']=='bonds_payable'for r in rows(t)))
 def test_explicit_liability_bond_is_retained(self):
  t=self.body().replace('<TR><TD>Ⅵ. 유형자산</TD>', '<TR><TD>부채</TD><TD></TD><TD></TD></TR><TR><TD>3.회사채</TD>')
  r=next(r for r in rows(t)if r['metric']=='bonds_payable')
  self.assertEqual(r['amount_krw'],'1200');self.assertEqual(r['balance_sheet_side'],'LIABILITY')
if __name__=='__main__':unittest.main(verbosity=2)
