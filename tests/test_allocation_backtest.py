"""Independent execution/accounting and missing-publication boundaries."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

path = Path(__file__).resolve().parents[1] / "scripts/allocation_backtest.py"
spec = importlib.util.spec_from_file_location("allocation_backtest", path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class AllocationTests(unittest.TestCase):
    def test_unpublished_month_cannot_change_macro(self):
        months = pd.date_range("2020-01-01", periods=14, freq="MS")
        values = pd.Series(5., index=months)
        values.iloc[-1] = 1000.
        releases = pd.DataFrame({"ReleaseDate": months + pd.offsets.MonthBegin(1) + pd.Timedelta(days=5)}, index=months)
        row, errors = engine.disclosed_macro(pd.Timestamp("2021-02-01"), values, releases, 12)
        self.assertEqual(errors, [])
        self.assertEqual(row["macro_month"], "2020-12")
        self.assertEqual(row["unemployment_ma"], 5.)

    def test_missing_official_month_is_gap_even_with_stored_value(self):
        months = pd.date_range("2024-12-01", periods=12, freq="MS")
        values = pd.Series(4.4, index=months)
        releases = pd.DataFrame({"ReleaseDate": months + pd.offsets.MonthBegin(1) + pd.Timedelta(days=5)}, index=months)
        releases = releases.drop(pd.Timestamp("2025-10-01"))
        row, errors = engine.disclosed_macro(pd.Timestamp("2025-12-31"), values, releases, 12)
        self.assertNotIn("unemployment_ma", row)
        self.assertEqual(errors[0]["month"], "2025-10")

    def test_annual_rebalance_fee_and_weights(self):
        values = pd.Series([.6, .2, .2])
        target = pd.Series([.25, .25, .5])
        after, fee, traded = engine.rebalance(values, target, 0., .001)
        self.assertAlmostEqual(after.sum() + fee, 1.)
        np.testing.assert_allclose(after / after.sum(), target)
        self.assertAlmostEqual(fee, .001 * traded)

    def test_initial_entry_fee_is_not_omitted(self):
        after, fee, _ = engine.rebalance(pd.Series([0., 0.]), pd.Series([.5, .5]), 1., .001)
        self.assertAlmostEqual(after.sum(), 1 / 1.001)
        self.assertAlmostEqual(after.sum() + fee, 1.)

    def test_switch_earns_old_asset_return_and_does_not_trade_fixed(self):
        dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-03"])
        prices = pd.DataFrame({"IWD": [1., 1., 1.], "GLD": [1., 1., 1.], "IEF": [1., 1., 1.],
                               "QQQ": [1., 1., 2.], "SHY": [1., 1., 10.]}, index=dates)
        plan = pd.DataFrame([{"execution_date": "2020-01-31", "signal_date": "2020-01-30", "kind": "initial", "selected": "QQQ"},
                             {"execution_date": "2020-02-03", "signal_date": "2020-01-31", "kind": "timing", "selected": "SHY"}])
        cfg = {"fixed_weights": {"IWD": .25, "GLD": .25, "IEF": .25}, "risk_asset": "QQQ", "defensive_asset": "SHY", "timing_weight": .25}
        nav, trades, weights = engine.simulate(prices, plan, cfg, .001)
        initial_fixed = .25 / 1.001
        switch_budget = .5 / 1.001 * .999 / 1.001
        self.assertAlmostEqual(nav.iloc[-1], 3 * initial_fixed + switch_budget)
        self.assertAlmostEqual(weights.iloc[-1].IWD * nav.iloc[-1], initial_fixed)
        self.assertAlmostEqual(trades.iloc[-1].cost, .001 * (.5 / 1.001 + switch_budget))

    def test_price_missing_session_fails(self):
        dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
        with self.assertRaises(engine.DataGap):
            engine.check_dates(pd.Series([1., 2.], index=dates[[0, 2]]), dates, "ETF")

    def test_strict_and_rule_and_next_session(self):
        dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-03"])
        macro = pd.Series([4., 6.], index=pd.to_datetime(["2019-11-01", "2019-12-01"]))
        releases = pd.DataFrame({"ReleaseDate": pd.to_datetime(["2019-12-06", "2020-01-10"])}, index=macro.index)
        price = pd.Series([100., 90., 1000.], index=dates)
        cfg = {"price_ma_sessions": 1, "macro_ma_months": 2, "annual_rebalance_month": 1,
               "risk_asset": "QQQ", "defensive_asset": "SHY"}
        plan, gaps = engine.monthly_plan(dates, price, macro, releases, cfg)
        self.assertFalse(gaps)
        # Equality to the price MA is not 'below', even when macro is above MA.
        self.assertEqual(plan.iloc[-1].selected, "QQQ")
        self.assertEqual(plan.iloc[-1].signal_date, "2020-01-31")
        self.assertEqual(plan.iloc[-1].execution_date, "2020-02-03")
        self.assertEqual(plan.iloc[-1].sp500_close, 90.)

    def test_price_condition_false_preserves_macro_gap_without_fabrication(self):
        dates = pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02"])
        macro = pd.Series([4., 5.], index=pd.to_datetime(["2025-10-01", "2025-11-01"]))
        releases = pd.DataFrame({"ReleaseDate": [pd.Timestamp("2025-12-16")]}, index=macro.index[1:])
        cfg = {"price_ma_sessions": 1, "macro_ma_months": 2, "annual_rebalance_month": 1,
               "risk_asset": "QQQ", "defensive_asset": "SHY"}
        plan, gaps = engine.monthly_plan(dates, pd.Series(100., index=dates), macro, releases, cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(plan.iloc[-1].selected, "QQQ")
        self.assertEqual(plan.iloc[-1].macro_quality, "data_gap")
        self.assertNotIn("unemployment_ma", plan.columns)


if __name__ == "__main__":
    unittest.main()
