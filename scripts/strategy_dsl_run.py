from __future__ import annotations

"""Checked execution lifecycle shared by the public Strategy DSL CLI.

Providers, selection, NAV and metrics retain their existing owners. This module
owns input snapshots, automatic preflight, run status and artifact publication.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import subprocess
import uuid

import pandas as pd

from execution_contract import (
    RUN_ORCHESTRATION_CONTRACT_VERSION, RUN_EXIT_CODES, PERFORMANCE_TEMPLATE_VERSION, HELD_RETURN_TOLERANCE_BPS,
)
from quant_backtest_postprocess import canonical_report_readiness, PERIOD_CHART_ORDER
from quant_backtest_template_CURRENT import (
    BacktestConfig, expected_market_sessions, validate_daily_nav,
)
from strategy_dsl import StrategySpec, compile_execution_plan, load_strategy_spec
from strategy_dsl_preflight import preflight_strategy
from strategy_dsl_runner import run_strategy, run_current_postprocess

def exit_code_for_run(result: dict[str, Any]) -> int:
    return RUN_EXIT_CODES[result["status"]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_status(out: Path, record: dict[str, Any]) -> None:
    temporary = out / "run_status.json.tmp"
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, out / "run_status.json")


def _save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _require_files(out: Path, names: list[str]) -> None:
    missing = [name for name in names if not (out / name).is_file()]
    if missing:
        raise ValueError(f"required artifacts missing: {missing}")


def _check_execution_artifacts(out: Path, spec: StrategySpec) -> pd.DataFrame:
    names = ["daily_nav.csv", "target_weights.csv", "execution_plan.json", "strategy_fingerprint.txt",
             "history_coverage.json", "return_reference_audit.json", "held_return_checks.csv"]
    labels = [f"D{i:02d}" for i in range(1, 11)] if spec.portfolio.selection == "deciles" else [None]
    if spec.portfolio.selection == "deciles":
        names += ["decile_membership.csv", "decile_partition_audit.csv", "decile_contract.json",
                  "execution_schedule.csv", "execution_trades.csv"]
        names += [f"{label}/{name}" for label in labels for name in
                  ("daily_nav.csv", "target_weights.csv", "return_reference_audit.json", "held_return_checks.csv")]
    else:
        names += ["selections.csv"]
    if spec.benchmark is not None:
        names += ["benchmark_coverage.json"]
    _require_files(out, names)
    expected = [f"NAV_{label + '_' if label else ''}{series}" for label in labels
                for series in ("Gross", *(f"Net_{name}" for name in spec.cost_scenarios))]
    if spec.benchmark is not None:
        expected += ["NAV_Benchmark"]
    frame = pd.read_csv(out / "daily_nav.csv")
    if set(frame.columns) != {"Date", *expected}:
        raise ValueError("daily NAV columns do not match the requested portfolios/costs/benchmark")
    dates = pd.DatetimeIndex(pd.to_datetime(frame.pop("Date"), errors="raise"))
    if not dates.equals(expected_market_sessions(pd.Timestamp(spec.period.start), pd.Timestamp(spec.period.end), "XKRX")):
        raise ValueError("daily NAV dates must exactly match the requested XKRX sessions")
    frame.index = dates
    validate_daily_nav(frame)  # CURRENT owns numeric NAV validation; never fills or changes the file.
    fingerprint = spec.fingerprint()
    plan = json.loads((out / "execution_plan.json").read_text(encoding="utf-8"))
    if plan["strategy_fingerprint"] != fingerprint or (out / "strategy_fingerprint.txt").read_text().strip() != fingerprint:
        raise ValueError("execution artifacts do not match the input snapshot fingerprint")
    history = json.loads((out / "history_coverage.json").read_text())
    if history["status"] != "complete":
        raise ValueError("execution history coverage must be complete")
    references = json.loads((out / "return_reference_audit.json").read_text())
    if labels == [None]:
        references = {"top_n": references}
    elif set(references) != set(labels):
        raise ValueError("held-return audits must include all ten deciles")
    for scenarios in references.values():
        if set(scenarios) != set(spec.cost_scenarios):
            raise ValueError("held-return audits must include every cost scenario")
        if any(summary["enabled"] is not True or summary["tolerance_bps"] != HELD_RETURN_TOLERANCE_BPS
               for summary in scenarios.values()):
            raise ValueError("held-return validation must be enabled with the execution contract tolerance")
    return frame


def _check_report_artifacts(out: Path, daily: pd.DataFrame, spec: StrategySpec) -> None:
    names = ["metrics_CURRENT.csv", "chat_manifest_CURRENT.json", "daily_nav_canonical.csv", "monthly_nav_canonical.csv"]
    if spec.benchmark is not None:
        names += ["benchmark_statistics_CURRENT.csv"]
    _require_files(out, names)
    periods = {"book_validation", "from_2001", "from_2021", "longest"}
    metrics = pd.read_csv(out / "metrics_CURRENT.csv")
    actual = list(zip(metrics["period"], metrics["전략"]))
    if len(actual) != len(set(actual)) or set(actual) != {(p, s) for p in periods for s in daily.columns}:
        raise ValueError("canonical metrics must include all four periods and every NAV series")
    manifest = json.loads((out / "chat_manifest_CURRENT.json").read_text(encoding="utf-8"))
    if manifest["template_version"] != PERFORMANCE_TEMPLATE_VERSION or set(manifest["periods"]) != periods:
        raise ValueError("canonical report version/periods mismatch")
    if manifest["market_calendar"] != "XKRX" or Path(manifest["source_daily_csv"]).resolve() != out.parent / "artifacts/daily_nav.csv":
        raise ValueError("canonical report calendar/source must match the published execution NAV")
    if [(item["period"], item["chart"]) for item in manifest["render_order"]] != PERIOD_CHART_ORDER:
        raise ValueError("canonical report must include the nine charts in CURRENT order")
    if spec.benchmark is not None:
        if manifest["benchmark_series"] != "NAV_Benchmark":
            raise ValueError("canonical report must use the explicit requested benchmark")
        statistics = pd.read_csv(out / "benchmark_statistics_CURRENT.csv")
        actual = list(zip(statistics["period"], statistics["strategy"]))
        expected = {(p, s) for p in periods for s in daily.columns if s != "NAV_Benchmark"}
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("canonical benchmark statistics must include all periods and strategy series")


def _inventory(out: Path) -> list[dict[str, Any]]:
    return [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size}
            for path in sorted(out.rglob("*")) if path.is_file()]


def run_checked_strategy(
    strategy_json: str | Path,
    repo_root: str | Path,
    output_dir: str | Path | None = None,
    *,
    postprocess: bool = True,
) -> dict[str, Any]:
    """Run a frozen DSL through preflight and publish only validated outputs.

    Explicit output directories must be new. Operational setup/write failures
    propagate as OSError; they must never overwrite an earlier run's status.
    Expected gaps and execution/report failures return a persisted result.
    """
    root = Path(repo_root).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    out = Path(output_dir).resolve() if output_dir is not None else root / "results/dsl/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    record = {
        "run_contract_version": RUN_ORCHESTRATION_CONTRACT_VERSION,
        "run_id": run_id, "status": "running", "phase": "input",
        "started_at": _utc_now(), "finished_at": None,
        "strategy_id": None, "strategy_fingerprint": None, "versions": {},
        "mode": "canonical_report" if postprocess else "execution_only",
        "nav_ready": False, "report_ready": False,
        "input_path": str(Path(strategy_json).resolve()),
        "output_dir": str(out), "status_file": str(out / "run_status.json"),
        "completed_stages": [], "outputs": {}, "artifacts": {}, "error": None,
    }
    _save_status(out, record)

    def phase(name):
        record["phase"] = name
        _save_status(out, record)

    def complete(name):
        record["completed_stages"].append(name)
        _save_status(out, record)

    def finish(status, error=None):
        record["status"] = status
        record["error"] = error
        record["finished_at"] = _utc_now()
        _save_status(out, record)
        return record

    try:
        raw_path = out / "strategy_input.json"
        raw_path.write_bytes(Path(strategy_json).read_bytes())
        spec = load_strategy_spec(raw_path)
        plan = compile_execution_plan(spec)
        record.update(strategy_id=spec.strategy_id, strategy_fingerprint=spec.fingerprint(),
                      versions={key: value for key, value in plan.items() if key.endswith("_version")})
        snapshot = out / "strategy_normalized.json"
        # Preserve scenario insertion order: sorting mapping keys would change
        # legacy NAV column/audit order even with the same semantic fingerprint.
        _save_json(snapshot, spec.to_dict())
        _save_json(out / "execution_plan.json", plan)
        complete("input")

        phase("preflight")
        preflight = preflight_strategy(snapshot, root)
        _save_json(out / "preflight.json", preflight)
        if preflight["status"] in {"capability_gap", "data_gap"}:
            record["gap_phase"] = preflight["phase"]
            return finish(preflight["status"], preflight["error"])
        if preflight["status"] != "ok" or preflight.get("ready_for_execution") is not True:
            raise ValueError("preflight did not authorize execution")
        if preflight["strategy_fingerprint"] != spec.fingerprint():
            raise ValueError("preflight fingerprint does not match the input snapshot")
        complete("preflight")

        if postprocess:
            phase("report_readiness")
            try:
                dates = expected_market_sessions(pd.Timestamp(preflight["krx_panel"]["actual_start"]),
                                                 pd.Timestamp(preflight["krx_panel"]["actual_end"]), "XKRX")
                readiness = canonical_report_readiness(dates, BacktestConfig(
                    book_start=spec.period.book_start, book_end=spec.period.book_end,
                    as_of_date=spec.period.as_of_date or spec.period.end,
                    standard_end_year=pd.Timestamp(spec.period.as_of_date or spec.period.end).year,
                    market_calendar="XKRX", initial_capital=spec.initial_capital,
                ))
            except (ValueError, AssertionError) as exc:
                error = {"type": type(exc).__name__, "message": str(exc)}
                _save_json(out / "report_readiness.json", {"ready": False, "error": error})
                return finish("data_gap", error)
            _save_json(out / "report_readiness.json", readiness)
            complete("report_readiness")

        phase("execution")
        if load_strategy_spec(snapshot).fingerprint() != spec.fingerprint():
            raise ValueError("input snapshot changed after preflight")
        work = out / "_execution"
        run_strategy(snapshot, root, work, postprocess=False)
        daily = _check_execution_artifacts(work, spec)
        work.rename(out / "artifacts")
        record["nav_ready"] = True
        record["outputs"]["daily_nav"] = "artifacts/daily_nav.csv"
        record["outputs"]["target_weights"] = "artifacts/target_weights.csv"
        record["artifacts"]["execution"] = _inventory(out / "artifacts")
        complete("execution")

        if postprocess:
            phase("postprocess")
            report_work = out / "_report"
            report_work.mkdir()
            try:
                process = run_current_postprocess(spec, root, report_work, daily, capture_output=True,
                                                  daily_csv=out / "artifacts/daily_nav.csv")
            except subprocess.CalledProcessError as exc:
                (out / "postprocess.log").write_text((exc.stdout or "") + (exc.stderr or ""), encoding="utf-8")
                raise
            if process is not None:
                (out / "postprocess.log").write_text((process.stdout or "") + (process.stderr or ""), encoding="utf-8")
            _check_report_artifacts(report_work, daily, spec)
            report_work.rename(out / "report")
            record["report_ready"] = True
            record["outputs"]["metrics"] = "report/metrics_CURRENT.csv"
            record["outputs"]["chat_manifest"] = "report/chat_manifest_CURRENT.json"
            record["artifacts"]["report"] = _inventory(out / "report")
            complete("postprocess")
        phase("complete")
        return finish("ok")
    except KeyboardInterrupt:
        return finish("interrupted", {"type": "KeyboardInterrupt", "message": "run interrupted; unfinished artifacts remain private"})
    except Exception as exc:
        status = "capability_gap" if record["phase"] == "input" and isinstance(exc, (KeyError, TypeError, ValueError)) else "failed"
        error = {"type": type(exc).__name__, "message": str(exc)}
        if hasattr(exc, "validation_path"):
            error["path"] = exc.validation_path
        return finish(status, error)
