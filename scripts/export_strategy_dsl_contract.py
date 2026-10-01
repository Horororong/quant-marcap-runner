from __future__ import annotations

"""Generate/check the machine-readable Strategy DSL contract."""

from pathlib import Path
import argparse
import json

from execution_contract import (
    CORPORATE_ACTION_REGISTRY_VERSION,
    CORPORATE_ACTION_RECONCILIATION_VERSION,
    DECILE_RESEARCH_CONTRACT,
    DSL_MACHINE_CONTRACT_VERSION,
    EXECUTION_ENGINE_VERSION,
    PROJECT_TEMPLATE_VERSION,
    PERFORMANCE_TEMPLATE_VERSION,
    PREFLIGHT_CONTRACT_VERSION,
    HISTORY_AUDIT_CONTRACT_VERSION,
    KRX_MARKET_NORMALIZATION_VERSION,
    HELD_RETURN_TOLERANCE_BPS,
    RUN_ORCHESTRATION_CONTRACT,
)
from factor_registry import FACTOR_REGISTRY_VERSION, factor_catalog, factor_source_constraints, filter_field_catalog
from krx_technical_factor_adapter import technical_factor_catalog
from krx_history_audit import PRICE_DIFFERENCE_THRESHOLD_BPS
from krx_market_normalization import MARKET_LABELS
from strategy_dsl_aliases import alias_catalog, direction_alias_catalog
from strategy_dsl import (
    build_strategy_json_schema,
    INPUT_VALIDATION_CONTRACT,
    SCHEMA_VERSION,
    SUPPORTED_ASSET_CLASSES,
    SUPPORTED_BENCHMARK_SOURCES,
    SUPPORTED_BENCHMARK_SYMBOLS,
    SUPPORTED_DIRECTIONS,
    SUPPORTED_EXECUTION_PRICES,
    SUPPORTED_FACTOR_TRANSFORMS,
    SUPPORTED_FILTER_OPS,
    SUPPORTED_PORTFOLIO_SELECTIONS,
    SUPPORTED_REBALANCE_FREQUENCIES,
    SUPPORTED_TRADING_DAY_RULES,
    SUPPORTED_WEIGHTINGS,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config/strategy_dsl_schema_v1.json"
CAPABILITIES_PATH = ROOT / "config/strategy_dsl_capabilities_v1.json"


def build_capabilities() -> dict:
    return {
        "dsl_machine_contract_version": DSL_MACHINE_CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "input_validation": INPUT_VALIDATION_CONTRACT,
        "run_orchestration": RUN_ORCHESTRATION_CONTRACT,
        "project_template_version": PROJECT_TEMPLATE_VERSION,
        "performance_template_version": PERFORMANCE_TEMPLATE_VERSION,
        "execution_engine_version": EXECUTION_ENGINE_VERSION,
        "factor_registry_version": FACTOR_REGISTRY_VERSION,
        "corporate_action_registry_version": CORPORATE_ACTION_REGISTRY_VERSION,
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
        "history_audit_contract_version": HISTORY_AUDIT_CONTRACT_VERSION,
        "krx_market_normalization_version": KRX_MARKET_NORMALIZATION_VERSION,
        "krx_market_normalization": {
            "source_to_canonical": dict(MARKET_LABELS),
            "source_label_field": "SourceMarket",
            "unknown_label_policy": "fail before write; no prefix guessing",
            "segment_membership": "historically observed provenance only; never an eligibility or survival filter",
            "canonical_equity_markets": ["KOSPI", "KOSDAQ"],
        },
        "asset_classes": sorted(SUPPORTED_ASSET_CLASSES),
        "markets": ["KOSPI", "KOSDAQ"],
        "benchmarks": {
            "sources": sorted(SUPPORTED_BENCHMARK_SOURCES),
            "symbols": sorted(SUPPORTED_BENCHMARK_SYMBOLS),
            "path_template": "data/indices/{symbol}.csv",
            "alignment": "exact strategy daily dates; no forward fill",
            "output_series": "NAV_Benchmark",
            "audit_output": "benchmark_coverage.json",
            "return_basis": "price_index_close",
            "includes_dividends": False,
            "normalization": "first exact strategy date = 1.0",
        },
        "filter_ops": sorted(SUPPORTED_FILTER_OPS),
        "filter_fields": filter_field_catalog(),
        "factor_transforms": sorted(SUPPORTED_FACTOR_TRANSFORMS),
        "factor_directions": sorted(SUPPORTED_DIRECTIONS),
        "factors": factor_catalog(),
        "technical_factors": technical_factor_catalog(),
        "factor_source_constraints": factor_source_constraints(),
        "natural_language_factor_aliases": alias_catalog(),
        "natural_language_direction_aliases": direction_alias_catalog(),
        "portfolio_weightings": sorted(SUPPORTED_WEIGHTINGS),
        "portfolio_selections": sorted(SUPPORTED_PORTFOLIO_SELECTIONS),
        "decile_research": {
            **DECILE_RESEARCH_CONTRACT,
            "request": {"portfolio": {"selection": "deciles", "weighting": "equal"}},
            "command": "python scripts/strategy_dsl_runner.py <decile_strategy.json>",
            "outputs": ["daily_nav.csv", "decile_membership.csv", "decile_partition_audit.csv", "decile_contract.json", "target_weights.csv", "execution_schedule.csv", "execution_trades.csv", "D01..D10/daily_nav.csv", "D01..D10/target_weights.csv"],
            "target_weights_layout": "root long format signal_date, decile, Code, target_weight; bucket directories wide format",
            "population_check": "at execution after all filters and factor missing-value intersection; preflight normally checks sources only; relevant known event gaps trigger shared selection and a planned exposure gate",
            "research_window_command": "python scripts/strategy_dsl_runner.py <decile_strategy.json> --execution-only",
        },
        "rebalance_frequencies": sorted(SUPPORTED_REBALANCE_FREQUENCIES),
        "trading_day_rules": sorted(SUPPORTED_TRADING_DAY_RULES),
        "execution_prices": sorted(SUPPORTED_EXECUTION_PRICES),
        "execution_constraints": {
            "minimum_lag_sessions": 1,
            "lookahead_prevention": "signal-date information cannot be executed before a later trading session",
            "held_return_reference": "mandatory in public DSL runners: decimal ChangesRatio/100 checked before NAV and before execution-day rebalance",
            "held_return_tolerance_bps": HELD_RETURN_TOLERANCE_BPS,
            "held_return_failure_policy": "fail on missing/non-finite reference or inconsistent effective held return; never substitute reference for NAV return",
        },
        "preflight": {
            "history_coverage": "exact XKRX sessions for each requested market; does not certify security-level or corporate-action completeness",
            "command": "python scripts/strategy_dsl_preflight.py <strategy.json>",
            "always_zero_command": "python scripts/strategy_dsl_preflight.py <strategy.json> --always-zero",
            "statuses": ["ok", "capability_gap", "data_gap"],
            "exit_codes": {
                "ok": 0,
                "capability_gap": 2,
                "data_gap": 3,
            },
            "classification": {
                "capability_gap": "strategy cannot be represented by the current DSL/registry contract",
                "data_gap": "strategy is representable but required PIT data is unavailable or incomplete",
            },
            "known_event_gate": "relevant config/kr_corporate_action_gaps.json entries trigger shared factor/target selection and exact lag/lineage trace; planned exposure is data_gap before NAV",
            "known_event_scope": "known gaps only; does not certify unregistered events, drift, tradability, returns or costs",
            "does_not_compute": ["NAV", "return drift", "trading costs", "performance metrics"],
        },
        "ai_workflow": [
            "read config/strategy_dsl_capabilities_v1.json",
            "resolve registered natural-language aliases only",
            "generate config/strategy_dsl_schema_v1.json-constrained Strategy DSL",
            "run strategy_dsl_runner.py --validate-only",
            "optionally inspect strategy_dsl_preflight.py readiness",
            "execute via strategy_dsl_runner.py: mandatory automatic preflight and CURRENT date/period readiness",
            "read run_status.json; formal success requires nav_ready and report_ready; --execution-only requests research NAV explicitly",
        ],
        "corporate_actions": {
            "supported_event_types": ["stock_merger", "stock_split", "cash_share_exchange"],
            "cash_exchange_contract": {
                "entitlement": "completed legal exchange; no successor; share_ratio=0; fixed positive KRW cash_per_share",
                "payment": "payment_date and payment_source URL with payment_status=verified_actual; planned dates rejected",
                "valuation": "nominal fixed receivable, no interest, discount, withholding, credit risk or partial settlement",
                "liquidity": "receivable contributes to NAV but cannot fund target weights or costs; reject rather than scale targets",
                "suspension": "observed flat closes, original Volume=0 and exchange reference=0 required",
                "receipt": "first observed session close on/after actual payment; zero turnover/cost and no second return",
                "reconciliation": "cash disposal candidate reconciliation remains unsupported",
                "actual_coverage": "no cash exchange in production registry; Jeisys actual payment evidence unresolved",
                "known_gap_policy": "config/kr_corporate_action_gaps.json blocks affected holdings from entitlement date; no survival exclusion",
            },
            "merger_contract": "stock-only succession with zero cash_per_share; mixed stock/cash mergers rejected",
            "split_contract": "same code, shares_after/shares_before > 0, zero cash; event_date is trading resumption; adjusted event return still checked against exchange reference",
            "registry": "config/kr_corporate_actions.csv",
            "unregistered_held_price_gap_policy": "fail",
            "history_completeness": "unverified; presence of registered events is not a coverage certificate",
        },
        "corporate_action_reconciliation": {
            "version": CORPORATE_ACTION_RECONCILIATION_VERSION,
            "command": "python scripts/corporate_action_reconciliation.py --start YYYY-MM-DD --end YYYY-MM-DD --output-dir <audit_dir>",
            "outputs": ["corporate_action_reconciliation.json", "registry_event_checks.csv", "candidate_reconciliation.csv"],
            "match_policy": "exact Code and event date; manually evidenced same-code split, observed suspension and adjusted exchange return agreement within held tolerance",
            "candidate_policy": "retain every candidate; never change eligibility, holdings, NAV or registry; merger disposal reconciliation unsupported",
            "exit_codes": {"available_registered_split_checks_pass": 0, "data_gap_or_event_mismatch": 3},
        },
        "history_audit": {
            "command": "python scripts/krx_history_audit.py --start YYYY-MM-DD --end YYYY-MM-DD --output-dir <audit_dir>",
            "outputs": ["history_audit.json", "security_observation_coverage.csv", "history_review_candidates.csv"],
            "price_difference_threshold_bps": PRICE_DIFFERENCE_THRESHOLD_BPS,
            "candidate_policy": "diagnostics only; never infer events, cash flows or universe exclusions",
            "exit_codes": {"market_session_complete": 0, "data_gap": 3},
            "completeness_scope": "market-session presence; registered corporate-action history remains unverified",
        },
        "canonical_performance": {
            "template_version": PERFORMANCE_TEMPLATE_VERSION,
            "source": "scripts/quant_backtest_template_CURRENT.py",
            "periods": ["book_validation", "from_2001", "from_2021", "longest"],
            "dsl_market_calendar": "XKRX",
            "daily_coverage": "exact sessions; mismatch stops report before canonical outputs",
            "benchmark_statistics_output": "benchmark_statistics_CURRENT.csv (only with explicit benchmark)",
            "metrics_added": ["누적수익률", "Sortino", "Calmar", "월간승률"],
            "zero_denominator_policy": "NaN; never fabricate infinity or zero",
        },
        "canonical_outputs": [
            "daily_nav.csv",
            "target_weights.csv",
            "selections.csv",
            "execution_plan.json",
            "strategy_fingerprint.txt",
            "factor_provider_coverage.csv",
            "history_coverage.json",
            "return_reference_audit.json",
            "held_return_checks.csv",
            "corporate_actions_applied.csv",
            "cash_entitlements.csv (when held cash exchanges occur)",
            "cash_payments.csv (when received within window)",
            "cash_balances_{gross|net}_{scenario}.csv (cash exchange runs)",
            "metrics_CURRENT.csv",
            "chat_manifest_CURRENT.json",
        ],
        "unsupported": [
            "DART factors beyond the registered catalog",
            "parameterized momentum/technical lookbacks",
            "dynamic historical sell-tax schedules",
            "next-open or VWAP execution",
            "market-cap or factor-weighted portfolios",
            "ETF/macro/asset-allocation DSL",
            "unregistered corporate-action or delisting cash-flow assumptions",
        ],
    }


def render_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def contract_files() -> dict[Path, str]:
    return {
        SCHEMA_PATH: render_json(build_strategy_json_schema()),
        CAPABILITIES_PATH: render_json(build_capabilities()),
    }


def write_contract_files() -> None:
    for path, content in contract_files().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_contract_files() -> None:
    stale = []
    for path, expected in contract_files().items():
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != expected:
            stale.append(str(path.relative_to(ROOT)))
    if stale:
        raise SystemExit(
            "Strategy DSL machine contract files are missing/stale: "
            + ", ".join(stale)
            + ". Run: python scripts/export_strategy_dsl_contract.py --write"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.write:
        write_contract_files()
        print(SCHEMA_PATH.relative_to(ROOT))
        print(CAPABILITIES_PATH.relative_to(ROOT))
    else:
        check_contract_files()
        print("STRATEGY DSL MACHINE CONTRACT: PASS")


if __name__ == "__main__":
    main()
