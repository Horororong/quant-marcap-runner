"""Independent formula, compatibility, exact calendar and report integration checks.

Generated NAV fixtures test implementation only, never investment performance.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
from quant_backtest_template_CURRENT import (
    BacktestConfig, calculate_metrics, calculate_benchmark_statistics,
    expected_market_sessions, assert_daily_session_coverage,
    _daily_full_coverage, run_four_periods, standard_period_windows,
)
from quant_backtest_postprocess import derive_complete_monthly
from strategy_dsl_runner import load_project_engine, run_current_postprocess
from strategy_dsl import load_strategy_spec


def fails(fn, text):
    try:
        fn()
    except (ValueError, AssertionError) as e:
        assert text in str(e), str(e)
    else:
        raise AssertionError('expected failure: ' + text)


def main():
    engine = load_project_engine(ROOT)
    for name in ('calculate_metrics', 'calculate_benchmark_statistics', 'run_four_periods',
                 'build_chat_payload', 'combine_period_payloads', 'validate_daily_nav'):
        import quant_backtest_template_CURRENT as current
        assert getattr(engine, name) is getattr(current, name), name
    assert engine.TEMPLATE_VERSION == 'v2-16'
    assert engine.PERFORMANCE_TEMPLATE_VERSION == 'v2-17'
    assert engine.BacktestConfig().standard_start_year == 2000
    assert BacktestConfig().standard_start_year == 2001

    # Independent monthly formulas with real losses, zero month and nonzero risk-free rate.
    idx = pd.date_range('2024-01-31', periods=6, freq='ME')
    rs = np.array([.05, -.04, 0, .02, -.01, .03])
    rb = np.array([.02, -.02, .01, -.03, 0, .01])
    monthly = pd.DataFrame({'S': np.cumprod(1 + rs), 'B': np.cumprod(1 + rb)}, index=idx)
    cfg = BacktestConfig(risk_free_rate=.024, as_of_date='2025-01-01')
    out = calculate_metrics(monthly, cfg).loc['S']
    rf = (1.024 ** (1 / 12)) - 1
    excess = rs - rf
    cagr = monthly.S.iloc[-1] ** 2 - 1
    # Include the implicit initial NAV=1 in the independent running-peak oracle.
    mdd = (monthly.S.to_numpy() / np.maximum.accumulate(np.r_[1, monthly.S.to_numpy()])[1:] - 1).min()
    assert np.isclose(out.CAGR, cagr, atol=1e-14)
    assert np.isclose(out.Sharpe, excess.mean() / excess.std(ddof=1) * np.sqrt(12), atol=1e-14)
    assert np.isclose(out.Sortino, excess.mean() * 12 / (np.sqrt(np.mean(np.minimum(excess, 0)**2)) * np.sqrt(12)), atol=1e-14)
    assert np.isclose(out.Calmar, cagr / abs(mdd), atol=1e-14)
    assert np.isclose(out['월간승률'], .5)
    bm = calculate_benchmark_statistics(monthly, 'S', 'B', cfg)
    active = rs - rb
    beta = np.sum((rs-rs.mean()) * (rb-rb.mean())) / np.sum((rb-rb.mean())**2)
    assert np.isclose(bm['tracking_error'], active.std(ddof=1) * np.sqrt(12), atol=1e-14)
    assert np.isclose(bm['information_ratio'], active.mean() / active.std(ddof=1) * np.sqrt(12), atol=1e-14)
    assert np.isclose(bm['beta'], beta, atol=1e-14)
    assert np.isclose(bm['alpha_annualized_arithmetic'], ((rs-rf).mean()-beta*(rb-rf).mean())*12, atol=1e-14)
    assert np.isclose(bm['downside_capture'], rs[rb < 0].mean() / rb[rb < 0].mean(), atol=1e-14)
    monotone = pd.DataFrame({'S': 1.01 ** np.arange(1, 7), 'B': np.ones(6)}, index=idx)
    undefined = calculate_metrics(monotone, BacktestConfig(as_of_date='2025-01-01')).loc['S']
    assert np.isnan(undefined.Sortino) and np.isnan(undefined.Calmar)
    assert np.isnan(calculate_benchmark_statistics(monotone, 'S', 'B', cfg)['beta'])
    fails(lambda: calculate_benchmark_statistics(monthly, 'S', 'S', cfg), 'must differ')
    partial = monthly.copy()
    partial.attrs['performance_baseline_date'] = pd.Timestamp('2024-01-15')
    pm = calculate_metrics(partial, cfg).loc['S']
    assert np.isclose(pm['월간승률'], .4)
    pb = calculate_benchmark_statistics(partial, 'S', 'B', cfg)
    assert np.isclose(pb['tracking_error'], active[1:].std(ddof=1) * np.sqrt(12))

    # Previously checked CURRENT outputs: all original columns, all four periods.
    baseline = json.loads((ROOT / 'config/testing/canonical_performance_v215_baseline.json').read_text())
    dates = pd.bdate_range('2000-01-03', '2024-12-31')
    values = np.cumprod(1 + .0002 + .001 * np.sin(np.arange(len(dates)) / 19))
    daily = pd.DataFrame({'S': values}, index=dates)
    _, month = derive_complete_monthly(daily, pd.Timestamp('2025-01-01'))
    config = BacktestConfig(book_start='2000-01-01', book_end='2021-12-31', as_of_date='2025-01-01', standard_end_year=2026)
    results = run_four_periods(month, config, daily)
    for key, metrics in baseline.items():
        row = results[key]['metrics'].loc['S']
        for field, expected in metrics.items():
            if isinstance(expected, str): assert row[field] == expected
            else: assert np.isclose(row[field], expected, rtol=1e-12, atol=1e-12), (key, field, row[field], expected)

    future_months = pd.DataFrame({'S': np.ones(324)}, index=pd.date_range('2001-01-31', periods=324, freq='ME'))
    future_config = BacktestConfig(book_start='2001-01-01', book_end='2021-12-31', as_of_date='2028-01-01', standard_end_year=2028)
    assert standard_period_windows(future_months, future_config)['from_2001'][1] == pd.Timestamp('2027-12-31')

    # Exact holiday-aware validation, deletions, extra dates and forged coverage flag.
    days = expected_market_sessions(pd.Timestamp('2017-10-01'), pd.Timestamp('2017-10-31'), 'XKRX')
    nav = pd.DataFrame({'S': np.linspace(1, 1.1, len(days))}, index=days)
    assert _daily_full_coverage(nav, pd.Timestamp('2017-10-01'), pd.Timestamp('2017-10-31'), market_calendar='XKRX')
    assert not _daily_full_coverage(nav, pd.Timestamp('2017-10-01'), pd.Timestamp('2017-10-31'))
    missing = nav.drop(days[3]); missing.attrs['coverage_verified'] = True
    fails(lambda: assert_daily_session_coverage(missing, pd.Timestamp('2017-10-01'), pd.Timestamp('2017-10-31'), 'XKRX'), 'missing=1')
    extra = pd.concat([nav, pd.DataFrame({'S': [1]}, index=[pd.Timestamp('2017-10-08')])]).sort_index()
    fails(lambda: assert_daily_session_coverage(extra, pd.Timestamp('2017-10-01'), pd.Timestamp('2017-10-31'), 'XKRX'), 'extra=1')
    missing_month = pd.DataFrame({'S': [missing.S.iloc[-1]]}, index=[pd.Timestamp('2017-10-31')])
    assert calculate_metrics(missing_month, BacktestConfig(market_calendar='XKRX', as_of_date='2018-01-01'), missing).loc['S', 'MDD_source'] == 'monthly_fallback'

    # Full public CLI produces all four periods, all nine chart manifest entries,
    # optional benchmark statistics, strict calendars, and no outputs on failure.
    sessions = expected_market_sessions(pd.Timestamp('2000-01-01'), pd.Timestamp('2024-12-31'), 'XKRX')
    n = np.arange(len(sessions))
    full = pd.DataFrame({'NAV_Gross': np.cumprod(1+.0002+.001*np.sin(n/19)),
                         'NAV_Net': np.cumprod(1+.00019+.001*np.sin(n/19)),
                         'NAV_Benchmark': np.cumprod(1+.00015+.0015*np.cos(n/23))}, index=sessions)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); src = td/'nav.csv'; full.to_csv(src, index_label='Date')
        cmd = [sys.executable, str(ROOT/'scripts/quant_backtest_postprocess.py'), '--daily-csv', str(src),
               '--title', 'synthetic implementation test', '--book-start', '2000-01-01', '--book-end', '2021-12-31',
               '--as-of-date', '2025-01-01', '--market-calendar', 'XKRX', '--benchmark-series', 'NAV_Benchmark']
        out = td/'valid'
        subprocess.run(cmd+['--output-dir', str(out)], check=True, capture_output=True, text=True)
        metrics = pd.read_csv(out/'metrics_CURRENT.csv')
        assert set(metrics.period) == {'book_validation','from_2001','from_2021','longest'}
        assert len(metrics) == 12 and set(metrics.MDD_source) == {'daily'}
        assert {'Sortino','Calmar','월간승률','누적수익률'} <= set(metrics.columns)
        manifest = json.loads((out/'chat_manifest_CURRENT.json').read_text())
        assert len(manifest['render_order']) == 9 and manifest['template_version'] == 'v2-17'
        assert [x['period'] for x in manifest['render_order']] == ['from_2001']*3+['from_2021']*3+['longest']*3
        stats = pd.read_csv(out/'benchmark_statistics_CURRENT.csv')
        assert len(stats) == 8 and set(stats.strategy) == {'NAV_Gross','NAV_Net'}
        assert manifest['market_calendar'] == 'XKRX'
        assert manifest['calendar_package_version']
        payload_metrics = manifest['chart_payload']['periods']['from_2001']['series']['NAV_Net']['metrics']
        assert {'Sortino','Calmar','monthly_win_rate_pct','cumulative_return_pct'} <= set(payload_metrics)
        json.dumps(manifest, allow_nan=False)
        for label, damaged in [('missing',full.drop(sessions[100])), ('extra',pd.concat([full,full.iloc[:1].set_axis([pd.Timestamp('2000-01-02')])])), ('last',full.drop(sessions[-1]))]:
            damaged.to_csv(src, index_label='Date')
            blocked=td/label
            result = subprocess.run(cmd+['--output-dir',str(blocked)],capture_output=True,text=True)
            assert result.returncode != 0 and 'session mismatch' in result.stderr and not blocked.exists(), result.stderr
        full.to_csv(src,index_label='Date')
        # Reusing an output directory without a benchmark must remove stale stats.
        no_benchmark=cmd[:-2]
        subprocess.run(no_benchmark+['--output-dir',str(out)],check=True,capture_output=True)
        assert not (out/'benchmark_statistics_CURRENT.csv').exists()
        src.write_text('Date,NAV\n2024-01-02,1\n2024-01-03,1.01\n')
        blocked=td/'short'
        result=subprocess.run(no_benchmark+['--output-dir',str(blocked)],capture_output=True,text=True)
        assert result.returncode != 0 and not blocked.exists()
    # DSL passes explicit XKRX and its exact benchmark column into the common CLI.
    spec=load_strategy_spec(ROOT/'config/strategies/super_value_dart_benchmark_dsl.json')
    with patch('strategy_dsl_runner.subprocess.run') as call:
        run_current_postprocess(spec,ROOT,Path('/tmp/not-written'),full)
        args=call.call_args.args[0]
        assert args[args.index('--market-calendar')+1]=='XKRX'
        assert args[args.index('--benchmark-series')+1]=='NAV_Benchmark'
    print('CANONICAL PERFORMANCE: PASS (synthetic formulas/report; no investment claims)')


if __name__ == '__main__':
    main()
