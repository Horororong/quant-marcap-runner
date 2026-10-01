from __future__ import annotations

"""Strategy DSL v1 for quant-marcap-runner.

The DSL is deliberately deterministic: AI or a human may author the JSON, but
execution consumes only a validated StrategySpec. No performance calculation
lives here; canonical metrics remain in quant_backtest_template_CURRENT.py.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Mapping, Sequence
import hashlib
import json
import re

from factor_registry import FACTOR_REGISTRY_VERSION, get_factor_definition, get_filter_definition, validate_factor_strategy_constraints
from execution_contract import (
    CORPORATE_ACTION_REGISTRY_VERSION,
    DECILE_RESEARCH_CONTRACT,
    DSL_MACHINE_CONTRACT_VERSION,
    EXECUTION_ENGINE_VERSION,
    PROJECT_TEMPLATE_VERSION,
    PERFORMANCE_TEMPLATE_VERSION,
    PREFLIGHT_CONTRACT_VERSION,
    HISTORY_AUDIT_CONTRACT_VERSION,
    KRX_MARKET_NORMALIZATION_VERSION,
    HELD_RETURN_TOLERANCE_BPS,
)

SCHEMA_VERSION = "1.0"
STRATEGY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
SUPPORTED_ASSET_CLASSES = {"kr_equity"}
SUPPORTED_FILTER_OPS = {
    "gt", "gte", "lt", "lte", "eq", "ne", "in", "not_in", "notnull",
    "top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct",
}
SUPPORTED_FACTOR_TRANSFORMS = {"identity", "inverse", "log1p"}
SUPPORTED_DIRECTIONS = {"high", "low"}
SUPPORTED_WEIGHTINGS = {"equal"}
SUPPORTED_PORTFOLIO_SELECTIONS = {"top_n", "deciles"}
SUPPORTED_REBALANCE_FREQUENCIES = {"months"}
SUPPORTED_TRADING_DAY_RULES = {"last"}
SUPPORTED_EXECUTION_PRICES = {"next_close"}
SUPPORTED_BENCHMARK_SOURCES = {"index"}
SUPPORTED_BENCHMARK_SYMBOLS = {"KOSPI", "KOSDAQ", "KOSPI200", "KOSDAQ150"}


def _as_tuple(value: Any, *, name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be an array")
    return tuple(value)


@dataclass(frozen=True)
class FilterSpec:
    field: str
    op: str
    value: Any = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FilterSpec":
        obj = cls(field=str(raw["field"]).strip(), op=str(raw["op"]).strip(), value=raw.get("value"))
        if not obj.field:
            raise ValueError("filter.field cannot be empty")
        get_filter_definition(obj.field)
        if obj.op not in SUPPORTED_FILTER_OPS:
            raise ValueError(f"unsupported filter op: {obj.op}")
        if obj.op != "notnull" and obj.value is None:
            raise ValueError(f"filter {obj.field}/{obj.op} requires value")
        if obj.op in {"top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct"}:
            pct = float(obj.value)
            if not (0.0 < pct < 100.0):
                raise ValueError("percentile filter value must be between 0 and 100")
        return obj


@dataclass(frozen=True)
class UniverseSpec:
    markets: tuple[str, ...] = ("KOSPI", "KOSDAQ")
    filters: tuple[FilterSpec, ...] = ()
    require_tradable_on_signal: bool = True

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "UniverseSpec":
        markets = tuple(str(x).upper().strip() for x in _as_tuple(raw.get("markets", ["KOSPI", "KOSDAQ"]), name="universe.markets"))
        if not markets:
            raise ValueError("universe.markets cannot be empty")
        bad = set(markets) - {"KOSPI", "KOSDAQ"}
        if bad:
            raise ValueError(f"unsupported KRX markets: {sorted(bad)}")
        filters = tuple(FilterSpec.from_dict(x) for x in raw.get("filters", []))
        return cls(markets=markets, filters=filters, require_tradable_on_signal=bool(raw.get("require_tradable_on_signal", True)))


@dataclass(frozen=True)
class FactorSpec:
    name: str
    source: str
    field: str
    direction: str
    weight: float = 1.0
    transform: str = "identity"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FactorSpec":
        obj = cls(
            name=str(raw["name"]).strip(),
            source=str(raw.get("source", "krx")).strip().lower(),
            field=str(raw["field"]).strip(),
            direction=str(raw["direction"]).strip().lower(),
            weight=float(raw.get("weight", 1.0)),
            transform=str(raw.get("transform", "identity")).strip().lower(),
        )
        if not obj.name or not obj.field:
            raise ValueError("factor name/field cannot be empty")
        get_factor_definition(obj.source, obj.field)
        if obj.direction not in SUPPORTED_DIRECTIONS:
            raise ValueError(f"unsupported factor direction: {obj.direction}")
        if obj.transform not in SUPPORTED_FACTOR_TRANSFORMS:
            raise ValueError(f"unsupported factor transform: {obj.transform}")
        if not (obj.weight > 0):
            raise ValueError("factor.weight must be > 0")
        return obj


@dataclass(frozen=True)
class PortfolioSpec:
    number_of_positions: int | None
    weighting: str = "equal"
    selection: str = "top_n"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PortfolioSpec":
        if not isinstance(raw, Mapping):
            raise TypeError("portfolio must be an object")
        selection = str(raw.get("selection", "top_n")).strip().lower()
        if selection not in SUPPORTED_PORTFOLIO_SELECTIONS:
            raise ValueError(f"unsupported portfolio selection: {selection}")
        number = raw.get("number_of_positions")
        if selection == "deciles":
            if number is not None:
                raise ValueError("deciles uses the full eligible universe; number_of_positions must be omitted or null")
        elif isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError("portfolio.number_of_positions must be an integer >= 1 for top_n")
        extra = set(raw) - {"number_of_positions", "weighting", "selection"}
        if extra:
            raise ValueError(f"unsupported portfolio fields: {sorted(extra)}")
        obj = cls(number_of_positions=number, weighting=str(raw.get("weighting", "equal")).lower(), selection=selection)
        if obj.weighting not in SUPPORTED_WEIGHTINGS:
            raise ValueError(f"unsupported weighting in DSL v1: {obj.weighting}")
        return obj


@dataclass(frozen=True)
class RebalanceSpec:
    frequency: str = "months"
    months: tuple[int, ...] = (4, 10)
    trading_day: str = "last"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RebalanceSpec":
        frequency = str(raw.get("frequency", "months")).lower()
        months = tuple(sorted(set(int(x) for x in _as_tuple(raw.get("months", [4, 10]), name="rebalance.months"))))
        trading_day = str(raw.get("trading_day", "last")).lower()
        if frequency not in SUPPORTED_REBALANCE_FREQUENCIES:
            raise ValueError(f"unsupported rebalance frequency: {frequency}")
        if any(m < 1 or m > 12 for m in months) or not months:
            raise ValueError("rebalance.months must contain months 1..12")
        if trading_day not in SUPPORTED_TRADING_DAY_RULES:
            raise ValueError(f"unsupported trading_day rule: {trading_day}")
        return cls(frequency=frequency, months=months, trading_day=trading_day)


@dataclass(frozen=True)
class ExecutionSpec:
    lag_sessions: int = 1
    price: str = "next_close"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExecutionSpec":
        obj = cls(lag_sessions=int(raw.get("lag_sessions", 1)), price=str(raw.get("price", "next_close")).lower())
        if obj.lag_sessions < 1:
            raise ValueError("execution.lag_sessions must be >= 1")
        if obj.price not in SUPPORTED_EXECUTION_PRICES:
            raise ValueError(f"unsupported execution price: {obj.price}")
        return obj


@dataclass(frozen=True)
class CostScenarioSpec:
    commission_bps: float = 0.0
    sell_tax_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CostScenarioSpec":
        obj = cls(**{k: float(raw.get(k, 0.0)) for k in cls.__dataclass_fields__})
        for k, v in asdict(obj).items():
            if v < 0:
                raise ValueError(f"cost {k} must be >= 0")
        return obj


@dataclass(frozen=True)
class BenchmarkSpec:
    source: str = "index"
    symbol: str = "KOSPI"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BenchmarkSpec":
        missing = {"source", "symbol"} - set(raw)
        if missing:
            raise ValueError(f"benchmark requires explicit fields: {sorted(missing)}")
        extra = set(raw) - {"source", "symbol"}
        if extra:
            raise ValueError(f"unsupported benchmark fields: {sorted(extra)}")
        obj = cls(
            source=str(raw["source"]).strip().lower(),
            symbol=str(raw["symbol"]).strip().upper(),
        )
        if obj.source not in SUPPORTED_BENCHMARK_SOURCES:
            raise ValueError(f"unsupported benchmark source: {obj.source}")
        if obj.symbol not in SUPPORTED_BENCHMARK_SYMBOLS:
            raise ValueError(
                f"unsupported benchmark symbol: {obj.symbol}; "
                f"supported={sorted(SUPPORTED_BENCHMARK_SYMBOLS)}"
            )
        return obj


@dataclass(frozen=True)
class PeriodSpec:
    start: str
    end: str
    book_start: str
    book_end: str
    as_of_date: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PeriodSpec":
        required = ("start", "end", "book_start", "book_end")
        missing = [k for k in required if not raw.get(k)]
        if missing:
            raise ValueError(f"period missing required fields: {missing}")
        return cls(**{k: raw.get(k) for k in ("start", "end", "book_start", "book_end", "as_of_date")})


@dataclass(frozen=True)
class StrategySpec:
    schema_version: str
    strategy_id: str
    title: str
    asset_class: str
    universe: UniverseSpec
    factors: tuple[FactorSpec, ...]
    portfolio: PortfolioSpec
    rebalance: RebalanceSpec
    execution: ExecutionSpec
    cost_scenarios: Mapping[str, CostScenarioSpec]
    period: PeriodSpec
    benchmark: BenchmarkSpec | None = None
    initial_capital: float = 10_000_000.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StrategySpec":
        version = str(raw.get("schema_version", "")).strip()
        if version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}; got {version!r}")
        strategy_id = str(raw.get("strategy_id", "")).strip().lower()
        if not STRATEGY_ID_RE.match(strategy_id):
            raise ValueError("strategy_id must match [a-z0-9][a-z0-9_-]{2,63}")
        title = str(raw.get("title", "")).strip()
        if not title:
            raise ValueError("title cannot be empty")
        asset_class = str(raw.get("asset_class", "")).strip().lower()
        if asset_class not in SUPPORTED_ASSET_CLASSES:
            raise ValueError(f"unsupported asset_class in DSL v1: {asset_class}")
        factors = tuple(FactorSpec.from_dict(x) for x in raw.get("factors", []))
        if not factors:
            raise ValueError("at least one factor is required")
        names = [x.name for x in factors]
        if len(names) != len(set(names)):
            raise ValueError("factor names must be unique")
        universe = UniverseSpec.from_dict(raw.get("universe", {}))
        rebalance = RebalanceSpec.from_dict(raw.get("rebalance", {}))
        validate_factor_strategy_constraints(factors, rebalance.months, universe.filters)
        costs_raw = raw.get("cost_scenarios", {})
        if not isinstance(costs_raw, Mapping) or not costs_raw:
            raise ValueError("cost_scenarios must be a non-empty object")
        costs = {str(k): CostScenarioSpec.from_dict(v) for k, v in costs_raw.items()}
        benchmark_raw = raw.get("benchmark")
        if benchmark_raw is not None and not isinstance(benchmark_raw, Mapping):
            raise TypeError("benchmark must be an object or null")
        benchmark = BenchmarkSpec.from_dict(benchmark_raw) if benchmark_raw is not None else None
        initial_capital = float(raw.get("initial_capital", 10_000_000.0))
        if initial_capital <= 0:
            raise ValueError("initial_capital must be > 0")
        return cls(
            schema_version=version,
            strategy_id=strategy_id,
            title=title,
            asset_class=asset_class,
            universe=universe,
            factors=factors,
            portfolio=PortfolioSpec.from_dict(raw["portfolio"]),
            rebalance=rebalance,
            execution=ExecutionSpec.from_dict(raw.get("execution", {})),
            cost_scenarios=costs,
            period=PeriodSpec.from_dict(raw["period"]),
            benchmark=benchmark,
            initial_capital=initial_capital,
            metadata=dict(raw.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        # Retain normalized JSON/fingerprints of existing top-N strategies.
        if self.portfolio.selection == "top_n":
            out["portfolio"].pop("selection")
        out["cost_scenarios"] = {k: asdict(v) for k, v in self.cost_scenarios.items()}
        return out

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_strategy_spec(path: str | Path) -> StrategySpec:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError("strategy JSON root must be an object")
    return StrategySpec.from_dict(raw)


def compile_execution_plan(spec: StrategySpec) -> dict[str, Any]:
    """Return a normalized, serializable plan that is stable across model runs."""
    return {
        "schema_version": spec.schema_version,
        "strategy_id": spec.strategy_id,
        "strategy_fingerprint": spec.fingerprint(),
        "factor_registry_version": FACTOR_REGISTRY_VERSION,
        "execution_engine_version": EXECUTION_ENGINE_VERSION,
        "corporate_action_registry_version": CORPORATE_ACTION_REGISTRY_VERSION,
        "dsl_machine_contract_version": DSL_MACHINE_CONTRACT_VERSION,
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
        "history_audit_contract_version": HISTORY_AUDIT_CONTRACT_VERSION,
        "krx_market_normalization_version": KRX_MARKET_NORMALIZATION_VERSION,
        "project_template_version": PROJECT_TEMPLATE_VERSION,
        "performance_template_version": PERFORMANCE_TEMPLATE_VERSION,
        "asset_class": spec.asset_class,
        "data_contract": {
            "price_universe": "data/krx_equities/yearly/marcap-YYYY.parquet",
            "factor_sources": sorted(
                {f.source for f in spec.factors}
                | {get_filter_definition(f.field).source for f in spec.universe.filters}
            ),
            "pit_required": True,
            "held_return_reference": "mandatory ChangesRatio/100 at execution; no automatic replacement of NAV returns",
            "held_return_tolerance_bps": HELD_RETURN_TOLERANCE_BPS,
            "session_coverage": "exact XKRX sessions in requested period for each requested market; fail on missing or unexpected dates",
        },
        "universe": asdict(spec.universe),
        "factors": [asdict(x) for x in spec.factors],
        "factor_contracts": [
            {
                "name": factor.name,
                "source": definition.source,
                "field": definition.field,
                "storage": definition.storage,
                "description": definition.description,
            }
            for factor in spec.factors
            for definition in [get_factor_definition(factor.source, factor.field)]
        ],
        "filter_contracts": [
            {
                "field": flt.field,
                "source": definition.source,
                "storage": definition.storage,
                "description": definition.description,
            }
            for flt in spec.universe.filters
            for definition in [get_filter_definition(flt.field)]
        ],
        "benchmark": asdict(spec.benchmark) if spec.benchmark is not None else None,
        "portfolio": asdict(spec.portfolio),
        "decile_contract": dict(DECILE_RESEARCH_CONTRACT) if spec.portfolio.selection == "deciles" else None,
        "rebalance": asdict(spec.rebalance),
        "execution": asdict(spec.execution),
        "cost_scenarios": {k: asdict(v) for k, v in spec.cost_scenarios.items()},
        "period": asdict(spec.period),
        "initial_capital": spec.initial_capital,
        "canonical_metrics_source": "scripts/quant_backtest_template_CURRENT.py",
        "project_engine": "scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py",
    }
