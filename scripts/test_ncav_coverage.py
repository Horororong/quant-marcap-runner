import unittest
import pandas as pd
from ncav_coverage import financial_pairs
class Tests(unittest.TestCase):
 def rows(self):
  base=dict(corp_code='00123456',rcept_no='20260814000001',bsns_year='2026',reprt_code='11012',thstrm_nm='2026.06.30',currency='KRW',sj_div='BS',fs_div='OFS')
  return[{**base,'account_id':'ifrs-full_CurrentAssets','account_nm':'유동자산','thstrm_amount':'9,007,199,254,740,993'},{**base,'account_id':'ifrs-full_Liabilities','account_nm':'부채총계','thstrm_amount':'1'}]
 def test_exact_decimal(self):self.assertEqual(financial_pairs(pd.DataFrame(self.rows()))[0]['ncav'],'9007199254740992')
 def test_no_cross_scope_receipt_period(self):
  for key,val in [('fs_div','CFS'),('rcept_no','20260814000002'),('thstrm_nm','2025.06.30')]:
   x=self.rows();x[1][key]=val;self.assertFalse(any(r['status']=='paired'for r in financial_pairs(pd.DataFrame(x))))
 def test_conflict_blocked(self):
  x=self.rows();x.append({**x[0],'thstrm_amount':'3'});self.assertEqual(financial_pairs(pd.DataFrame(x))[0]['status'],'held')
 def test_not_current_liabilities(self):
  x=self.rows();x[1].update(account_id='ifrs-full_CurrentLiabilities',account_nm='부채총계');self.assertFalse(any(r['status']=='paired'for r in financial_pairs(pd.DataFrame(x))))

class CodeFilterTests(unittest.TestCase):
 def test_collectors_preserve_alpha_codes(self):
  import ast,re
  from pathlib import Path
  root=Path(__file__).resolve().parents[1]
  for name in ['update_dart_financials.py','scripts/backfill_dart_full_financials.py','scripts/backfill_dart_value_factors.py','scripts/backfill_dart_legacy_quarterly.py']:
   tree=ast.parse((root/name).read_text())
   patterns=[n.args[0].value for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='fullmatch'and n.args and isinstance(n.args[0],ast.Constant)and n.args[0].value=='[0-9A-Z]{6}']
   self.assertTrue(patterns,name)
   for p in patterns:
    for code in ['005930','0001A0','00088K']:self.assertIsNotNone(re.fullmatch(p,code))
    for code in ['12345','1234567','001 00','']:self.assertIsNone(re.fullmatch(p,code))

if __name__=='__main__':unittest.main()
