from __future__ import annotations

"""Run lifecycle failures, immutable input and actual CURRENT handoff.

Artificial execution artifacts exercise orchestration only, never investment
results. Real KRX/decile/corporate-action execution is tested separately.
"""

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from execution_contract import RUN_ORCHESTRATION_CONTRACT, RUN_EXIT_CODES
from export_strategy_dsl_contract import build_capabilities
from quant_backtest_postprocess import canonical_report_readiness, derive_complete_monthly
from quant_backtest_template_CURRENT import BacktestConfig, expected_market_sessions, standard_period_windows
from strategy_dsl import compile_execution_plan, load_strategy_spec
from strategy_dsl_preflight import preflight_strategy
from strategy_dsl_run import run_checked_strategy, exit_code_for_run

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config/strategies/kr_equity_split_research.json"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_status(result):
    saved = json.loads(Path(result["status_file"]).read_text())
    assert saved == result and saved["finished_at"] is not None
    assert saved["run_contract_version"] == RUN_ORCHESTRATION_CONTRACT["version"]
    assert saved["phase"] in RUN_ORCHESTRATION_CONTRACT["stages"]
    assert exit_code_for_run(result) == RUN_EXIT_CODES[result["status"]]
    return saved


def fake_preflight(path, root):
    spec = load_strategy_spec(path)
    dates = expected_market_sessions(pd.Timestamp(spec.period.start), pd.Timestamp(spec.period.end), "XKRX")
    return {"status": "ok", "phase": "ready", "ready_for_execution": True,
            "strategy_fingerprint": spec.fingerprint(),
            "krx_panel": {"actual_start": dates[0].date().isoformat(), "actual_end": dates[-1].date().isoformat()}}


def artificial_execution(path, root, out, *, postprocess):
    assert postprocess is False
    spec = load_strategy_spec(path)
    assert spec.portfolio.selection == "top_n"
    dates = expected_market_sessions(pd.Timestamp(spec.period.start), pd.Timestamp(spec.period.end), "XKRX")
    n = np.arange(len(dates))
    values = np.cumprod(1 + .0002 + .001 * np.sin(n / 19))
    daily = pd.DataFrame({"NAV_Gross": values, **{f"NAV_Net_{name}": values for name in spec.cost_scenarios}}, index=dates)
    if spec.benchmark is not None:
        daily["NAV_Benchmark"] = np.cumprod(1 + .00015 + .0015 * np.cos(n / 23))
    out.mkdir()
    daily.to_csv(out / "daily_nav.csv", index_label="Date")
    pd.DataFrame({"000001": [1.]}, index=[dates[0]]).to_csv(out / "target_weights.csv", index_label="signal_date")
    pd.DataFrame({"Code": ["000001"]}).to_csv(out / "selections.csv", index=False)
    write_json(out / "execution_plan.json", compile_execution_plan(spec))
    (out / "strategy_fingerprint.txt").write_text(spec.fingerprint() + "\n")
    write_json(out / "history_coverage.json", {"status": "complete", "expected_sessions": len(dates)})
    write_json(out / "return_reference_audit.json", {name: {"enabled": True, "tolerance_bps": 1.0} for name in spec.cost_scenarios})
    pd.DataFrame(columns=["Date", "Code"]).to_csv(out / "held_return_checks.csv", index=False)
    if spec.benchmark is not None:
        write_json(out / "benchmark_coverage.json", {"exact_date_alignment": True})
    return {"output_dir": out}


def full_report_raw():
    raw = json.loads(EXAMPLE.read_text())
    raw["strategy_id"] = "synthetic_orchestration_report"
    raw["title"] = "synthetic implementation test; no investment claims"
    raw["period"] = {"start": "2000-01-01", "end": "2024-12-31", "book_start": "2000-01-01",
                     "book_end": "2021-12-31", "as_of_date": "2025-01-01"}
    raw["cost_scenarios"] = {"zero": {}}
    raw["benchmark"] = {"source": "index", "symbol": "KOSPI"}
    return raw


