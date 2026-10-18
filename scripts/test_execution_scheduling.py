"""Synthetic close-order boundaries and independent quantity/cash accounting."""
import unittest
from pathlib import Path
import pandas as pd
from strategy_dsl_runner import load_project_engine
from execution_scheduling import resolve_deferred_schedule

ROOT = Path(__file__).resolve().parents[1]


class Scheduling(unittest.TestCase):
    def fixture(self):
        d = pd.bdate_range('2024-01-02', periods=7)
        p = pd.DataFrame({'000001': [100., 100., 100., 100., 50., 55., 60.],
                          '000002': [100., 100., 100., 100., 100., 110., 120.]}, index=d)
        mask = pd.DataFrame(True, index=d, columns=p.columns)
        mask.loc[d[2:4], '000001'] = False
        w = pd.DataFrame({'000001': [1., 0.], '000002': [0., 1.]}, index=d[[0, 2]])
        e = load_project_engine(ROOT)
        event = pd.DataFrame([dict(event_date=d[4], event_type='stock_split', predecessor_code='000001',
                                  successor_code='000001', share_ratio=2., cash_per_share=0., source='synthetic')])
        r = p.pct_change(fill_method=None)
        r.loc[d[4], '000001'] = 0.
        return e, d, p, mask, w, event, r

    def runbook(self, policy='defer_full_rebalance', **patch):
        e, d, p, mask, w, event, ref = self.fixture()
        kw = dict(close_prices=p, target_weights=w, initial_capital=10000., tradable_mask=mask,
                  corporate_action_events=event, reference_returns=ref,
                  cost_assumptions=e.TradingCostAssumptions(commission_bps=10., sell_tax_bps=20.),
                  execution_assumptions=e.ExecutionAssumptions(nontradable_policy=policy))
        kw.update(patch)
        return e.simulate_target_weight_portfolio(**kw)

    def test_delayed_split_sale_independent_gross_net_quantity_cash(self):
        _, d, _, _, _, _, _ = self.fixture()
        out = self.runbook()
        # First buy100 shares; split produces200. Both lots are sold only on
        # the first liquid session. Net has99.9 original shares, then199.8.
        for day, gross, net in [(d[1], 10000., 9990.), (d[3], 10000., 9990.),
                                (d[4], 10000., 9990. * (1 - .004)),
                                (d[5], 11000., 9990. * (1 - .004) * 1.1),
                                (d[6], 12000., 9990. * (1 - .004) * 1.2)]:
            self.assertAlmostEqual(out['daily_nav'].at[day, 'Gross'] * 10000, gross, places=7)
            self.assertAlmostEqual(out['daily_nav'].at[day, 'Net'] * 10000, net, places=7)
        audit = out['execution_schedule'].iloc[1]
        self.assertEqual(audit.planned_execution_date, d[3])
        self.assertEqual(audit.execution_date, d[4])
        self.assertEqual(audit.deferred_sessions, 1)
        self.assertEqual(out['trades'].at[d[3], 'cost_fraction'], 0.)

    def test_default_reject_retains_original_halt_failure(self):
        with self.assertRaises((ValueError, RuntimeError, AssertionError)):
            self.runbook(policy='reject')

    def test_unfilled_end_and_overlap_fail_instead_of_dropping(self):
        e, d, p, mask, w, _, _ = self.fixture()
        base = e._schedule_signal_execution_dates(d, w.index, 1)
        mask.loc[d[3]:, '000001'] = False
        with self.assertRaisesRegex(ValueError, 'pending_order_at_requested_end'):
            resolve_deferred_schedule(base, w, p, mask)
        w.loc[d[4]] = [1., 0.]
        base = e._schedule_signal_execution_dates(d, w.index, 1)
        with self.assertRaisesRegex(ValueError, 'pending_order_conflict'):
            resolve_deferred_schedule(base, w, p, mask)

    def test_no_missing_hold_price_fill_or_ordinary_return_waiver(self):
        _, d, p, _, _, _, ref = self.fixture()
        p.loc[d[3], '000001'] = float('nan')
        with self.assertRaises((ValueError, RuntimeError, AssertionError)):
            self.runbook(close_prices=p, corporate_action_events=pd.DataFrame())
        ref.loc[d[2], '000001'] = .05
        with self.assertRaisesRegex(RuntimeError, 'held-return reference'):
            self.runbook(reference_returns=ref)

    def test_unobserved_liquidity_shorts_and_illiquid_action_books_rejected(self):
        e, d, p, mask, w, event, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'tradable mask'):
            self.runbook(tradable_mask=None)
        with self.assertRaisesRegex(ValueError, 'long-only'):
            e.ExecutionAssumptions(nontradable_policy='defer_full_rebalance', allow_short=True)
        event['event_type'] = 'cash_share_exchange'
        with self.assertRaisesRegex(ValueError, 'split/no-action'):
            self.runbook(corporate_action_events=event)

    def test_no_early_fill_and_entire_order_waits_for_target(self):
        e, d, p, mask, w, _, _ = self.fixture()
        mask.loc[d[4], '000002'] = False
        out, audit = resolve_deferred_schedule(e._schedule_signal_execution_dates(d, w.index, 1), w, p, mask)
        self.assertEqual(out[d[0]], d[1])
        self.assertEqual(out[d[2]], d[5])
        self.assertEqual(audit[1]['deferred_sessions'], 2)

    def test_all_ten_deciles_use_same_deferred_engine_and_cost_owner(self):
        import json
        from strategy_dsl import StrategySpec
        from strategy_dsl_deciles import execute_decile_nav, DECILE_LABELS
        from strategy_dsl_runner import return_reference_matrix
        e, d, _, _, _, _, _ = self.fixture()
        raw = json.loads((ROOT / 'config/strategies/research_size_deciles_2019_2020_v1.json').read_bytes())
        raw.pop('research')
        raw['execution']['nontradable_policy'] = 'defer_full_rebalance'
        raw['cost_scenarios'] = {'fixed': {'commission_bps': 10., 'sell_tax_bps': 20.}}
        raw['initial_capital'] = 10000.
        raw['period'] = dict(start=str(d[0].date()), end=str(d[-1].date()), book_start=str(d[0].date()),
                             book_end=str(d[-1].date()), as_of_date=str(d[-1].date()))
        spec = StrategySpec.from_dict(raw)
        rows, events, targets = [], [], {}
        for i, label in enumerate(DECILE_LABELS):
            old, new = f'{100001 + 2*i:06d}', f'{100002 + 2*i:06d}'
            targets[label] = pd.DataFrame({old: [1., 0.], new: [0., 1.]}, index=d[[0, 2]])
            events.append(dict(event_date=d[4], event_type='stock_split', predecessor_code=old,
                               successor_code=old, share_ratio=2., cash_per_share=0., source='synthetic'))
            for n, day in enumerate(d):
                rows.append(dict(Date=day, Code=old, Close=[100., 100., 100., 100., 50., 55., 60.][n],
                                 Volume=0. if n in [2, 3] else 10., ChangesRatio=0. if n < 5 else (10. if n == 5 else (60/55-1)*100)))
                rows.append(dict(Date=day, Code=new, Close=[100., 100., 100., 100., 100., 110., 120.][n],
                                 Volume=10., ChangesRatio=0. if n < 5 else (10. if n == 5 else (120/110-1)*100)))
        panel = pd.DataFrame(rows)
        result = execute_decile_nav(panel, spec, targets, e, pd.DataFrame(events),
                                    return_reference_matrix(panel, sorted(panel.Code.unique())))
        for label in DECILE_LABELS:
            self.assertAlmostEqual(result['daily_nav'].at[d[-1], f'NAV_{label}_Gross'] * 10000, 12000., places=7)
            self.assertAlmostEqual(result['daily_nav'].at[d[-1], f'NAV_{label}_Net_fixed'] * 10000, 9990. * .996 * 1.2, places=7)
            execution = result['decile_results'][label]['execution_scenarios']['fixed']
            self.assertEqual(execution['execution_schedule'].iloc[1].execution_date, d[4])


if __name__ == '__main__':
    unittest.main(verbosity=2)
