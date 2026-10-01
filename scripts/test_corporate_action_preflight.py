from __future__ import annotations

"""Known-event planning gate: timing/lineage and actual KRX public modes."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import subprocess
import sys
import pandas as pd

from corporate_action_preflight import trace_planned_exposures
from strategy_dsl_preflight import preflight_strategy, exit_code_for
from strategy_dsl_runner import load_project_engine, run_strategy

ROOT = Path(__file__).resolve().parents[1]


def temporal_cases(engine):
    dates = pd.to_datetime(['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-08'])
    gap = pd.DataFrame([dict(event_date=dates[2], predecessor_code='000001', reason='unverified actual payment', evidence='synthetic')])
    empty = pd.DataFrame()
    buy = pd.DataFrame({'000001': [1.]}, index=[dates[0]])
    execution = engine.ExecutionAssumptions()
    rows, count = trace_planned_exposures({'top_n': buy}, dates, gap, empty, engine, execution)
    assert count == 1 and len(rows) == 1
    assert rows[0]['check_date'] == '2024-01-04' and rows[0]['phase'] == 'prior_holding_before_close'
    # Event-day closing sell does not remove the earlier holding's entitlement.
    sold = pd.DataFrame({'000001': [1., 0.]}, index=dates[:2])
    rows, _ = trace_planned_exposures({'top_n': sold}, dates, gap, empty, engine, execution)
    assert len(rows) == 1 and rows[0]['phase'] == 'prior_holding_before_close'
    later = gap.copy(); later.event_date = dates[3]
    assert not trace_planned_exposures({'top_n': sold}, dates, later, empty, engine, execution)[0]
    # A later execution lag can cause a first attempted purchase on the event day.
    rows, _ = trace_planned_exposures({'D03': buy}, dates, gap, empty, engine, engine.ExecutionAssumptions(execution_lag_sessions=2))
    assert rows[0]['phase'] == 'target_at_close' and rows[0]['portfolio'] == 'D03'
    # First signal on the final session never executes beyond the window.
    end_only = pd.DataFrame({'000001': [1.]}, index=[dates[-1]])
    try:trace_planned_exposures({'top_n': end_only}, dates, gap, empty, engine, execution)
    except ValueError as exc:assert '체결일 데이터가 없습니다' in str(exc)
    else:raise AssertionError('missing lag session must not extend the window')
    # Known gaps remain applicable when legal conversion predates the run.
    past = gap.copy(); past.event_date = pd.Timestamp('2024-01-01')
    rows, _ = trace_planned_exposures({'top_n': buy}, dates, past, empty, engine, execution)
    assert rows[0]['check_date'] == '2024-01-03' and rows[0]['phase'] == 'target_at_close'
    # Verified stock succession preserves original selection lineage.
    events = pd.DataFrame([dict(event_date=dates[2], event_type='stock_merger', predecessor_code='000001', successor_code='000002')])
    successor_gap = later.copy(); successor_gap.predecessor_code = '000002'
    rows, _ = trace_planned_exposures({'D01': buy}, dates, successor_gap, events, engine, execution)
    assert rows[0]['Code'] == '000002' and rows[0]['origin_selected_codes'] == ['000001']
    assert rows[0]['origin_signal_dates'] == ['2024-01-02']
    # A verified earlier cash disposal removes stock exposure; no cash is valued.
    cash = events.copy(); cash.event_type = 'cash_share_exchange'; cash.successor_code = ''
    assert not trace_planned_exposures({'D01': buy}, dates, later, cash, engine, execution)[0]
    unheld = buy.copy(); unheld['000001'] = 0.
    assert not trace_planned_exposures({'D10': unheld}, dates, gap, empty, engine, execution)[0]
    # Independent engine oracle confirms the before-close event-day ordering.
    prices = pd.DataFrame(100., index=dates, columns=['000001'])
    for target, event_gap, should_fail in [(buy, gap, True), (sold, gap, True), (sold, later, False)]:
        try:
            engine.simulate_target_weight_portfolio(prices, target, corporate_action_gaps=event_gap)
        except RuntimeError as exc:
            assert should_fail and 'unresolved corporate action' in str(exc)
        else:
            assert not should_fail


def real_modes(engine):
    spec = json.loads((ROOT / 'config/strategies/kr_equity_market_segment_research.json').read_text())
    spec['strategy_id'] = 'jeisys_known_event_preflight'
    spec['universe']['filters'] = [dict(field='Close', op='gte', value=12000), dict(field='Close', op='lte', value=14000)]
    spec['rebalance']['months'] = [9]
    spec['period'] = dict(start='2024-09-02', end='2024-10-24', book_start='2024-09-02', book_end='2024-10-24', as_of_date='2024-10-24')
    raw = pd.read_parquet(ROOT / 'data/krx_equities/yearly/marcap-2024.parquet')
    signal = raw[raw.Date.eq('2024-09-30') & raw.Market.eq('KOSDAQ') & raw.Volume.gt(0) & raw.Close.between(12000, 14000)]
    ranked = signal.sort_values(['Marcap', 'Code'], ascending=[False, True]).Code.tolist()
    assert len(ranked) == 53 and ranked.index('287410') == 2
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for mode in ('top_n', 'deciles'):
            spec['portfolio'] = dict(selection=mode, weighting='equal')
            if mode == 'top_n':spec['portfolio']['number_of_positions'] = 3
            path = tmp / f'{mode}.json';path.write_text(json.dumps(spec))
            # No NAV function is called, including the engine referenced by preflight.
            with patch('strategy_dsl_preflight.load_project_engine', return_value=engine), patch.object(engine, 'simulate_target_weight_portfolio', side_effect=AssertionError('preflight must not calculate NAV')):
                result = preflight_strategy(path, ROOT)
            assert result['preflight_contract_version'] == '3'
            assert result['status'] == 'data_gap' and result['phase'] == 'corporate_actions'
            assert result['ready_for_execution'] is False and exit_code_for(result) == 3
            exposure = result['corporate_action_audit']['exposures']
            assert len(exposure) == 1 and exposure[0]['Code'] == '287410'
            assert exposure[0]['portfolio'] == ('D01' if mode == 'deciles' else 'top_n')
            assert exposure[0]['event_date'] == exposure[0]['check_date'] == '2024-10-23'
            assert exposure[0]['origin_signal_dates'] == ['2024-09-30']
            # The public runner's existing holding guard rejects the same event.
            output = tmp / mode
            try:run_strategy(path, ROOT, output, postprocess=False)
            except RuntimeError as exc:assert 'unresolved corporate action: date=2024-10-23, asset=287410' in str(exc)
            else:raise AssertionError('runner accepted a known unresolved event')
            assert not output.exists()
            cli = subprocess.run([sys.executable, str(ROOT / 'scripts/strategy_dsl_preflight.py'), str(path)], capture_output=True, text=True)
            assert cli.returncode == 3 and json.loads(cli.stdout)['status'] == 'data_gap', cli.stderr
        # The same full historical signal universe can be safe with a different
        # explicit top_n; no future-survival or global code exclusion is applied.
        spec['portfolio'] = dict(selection='top_n', weighting='equal', number_of_positions=1)
        path = tmp / 'unaffected.json';path.write_text(json.dumps(spec))
        with patch('strategy_dsl_preflight.load_project_engine', return_value=engine), patch.object(engine, 'simulate_target_weight_portfolio', side_effect=AssertionError('no NAV')):
            result = preflight_strategy(path, ROOT)
        assert result['status'] == 'ok' and result['ready_for_execution']
        assert result['corporate_action_audit']['selection_performed']
        assert not result['corporate_action_audit']['exposures']
        assert result['corporate_action_audit']['executed_target_count'] == 1
        safe = run_strategy(path, ROOT, tmp / 'unaffected', postprocess=False)
        assert safe['engine_result']['daily_nav'].notna().all().all()
        # A window ending before entitlement retains its source-only fast path.
        spec['period']['end'] = spec['period']['book_end'] = spec['period']['as_of_date'] = '2024-10-18'
        path = tmp / 'earlier.json';path.write_text(json.dumps(spec))
        with patch('strategy_dsl_runner.build_target_weights_from_panel', side_effect=AssertionError('unnecessary selection')):
            result = preflight_strategy(path, ROOT)
        assert result['status'] == 'ok' and not result['corporate_action_audit']['selection_performed']


def main():
    engine = load_project_engine(ROOT)
    temporal_cases(engine)
    real_modes(engine)
    print('KNOWN CORPORATE-ACTION PREFLIGHT: PASS — real top_n/decile selection, exact lag, event-day order, successor lineage, source-only fast path and no NAV')


if __name__ == '__main__':main()
