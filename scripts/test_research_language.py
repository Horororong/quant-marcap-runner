import copy,json,unittest
from pathlib import Path
from research_language import translate,confirmation_digest
ROOT=Path(__file__).resolve().parents[1]
TEXT='2024년 코스피·코스닥에서 시가총액 10조원 이상 종목을 시가총액이 큰 순으로 상위1종목 동일비중으로 구성하고 4월말 리밸런싱. 1거래일 뒤 종가 체결, 수수료 1.5bp, 매도세 15bp, 스프레드 3bp, 슬리피지 5bp, 벤치마크 코스피.'
class Language(unittest.TestCase):
 def test_paraphrases_are_the_same_complete_DSL(self):
  first=translate(TEXT)
  for text in [TEXT.replace('코스피·코스닥','코스피와코스닥'),TEXT.replace('시가총액이 큰 순으로','시총 높은 순으로').replace('동일비중','같은 비중'),TEXT.replace('리밸런싱.','리밸런싱해줘.')]:
   self.assertEqual(translate(text)['strategy'],first['strategy'])
 def test_requested_period_and_terms_match_existing_example(self):
  original=json.loads((ROOT/'config/strategies/research_size_top1_2024.json').read_text())
  from strategy_dsl import StrategySpec
  raw=translate(TEXT,research=original.get('research'))['strategy'];expected=StrategySpec.from_dict(original).to_dict()
  for key in ['universe','portfolio','period','execution','rebalance','cost_scenarios','benchmark','initial_capital','research']:
   self.assertEqual(raw.get(key),expected.get(key),key)
  for key in ['source','field','direction','weight']:self.assertEqual(raw['factors'][0][key],expected['factors'][0][key])
 def test_variations_have_exact_new_conditions(self):
  s=translate(TEXT.replace('2024年','2024년').replace('2024년','2020년').replace('상위1종목','상위3종목').replace('시가총액이 큰 순으로','3-1 모멘텀 높은 순으로').replace('4월말','분기말').replace('수수료 1.5bp','수수료 2.5bp'))['strategy']
  self.assertEqual(s['period']['start'],'2020-01-01');self.assertEqual(s['period']['end'],'2020-12-31')
  self.assertEqual(s['factors'][0]['field'],'momentum_3_1');self.assertEqual(s['portfolio']['number_of_positions'],3)
  self.assertEqual(s['rebalance']['months'],(3,6,9,12));self.assertEqual(s['cost_scenarios']['fixed_cost']['commission_bps'],2.5)
 def test_changes_require_fresh_confirmation_and_preserve_base(self):
  a=translate(TEXT);b=translate('수수료를 2.5bp로 변경',base=a['strategy'])
  self.assertNotEqual(a['confirmation_digest'],b['confirmation_digest']);self.assertEqual(a['strategy']['cost_scenarios']['fixed_cost']['commission_bps'],1.5)
  self.assertEqual(b['strategy']['cost_scenarios']['fixed_cost']['commission_bps'],2.5)
  self.assertEqual(confirmation_digest(b['strategy']),b['confirmation_digest'])
 def test_missing_defaults_are_visible_but_never_execution_permission(self):
  o=translate('2024년 코스피에서 시총 큰 순으로 상위1종목 4월말')
  self.assertGreaterEqual(len(o['defaults_applied']),7);self.assertEqual(o['status'],'interpreted_requires_confirmation')
  self.assertFalse(o['language']['external_model_connected'])
 def test_unconsumed_unsupported_and_ambiguous_requests_are_rejected(self):
  for text in [TEXT+'손절5%',TEXT+' 레버리지2배',TEXT.replace('1거래일 뒤 종가 체결','당일종가 체결'),TEXT.replace('3-1 모멘텀','12개월 모멘텀').replace('시가총액이 큰 순으로','12개월 모멘텀 높은 순으로'),TEXT.replace('동일비중','시총가중'),TEXT+'매도세 3bp',TEXT.replace('상위1종목','상위1종목 상위2종목')]:
   with self.assertRaises(ValueError,msg=text):translate(text)
if __name__=='__main__':unittest.main(verbosity=2)
