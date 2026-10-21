import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research_period_analysis import period_request,analyze_saved_nav
import test_saved_research_comparisons as saved_fixtures
from research_language import translate
from test_research_language import TEXT
from strategy_dsl import StrategySpec
from strategy_dsl_runner import run_current_postprocess,signal_dates_from_panel
from quant_backtest_postprocess import report_context

class PeriodAnalysis(unittest.TestCase):
 def setUp(self):saved_fixtures.SavedComparison.setUp(self)
 def request(self):return dict(source_job_id=self.ids[0],start='2024-06-03',end='2024-10-31')
 def test_bad_ranges_rejected_without_job_or_engine(self):
  for start,end in [('2024-02-30','2024-03-01'),('2024-10-01','2024-01-01'),('2024-1-01','2024-02-01'),(None,'2024-01-01')]:
   with self.assertRaises((ValueError,TypeError)):period_request(start,end)
  self.assertEqual(self.w.saved('jobs').__len__(),2)
 def test_analysis_job_keeps_source_fingerprint_and_explicit_no_engine_contract(self):
  with patch.object(self.w.pool,'submit'):
   job=self.w.analyze(self.request())
  self.assertEqual(job['mode'],'analysis');self.assertFalse(job['engine_rerun'])
  self.assertEqual(job['fingerprint'],'fixture-0');self.assertEqual(job['source_job_id'],self.ids[0])
  self.assertEqual(len(job['source_snapshot']['files']),7)
 def test_failed_or_analysis_source_is_rejected(self):
  p=self.w.store/'jobs'/str(self.ids[0]+'.json');original=json.loads(p.read_text())
  for mode,status in [('run','data_gap'),('analysis','ok')]:
   p.write_text(json.dumps({**original,'mode':mode,'status':status}))
   with self.assertRaisesRegex(ValueError,'성공한 원래 백테스트'):self.w.analyze(self.request())
 def test_source_mutation_blocks_before_any_current_or_engine_call(self):
  with patch.object(self.w.pool,'submit'):job=self.w.analyze(self.request())
  (self.w.store/'runs'/self.ids[0]/'run/artifacts/daily_nav.csv').write_text('changed')
  with patch('strategy_dsl_runner.run_current_postprocess')as post,patch('strategy_dsl_run.run_checked_strategy')as engine:
   with self.assertRaisesRegex(ValueError,'ANALYSIS_SOURCE_CHANGED'):
    analyze_saved_nav(self.w.root,self.w.store,job,self.w.store/'runs'/job['id'])
  post.assert_not_called();engine.assert_not_called()
 def test_exact_date_amendment_requires_fresh_confirmation(self):
  original=translate(TEXT);amended=translate('기간을 2019-12-02부터 2020-12-30까지로 변경',base=original['strategy'])
  self.assertEqual(amended['strategy']['period']['start'],'2019-12-02')
  self.assertEqual(amended['strategy']['period']['as_of_date'],'2020-12-30')
  self.assertNotEqual(original['confirmation_digest'],amended['confirmation_digest'])
  with self.assertRaises(ValueError):self.w.submit(dict(strategy=amended['strategy'],confirmation_digest=original['confirmation_digest']),'run')
  with self.assertRaises(ValueError):translate('기간을 2020-02-30부터 2020-12-30까지로 변경',base=original['strategy'])
 def test_current_transport_is_dedicated_isolated_and_no_shell(self):
  import pandas as pd,sys
  with patch('strategy_dsl_runner.subprocess.run',return_value=subprocess.CompletedProcess([],0,'',''))as child:
   run_current_postprocess(StrategySpec.from_dict(translate(TEXT)['strategy']),self.w.root,self.w.store,pd.DataFrame(columns=['NAV_Gross']))
  cmd=child.call_args.args[0];self.assertEqual(cmd[:3],[sys.executable,'-I','-c']);self.assertNotIn('shell',child.call_args.kwargs)
 def test_context_labels_existing_nav_without_altering_original_strategy(self):
  run=self.w.store/'runs'/self.ids[0]/'run';csv=run/'artifacts/daily_nav.csv';original=(run/'strategy_normalized.json').read_bytes()
  before=report_context(csv,self.w.root,'test')
  (run/'analysis_context.json').write_text(json.dumps(dict(operation='existing_nav_analysis',engine_rerun=False)))
  after=report_context(csv,self.w.root,'test')
  self.assertNotIn('analysis_context.json',before[1]);self.assertIn('analysis_context.json',after[1])
  self.assertIn('엔진 재실행 없음',after[0]);self.assertEqual((run/'strategy_normalized.json').read_bytes(),original)

if __name__=='__main__':unittest.main()
