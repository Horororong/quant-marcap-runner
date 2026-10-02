from __future__ import annotations

"""Synthetic contract boundaries; optional original-source Samsung oracle."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import faulthandler
import tempfile
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import dart_value_factor_adapter as dart
from factor_registry import build_external_provider
from strategy_dsl import StrategySpec, load_strategy_spec

ROOT = Path(__file__).resolve().parents[1]
POLICY = "latest_disclosed_quarter"


def report(date, code="000001", scope="CFS", **values):
    row = {"Code": code, "fs_div": scope, "filing_date": pd.Timestamp(date),
           "rcept_no": date.replace("-", "") + "000001"}
    for metric in ("equity", "revenue", "net_income", "ocf"):
        row[metric + "_current"] = np.nan
        row[metric + "_cum"] = np.nan
    row.update(values)
    return row


def cache_for(signal, entries):
    return {key: pd.DataFrame(entries.get(key, [])) for key in dart.required_periods(signal, POLICY)}


class QuarterTests(unittest.TestCase):
    def test_candidate_window_and_year_boundary(self):
        self.assertEqual(dart.candidate_quarters("2020-01-03"),
                         [(2019, "FY"), (2019, "Q3"), (2019, "H1"), (2019, "Q1")])
        self.assertEqual(dart.candidate_quarters("2020-03-30")[0], (2019, "FY"))
        self.assertEqual(dart.candidate_quarters("2020-03-31")[0], (2020, "Q1"))
        self.assertEqual(set(dart.required_periods("2020-05-29", POLICY)),
                         {(2019, "Q1"), (2019, "H1"), (2019, "Q3"), (2019, "FY"), (2020, "Q1")})

    def test_q1_and_late_correction_are_pit(self):
        entries = {(2020, "Q1"): [
            report("2020-05-15", equity_current=100, revenue_current=20,
                   net_income_current=3, ocf_current=5),
            report("2020-06-01", equity_current=999, revenue_current=999,
                   net_income_current=999, ocf_current=999)]}
        before = dart.build_latest_quarter_inputs("2020-05-14", cache_for("2020-05-14", entries))
        self.assertTrue(before.empty)
        on = dart.build_latest_quarter_inputs("2020-05-15", cache_for("2020-05-15", entries)).iloc[0]
        self.assertEqual((on.revenue_q, on.net_income_q, on.ocf_q), (20, 3, 5))
        self.assertEqual(on.available_date, pd.Timestamp("2020-05-15"))
        later = dart.build_latest_quarter_inputs("2020-06-01", cache_for("2020-06-01", entries)).iloc[0]
        self.assertEqual(later.equity, 999)

    def test_q2_q3_and_q4_formulas(self):
        entries = {
            (2020, "Q1"): [report("2020-05-15", revenue_cum=10, net_income_cum=2, ocf_current=3)],
            (2020, "H1"): [report("2020-08-14", equity_current=100, revenue_cum=35,
                                  net_income_cum=7, ocf_current=11)],
            (2020, "Q3"): [report("2020-11-13", equity_current=110, revenue_current=40,
                                  revenue_cum=75, net_income_cum=16, ocf_current=20)],
            (2020, "FY"): [report("2021-03-26", equity_current=120, revenue_current=130,
                                  net_income_current=30, ocf_current=32)],
        }
        for signal, expected in (("2020-09-01", (25, 5, 8)), ("2020-11-16", (40, 9, 9)),
                                 ("2021-04-01", (55, 14, 12))):
            row = dart.build_latest_quarter_inputs(signal, cache_for(signal, entries)).iloc[0]
            self.assertEqual((row.revenue_q, row.net_income_q, row.ocf_q), expected)

    def test_latest_incomplete_report_cannot_fall_back_to_older_complete_quarter(self):
        entries = {
            (2020, "Q1"): [report("2020-05-15", equity_current=100, revenue_current=20,
                                  net_income_current=2, ocf_current=3)],
            (2020, "H1"): [report("2020-08-14", equity_current=110, revenue_current=25)],
        }
        row = dart.build_latest_quarter_inputs("2020-09-01", cache_for("2020-09-01", entries)).iloc[0]
        self.assertEqual(row.report_period, "H1")
        self.assertTrue(pd.isna(row.net_income_q))
        self.assertTrue(pd.isna(row.ocf_q))

    def test_no_cross_scope_subtraction_and_complete_ofs_fallback(self):
        entries = {
            (2020, "Q1"): [report("2020-05-15", scope="OFS", revenue_cum=10,
                                  net_income_cum=2, ocf_current=3)],
            (2020, "H1"): [report("2020-08-14", equity_current=100, revenue_cum=35,
                                  net_income_cum=7, ocf_current=11)],
        }
        row = dart.build_latest_quarter_inputs("2020-09-01", cache_for("2020-09-01", entries)).iloc[0]
        self.assertEqual(row.fs_div, "CFS")
        self.assertTrue(pd.isna(row.ocf_q))
        entries[(2020, "H1")].append(report("2020-08-14", scope="OFS", equity_current=80,
                                            revenue_current=25, net_income_current=5, ocf_current=11))
        row = dart.build_latest_quarter_inputs("2020-09-01", cache_for("2020-09-01", entries)).iloc[0]
        self.assertEqual((row.fs_div, row.ocf_q), ("OFS", 8))

    def test_newer_scope_report_beats_older_complete_scope(self):
        entries = {
            (2020, "Q1"): [report("2020-05-15", equity_current=100, revenue_current=20,
                                  net_income_current=2, ocf_current=3)],
            (2020, "H1"): [report("2020-08-14", scope="OFS", equity_current=80, revenue_current=25)],
        }
        row = dart.build_latest_quarter_inputs("2020-09-01", cache_for("2020-09-01", entries)).iloc[0]
        self.assertEqual((row.report_period, row.fs_div), ("H1", "OFS"))

    def test_predecessor_correction_date_is_not_hidden(self):
        entries = {
            (2020, "Q1"): [report("2020-05-15", revenue_cum=10, net_income_cum=2, ocf_current=3),
                           report("2020-09-02", revenue_cum=12, net_income_cum=3, ocf_current=4)],
            (2020, "H1"): [report("2020-08-14", equity_current=100, revenue_cum=35,
                                  net_income_cum=7, ocf_current=11)],
        }
        before = dart.build_latest_quarter_inputs("2020-09-01", cache_for("2020-09-01", entries)).iloc[0]
        after = dart.build_latest_quarter_inputs("2020-09-03", cache_for("2020-09-03", entries)).iloc[0]
        self.assertEqual((before.ocf_q, after.ocf_q), (8, 7))
        self.assertEqual(after.available_date, pd.Timestamp("2020-09-02"))

    def test_missing_dependency_stays_nan(self):
        entries = {(2020, "FY"): [report("2021-03-26", equity_current=100,
                                         revenue_current=10, net_income_current=2, ocf_current=3)]}
        row = dart.build_latest_quarter_inputs("2021-04-01", cache_for("2021-04-01", entries)).iloc[0]
        self.assertTrue(pd.isna(row.net_income_q))

    def test_report_with_no_registered_accounts_is_not_hidden(self):
        raw = pd.DataFrame([{"stock_code": "000001", "fs_div_requested": "CFS",
                             "rcept_no": "20200814000001", "filing_date": pd.Timestamp("2020-08-14"),
                             "sj_div": "IS", "account_id": "unregistered", "account_nm": "unregistered"}])
        self.assertTrue(dart.report_snapshots(raw).empty)
        snapshot = dart.report_snapshots(raw, keep_empty_reports=True)
        entries = {(2020, "Q1"): [report("2020-05-15", equity_current=100, revenue_current=20,
                                         net_income_current=2, ocf_current=3)]}
        cache = cache_for("2020-09-01", entries)
        cache[(2020, "H1")] = snapshot
        row = dart.build_latest_quarter_inputs("2020-09-01", cache).iloc[0]
        self.assertEqual(row.report_period, "H1")
        self.assertTrue(pd.isna(row.equity))

    def test_all_months_explicit_policy_and_legacy_fingerprint(self):
        raw = json.loads((ROOT / "config/strategies/super_value_dart_dsl.json").read_text())
        legacy = StrategySpec.from_dict(raw)
        self.assertEqual(legacy.fingerprint(), "6401144337f863ea586717d1f736b8416f1890c83b16994f6f8866e8522f85db")
        raw["rebalance"]["dart_period_policy"] = "legacy_april_october"
        self.assertEqual(StrategySpec.from_dict(raw).fingerprint(), legacy.fingerprint())
        raw["rebalance"].update(months=list(range(1, 13)), dart_period_policy=POLICY)
        new = StrategySpec.from_dict(raw)
        self.assertEqual(new.rebalance.months, tuple(range(1, 13)))
        self.assertNotEqual(new.fingerprint(), legacy.fingerprint())
        self.assertEqual(StrategySpec.from_dict(new.to_dict()).fingerprint(), new.fingerprint())
        raw["rebalance"].pop("dart_period_policy")
        with self.assertRaisesRegex(ValueError, "supports rebalance months"):
            StrategySpec.from_dict(raw)
        raw["rebalance"]["dart_period_policy"] = "guessed"
        with self.assertRaises(ValueError):
            StrategySpec.from_dict(raw)

    def test_dart_filter_inherits_selected_policy(self):
        raw = json.loads((ROOT / "config/strategies/kr_equity_rank_demo.json").read_text())
        raw["universe"]["filters"] = [{"field": "book_to_price", "op": "gt", "value": 0}]
        raw["rebalance"].update(months=[3, 6, 9, 12], dart_period_policy=POLICY)
        self.assertEqual(StrategySpec.from_dict(raw).rebalance.months, (3, 6, 9, 12))
        self.assertEqual(build_external_provider("dart", ROOT, POLICY)._adapter.period_policy, POLICY)

    def test_shared_ranking_deciles_and_coverage_receive_policy(self):
        from strategy_dsl_runner import build_target_weights_from_panel, factor_provider_coverage_audit
        from strategy_dsl_deciles import build_decile_target_weights_from_panel
        raw = json.loads((ROOT / "config/strategies/super_value_dart_dsl.json").read_text())
        raw["factors"] = [{"name": "bp", "source": "dart", "field": "book_to_price", "direction": "high"}]
        raw["portfolio"]["number_of_positions"] = 2
        raw["rebalance"].update(months=[5], dart_period_policy=POLICY)
        raw["period"].update(start="2020-05-01", end="2020-06-02", book_start="2020-05-01",
                             book_end="2020-06-02", as_of_date="2020-06-02")
        spec = StrategySpec.from_dict(raw)
        panel = pd.DataFrame({"Date": [pd.Timestamp("2020-05-29")] * 10,
                              "Code": [f"{i:06d}" for i in range(1, 11)], "Marcap": [100] * 10,
                              "Name": ["fixture"] * 10, "Market": ["KOSPI"] * 10})

        class Provider:
            def factor_frame(self, signal, cross_section, fields):
                return pd.DataFrame({"Code": cross_section.Code, "book_to_price": range(1, 11),
                                     "dart_report_period": ["Q1"] * 10})
            def coverage_report(self, signal, fields):
                return [{"signal_date": signal, "source": "dart", "ratio": 1.0}]

        with patch("strategy_dsl_runner.build_external_provider", return_value=Provider()) as factory:
            _, selected = build_target_weights_from_panel(panel, spec, ROOT)
            self.assertEqual(selected.Code.tolist(), ["000010", "000009"])
            self.assertEqual(set(selected.dart_report_period), {"Q1"})
            self.assertFalse(factor_provider_coverage_audit(panel, spec, ROOT).empty)
            raw["portfolio"] = {"selection": "deciles", "weighting": "equal"}
            _, members, _ = build_decile_target_weights_from_panel(panel, StrategySpec.from_dict(raw), ROOT)
            self.assertEqual(len(members), 10)
            self.assertEqual(factory.call_count, 3)
            for call in factory.call_args_list:
                self.assertEqual(call.args, ("dart", ROOT, POLICY))

    def test_kit_collects_actual_policy_dependencies(self):
        import build_sandbox_kit as builder
        signals = {"status": "ok", "signal_dates": ["2020-05-29"]}
        strategy = "config/strategies/kr_equity_dart_custom_month_research.json"
        with patch("strategy_dsl_preflight.preflight_strategy", return_value=signals):
            files, coverage = builder.selected_sources(ROOT, [strategy])
        self.assertEqual(set(map(tuple, coverage["dart_periods"])),
                         set(dart.required_periods("2020-05-29", POLICY)))
        for year, period in dart.required_periods("2020-05-29", POLICY):
            self.assertTrue(any(f"dart_full_{year}_{period}_" in path for path in files))

    def test_missing_coverage_blocks_before_snapshot(self):
        adapter = dart.DartValueFactorAdapter(ROOT, POLICY)
        adapter._mapping = pd.DataFrame()
        adapter._state = pd.DataFrame()
        with patch.object(dart, "signal_completeness_report", return_value=[{
            "ratio": 0.5, "raw_ok": True, "year": 2020, "period": "Q1",
            "completed_codes": 1, "expected_codes": 2}]), patch.object(adapter, "_snapshot") as snapshot:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                adapter.factor_frame(pd.Timestamp("2020-05-29"), pd.DataFrame())
            snapshot.assert_not_called()


def real_source_check():
    """Original four IFRS Q1 amounts, independent of report-snapshot formulas.

    Source filtering limits this oracle to Samsung, without changing the whole
    source completeness gate or certifying the remaining universe.
    """
    signal = pd.Timestamp("2020-05-29")
    adapter = dart.DartValueFactorAdapter(ROOT, POLICY)
    coverage = adapter.coverage_report(signal)
    assert all(r["ratio"] == 1 and r["raw_ok"] for r in coverage), coverage
    source = None
    for year, period in dart.required_periods(signal, POLICY):
        raw = dart.load_financial_raw(ROOT, year, period)
        raw = raw[raw.stock_code == "005930"].copy()
        adapter._period_cache[(year, period)] = dart.report_snapshots(raw)
        if (year, period) == (2020, "Q1"):
            source = raw[(raw.fs_div_requested == "CFS") & (raw.filing_date <= signal)].copy()
    receipt = source.sort_values(["filing_date", "rcept_no"]).iloc[-1].rcept_no
    source = source[source.rcept_no == receipt]
    row = adapter.factor_frame(signal, pd.DataFrame({"Code": ["005930"], "Marcap": [1000.0]})).iloc[0]
    concepts = {"equity": ("BS", "ifrs-full_Equity"), "revenue_q": ("IS", "ifrs-full_Revenue"),
                "net_income_q": ("IS", "ifrs-full_ProfitLoss"),
                "ocf_q": ("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities")}
    for field, (statement, concept) in concepts.items():
        original = source[(source.sj_div == statement) & (source.account_id == concept)]
        assert len(original) == 1, (field, len(original))
        expected = float(original.iloc[0].thstrm_amount.replace(",", ""))
        assert row[field] == expected, (field, row[field], expected)
    assert row.report_year == 2020 and row.report_period == "Q1"
    assert row.available_date <= signal
    print("REAL MAY 2020 DART Q1 SOURCE ORACLE: PASS", receipt)


def real_execution_check():
    from strategy_dsl_run import run_checked_strategy
    from strategy_dsl_runner import run_strategy
    print("REAL CUSTOM-MONTH CHECKED NAV: START", flush=True)
    faulthandler.enable()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "run"
        stop = Event()
        started = time.monotonic()

        def heartbeat():
            while not stop.wait(30):
                try:
                    phase = json.loads((output / "run_status.json").read_text())["phase"]
                except (FileNotFoundError, json.JSONDecodeError):
                    phase = "initializing"
                print(f"REAL CUSTOM-MONTH CHECKED NAV: RUNNING {time.monotonic() - started:.0f}s phase={phase}", flush=True)

        monitor = Thread(target=heartbeat, daemon=True)
        monitor.start()
        try:
            actual_execution = {}

            def capture_execution(*args, **kwargs):
                actual = run_strategy(*args, **kwargs)
                actual_execution.update(actual["engine_result"])
                return actual

            # Transparently capture the real engine return. The checked runner
            # publishes NAV/selection artifacts, not an execution_schedule CSV.
            with patch("strategy_dsl_run.run_strategy", side_effect=capture_execution) as execution:
                result = run_checked_strategy(
                    ROOT / "config/strategies/kr_equity_dart_custom_month_research.json",
                    ROOT, output, postprocess=False)
                self_calls = execution.call_count
            assert self_calls == 1
            assert result["status"] == "ok" and result["nav_ready"] and not result["report_ready"], result
            selections = pd.read_csv(output / "artifacts/selections.csv", dtype={"Code": str})
            assert len(selections) == 10
            assert set(selections.signal_date) == {"2020-05-29"}
            assert (pd.to_datetime(selections.dart_available_date) <= pd.to_datetime(selections.signal_date)).all()
            assert selections.dart_report_period.eq("Q1").all()
            nav = pd.read_csv(output / "artifacts/daily_nav.csv").drop(columns="Date")
            assert np.isfinite(nav.to_numpy()).all() and (nav.to_numpy() > 0).all()
            schedule = actual_execution["execution_scenarios"]["gross"]["execution_schedule"]
            assert set(pd.to_datetime(schedule.execution_date)) == {pd.Timestamp("2020-06-01")}, schedule
            assert not (output / "report").exists()
            print("REAL CUSTOM-MONTH CHECKED NAV: PASS (May signal, June t+1, Q1 PIT, validated NAV)", flush=True)
        finally:
            stop.set()
            monitor.join(timeout=2)


if __name__ == "__main__":
    real = "--real-data" in sys.argv
    if real:
        sys.argv.remove("--real-data")
    result = unittest.main(verbosity=2, exit=False).result
    if not result.wasSuccessful():
        sys.exit(1)
    if real:
        real_source_check()
        real_execution_check()