def readiness_test():
    config = BacktestConfig(book_start="2000-01-01", book_end="2021-12-31", as_of_date="2025-01-01",
                           standard_end_year=2025, market_calendar="XKRX")
    dates = expected_market_sessions(pd.Timestamp("2000-01-01"), pd.Timestamp("2024-12-31"), "XKRX")
    ready = canonical_report_readiness(dates, config)
    # Compare date readiness against CURRENT's real NAV period policy.
    _, monthly = derive_complete_monthly(pd.DataFrame({"S": np.ones(len(dates))}, index=dates), pd.Timestamp(config.as_of_date))
    windows = standard_period_windows(monthly, config)
    assert ready["periods"] == {p: {"start": a.date().isoformat(), "end": b.date().isoformat()} for p, (a, b, _) in windows.items()}
    for damaged in (dates[dates.year >= 2021], dates.drop(dates[100]), dates[:-1], dates[::-1], dates.insert(1, dates[0])):
        try:
            canonical_report_readiness(damaged, config)
        except (ValueError, AssertionError):
            pass
        else:
            raise AssertionError("invalid report date coverage accepted")
    early = deepcopy(config)
    early.book_end = "2018-12-31"
    try:
        canonical_report_readiness(dates[dates.year <= 2020], early)
    except ValueError as exc:
        assert "from_2021" in str(exc)
    else:
        raise AssertionError("future standard period accepted")


