"""Independent audit of the predeclared largest-cap long experiment.

Reads original annual rows, not engine event returns/weights/schedules. This
oracle only checks an existing run; it neither executes DSL nor computes metrics.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]


def verify(run, out):
    spec = json.loads((run / 'strategy_normalized.json').read_bytes())
    assert spec['execution']['nontradable_policy'] == 'defer_full_rebalance'
    assert spec['universe']['filters'] == [dict(field='Marcap', op='gte', value=10**13)]
    assert [(f['source'], f['field'], f['direction'], f.get('transform', 'identity')) for f in spec['factors']] == [('krx', 'Marcap', 'high', 'identity')]
    assert spec['portfolio']['number_of_positions'] == 1 and spec['rebalance']['months'] == [4]
    actual = pd.read_csv(run / 'artifacts/daily_nav.csv', index_col='Date', parse_dates=True)
    targets = pd.read_csv(run / 'artifacts/target_weights.csv', index_col=0, parse_dates=True)
    codes = list(targets)
    annual, days, expected_selections = [], [], {}
    for year in range(pd.Timestamp(spec['period']['start']).year, pd.Timestamp(spec['period']['end']).year + 1):
        x = pd.read_parquet(ROOT / f'data/krx_equities/yearly/marcap-{year}.parquet',
                            columns=['Date', 'Code', 'Market', 'Marcap', 'Close', 'Volume'])
        x['Code'] = x.Code.astype(str).str.zfill(6)
        x = x[x.Date.between(spec['period']['start'], spec['period']['end'])]
        x = x[x.Market.astype(str).replace({'KOSDAQ GLOBAL': 'KOSDAQ'}).isin(spec['universe']['markets'])]
        days.extend(x.Date.unique())
        signal = x.loc[x.Date.dt.month.eq(4), 'Date'].max()
        cross = x[x.Date.eq(signal) & x.Marcap.ge(10**13) & x.Volume.gt(0) & x.Close.gt(0)]
        ranked = cross.sort_values(['Marcap', 'Code'], ascending=[False, True])
        assert len(ranked), ('empty original population', signal)
        expected_selections[signal] = ranked.iloc[0].Code
        annual.append(x[x.Code.isin(codes)][['Date', 'Code', 'Close', 'Volume']].copy())
        del x
    dates = pd.DatetimeIndex(days).unique().sort_values()
    # Compare exact instants after explicit storage-unit normalization; CSV
    # parses microseconds while original parquet uses nanoseconds in pandas3.
    pd.testing.assert_index_equal(actual.index.as_unit('ns'), dates.rename('Date').as_unit('ns'))
    assert list(targets.index) == list(expected_selections)
    for date, code in expected_selections.items():
        assert targets.loc[date, code] == 1. and targets.loc[date].drop(code).eq(0).all()
    panel = pd.concat(annual)
    px = panel.pivot(index='Date', columns='Code', values='Close').reindex(index=dates, columns=codes)
    volume = panel.pivot(index='Date', columns='Code', values='Volume').reindex_like(px)
    manifest = json.loads((Path(__file__).parent / 'source_manifest.json').read_bytes())
    body = Path(__file__).parent / 'evidence/20180503000318_body.html'
    pin = next(x for x in manifest['responses'] if x['file'] == body.name)
    assert hashlib.sha256(body.read_bytes()).hexdigest() == pin['sha256']
    text = body.read_bytes().decode('utf-8')
    for token in ['128,386,494', '6,419,324,700', '2018년05월04일', 'A005930']:
        assert token in text
    lag = spec['execution']['lag_sessions']
    arrivals = {dates[dates.get_loc(s) + lag]: (s, c) for s, c in expected_selections.items()}
    records, order_records = [], []
    for book, costs in [('Gross', {})] + [('Net_' + k, v) for k, v in spec['cost_scenarios'].items()]:
        shares = dict.fromkeys(codes, 0.)
        cash = float(spec['initial_capital'])
        pending = None
        for date in dates:
            # Evidence-derived share quantity; never use engine event_return.
            if date == pd.Timestamp('2018-05-04'):
                shares['005930'] *= 50
            if date in arrivals:
                assert pending is None, ('independent conflicting order', date)
                signal, target = arrivals[date]
                pending = dict(signal=signal, planned=date, target=target)
            held = {c for c, q in shares.items() if q}
            assert all(pd.notna(px.at[date, c]) and px.at[date, c] > 0 for c in held)
            value = cash + sum(shares[c] * px.at[date, c] for c in held)
            fee = 0.
            if pending is not None:
                required = held | {pending['target']}
                liquid = all(pd.notna(px.at[date, c]) and px.at[date, c] > 0 and pd.notna(volume.at[date, c]) and volume.at[date, c] > 0 for c in required)
                if liquid:
                    target = pending['target']
                    current = shares[target] * px.at[date, target]
                    buys = max(value - current, 0.)
                    sells = sum(shares[c] * px.at[date, c] for c in held if c != target)
                    common = sum(costs.get(k, 0.) for k in ['commission_bps', 'spread_bps', 'slippage_bps', 'market_impact_bps']) / 10000
                    fee = buys * common + sells * (common + costs.get('sell_tax_bps', 0.) / 10000)
                    new_quantity = (value - fee) / px.at[date, target]
                    cash += sells - (new_quantity - shares[target]) * px.at[date, target] - fee
                    shares = dict.fromkeys(codes, 0.)
                    shares[target] = new_quantity
                    value = cash + new_quantity * px.at[date, target]
                    order_records.append(dict(book=book, signal_date=str(pending['signal'].date()),
                                              planned_execution_date=str(pending['planned'].date()), execution_date=str(date.date()), security=target))
                    pending = None
            expected = float(actual.at[date, 'NAV_' + book]) * spec['initial_capital']
            error = abs(expected - value)
            assert error <= 1e-5, (date, book, value, expected, error)
            assert cash >= -1e-5, (date, book, cash)
            records.append(dict(Date=str(date.date()), book=book, quantity_005930=shares.get('005930', 0.),
                                quantity_000660=shares.get('000660', 0.), cash=cash, trading_cost=fee,
                                independent_value=value, engine_value=expected, absolute_error=error))
        assert pending is None
    audit = pd.read_csv(run / 'artifacts/execution_schedule.csv')
    independent = pd.DataFrame(order_records)
    for cost_name in spec['cost_scenarios']:
        a = audit[audit.cost_scenario.eq(cost_name)]
        b = independent[independent.book.eq('Net_' + cost_name)]
        for col in ['signal_date', 'planned_execution_date', 'execution_date']:
            assert a[col].tolist() == b[col].tolist(), (cost_name, col)
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(records).to_csv(out / 'independent_daily_ledger.csv', index=False)
    independent.to_csv(out / 'independent_orders.csv', index=False)
    result = dict(status='PASS_INDEPENDENT_FULL_REQUESTED_RESEARCH_LEDGER', sessions=len(dates), rows=len(records),
                  max_nav_error=max(r['absolute_error'] for r in records), numerical_tolerance_currency=1e-5,
                  source_selection_exact=True, independent_order_dates_exact=True, investment_approved=False,
                  scope='Predeclared deferred-close price/cap research, not original fixed-lag, cash-dividend total return, brokerage account or investment PIT certification')
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    verify(a.run, a.output)
