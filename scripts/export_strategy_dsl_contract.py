from __future__ import annotations

"""Generate/check the machine-readable Strategy DSL contract."""

from pathlib import Path
import argparse
import json

from execution_contract import (
    CORPORATE_ACTION_REGISTRY_VERSION,
    DSL_MACHINE_CONTRACT_VERSION,
    EXECUTION_ENGINE_VERSION,
    PROJECT_TEMPLATE_VERSION,
    PREFLIGHT_CONTRACT_VERSION,
)
from factor_registry import FACTOR_REGISTRY_VERSION, factor_catalog, factor_source_constraints, filter_field_catalog, filterable_fields, supported_fields, supported_sources
from krx_technical_factor_adapter import technical_factor_catalog
from strategy_dsl_aliases import alias_catalog, direction_alias_catalog
from strategy_dsl import (
    SCHEMA_VERSION,
    STRATEGY_ID_RE,
    SUPPORTED_ASSET_CLASSES,
    SUPPORTED_BENCHMARK_SOURCES,
    SUPPORTED_BENCHMARK_SYMBOLS,
    SUPPORTED_DIRECTIONS,
    SUPPORTED_EXECUTION_PRICES,
    SUPPORTED_FACTOR_TRANSFORMS,
    SUPPORTED_FILTER_OPS,
    SUPPORTED_REBALANCE_FREQUENCIES,
    SUPPORTED_TRADING_DAY_RULES,
    SUPPORTED_WEIGHTINGS,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config/strategy_dsl_schema_v1.json"
CAPABILITIES_PATH = ROOT / "config/strategy_dsl_capabilities_v1.json"


def _factor_source_field_constraint() -> dict:
    variants = []
    for source in supported_sources():
        variants.append({
            "properties": {
                "source": {"const": source},
                "field": {"enum": supported_fields(source)},
            },
            "required": ["source", "field"],
        })
    return {"oneOf": variants}


def build_strategy_json_schema() -> dict:
    factor_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "source", "field", "direction"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "source": {"type": "string"},
            "field": {"type": "string"},
            "direction": {"enum": sorted(SUPPORTED_DIRECTIONS)},
            "weight": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
            "transform": {"enum": sorted(SUPPORTED_FACTOR_TRANSFORMS), "default": "identity"},
        },
        "allOf": [_factor_source_field_constraint()],
    }
    filter_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "op"],
        "properties": {
            "field": {"enum": filterable_fields()},
            "op": {"enum": sorted(SUPPORTED_FILTER_OPS)},
            "value": {},
        },
    }
    cost_item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: {"type": "number", "minimum": 0, "default": 0.0}
            for name in (
                "commission_bps",
                "sell_tax_bps",
                "spread_bps",
                "slippage_bps",
                "market_impact_bps",
            )
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "strategy_dsl_schema_v1.json",
        "title": "quant-marcap-runner Strategy DSL",
        "description": "Machine contract for deterministic Korean-equity Strategy DSL generation.",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "strategy_id",
            "title",
            "asset_class",
            "universe",
            "factors",
            "portfolio",
            "rebalance",
            "execution",
            "cost_scenarios",
            "period",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "strategy_id": {"type": "string", "pattern": STRATEGY_ID_RE.pattern},
            "title": {"type": "string", "minLength": 1},
            "asset_class": {"enum": sorted(SUPPORTED_ASSET_CLASSES)},
            "universe": {
                "type": "object",
                "additionalProperties": False,
                "required": ["markets"],
                "properties": {
                    "markets": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"enum": ["KOSPI", "KOSDAQ"]},
                    },
                    "filters": {
                        "type": "array",
                        "items": filter_item,
                        "default": [],
                    },
                    "require_tradable_on_signal": {"type": "boolean", "default": True},
                },
            },
            "factors": {"type": "array", "minItems": 1, "items": factor_item},
            "portfolio": {
                "type": "object",
                "additionalProperties": False,
                "required": ["number_of_positions", "weighting"],
                "properties": {
                    "number_of_positions": {"type": "integer", "minimum": 1},
                    "weighting": {"enum": sorted(SUPPORTED_WEIGHTINGS)},
                },
            },
            "rebalance": {
                "type": "object",
                "additionalProperties": False,
                "required": ["frequency", "months", "trading_day"],
                "properties": {
                    "frequency": {"enum": sorted(SUPPORTED_REBALANCE_FREQUENCIES)},
                    "months": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "integer", "minimum": 1, "maximum": 12},
                    },
                    "trading_day": {"enum": sorted(SUPPORTED_TRADING_DAY_RULES)},
                },
            },
            "execution": {
                "type": "object",
                "additionalProperties": False,
                "required": ["lag_sessions", "price"],
                "properties": {
                    "lag_sessions": {"type": "integer", "minimum": 1},
                    "price": {"enum": sorted(SUPPORTED_EXECUTION_PRICES)},
                },
            },
            "cost_scenarios": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": cost_item,
            },
            "benchmark": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["source", "symbol"],
                "properties": {
                    "source": {"enum": sorted(SUPPORTED_BENCHMARK_SOURCES)},
                    "symbol": {"enum": sorted(SUPPORTED_BENCHMARK_SYMBOLS)},
                },
            },
            "period": {
                "type": "object",
                "additionalProperties": False,
                "required": ["start", "end", "book_start", "book_end"],
                "properties": {
                    "start": {"type": "string", "format": "date"},
                    "end": {"type": "string", "format": "date"},
                    "book_start": {"type": "string", "format": "date"},
                    "book_end": {"type": "string", "format": "date"},
                    "as_of_date": {"type": ["string", "null"], "format": "date"},
                },
            },
            "initial_capital": {"type": "number", "exclusiveMinimum": 0, "default": 10000000},
            "metadata": {"type": "object", "additionalProperties": True},
        },
    }


def build_capabilities() -> dict:
    return {
        "dsl_machine_contract_version": DSL_MACHINE_CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "project_template_version": PROJECT_TEMPLATE_VERSION,
        "execution_engine_version": EXECUTION_ENGINE_VERSION,
        "factor_registry_version": FACTOR_REGISTRY_VERSION,
        "corporate_action_registry_version": CORPORATE_ACTION_REGISTRY_VERSION,
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
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
        "rebalance_frequencies": sorted(SUPPORTED_REBALANCE_FREQUENCIES),
        "trading_day_rules": sorted(SUPPORTED_TRADING_DAY_RULES),
        "execution_prices": sorted(SUPPORTED_EXECUTION_PRICES),
        "execution_constraints": {
            "minimum_lag_sessions": 1,
            "lookahead_prevention": "signal-date information cannot be executed before a later trading session",
        },
        "preflight": {
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
            "does_not_compute": ["factor values", "holdings", "NAV", "performance metrics"],
        },
        "ai_workflow": [
            "read config/strategy_dsl_capabilities_v1.json",
            "resolve registered natural-language aliases only",
            "generate config/strategy_dsl_schema_v1.json-constrained Strategy DSL",
            "run strategy_dsl_runner.py --validate-only",
            "run strategy_dsl_preflight.py",
            "execute only when preflight status is ok",
            "run canonical CURRENT postprocess for formal metrics",
        ],
        "corporate_actions": {
            "supported_event_types": ["stock_merger"],
            "registry": "config/kr_corporate_actions.csv",
            "unregistered_held_price_gap_policy": "fail",
        },
        "canonical_outputs": [
            "daily_nav.csv",
            "target_weights.csv",
            "selections.csv",
            "execution_plan.json",
            "strategy_fingerprint.txt",
            "factor_provider_coverage.csv",
            "corporate_actions_applied.csv",
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
