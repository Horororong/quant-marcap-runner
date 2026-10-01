from __future__ import annotations

"""Independent share/cash accounting oracle; every cash fixture is synthetic.

Actual Jeisys evidence is tested as an unresolved payment gap, never a payment
fixture. No synthetic NAV in this file is an investment backtest.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import numpy as np
import pandas as pd

from cash_share_exchange import validate_cash_exchanges
from corporate_action_registry import load_corporate_actions
from strategy_dsl_runner import load_project_engine, execute_daily_nav, save_cash_exchange_audits, run_strategy
from strategy_dsl_deciles import DECILE_LABELS, execute_decile_nav
from test_strategy_dsl_deciles import make_spec

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    dates = pd.bdate_range('2024-01-02', periods=9)
    prices = pd.DataFrame({'000001': [100.] * 4 + [np.nan] * 5,
                           '000002': [100., 100., 110., 120., 90., 100., 105., 115., 120.]}, index=dates)
    volumes = pd.DataFrame(1000., index=dates, columns=prices.columns)
    volumes.loc[dates[2:4], '000001'] = 0
    volumes.loc[dates[4:], '000001'] = np.nan
    mask = prices.notna() & volumes.gt(0)
    reference = prices.pct_change(fill_method=None).fillna(0)
    targets = pd.DataFrame([[.6, .2], [0., .2], [0., 1.]], columns=prices.columns,
                           index=[dates[0], dates[3], dates[5]])
    events = pd.DataFrame([dict(event_date=dates[3], event_type='cash_share_exchange',
                               predecessor_code='000001', successor_code='', share_ratio=0., cash_per_share=120.,
                               source='https://example.org/synthetic-entitlement', payment_date=dates[6],
                               payment_status='verified_actual', payment_source='https://example.org/synthetic-payment')])
    return dates, prices, volumes, mask, reference, targets, events


def fail(fn, fragment):
    try:
        fn()
    except (ValueError, RuntimeError, KeyError) as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError(f'expected rejection: {fragment}')


def ledger(prices, targets, events, commission, sell_tax):
    """Dollar/quantity ledger, independent of return/drift engine equations.

    Existing fixed-bps target-weight convention: compute cost on pre-cost NAV
    trades, deduct it, allocate target stock weights on remaining NAV. Fixed
    receivables are not proportionately reduced by this trading expense.
    """
    shares = {c: 0. for c in prices}
    cash, claims = 10000., []
    rows, balances = [], []
    schedule = {prices.index[prices.index.get_loc(sig) + 1]: target
                for sig, target in targets.iterrows()}
    for date, px in prices.iterrows():
        for _, event in events.loc[events.event_date.eq(date)].iterrows():
            code = event.predecessor_code
            claims.append([event.payment_date, shares[code] * event.cash_per_share])
            shares[code] = 0.
        for claim in claims:
            if claim[0] <= date:
                cash += claim[1]
                claim[1] = 0.
        holding_value = {c: shares[c] * float(px[c]) if shares[c] else 0. for c in prices}
        pending = sum(c[1] for c in claims)
        value = cash + sum(holding_value.values()) + pending
        if date in schedule:
            target = schedule[date]
            desired = {c: float(target[c]) * value for c in prices}
            buys = sum(max(desired[c] - holding_value[c], 0) for c in prices)
            sells = sum(max(holding_value[c] - desired[c], 0) for c in prices)
            value -= buys * commission + sells * (commission + sell_tax)
            cash = value * (1 - float(target.sum())) - pending
            assert cash >= -1e-8
            for c in prices:
                shares[c] = float(target[c]) * value / float(px[c]) if target[c] else 0.
        rows.append(value / 10000.)
        balances.append((cash / value, pending / value))
    return np.array(rows), np.array(balances)


def main():
    engine = load_project_engine(ROOT)
    d, px, vol, mask, ref, tw, events = fixture()
    def run(**overrides):
        kw = dict(close_prices=px, target_weights=tw, tradable_mask=mask,
                  source_volumes=vol, reference_returns=ref, corporate_action_events=events,
                  initial_capital=10000., cost_assumptions=engine.TradingCostAssumptions(commission_bps=100, sell_tax_bps=200))
        kw.update(overrides)
        return engine.simulate_target_weight_portfolio(**kw)
    out = run()
    for book, commission, tax, weight_key in [('Gross', 0., 0., 'weights'), ('Net', .01, .02, 'net_weights')]:
        expected, balances = ledger(px, tw, events, commission, tax)
        np.testing.assert_allclose(out['daily_nav'][book], expected, rtol=0, atol=1e-12)
        np.testing.assert_allclose(out[weight_key][['Cash', 'CashReceivable']], balances, rtol=0, atol=1e-12)
        np.testing.assert_allclose(out[weight_key].sum(axis=1), 1., rtol=0, atol=1e-12)
    entitlement = out['cash_entitlements'].iloc[0]
    assert entitlement.gross_amount == 7200.
    assert abs(entitlement.net_amount - 7142.4) < 1e-9
    assert len(out['cash_payments']) == 1 and out['cash_payments'].iloc[0].processing_date == d[6]
    assert out['trades'].loc[d[3], ['buy_turnover', 'sell_turnover', 'cost_fraction']].eq(0).all()
    # Separate gross/net receivables stay fixed through B's changing price and costs.
    for key, amount, nav in [('weights', 7200., 'Gross'), ('net_weights', 7142.4, 'Net')]:
        np.testing.assert_allclose(out[key].loc[d[3:6], 'CashReceivable'] * out['daily_nav'].loc[d[3:6], nav] * 10000., amount, atol=1e-9)
    one = tw.iloc[:1].copy(); one.iloc[0] = [1., 0.]
    pure = run(target_weights=one, cost_assumptions=engine.TradingCostAssumptions())
    assert pure['daily_nav'].loc[d[3]:, 'Gross'].eq(1.2).all()  # receipt is not a second gain
    assert pure['weights'].loc[d[3:6], 'Cash'].eq(0).all()
    assert pure['weights'].loc[d[3:6], 'CashReceivable'].eq(1).all()
    assert pure['weights'].loc[d[6]:, 'Cash'].eq(1).all()
    partial = run(close_prices=px.iloc[:6], source_volumes=vol.iloc[:6], tradable_mask=mask.iloc[:6], reference_returns=ref.iloc[:6], target_weights=tw.iloc[:2])
    assert partial['cash_payments'].empty and partial['weights'].iloc[-1].CashReceivable > 0
    early = tw.copy(); early.index = [d[0], d[3], d[4]]
    fail(lambda: run(target_weights=early), 'insufficient settled cash')
    tight = tw.iloc[:2].copy()
    tight.loc[d[3], '000002'] = 1 - float(out['weights'].loc[d[4], 'CashReceivable'])
    fail(lambda: run(target_weights=tight), 'insufficient settled cash after costs')
    mixed = events.copy()
    mixed['event_type'] = 'stock_merger'; mixed['successor_code'] = '000002'; mixed['share_ratio'] = 1.
    fail(lambda: run(corporate_action_events=mixed), 'mixed stock/cash merger is unsupported')
    same_day = events.copy(); same_day.payment_date = d[3]
    paid = run(corporate_action_events=same_day, target_weights=one, cost_assumptions=engine.TradingCostAssumptions())
    assert paid['cash_payments'].iloc[0].processing_date == d[3]
    assert paid['weights'].loc[d[3], 'Cash'] == 1. and paid['daily_nav'].loc[d[3], 'Gross'] == 1.2
    fail(lambda: run(execution_assumptions=engine.ExecutionAssumptions(allow_short=True)), 'long-only execution')
    # Legacy explicit leverage without cash events retains its separate contract.
    levered = pd.DataFrame([[0., 1.5]], columns=px.columns, index=[d[0]])
    assert not run(target_weights=levered, corporate_action_events=None, execution_assumptions=engine.ExecutionAssumptions(allow_short=True, max_gross_exposure=2.))['daily_nav'].empty
    fail(lambda: run(source_volumes=None), 'source volumes')
    for col, value in [('payment_status', 'planned'), ('payment_date', pd.NaT), ('payment_date', d[2]), ('payment_source', ''), ('successor_code', '000002'), ('share_ratio', 1.)]:
        bad = events.copy(); bad[col] = value
        fail(lambda: run(corporate_action_events=bad), 'cash exchange')
    fail(lambda: run(corporate_action_events=events.drop(columns=['payment_date'])), 'payment metadata')
    for source, col, date, value in [(vol, '000001', d[2], np.nan), (px, '000001', d[2], np.nan), (ref, '000001', d[2], .01)]:
        bad = source.copy(); bad.at[date, col] = value
        key = 'source_volumes' if source is vol else ('close_prices' if source is px else 'reference_returns')
        fail(lambda: run(**{key: bad}), 'suspension requires observed')
    bad = ref.copy(); bad.at[d[4], '000002'] += .01
    fail(lambda: run(reference_returns=bad), 'held-return reference check failed')
    repurchase = tw.copy(); repurchase.loc[d[5]] = [.1, .1]
    fail(lambda: run(target_weights=repurchase), 'cannot be repurchased')
    weekend = events.copy(); weekend.payment_date = pd.Timestamp('2024-01-06')
    settled = run(corporate_action_events=weekend, target_weights=tw.iloc[:2])
    assert settled['cash_payments'].iloc[0].processing_date == d[4]
    # Multiple claims: a second held security retires before either receipt.
    multi_px = pd.DataFrame(100., index=d, columns=['000001', '000002'])
    multi_vol = pd.DataFrame(1000., index=d, columns=multi_px.columns)
    multi_vol.loc[d[2]:, '000001'] = 0.; multi_vol.loc[d[3]:, '000002'] = 0.
    second = events.iloc[0].to_dict(); second.update(predecessor_code='000002', event_date=d[4], cash_per_share=80., payment_date=d[7])
    multi = run(close_prices=multi_px, source_volumes=multi_vol, tradable_mask=multi_vol.gt(0),
                reference_returns=multi_px * 0, target_weights=pd.DataFrame([[.5, .5]], columns=multi_px.columns, index=[d[0]]),
                corporate_action_events=pd.concat([events, pd.DataFrame([second])]), cost_assumptions=engine.TradingCostAssumptions())
    np.testing.assert_allclose(multi['daily_nav'].Gross, [1, 1, 1, 1.1, 1, 1, 1, 1, 1], atol=1e-12)
    assert len(multi['cash_entitlements']) == len(multi['cash_payments']) == 2
    assert abs(multi['weights'].loc[d[6], 'CashReceivable'] - .4) < 1e-12
    # Public common cost wrapper: Gross independent of scenario, audit files.
    wrapped = execute_daily_nav(engine, px, tw, {'zero': engine.TradingCostAssumptions(), 'cost': engine.TradingCostAssumptions(commission_bps=100, sell_tax_bps=200)}, engine.ExecutionAssumptions(), 10000., mask, events, ref, vol)
    with TemporaryDirectory() as tmp:
        save_cash_exchange_audits(wrapped, Path(tmp))
        assert len(pd.read_csv(Path(tmp) / 'cash_entitlements.csv')) == 2
        assert len(pd.read_csv(Path(tmp) / 'cash_payments.csv')) == 2
        assert (Path(tmp) / 'cash_balances_net_cost.csv').exists()
        save_cash_exchange_audits({'execution_scenarios': {'partial': partial}}, Path(tmp))
        assert not (Path(tmp) / 'cash_payments.csv').exists()
        assert not (Path(tmp) / 'cash_balances_net_cost.csv').exists()
        assert (Path(tmp) / 'cash_balances_net_partial.csv').exists()
        config = Path(tmp) / 'config'; config.mkdir()
        events.to_csv(config / 'kr_corporate_actions.csv', index=False)
        loaded = load_corporate_actions(tmp)
        assert loaded.iloc[0].successor_code == ''
        mixed.to_csv(config / 'kr_corporate_actions.csv', index=False)
        fail(lambda: load_corporate_actions(tmp), 'mixed stock/cash merger is unsupported')
        planned = events.copy(); planned.payment_status = 'planned'
        planned.to_csv(config / 'kr_corporate_actions.csv', index=False)
        fail(lambda: load_corporate_actions(tmp), 'planned dates are forbidden')
    panel = px.rename_axis('Date').reset_index().melt(id_vars='Date', var_name='Code', value_name='Close')
    panel = panel.merge(vol.rename_axis('Date').reset_index().melt(id_vars='Date', var_name='Code', value_name='Volume'), on=['Date', 'Code'])
    buckets = {label: tw.copy() for label in DECILE_LABELS}
    result = execute_decile_nav(panel, make_spec(), buckets, engine, events, ref)
    for label in DECILE_LABELS:
        assert len(result['decile_results'][label]['execution_scenarios']['zero']['cash_payments']) == 1
    # Actual case has evidenced entitlement and only a planned payment date.
    # Delisting confirmation is deliberately not treated as a payment receipt.
    actual = json.loads((ROOT / 'docs/audits/jeisys-cash-exchange/evidence.json').read_text())
    assert actual['actual_payment_status'] == 'unverified'
    actual_event = events.copy(); actual_event['payment_status'] = 'planned'
    actual_event['predecessor_code'] = '287410'
    fail(lambda: validate_cash_exchanges(actual_event), 'planned dates are forbidden')
    assert '287410' not in set(load_corporate_actions(ROOT).predecessor_code)
    # Real source, real signal-day universe: Jeisys is third by Marcap among
    # the 53 KOSDAQ securities whose Sep 30 closes lie in [12000, 14000].
    # No subsequent survival/tradability rule is used to choose these stocks.
    spec = json.loads((ROOT / 'config/strategies/kr_equity_market_segment_research.json').read_text())
    spec['strategy_id'] = 'jeisys_payment_evidence_gap'
    spec['universe']['filters'] = [dict(field='Close', op='gte', value=12000), dict(field='Close', op='lte', value=14000)]
    spec['rebalance']['months'] = [9]
    spec['period'] = dict(start='2024-09-02', end='2024-10-24', book_start='2024-09-02', book_end='2024-10-24', as_of_date='2024-10-24')
    raw = pd.read_parquet(ROOT / 'data/krx_equities/yearly/marcap-2024.parquet')
    signal = raw[raw.Date.eq('2024-09-30') & raw.Market.eq('KOSDAQ') & raw.Volume.gt(0) & raw.Close.between(12000, 14000)]
    ranked = signal.sort_values(['Marcap', 'Code'], ascending=[False, True]).Code.tolist()
    assert len(ranked) == 53 and ranked.index('287410') == 2
    with TemporaryDirectory() as tmp:
        for mode in ('top_n', 'deciles'):
            spec['portfolio'] = dict(selection=mode, weighting='equal')
            if mode == 'top_n':
                spec['portfolio']['number_of_positions'] = 3
            path = Path(tmp) / f'{mode}.json'; path.write_text(json.dumps(spec))
            output = Path(tmp) / mode
            fail(lambda: run_strategy(path, ROOT, output, postprocess=False), 'unresolved corporate action: date=2024-10-23, asset=287410')
            assert not output.exists()  # no partial report for the unresolved event
        # The gap blocks affected holdings, not the entire historical universe.
        spec['portfolio'] = dict(selection='top_n', weighting='equal', number_of_positions=1)
        path = Path(tmp) / 'unaffected.json'; path.write_text(json.dumps(spec))
        safe = run_strategy(path, ROOT, Path(tmp) / 'unaffected', postprocess=False)
        assert safe['engine_result']['daily_nav'].notna().all().all()
    print('CASH EXCHANGE: PASS — independent two-book share/cash oracle, costs, pending liquidity, multiple claims, payment timing, public cost/decile modes and actual evidence gap')


if __name__ == '__main__':
    main()
