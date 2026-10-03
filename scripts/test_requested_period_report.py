"""Synthetic NAV tests validate software only, never investment performance."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from quant_backtest_template_CURRENT import (
    BacktestConfig, expected_market_sessions, run_requested_periods, validate_report_periods,
    calculate_metrics, requested_period_readiness,
)
from quant_backtest_postprocess import write_requested_report, load_daily_nav
from unittest.mock import patch
from strategy_dsl_run import run_checked_strategy
from test_strategy_dsl_run import artificial_execution, fake_preflight, ROOT, EXAMPLE


class RequestedReportTests(unittest.TestCase):
    def setUp(self):
        self.dates = expected_market_sessions(pd.Timestamp('2020-01-01'), pd.Timestamp('2023-12-31'), 'XKRX')
        n = np.arange(len(self.dates))
        r = .0003 + .006 * np.sin(n / 17)
        r[0] = 0
        gross = np.cumprod(1+r)
        net = gross * np.exp(-n*.00002)
        self.daily = pd.DataFrame({'NAV_Gross':gross,'NAV_Net_fixed':net,'NAV_Benchmark':np.exp(n*.0001)},index=self.dates)
        self.cfg = BacktestConfig(as_of_date='2023-12-31',market_calendar='XKRX',initial_capital=10000,risk_free_rate=.024)

    def periods(self):
        return [{'id':'all','label':'최장','start':'longest','end':'latest'},
                {'id':'subset','label':'2021 이후','start':'2021-01-01','end':'2023-12-31'},
                {'id':'mid','label':'정확한 날짜','start':'2021-05-12','end':'2022-08-10'},
                {'id':'short','start':'2023-12-28','end':'2023-12-28'},
                {'id':'missing','start':'2000-01-01','end':'latest'}]

    def test_independent_period_baseline_and_metrics(self):
        result = run_requested_periods(self.daily,self.cfg,self.periods())
        p = result['periods']['mid']; m = p['metrics_frame'].loc['NAV_Gross']
        days = self.daily.loc['2021-05-12':'2022-08-10'].index
        previous = self.daily.index[self.daily.index.get_loc(days[0])-1]
        expected = self.daily.NAV_Gross.loc[days] / self.daily.NAV_Gross.loc[previous]
        elapsed = (days[-1]-previous).days / 365.2425
        self.assertAlmostEqual(m['최종배수'],expected.iloc[-1],14)
        self.assertAlmostEqual(m.CAGR,expected.iloc[-1]**(1/elapsed)-1,14)
        self.assertNotEqual(expected.iloc[0],1.)  # first selected day's return retained
        dd = expected.to_numpy() / np.maximum.accumulate(np.r_[1.,expected])[1:] - 1
        self.assertAlmostEqual(m.MDD,dd.min(),14)
        # Independent full-month sample oracle, excludes May2021/Aug2022 boundaries.
        month_ends = self.daily.groupby(self.daily.index.to_period('M')).tail(1)
        month_ends.index = month_ends.index.to_period('M')
        returns = month_ends.NAV_Gross.pct_change().loc['2021-06':'2022-07']
        self.assertEqual(p['monthly_statistical_samples'],len(returns))
        rf = 1.024**(1/12)-1
        self.assertAlmostEqual(m.Sharpe,((returns-rf).mean()/(returns-rf).std(ddof=1))*np.sqrt(12),12)
        self.assertAlmostEqual(m['연환산_표준편차'],returns.std(ddof=1)*np.sqrt(12),12)
        self.assertEqual(p['ending_asset_date'],'2022-08-10')
        self.assertEqual(p['series']['NAV_Gross']['points'][0]['asset'],10000)
        self.assertEqual(p['series']['NAV_Gross']['points'][0]['date'],previous.date().isoformat())
        for period in result['periods'].values():
            if period['ready']:
                for series in period['series'].values():
                    self.assertEqual(series['metrics']['final_asset'],series['points'][-1]['asset'])
                    if series['metrics']['mdd'] is not None:
                        self.assertAlmostEqual(min(x['drawdown_pct'] for x in series['points'])/100,series['metrics']['mdd'],14)
        self.assertFalse(result['readiness']['complete'])
        self.assertEqual(result['periods']['missing']['status'],'data_gap')
        self.assertNotIn('series',result['periods']['missing'])

    def test_short_samples_zero_denominators_and_negative_log_ticks(self):
        p = run_requested_periods(self.daily,self.cfg,self.periods())['periods']['short']
        m = p['series']['NAV_Gross']['metrics']
        for key in ('cagr','sharpe','annual_volatility','mdd','recovery_days'):
            self.assertIsNone(m[key])
        self.assertIsNotNone(m['final_asset'])
        flat = self.daily.copy(); flat.loc[:,:] = 1.
        p = run_requested_periods(flat,self.cfg,self.periods()[:1])['periods']['all']
        self.assertIsNone(p['series']['NAV_Gross']['metrics']['sharpe'])
        self.assertEqual(p['series']['NAV_Gross']['metrics']['annual_volatility'],0.)
        fall = flat.copy(); fall.loc[:,:] = np.geomspace(1,.125,len(fall))[:,None]
        p = run_requested_periods(fall,self.cfg,self.periods()[:1])['periods']['all']
        self.assertIn(.25,p['log_ticks']['values']);self.assertIn(.5,p['log_ticks']['values'])
        self.assertIn('0.25배',p['log_ticks']['labels'])
        self.assertEqual(p['series']['NAV_Gross']['points'][-1]['multiple'],.125)

    def test_fail_closed_dates_and_samples(self):
        with self.assertRaisesRegex(ValueError,'session mismatch'):
            run_requested_periods(self.daily.drop(self.dates[50]),self.cfg,self.periods())
        forged = self.daily.drop(self.dates[50]);forged.attrs['coverage_verified']=True
        with self.assertRaises(ValueError):
            calculate_metrics(forged,self.cfg,forged,requested_period=True)
        with self.assertRaisesRegex(ValueError,'no silent rescaling'):
            run_requested_periods(self.daily*2,self.cfg,self.periods())
        for bad in ([{'id':'x','start':'2021-02-30','end':'latest'}],
                    [{'id':'x','start':'longest','end':'latest','typo':True}],
                    [{'id':'x','start':2000,'end':'latest'}],self.periods()[:1]*2):
            with self.assertRaises(ValueError):validate_report_periods(bad)
        ready = requested_period_readiness(self.dates,[{'id':'future','start':'2024-01-01','end':'2024-02-01'}],self.cfg)
        self.assertFalse(ready['ready'])
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'bad.csv';bad=self.daily.copy();bad.iloc[0,0]=np.nan;bad.to_csv(src,index_label='Date')
            with self.assertRaisesRegex(ValueError,'no silent common-start shift'):
                load_daily_nav(src,'Date',None,preserve_origin=True)

    def test_manifest_and_offline_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'nav.csv';self.daily.to_csv(src,index_label='Date')
            cfg=BacktestConfig(title='합성 NAV · 소프트웨어 테스트 <script>',as_of_date='2023-12-31',market_calendar='XKRX')
            manifest=write_requested_report(self.daily,cfg,self.periods(),root/'report',benchmark='NAV_Benchmark',daily_csv=src,repo_root=root)
            json.dumps(manifest,allow_nan=False)
            self.assertFalse(manifest['readiness']['complete'])
            page=(root/'report/report_CURRENT.html').read_text()
            self.assertIn('plotly.js',page);self.assertIn("type:'log'",page)
            self.assertIn('customdata',page);self.assertIn('환율 미반영',page)
            self.assertNotIn('<h1>합성 NAV · 소프트웨어 테스트 <script>',page)
            self.assertIn('재현성·상세 진단',page)
            self.assertIn('three_interactive_charts_shared_period_selector',manifest['render_mode'])
            metrics=pd.read_csv(root/'report/metrics_CURRENT.csv')
            self.assertNotIn('missing',set(metrics.period))
            self.assertEqual(set(metrics.period),{'all','subset','mid','short'})

    def test_checked_lifecycle_and_missing_period_diagnosis(self):
        raw = json.loads(EXAMPLE.read_text())
        periods = [{'id':'short','start':'longest','end':'latest'},
                   {'id':'missing','start':'2000-01-01','end':'latest'}]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'strategy.json';source.write_text(json.dumps(raw))
            def fake_with_observed_anchor(path,repo,out,**kwargs):
                result=artificial_execution(path,repo,out,**kwargs)
                csv=out/'daily_nav.csv';frame=pd.read_csv(csv);columns=[c for c in frame if c!='Date']
                frame[columns]=frame[columns].div(frame[columns].iloc[0]);frame.to_csv(csv,index=False)
                return result
            with patch('strategy_dsl_run.preflight_strategy',side_effect=fake_preflight),patch('strategy_dsl_run.run_strategy',side_effect=fake_with_observed_anchor):
                good=run_checked_strategy(source,ROOT,root/'valid',report_periods=periods)
            self.assertEqual(good['status'],'ok',good)
            self.assertTrue(good['nav_ready']);self.assertTrue(good['report_ready']);self.assertFalse(good['report_complete'])
            self.assertEqual(good['period_readiness']['missing']['status'],'data_gap')
            with patch('strategy_dsl_run.preflight_strategy',side_effect=fake_preflight),patch('strategy_dsl_run.run_strategy') as execution:
                gap=run_checked_strategy(source,ROOT,root/'gap',report_periods=periods[1:])
                execution.assert_not_called()
            self.assertEqual(gap['status'],'data_gap');self.assertFalse(gap['report_ready'])
            self.assertIn('2000', (root/'gap/diagnostic_CURRENT.html').read_text())
            self.assertFalse((root/'gap/report/metrics_CURRENT.csv').exists())
            invalid=run_checked_strategy(source,ROOT,root/'invalid',postprocess=False,report_periods=periods)
            self.assertEqual(invalid['status'],'capability_gap');self.assertFalse(invalid['nav_ready'])


if __name__=='__main__':unittest.main(verbosity=2)
