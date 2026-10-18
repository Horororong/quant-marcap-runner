"""Projection follows full-universe scoring; independent old-builder comparison."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from annual_selected_preparation import prepare_annual_selected
from strategy_dsl import StrategySpec
from strategy_dsl_runner import build_target_weights_from_panel, required_panel_columns
from strategy_dsl_deciles import build_decile_target_weights_from_panel

ROOT = Path(__file__).resolve().parents[1]


class Preparation(unittest.TestCase):
    def fixture(self, root, deciles=False):
        raw = json.loads((ROOT / 'config/strategies/research_size_top1_2019_2025.json').read_bytes())
        raw.pop('research')
        raw['period'] = dict(start='2019-01-01', end='2020-12-31', book_start='2019-01-01', book_end='2020-12-31', as_of_date='2020-12-31')
        raw['execution']['data_loading'] = 'annual_selected_projection'
        if deciles:
            raw['portfolio'] = dict(selection='deciles', weighting='equal')
        spec = StrategySpec.from_dict(raw)
        rows = []
        for year in [2019, 2020]:
            p = root / f'data/krx_equities/yearly/marcap-{year}.parquet'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f'explicit synthetic fixture{year}'.encode())
            for date in pd.to_datetime([f'{year}-04-29', f'{year}-04-30', f'{year}-05-02']):
                for i in range(1, 13):
                    # Every row participates before projection. Last code
                    # fails original cap filter; top code changes with year.
                    cap = (i if year == 2019 else 13 - i) * 1e13 if i < 12 else 1.
                    rows.append(dict(Date=date, Code=f'{i:06d}', Name=f'fixture{i}', Market='KOSPI' if i % 2 else 'KOSDAQ',
                                     Close=100., Volume=100., Amount=10000., Marcap=cap, ChangesRatio=0.))
        return spec, pd.DataFrame(rows).loc[:, required_panel_columns(spec)]

    def prepare(self, spec, panel, root):
        class Engine:
            def load_krx_equity_panel(self, start, end, markets, columns, repo_root):
                return panel.loc[panel.Date.between(start, end), columns].copy()
        def coverage(frame, start, end, markets):
            # Source audit must see BOTH markets and all12 historical codes,
            # including filtered/nonselected rows; projected audits would fail.
            self.assertEqual(set(frame.Code), {f'{i:06d}' for i in range(1, 13)})
            self.assertEqual(set(frame.Market), {'KOSPI', 'KOSDAQ'})
            return dict(status='complete')
        with patch('krx_history_audit.require_session_coverage', side_effect=coverage), \
             patch('corporate_action_registry.load_corporate_actions', return_value=pd.DataFrame()):
            return prepare_annual_selected(spec, root, Engine())

    def test_full_source_top_n_matches_old_builder_then_projects_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, panel = self.fixture(root)
            expected, selections = build_target_weights_from_panel(panel, spec, root)
            got = self.prepare(spec, panel, root)
            pd.testing.assert_frame_equal(got['selections'], selections)
            pd.testing.assert_frame_equal(got['targets']['top_n'], expected.loc[:, got['targets']['top_n'].columns])
            self.assertEqual(set(got['panel'].Code), {'000001', '000011'})
            self.assertEqual(got['preparation_audit']['source_rows'], 72)
            self.assertEqual(got['preparation_audit']['observation_rows'], 12)
            self.assertEqual(len(got['dates']), 6)

    def test_deciles_use_same_preparation_without_dropping_eligible_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, panel = self.fixture(root, deciles=True)
            expected, membership, audit = build_decile_target_weights_from_panel(panel, spec, root)
            got = self.prepare(spec, panel, root)
            pd.testing.assert_frame_equal(got['selections'], membership)
            pd.testing.assert_frame_equal(got['partition_audit'], audit)
            for label, w in got['targets'].items():
                pd.testing.assert_frame_equal(w, expected[label].loc[:, w.columns])
            self.assertNotIn('000012', set(got['panel'].Code))
            self.assertEqual(set(got['panel'].Code), {f'{i:06d}' for i in range(1, 12)})

    def test_dart_not_silently_moved_around_existing_pit_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, _ = self.fixture(root)
            with patch('factor_registry.external_sources', return_value=['dart']):
                with self.assertRaisesRegex(ValueError, 'original PIT gates'):
                    prepare_annual_selected(spec, root, None)

    def test_korean_execution_contract_is_explicit_and_cannot_change_lag(self):
        from research_workbench import korean_spec
        from test_research_workbench import REQUEST
        baseline = korean_spec(REQUEST).to_dict()
        contract = dict(nontradable_policy='defer_full_rebalance', data_loading='annual_selected_projection')
        after = korean_spec(REQUEST, execution_contract=contract).to_dict()
        self.assertEqual(after['execution'], dict(baseline['execution'], **contract))
        for key in ['universe', 'factors', 'portfolio', 'rebalance', 'cost_scenarios', 'period', 'benchmark']:
            self.assertEqual(after[key], baseline[key])
        with self.assertRaisesRegex(ValueError, 'lag/price remain unchanged'):
            korean_spec(REQUEST, execution_contract={'lag_sessions': 2})

    def test_implicit_legacy_execution_and_fingerprint_preserved(self):
        from strategy_dsl import load_strategy_spec
        spec = load_strategy_spec(ROOT / 'config/strategies/research_size_top1_2019_2025.json')
        self.assertEqual(spec.execution.to_dict(), {'lag_sessions': 1, 'price': 'next_close'})
        raw = spec.to_dict()
        raw['execution']['nontradable_policy'] = 'defer_full_rebalance'
        self.assertNotEqual(StrategySpec.from_dict(raw).fingerprint(), spec.fingerprint())
        for bad in ['skip_security', 'forward_fill', 'reject']:
            raw['execution']['nontradable_policy'] = bad
            with self.assertRaises(ValueError):
                StrategySpec.from_dict(raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
