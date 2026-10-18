"""Selected-scope gating retains held gaps and verified successor lineage."""
import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from strategy_dsl import StrategySpec
from stock_dividend_research import selected_action_scope,load_strategy_actions
ROOT=Path(__file__).resolve().parents[1]
class Scope(unittest.TestCase):
 def spec(self):
  d=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json').read_text());d['period'].update(end='2025-12-31',book_end='2025-12-31',as_of_date='2025-12-31');return StrategySpec.from_dict(d)
 def test_unheld_catalog_lifecycle_does_not_block_other_stock(self):
  s=self.spec();w=pd.DataFrame({'005930':[1.],'068270':[0.]},index=pd.to_datetime(['2019-04-30']))
  used=selected_action_scope(ROOT,s,w,s.period.start,s.period.end);self.assertEqual(used,{'005930'})
  events=load_strategy_actions(ROOT,s,start=s.period.start,end=s.period.end,asset_codes=used);self.assertFalse(events.event_type.eq('stock_dividend').any())
  with self.assertRaisesRegex(ValueError,'lifecycle'):load_strategy_actions(ROOT,s,start=s.period.start,end=s.period.end,asset_codes={'068270'})
 def test_recursive_successors_are_kept_without_new_selection(self):
  s=self.spec();w=pd.DataFrame({'111111':[1.]});e=pd.DataFrame([dict(predecessor_code='111111',successor_code='222222',event_type='stock_merger'),dict(predecessor_code='222222',successor_code='333333',event_type='stock_merger')])
  with patch('corporate_action_registry.load_corporate_actions',return_value=e):self.assertEqual(selected_action_scope(ROOT,s,{'D01':w},s.period.start,s.period.end),{'111111','222222','333333'})
if __name__=='__main__':unittest.main(verbosity=2)