def failures_and_snapshot_test(tmp):
    raw = json.loads(EXAMPLE.read_text())
    source = tmp / "strategy.json"
    # The integrated CLI must retain strict validation before either shared
    # preflight selection or execution can access data. Test representative
    # semantic-loss boundaries through the checked entry point itself.
    bad_inputs = []
    for key, value, expected_path in (
        ("universe", {**raw["universe"], "require_tradable_on_signal": "false"}, "$.universe.require_tradable_on_signal"),
        ("rebalance", {**raw["rebalance"], "months": [4.5]}, "$.rebalance.months[0]"),
        ("execution", {**raw["execution"], "lag_sessions": 1.5}, "$.execution.lag_sessions"),
        ("period", {**raw["period"], "start": "2024-02-30"}, "$.period.start"),
        ("cost_scenarios", {"invalid": {"commission_bps": float("inf")}}, "$.cost_scenarios.invalid.commission_bps"),
    ):
        item = deepcopy(raw)
        item[key] = value
        bad_inputs.append((item, expected_path))
    for index, (item, expected_path) in enumerate(bad_inputs):
        write_json(source, item)
        out = tmp / f"strict_boundary_{index}"
        with patch("strategy_dsl_run.preflight_strategy") as preflight, patch("strategy_dsl_run.run_strategy") as execution:
            result = run_checked_strategy(source, ROOT, out, postprocess=False)
            preflight.assert_not_called(); execution.assert_not_called()
        assert result["status"] == "capability_gap" and result["phase"] == "input", result
        assert result["error"]["path"] == expected_path, result
        assert not result["nav_ready"] and not result["report_ready"]
        assert not (out / "artifacts").exists() and not (out / "report").exists()
        assert (out / "strategy_input.json").read_bytes() == source.read_bytes()
        read_status(result)
    invalid = deepcopy(raw)
    invalid["execution"]["stop_loss_pct"] = 10
    write_json(source, invalid)
    with patch("strategy_dsl_run.preflight_strategy") as preflight, patch("strategy_dsl_run.run_strategy") as execution:
        result = run_checked_strategy(source, ROOT, tmp / "invalid", postprocess=False)
        assert result["status"] == "capability_gap" and not result["nav_ready"]
        preflight.assert_not_called(); execution.assert_not_called()
    read_status(result)
    missing = run_checked_strategy(tmp / "missing.json", ROOT, tmp / "missing_input", postprocess=False)
    assert missing["status"] == "failed" and missing["phase"] == "input"
    read_status(missing)
    write_json(source, raw)
    for key, value in (("ready_for_execution", False), ("strategy_fingerprint", "wrong")):
        def bad_preflight(path, root):
            result = fake_preflight(path, root)
            result[key] = value
            return result
        with patch("strategy_dsl_run.preflight_strategy", side_effect=bad_preflight), patch("strategy_dsl_run.run_strategy") as execution:
            result = run_checked_strategy(source, ROOT, tmp / key, postprocess=False)
            execution.assert_not_called()
        assert result["status"] == "failed" and result["phase"] == "preflight"
        read_status(result)
    with patch("strategy_dsl_run.run_strategy") as execution:
        result = run_checked_strategy(source, ROOT, tmp / "short_formal")
        assert result["status"] == "data_gap" and result["phase"] == "report_readiness", result
        assert not result["nav_ready"] and not result["report_ready"]
        execution.assert_not_called()
    read_status(result)
    assert not (Path(result["output_dir"]) / "artifacts").exists()

    def frozen_preflight(snapshot, root):
        write_json(source, invalid)
        return fake_preflight(snapshot, root)
    with patch("strategy_dsl_run.preflight_strategy", side_effect=frozen_preflight), patch("strategy_dsl_run.run_strategy", side_effect=artificial_execution):
        result = run_checked_strategy(source, ROOT, tmp / "snapshot", postprocess=False)
    assert result["status"] == "ok" and result["nav_ready"] and not result["report_ready"], result
    read_status(result)
    assert load_strategy_spec(Path(result["output_dir"]) / "strategy_normalized.json").fingerprint() == result["strategy_fingerprint"]
    assert json.loads(source.read_text())["execution"]["stop_loss_pct"] == 10
    before = (Path(result["output_dir"]) / "run_status.json").read_bytes()
    try:
        run_checked_strategy(source, ROOT, Path(result["output_dir"]), postprocess=False)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing output directory overwritten")
    assert (Path(result["output_dir"]) / "run_status.json").read_bytes() == before
    write_json(source, raw)
    with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=artificial_execution):
        runs = [run_checked_strategy(source, tmp / "isolated_repo", postprocess=False) for _ in range(2)]
    assert runs[0]["run_id"] != runs[1]["run_id"] and runs[0]["output_dir"] != runs[1]["output_dir"]
    assert runs[0]["strategy_fingerprint"] == runs[1]["strategy_fingerprint"]
    assert (Path(runs[0]["output_dir"]) / runs[0]["outputs"]["daily_nav"]).read_bytes() == (Path(runs[1]["output_dir"]) / runs[1]["outputs"]["daily_nav"]).read_bytes()
    for record in runs:
        read_status(record)

    def crash(path, root, out, **kwargs):
        out.mkdir(); (out / "daily_nav.csv").write_text("partial")
        raise RuntimeError("synthetic execution failure")
    with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=crash):
        result = run_checked_strategy(source, ROOT, tmp / "crashed", postprocess=False)
    assert result["status"] == "failed" and result["phase"] == "execution" and not result["nav_ready"]
    assert not (Path(result["output_dir"]) / "artifacts").exists()
    read_status(result)
    for damage in ("daily_nav.csv", "return_reference_audit.json", "strategy_fingerprint.txt"):
        def damaged(path, root, out, **kwargs):
            artificial_execution(path, root, out, **kwargs)
            if damage == "daily_nav.csv":
                frame = pd.read_csv(out / damage); frame.loc[0, "NAV_Gross"] = np.nan; frame.to_csv(out / damage, index=False)
            elif damage == "return_reference_audit.json":
                audits = json.loads((out / damage).read_text())
                for audit in audits.values():
                    audit["enabled"] = False
                write_json(out / damage, audits)
            else:
                (out / damage).write_text("wrong fingerprint")
        with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=damaged):
            result = run_checked_strategy(source, ROOT, tmp / ("damaged_" + damage), postprocess=False)
        assert result["status"] == "failed" and not result["nav_ready"], result
        assert not (Path(result["output_dir"]) / "artifacts").exists()
        read_status(result)


