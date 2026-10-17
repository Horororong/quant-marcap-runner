"""Explicit-model boundaries, original strict account behavior remains unchanged."""
from dataclasses import asdict
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json,unittest
from stock_dividend import *
from stock_dividend_research import validate_model
from strategy_dsl import StrategySpec
ROOT=Path(__file__).resolve().parents[1]

def ev(d='2020-01-01',kind='primary'):
 return Evidence('https://example.org/source' if kind=='primary' else 'model:explicit-v1','a'*64,'synthetic test metadata; not actual issuer evidence',d,kind)

class Research(unittest.TestCase):
 def test_unknown_lifecycle_is_not_carried_indefinitely_into_future_periods(self):
  from stock_dividend_research import load_strategy_actions
  raw=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json').read_text())
  raw['period']['end']='2021-12-31';raw['period']['book_end']='2021-12-31';raw['period']['as_of_date']='2021-12-31'
  with self.assertRaisesRegex(ValueError,'beyond catalog support'):
   load_strategy_actions(ROOT,StrategySpec.from_dict(raw),asset_codes={'068270','091990'})
 def test_preferred_share_security_codes_are_valid_without_universe_exclusion(self):
  self.assertEqual(code('00088K'),'00088K')
  b=StockDividendBook('0',{'00088K':'1.5'},scope='modeled_research',quantity_policy='research_pro_rata')
  self.assertEqual(b.close('2020-01-02',{'00088K':'100'})['value'],'150.0')
  for bad in ['00088k','00088','000088K']:
   with self.assertRaises(ValueError):code(bad)
 def test_policy_and_fingerprint(self):
  raw=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json').read_text())
  a=StrategySpec.from_dict(raw);b=deepcopy(raw);b['research']['conditional_fraction']=.9
  self.assertNotEqual(a.fingerprint(),StrategySpec.from_dict(b).fingerprint())
  for k,v in [('distribution_tax_basis','after_tax'),('conditional_fraction',1.01),('conditional_fraction',True),('settlement_lag_sessions',True)]:
   x=deepcopy(raw['research']);x[k]=v
   with self.assertRaises(Exception):validate_model(x)
 def test_fractional_research_and_separate_virtual_release(self):
  b=StockDividendBook('1000',{'000001':'100.5'},scope='modeled_research',quantity_policy='research_pro_rata')
  t=Terms('E','000001','2020-01-02','2020-01-03','.05',ev())
  b.close('2020-01-02',{'000001':'96'},entitlements=[t],marks=[RightMark('E','2020-01-02','86.4','explicit .9 conditional haircut',ev('2020-01-02','research_model'))],trades=[Trade('000001','sell','100.5')])
  self.assertEqual(b.claims['E']['quantity'],Decimal('5.025'))
  self.assertEqual(b.cash,Decimal('10648'))
  # Later publication recognizes a prior actual decision, never before evidence.
  snap=deepcopy(b.__dict__)
  with self.assertRaisesRegex(ValueError,'future evidence'):
   b.close('2020-01-03',{'000001':'97'},decisions=[Decision('E','2020-01-03',True,ev('2020-01-06'))])
  self.assertEqual(b.__dict__,snap)
  b.close('2020-01-06',{'000001':'100'},decisions=[Decision('E','2020-01-03',True,ev('2020-01-06'))],marks=[RightMark('E','2020-01-06','100','approved share equivalent',ev('2020-01-06','research_model'))])
  before=b.cash+Decimal('502.5')
  s=b.close('2020-01-07',{'000001':'100'},settlements=[VirtualSettlement('E','2020-01-07','2020-01-07',ev('2020-01-06'))])
  self.assertEqual(Decimal(s['value']),before);self.assertEqual(b.cash,Decimal('10648'));self.assertEqual(b.shares['000001'],Decimal('5.025'))
  self.assertEqual(s['actions'][0]['action'],'virtual_listing_settlement');self.assertFalse(s['actions'][0]['actual_account_credit_certified'])
  with self.assertRaises(ValueError):b.close('2020-01-08',{'000001':'100'},settlements=[VirtualSettlement('E','2020-01-08','2020-01-07',ev())])
 def test_whole_account_is_not_relaxed(self):
  with self.assertRaises(ValueError):StockDividendBook('0',{'000001':'1.5'},scope='evidenced_research')
  with self.assertRaises(ValueError):StockDividendBook('0',scope='evidenced_research',quantity_policy='research_pro_rata')
  with self.assertRaises(ValueError):ev(kind='research_model').check('2020-01-02','evidenced_research')
 def test_model_cannot_supply_historical_fact(self):
  b=StockDividendBook('0',{'000001':'100'},scope='modeled_research',quantity_policy='research_pro_rata')
  with self.assertRaisesRegex(ValueError,'historical entitlement facts'):
   b.close('2020-01-02',{'000001':'100'},entitlements=[Terms('E','000001','2020-01-02','2020-01-03','.05',ev(kind='research_model'))])
 def test_no_liquidity_from_conditional_rights_and_cancellation(self):
  b=StockDividendBook('0',{'000001':'100'},scope='modeled_research',quantity_policy='research_pro_rata')
  t=Terms('E','000001','2020-01-02','2020-01-03','.05',ev())
  b.close('2020-01-02',{'000001':'100'},entitlements=[t],marks=[RightMark('E','2020-01-02','90','conditional haircut .9',ev(kind='research_model'))])
  with self.assertRaisesRegex(ValueError,'insufficient settled cash'):
   b.close('2020-01-03',{'000001':'100'},trades=[Trade('000001','buy','1')])
  with self.assertRaisesRegex(ValueError,'insufficient tradable shares'):
   b.close('2020-01-03',{'000001':'100'},trades=[Trade('000001','sell','101')])
  s=b.close('2020-01-03',{'000001':'100'},decisions=[Decision('E','2020-01-03',False,ev(),cancellation_treatment='verified_no_compensation',cancellation_evidence=ev())])
  self.assertEqual(s['rights_value'],'0');self.assertEqual(s['value'],'10000')

if __name__=='__main__':unittest.main(verbosity=2)
