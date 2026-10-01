from __future__ import annotations

"""Versioned machine contracts shared by Strategy DSL and execution modules."""

PROJECT_TEMPLATE_VERSION = "v2-16"
PERFORMANCE_TEMPLATE_VERSION = "v2-17"
EXECUTION_ENGINE_VERSION = "v2-16-exec-3"
CORPORATE_ACTION_REGISTRY_VERSION = "5"
DSL_MACHINE_CONTRACT_VERSION = "18"
KRX_MARKET_NORMALIZATION_VERSION = "1"
PREFLIGHT_CONTRACT_VERSION = "2"
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