def current_report_test(tmp):
    source = tmp / "full.json"
    write_json(source, full_report_raw())
    with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=artificial_execution):
        result = run_checked_strategy(source, ROOT, tmp / "full")
    assert result["status"] == "ok" and result["nav_ready"] and result["report_ready"], result
    read_status(result)
    out = Path(result["output_dir"])
    manifest = json.loads((out / result["outputs"]["chat_manifest"]).read_text())
    assert Path(manifest["source_daily_csv"]) == out / "artifacts/daily_nav.csv"
    assert Path(manifest["source_daily_csv"]).exists() and len(manifest["render_order"]) == 9
    assert not (out / "_report").exists() and not (out / "_execution").exists()
    for damage in ("metrics", "charts", "benchmark", "source"):
        def incomplete_report(spec, root, work, daily, **kwargs):
            shutil.copytree(out / "report", work, dirs_exist_ok=True)
            metadata = json.loads((work / "chat_manifest_CURRENT.json").read_text())
            metadata["source_daily_csv"] = str(kwargs["daily_csv"])
            if damage == "metrics":
                rows = pd.read_csv(work / "metrics_CURRENT.csv").iloc[1:]
                rows.to_csv(work / "metrics_CURRENT.csv", index=False)
            elif damage == "charts":
                metadata["render_order"].pop()
            elif damage == "benchmark":
                rows = pd.read_csv(work / "benchmark_statistics_CURRENT.csv").iloc[1:]
                rows.to_csv(work / "benchmark_statistics_CURRENT.csv", index=False)
            else:
                metadata["source_daily_csv"] = str(work / "stale_nav.csv")
            write_json(work / "chat_manifest_CURRENT.json", metadata)
            return subprocess.CompletedProcess([], 0, "", "")
        with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=artificial_execution), patch("strategy_dsl_run.run_current_postprocess", side_effect=incomplete_report):
            result = run_checked_strategy(source, ROOT, tmp / ("incomplete_" + damage))
        assert result["status"] == "failed" and result["nav_ready"] and not result["report_ready"], result
        assert not (Path(result["output_dir"]) / "report").exists()
        read_status(result)
    for name, failure in (("process_failed", subprocess.CalledProcessError(1, "CURRENT", output="test output", stderr="test report failure")),
                          ("interrupted", KeyboardInterrupt()), ("missing_report", None)):
        if failure is None:
            postprocess = patch("strategy_dsl_run.run_current_postprocess", return_value=subprocess.CompletedProcess([], 0, "", ""))
        else:
            postprocess = patch("strategy_dsl_run.run_current_postprocess", side_effect=failure)
        with patch("strategy_dsl_run.preflight_strategy", side_effect=fake_preflight), patch("strategy_dsl_run.run_strategy", side_effect=artificial_execution), postprocess:
            result = run_checked_strategy(source, ROOT, tmp / name)
        assert result["status"] == ("interrupted" if name == "interrupted" else "failed"), result
        assert result["phase"] == "postprocess" and result["nav_ready"] and not result["report_ready"]
        assert (Path(result["output_dir"]) / "artifacts/daily_nav.csv").exists()
        assert not (Path(result["output_dir"]) / "report").exists()
        read_status(result)


def main():
    assert build_capabilities()["run_orchestration"] == RUN_ORCHESTRATION_CONTRACT
    readiness_test()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        failures_and_snapshot_test(tmp)
        current_report_test(tmp)
    print("CHECKED DSL RUN LIFECYCLE: PASS (gaps, readiness, frozen input, distinct runs, atomic outputs, failures/interruption, actual CURRENT report)")


if __name__ == "__main__":
    main()
