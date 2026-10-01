from __future__ import annotations

"""Preflight Strategy DSL requests before expensive backtest execution.

The preflight separates two failure classes:
- capability_gap: the requested strategy cannot be represented by the current DSL.
- data_gap: the strategy is representable, but required PIT data is unavailable/incomplete.

Known evidence gaps additionally trigger shared signal selection and a planned
holding trace. The no-known-gap fast path stays source-only. NAV, return drift,
trading costs and performance are never calculated here.
"""

from pathlib import Path
from typing import Any
import argparse
import json
import traceback

import pandas as pd

from corporate_action_preflight import check_known_action_exposure, CorporateActionEvidenceGap
from execution_contract import PREFLIGHT_CONTRACT_VERSION
from krx_history_audit import require_session_coverage
from strategy_dsl import compile_execution_plan, load_strategy_spec
from strategy_dsl_runner import (
    benchmark_coverage_audit,
    factor_provider_coverage_audit,
    load_project_engine,
    required_panel_columns,
    signal_dates_from_panel,
)

EXIT_OK = 0
EXIT_CAPABILITY_GAP = 2
EXIT_DATA_GAP = 3


def _error_payload(
    *,
    status: str,
    phase: str,
    exc: BaseException,
    strategy_id: str | None = None,
    strategy_fingerprint: str | None = None,
) -> dict[str, Any]:
    result = {
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
        "status": status,
        "ready_for_execution": False,
        "phase": phase,
        "strategy_id": strategy_id,
        "strategy_fingerprint": strategy_fingerprint,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    if hasattr(exc, "corporate_action_audit"):
        result["corporate_action_audit"] = exc.corporate_action_audit
    if hasattr(exc, "history_coverage"):
        result["history_coverage"] = exc.history_coverage
    if hasattr(exc, "validation_path"):
        result["error"]["path"] = exc.validation_path
    return result


def preflight_strategy(
    strategy_json: str | Path,
    repo_root: str | Path,
) -> dict[str, Any]:
    strategy_path = Path(strategy_json)
    root = Path(repo_root).resolve()

    # Phase 1: representability / deterministic compile contract.
    try:
        spec = load_strategy_spec(strategy_path)
        plan = compile_execution_plan(spec)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return _error_payload(
            status="capability_gap",
            phase="compile",
            exc=exc,
        )

    strategy_id = spec.strategy_id
    fingerprint = spec.fingerprint()

    # Phase 2: PIT data availability only. Do not calculate factors or NAV here.
    try:
        engine = load_project_engine(root)
        panel = engine.load_krx_equity_panel(
            start=spec.period.start,
            end=spec.period.end,
            markets=spec.universe.markets,
            columns=required_panel_columns(spec),
            repo_root=root,
        )
        panel = panel.copy()
        history_coverage = require_session_coverage(panel, spec.period.start, spec.period.end, spec.universe.markets)
        panel["Date"] = pd.to_datetime(panel["Date"]).dt.normalize()
        dates = pd.DatetimeIndex(panel["Date"].dropna().unique()).sort_values()
        signal_dates = signal_dates_from_panel(panel, spec)
        provider_coverage = factor_provider_coverage_audit(panel, spec, root)
        benchmark_coverage = benchmark_coverage_audit(root, spec.benchmark, dates)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        return _error_payload(
            status="data_gap",
            phase="data",
            exc=exc,
            strategy_id=strategy_id,
            strategy_fingerprint=fingerprint,
        )
    except (KeyError, TypeError, ValueError, AssertionError) as exc:
        # A valid DSL can still expose a data-contract/schema problem at load time.
        return _error_payload(
            status="data_gap",
            phase="data_contract",
            exc=exc,
            strategy_id=strategy_id,
            strategy_fingerprint=fingerprint,
        )

    # Known events can be present in a universe yet absent from selected
    # holdings. Trace the shared signal plan before reporting readiness.
    try:
        corporate_action_audit = check_known_action_exposure(panel, spec, root, engine)
    except CorporateActionEvidenceGap as exc:
        return _error_payload(status="data_gap", phase="corporate_actions", exc=exc,
                              strategy_id=strategy_id, strategy_fingerprint=fingerprint)
    except (FileNotFoundError, RuntimeError, OSError, KeyError, TypeError, ValueError, AssertionError) as exc:
        return _error_payload(status="data_gap", phase="corporate_action_selection_contract", exc=exc,
                              strategy_id=strategy_id, strategy_fingerprint=fingerprint)

    coverage_rows: list[dict[str, Any]] = []
    if not provider_coverage.empty:
        for row in provider_coverage.to_dict(orient="records"):
            normalized = {}
            for key, value in row.items():
                if isinstance(value, pd.Timestamp):
                    normalized[key] = value.date().isoformat()
                elif pd.isna(value):
                    normalized[key] = None
                elif hasattr(value, "item"):
                    normalized[key] = value.item()
                else:
                    normalized[key] = value
            coverage_rows.append(normalized)

    codes = panel["Code"].astype(str).str.zfill(6)

    return {
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
        "status": "ok",
        "phase": "ready",
        "strategy_id": strategy_id,
        "strategy_fingerprint": fingerprint,
        "versions": {
            "schema_version": plan["schema_version"],
            "dsl_machine_contract_version": plan.get("dsl_machine_contract_version"),
            "factor_registry_version": plan.get("factor_registry_version"),
            "execution_engine_version": plan.get("execution_engine_version"),
            "corporate_action_registry_version": plan.get("corporate_action_registry_version"),
            "project_template_version": plan.get("project_template_version"),
        },
        "requested_period": {
            "start": spec.period.start,
            "end": spec.period.end,
        },
        "krx_panel": {
            "actual_start": pd.Timestamp(dates[0]).date().isoformat(),
            "actual_end": pd.Timestamp(dates[-1]).date().isoformat(),
            "rows": int(len(panel)),
            "distinct_codes": int(codes.nunique()),
            "markets": sorted(panel["Market"].astype(str).unique().tolist()),
        },
        "signal_dates": [pd.Timestamp(x).date().isoformat() for x in signal_dates],
        "factor_sources": list(plan["data_contract"]["factor_sources"]),
        "provider_coverage": coverage_rows,
        "corporate_action_audit": corporate_action_audit,
        "history_coverage": history_coverage,
        "benchmark": benchmark_coverage,
        "ready_for_execution": True,
    }


def exit_code_for(result: dict[str, Any]) -> int:
    status = result.get("status")
    if status == "ok":
        return EXIT_OK
    if status == "capability_gap":
        return EXIT_CAPABILITY_GAP
    if status == "data_gap":
        return EXIT_DATA_GAP
    raise ValueError(f"unknown preflight status: {status!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy_json", type=Path)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument(
        "--always-zero",
        action="store_true",
        help="print the structured gap result but return exit code 0; useful for orchestration that branches on JSON",
    )
    args = ap.parse_args()

    result = preflight_strategy(args.strategy_json, args.repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.always_zero:
        raise SystemExit(exit_code_for(result))


if __name__ == "__main__":
    main()
