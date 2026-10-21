"""Readiness failure boundaries; synthetic source fixtures, never performance."""
import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from research_planned_readiness import inspect_planned_strategy
ROOT=Path(__file__).resolve().parents[1]

class PlannedReadiness(unittest.TestCase):
 def fixture(self,mutate=None,deciles=False,deferred=False,no_signals=False,incomplete_calendar=False):
  dates=pd.to_datetime(['2024-05-02','2024-05-03','2024-05-07','2024-05-08'])
  rows=[dict(Date=d,Code=c,Market='KOSPI',Name=c,Close=100.,Volume=10.,Marcap=2e13,ChangesRatio=0.) for d in dates for c in ['000001','000002']]
  panel=pd.DataFrame(rows)
  if mutate:mutate(panel,dates)
  spec=json.loads((ROOT/'config/strategies/research_size_top1_2024.json').read_text());spec['period']={k:('2024-05-02' if k in ['start','book_start'] else '2024-05-08') for k in spec['period']}
  if deciles:spec['portfolio']=dict(selection='deciles',weighting='equal')
  if deferred:spec['execution']['nontradable_policy']='defer_full_rebalance_events_v1'
  engine=SimpleNamespace(load_krx_equity_panel=lambda **kwargs:panel.copy())
  ranked=panel[panel.Date.eq(dates[0])].copy();ranked['composite_score']=[.1,.2]
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'data/krx_equities/yearly';p.mkdir(parents=True);(p/'marcap-2024.parquet').write_bytes(b'explicit synthetic unit fixture')
   path=root/'spec.json';path.write_text(json.dumps(spec))
   # The real shared timing owner is retained; only source/provider inputs are
   # fixtures. Real shared selection equivalence is tested in actual-data CI.
   from strategy_dsl_runner import load_project_engine
   real=load_project_engine(ROOT);engine._schedule_signal_execution_dates=real._schedule_signal_execution_dates
   with patch('strategy_dsl_runner.load_project_engine',return_value=engine),patch('strategy_dsl_runner.engine_inputs',return_value=(None,None,SimpleNamespace(execution_lag_sessions=1,weight_tolerance=1e-10))),patch('strategy_dsl_runner.scored_signals_from_panel',return_value=[(dates[0],ranked)]),patch('strategy_dsl_runner.signal_dates_from_panel',return_value=[]if no_signals else[dates[0]]),patch('strategy_dsl_runner.factor_provider_coverage_audit',return_value=pd.DataFrame()),patch('strategy_dsl_runner.benchmark_coverage_audit',return_value=dict(status='complete')),patch('krx_history_audit.session_coverage_audit',return_value=dict(status='incomplete',markets={})if incomplete_calendar else dict(status='complete')):
    return inspect_planned_strategy(path,root)
 def test_unheld_discontinuity_does_not_block(self):
  def change(x,d):x.loc[x.Code.eq('000002'),'ChangesRatio']=50.
  r=self.fixture(change)
  self.assertEqual(r['status'],'ok');self.assertFalse(r['investment_approved'])
 def test_actual_selected_future_date_is_precise(self):
  def change(x,d):x.loc[x.Date.eq(d[2])&x.Code.eq('000001'),'ChangesRatio']=1.
  r=self.fixture(change);b=r['first_blocker'];self.assertEqual((b['kind'],b['security'],b['date']),('held_return_reference_gap','000001','2024-05-07'));self.assertAlmostEqual(b['difference_bps'],100.)
 def test_missing_quote_remains_unknown_and_persisted_range(self):
  def change(x,d):x.loc[x.Date.ge(d[2])&x.Code.eq('000001'),'Close']=float('nan')
  r=self.fixture(change);b=r['first_blocker'];self.assertEqual(b['kind'],'missing_held_quote');self.assertEqual(b['occurrences'],2);self.assertEqual(b['affected_through'],'2024-05-08');self.assertEqual(b['verdict'],'UNVERIFIED')
 def test_execution_day_no_volume_does_not_move_trade(self):
  def change(x,d):x.loc[x.Date.eq(d[1])&x.Code.eq('000001'),'Volume']=0.
  r=self.fixture(change);b=r['first_blocker'];self.assertEqual(b['kind'],'planned_trade_not_tradable');self.assertEqual(b['date'],'2024-05-03')
 def test_original_population_rule_never_relaxed(self):
  r=self.fixture(deciles=True);self.assertEqual(r['issues'][0]['kind'],'insufficient_eligible_population');self.assertEqual(r['issues'][0]['classification'],'strategy_definition');self.assertFalse(r['ready_for_execution'])
 def test_later_pending_conflict_does_not_hide_earlier_held_return_failure(self):
  from execution_scheduling import PendingOrderError
  def change(x,d):x.loc[x.Date.eq(d[2])&x.Code.eq('000001'),'ChangesRatio']=1.
  dates=pd.to_datetime(['2024-05-02','2024-05-03','2024-05-07','2024-05-08'])
  error=PendingOrderError('synthetic later pending conflict',dates[-1],dict(signal=dates[-2],planned=dates[-1],blocked=[]),resolved={dates[0]:dates[1]})
  with patch('execution_scheduling.resolve_deferred_schedule',side_effect=error):r=self.fixture(change,deferred=True)
  b=r['first_blocker'];self.assertEqual((b['kind'],b['date']),('held_return_reference_gap','2024-05-07'));self.assertFalse(b.get('diagnostic_only',False))
  self.assertFalse(r['ready_for_execution']);self.assertIn('top_n',r['resolved_schedule_prefix'])
 def test_unsupported_input_does_not_read_sources(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad.json';p.write_text('{}');r=inspect_planned_strategy(p,td);self.assertEqual(r['status'],'capability_gap');self.assertEqual(r['phase'],'compile')
 def test_empty_full_period_remains_blocked_and_calendar_gap_is_not_hidden(self):
  r=self.fixture(no_signals=True);self.assertFalse(r['ready_for_execution']);self.assertEqual(r['first_blocker']['kind'],'no_rebalance_signals');self.assertEqual(r['first_blocker']['classification'],'strategy_definition')
  missing=self.fixture(no_signals=True,incomplete_calendar=True);self.assertFalse(missing['ready_for_execution']);self.assertEqual(missing['first_blocker']['kind'],'market_calendar_scope_unverified')
 def test_empty_annual_fragment_preserves_strict_signal_owner_default(self):
  from strategy_dsl import StrategySpec
  from strategy_dsl_runner import signal_dates_from_panel
  raw=json.loads((ROOT/'config/strategies/research_size_top1_2024.json').read_text());raw['period']=dict(start='2019-12-02',end='2020-12-30',book_start='2019-12-02',book_end='2020-12-30',as_of_date='2020-12-30');spec=StrategySpec.from_dict(raw)
  fragment=pd.DataFrame(dict(Date=pd.to_datetime(['2019-12-02','2019-12-30'])))
  with self.assertRaisesRegex(RuntimeError,'no rebalance'):signal_dates_from_panel(fragment,spec)
  self.assertEqual(signal_dates_from_panel(fragment,spec,allow_empty=True),[])
  complete=pd.concat([fragment,pd.DataFrame(dict(Date=pd.to_datetime(['2020-04-29','2020-04-30','2020-05-04'])))])
  self.assertEqual(signal_dates_from_panel(complete,spec),[pd.Timestamp('2020-04-30')])

if __name__=='__main__':unittest.main(verbosity=2)
