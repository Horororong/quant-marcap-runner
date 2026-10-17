import unittest,json
from pathlib import Path
from research_workbench import korean_spec,WORKBENCH_CONTRACT
ROOT=Path(__file__).resolve().parents[1]
REQUEST='기간:2019-01-01~2020-12-31;시장:코스피·코스닥;필터:시가총액>=10조원;팩터:시가총액 낮은;포트폴리오:10분위;리밸런싱:4월말;체결:1거래일뒤종가;비용:수수료1.5bp,매도세15bp,스프레드3bp,슬리피지5bp;벤치마크:코스피'
class Workbench(unittest.TestCase):
 def test_translation_matches_original_selection_execution_costs(self):
  original=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json').read_text());s=korean_spec(REQUEST,research=original['research']).to_dict()
  for key in ['universe','portfolio','rebalance','execution','cost_scenarios','period','benchmark','initial_capital']:
   # Canonical normalization supplies optional defaults; compare canonical originals.
   from strategy_dsl import StrategySpec
   self.assertEqual(s[key],StrategySpec.from_dict(original).to_dict()[key],key)
  for k in ['source','field','direction','weight']:self.assertEqual(s['factors'][0][k],original['factors'][0][k])
  self.assertEqual(korean_spec(REQUEST).fingerprint(),korean_spec(REQUEST).fingerprint())
 def test_unrecognized_clause_is_never_ignored(self):
  for text in [REQUEST+';손절:5%',REQUEST.replace('시가총액 낮은','미등록초과수익 높은'),REQUEST.replace('1거래일뒤종가','당일종가'),REQUEST+';시장:코스피',REQUEST.replace('수수료1.5bp,','')]:
   with self.assertRaises(ValueError):korean_spec(text)
 def test_registered_technical_and_topn_are_reused(self):
  s=korean_spec(REQUEST.replace('시가총액 낮은','3-1 모멘텀 높은').replace('10분위','상위3개'))
  self.assertEqual(s.factors[0].field,'momentum_3_1');self.assertEqual(s.portfolio.number_of_positions,3)
if __name__=='__main__':unittest.main(verbosity=2)
