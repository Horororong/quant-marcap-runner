from __future__ import annotations

"""Versioned machine contracts shared by Strategy DSL and execution modules."""

PROJECT_TEMPLATE_VERSION = "v2-16"
PERFORMANCE_TEMPLATE_VERSION = "v2-17"
EXECUTION_ENGINE_VERSION = "v2-16-exec-3"
CORPORATE_ACTION_REGISTRY_VERSION = "5"
DSL_MACHINE_CONTRACT_VERSION = "21"
RUN_ORCHESTRATION_CONTRACT_VERSION = "1"
RUN_EXIT_CODES = {"ok": 0, "capability_gap": 2, "data_gap": 3, "failed": 4, "interrupted": 130}
RUN_ORCHESTRATION_CONTRACT = {
    "version": RUN_ORCHESTRATION_CONTRACT_VERSION,
    "command": "python scripts/strategy_dsl_runner.py <strategy.json>",
    "execution_only_command": "python scripts/strategy_dsl_runner.py <strategy.json> --execution-only",
    "python_entry_point": "scripts/strategy_dsl_run.py:run_checked_strategy",
    "automatic_preflight": True,
    "default_output": "results/dsl/runs/{unique_run_id}",
    "explicit_output": "--output-dir must name a new directory; existing runs are never overwritten",
    "status_file": "run_status.json",
    "statuses": ["running", *RUN_EXIT_CODES],
    "exit_codes": RUN_EXIT_CODES,
    "stages": ["input", "preflight", "report_readiness", "execution", "postprocess", "complete"],
    "input": "raw and canonical DSL snapshots; same canonical snapshot used for preflight and execution",
    "success": "ok requires validated NAV; canonical_report mode additionally requires validated CURRENT four-period/nine-chart outputs",
    "execution_only": "ok with nav_ready=true and report_ready=false; research NAV, no standard performance claim",
    "report_readiness": "CURRENT date/period policy checked before NAV; insufficient formal history is data_gap, never automatic research fallback",
    "failure": "stage and typed error persist; postprocess failure can retain nav_ready=true while report_ready=false and status=failed",
    "publication": "execution and report directories renamed from private staging only after their checks pass",
    "outputs": ["run_status.json", "strategy_input.json", "strategy_normalized.json", "execution_plan.json", "preflight.json",
                "report_readiness.json (formal mode)", "artifacts/daily_nav.csv", "artifacts/target_weights.csv",
                "report/metrics_CURRENT.csv (formal success)", "report/chat_manifest_CURRENT.json (formal success)"],
    "reproducibility_scope": "strategy snapshot and component contract versions; full source hashes/package manifest are a follow-up",
}
KRX_MARKET_NORMALIZATION_VERSION = "1"
PREFLIGHT_CONTRACT_VERSION = "3"
HISTORY_AUDIT_CONTRACT_VERSION = "1"
CORPORATE_ACTION_RECONCILIATION_VERSION = "1"
HELD_RETURN_TOLERANCE_BPS = 1.0

DECILE_RESEARCH_CONTRACT = {
    "version": "1",
    "bucket_count": 10,
    "ordering": "D01 best composite score, D10 worst",
    "partition": "contiguous balanced buckets; remainder assigned to best buckets first",
    "tie_policy": "composite_score ascending, then zero-padded Code ascending; ties may split",
    "minimum_eligible_universe": 10,
    "small_universe_policy": "error",
    "missing_factor_policy": "exclude intersection before ranking, same as top_n",
    "weighting": "equal within each bucket",
    "capital": "initial_capital applies independently to each of ten long-only portfolios",
    "execution": "same PROJECT engine, lag, tradability, costs and verified corporate actions",
    "metrics": "CURRENT postprocess only; no synthetic long-short spread NAV",
}

# Offline delivery is additive; factor, execution and performance versions stay unchanged.
from sandbox_bootstrap import KIT_CONTRACT_VERSION, SUPPORTED_PYTHON

SANDBOX_DISTRIBUTION_CONTRACT = {
    "version": KIT_CONTRACT_VERSION,
    "builder": "scripts/build_sandbox_kit.py",
    "bootstrap": "bootstrap_quant.py --destination <new-directory>",
    "runner": "scripts/sandbox_runtime.py",
    "instructions": "SANDBOX_START_HERE.md",
    "python_minors": list(SUPPORTED_PYTHON),
    "platform": "CPython Linux x86_64 glibc >= 2.28",
    "installation": "isolated venv; exact hashed wheels; no index, downloads or implicit dependencies",
    "integrity": "pinned clean Git commit; SHA256 code/data/transport; reject unexpected sources",
    "execution": "same run_checked_strategy; strict DSL before data; no metric implementation",
    "coverage": "manifest inventories original whole panels/shards; every request still requires preflight",
    "exports": "verified published artifacts, raw/normalized DSL, status, kit and execution manifests",
    "reproducibility_scope": "kit identity, source hashes, contract versions, actual Python/packages and DSL fingerprint",
    "default_profile": "2020 DART value and size deciles; 2024 verified split; execution-only research NAV",
}
