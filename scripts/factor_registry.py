from __future__ import annotations

"""Central factor catalog and provider registry for Strategy DSL.

The Strategy DSL validator asks this module whether a factor reference is
supported. The generic runner asks this module how each factor is supplied.
Adding a new factor source should therefore require a registry/provider change,
not edits to the ranking engine.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence, runtime_checkable

import pandas as pd

from krx_technical_factor_adapter import TECHNICAL_FACTOR_SPECS

FACTOR_REGISTRY_VERSION = "5"


@dataclass(frozen=True)
class FactorDefinition:
    source: str
    field: str
    storage: str  # "panel" or "external"
    description: str

    def __post_init__(self) -> None:
        if self.storage not in {"panel", "external"}:
            raise ValueError(f"invalid factor storage: {self.storage}")


FACTOR_DEFINITIONS: dict[tuple[str, str], FactorDefinition] = {}

FACTOR_SOURCE_CONSTRAINTS: dict[str, dict] = {
    "dart": {
        "rebalance_months": (4, 10),
        "reason": (
            "current DART value adapter reconstructs standalone Q4 for April "
            "and Q2 for October signals only"
        ),
    },
}


def register_factor(definition: FactorDefinition) -> None:
    key = (definition.source, definition.field)
    if key in FACTOR_DEFINITIONS:
        raise ValueError(f"duplicate factor definition: {key}")
    FACTOR_DEFINITIONS[key] = definition


# KRX fields already present in the daily PIT panel.
for _field, _description in {
    "Open": "signal-date open price",
    "High": "signal-date high price",
    "Low": "signal-date low price",
    "Close": "signal-date close price",
    "Volume": "signal-date traded volume",
    "Amount": "signal-date traded amount",
    "Marcap": "signal-date market capitalization",
    "Stocks": "signal-date listed share count",
    "ChangesRatio": "signal-date percentage price change",
    "Change": "signal-date decimal price change",
}.items():
    register_factor(FactorDefinition("krx", _field, "panel", _description))


# Standardized DART PIT value/profitability factors.
for _field, _description in {
    "earnings_yield": "standalone-quarter net income / signal-date market cap",
    "book_to_price": "latest reported equity / signal-date market cap",
    "cashflow_yield": "standalone-quarter operating cash flow / signal-date market cap",
    "sales_yield": "standalone-quarter revenue / signal-date market cap",
    "quarterly_roe": "standalone-quarter net income / latest reported positive equity",
    "quarterly_net_margin": "standalone-quarter net income / positive standalone-quarter revenue",
    "quarterly_ocf_margin": "standalone-quarter operating cash flow / positive standalone-quarter revenue",
}.items():
    register_factor(FactorDefinition("dart", _field, "external", _description))


# KRX exchange-reported technical factors.
for _field, _spec in TECHNICAL_FACTOR_SPECS.items():
    register_factor(FactorDefinition("technical", _field, "external", _spec.description))


def get_factor_definition(source: str, field: str) -> FactorDefinition:
    key = (str(source).strip().lower(), str(field).strip())
    try:
        return FACTOR_DEFINITIONS[key]
    except KeyError as exc:
        raise ValueError(
            f"unsupported factor reference: source={key[0]!r}, field={key[1]!r}; "
            f"supported fields for source={key[0]!r}: {supported_fields(key[0])}"
        ) from exc


def get_filter_definition(field: str) -> FactorDefinition:
    """Resolve a filter field to exactly one registered source.

    FilterSpec intentionally omits a source for backward compatibility. A field
    is therefore filterable only while its name maps unambiguously to one
    registered FactorDefinition.
    """
    key = str(field).strip()
    matches = [
        definition
        for (source, field_), definition in FACTOR_DEFINITIONS.items()
        if field_ == key
    ]
    if not matches:
        raise ValueError(
            f"unsupported filter field: {key!r}; "
            f"filterable fields={filterable_fields()}"
        )
    if len(matches) != 1:
        sources = sorted(x.source for x in matches)
        raise ValueError(
            f"ambiguous filter field {key!r}; registered sources={sources}. "
            "A future schema version must require an explicit filter source."
        )
    return matches[0]


def filterable_fields() -> list[str]:
    counts: dict[str, int] = {}
    for _, field in FACTOR_DEFINITIONS:
        counts[field] = counts.get(field, 0) + 1
    return sorted(field for field, count in counts.items() if count == 1)


def filter_field_catalog() -> list[dict[str, str]]:
    return [
        {
            "field": field,
            "source": get_filter_definition(field).source,
            "storage": get_filter_definition(field).storage,
            "description": get_filter_definition(field).description,
        }
        for field in filterable_fields()
    ]


def supported_sources() -> list[str]:
    return sorted({source for source, _ in FACTOR_DEFINITIONS})


def factor_catalog() -> list[dict[str, str]]:
    return [
        {
            "source": definition.source,
            "field": definition.field,
            "storage": definition.storage,
            "description": definition.description,
        }
        for _, definition in sorted(FACTOR_DEFINITIONS.items())
    ]


def supported_fields(source: str) -> list[str]:
    src = str(source).strip().lower()
    return sorted(field for (source_, field) in FACTOR_DEFINITIONS if source_ == src)


def factor_source_constraints() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for source, constraint in sorted(FACTOR_SOURCE_CONSTRAINTS.items()):
        row = dict(constraint)
        if "rebalance_months" in row:
            row["rebalance_months"] = list(row["rebalance_months"])
        out[source] = row
    return out


def validate_factor_strategy_constraints(
    factors: Iterable[object],
    rebalance_months: Iterable[int],
    filters: Iterable[object] = (),
) -> None:
    sources = {str(getattr(f, "source")).strip().lower() for f in factors}
    sources.update(get_filter_definition(getattr(flt, "field")).source for flt in filters)
    months = {int(m) for m in rebalance_months}
    for source in sorted(sources):
        constraint = FACTOR_SOURCE_CONSTRAINTS.get(source)
        if not constraint:
            continue
        allowed = constraint.get("rebalance_months")
        if allowed is not None:
            allowed_set = {int(m) for m in allowed}
            unsupported = sorted(months - allowed_set)
            if unsupported:
                raise ValueError(
                    f"factor source {source!r} supports rebalance months "
                    f"{sorted(allowed_set)} only; requested unsupported months={unsupported}. "
                    f"{constraint.get('reason', '')}".strip()
                )


def is_external_factor(source: str, field: str) -> bool:
    return get_factor_definition(source, field).storage == "external"


def panel_factor_fields(factors: Iterable[object]) -> set[str]:
    fields: set[str] = set()
    for factor in factors:
        definition = get_factor_definition(getattr(factor, "source"), getattr(factor, "field"))
        if definition.storage == "panel":
            fields.add(definition.field)
    return fields


def panel_filter_fields(filters: Iterable[object]) -> set[str]:
    fields: set[str] = set()
    for flt in filters:
        definition = get_filter_definition(getattr(flt, "field"))
        if definition.storage == "panel":
            fields.add(definition.field)
    return fields


def external_filter_sources(filters: Iterable[object]) -> list[str]:
    return sorted({
        get_filter_definition(getattr(flt, "field")).source
        for flt in filters
        if get_filter_definition(getattr(flt, "field")).storage == "external"
    })


def filter_fields_for_source(filters: Iterable[object], source: str) -> list[str]:
    src = str(source).strip().lower()
    fields: list[str] = []
    for flt in filters:
        definition = get_filter_definition(getattr(flt, "field"))
        if definition.source == src:
            fields.append(definition.field)
    return sorted(set(fields))


def external_sources(factors: Iterable[object]) -> list[str]:
    sources = {
        get_factor_definition(getattr(factor, "source"), getattr(factor, "field")).source
        for factor in factors
        if is_external_factor(getattr(factor, "source"), getattr(factor, "field"))
    }
    return sorted(sources)


def fields_for_source(factors: Iterable[object], source: str) -> list[str]:
    src = str(source).strip().lower()
    fields = []
    for factor in factors:
        if str(getattr(factor, "source")).strip().lower() != src:
            continue
        definition = get_factor_definition(getattr(factor, "source"), getattr(factor, "field"))
        fields.append(definition.field)
    return sorted(set(fields))


@runtime_checkable
class ExternalFactorProvider(Protocol):
    source: str

    def factor_frame(
        self,
        signal: pd.Timestamp,
        cross_section: pd.DataFrame,
        fields: Sequence[str],
    ) -> pd.DataFrame:
        ...

    def coverage_report(self, signal: pd.Timestamp, fields: Sequence[str]) -> list[dict]:
        ...


class DartFactorProvider:
    source = "dart"

    def __init__(self, repo_root: str | Path):
        from dart_value_factor_adapter import DartValueFactorAdapter

        self._adapter = DartValueFactorAdapter(repo_root)

    def factor_frame(
        self,
        signal: pd.Timestamp,
        cross_section: pd.DataFrame,
        fields: Sequence[str],
    ) -> pd.DataFrame:
        requested = [str(x) for x in fields]
        invalid = sorted(set(requested) - set(supported_fields(self.source)))
        if invalid:
            raise ValueError(f"unsupported DART factor fields: {invalid}")
        frame = self._adapter.factor_frame(signal, cross_section)
        keep = ["Code", *requested]
        missing = [c for c in keep if c not in frame.columns]
        if missing:
            raise KeyError(f"DART provider output missing fields: {missing}")
        return frame[keep].copy()

    def coverage_report(self, signal: pd.Timestamp, fields: Sequence[str]) -> list[dict]:
        rows = self._adapter.coverage_report(signal)
        return [{"source": self.source, **row} for row in rows]


class KrxTechnicalFactorProvider:
    source = "technical"

    def __init__(self, repo_root: str | Path):
        from krx_technical_factor_adapter import KrxTechnicalFactorAdapter

        self._adapter = KrxTechnicalFactorAdapter(repo_root)

    def factor_frame(
        self,
        signal: pd.Timestamp,
        cross_section: pd.DataFrame,
        fields: Sequence[str],
    ) -> pd.DataFrame:
        return self._adapter.factor_frame(signal, cross_section, fields)

    def coverage_report(self, signal: pd.Timestamp, fields: Sequence[str]) -> list[dict]:
        rows = self._adapter.coverage_report(signal, fields)
        return [{"source": self.source, **row} for row in rows]


PROVIDER_FACTORIES = {
    "dart": DartFactorProvider,
    "technical": KrxTechnicalFactorProvider,
}


def build_external_provider(source: str, repo_root: str | Path) -> ExternalFactorProvider:
    src = str(source).strip().lower()
    try:
        factory = PROVIDER_FACTORIES[src]
    except KeyError as exc:
        raise ValueError(f"no external factor provider registered for source={src!r}") from exc
    provider = factory(repo_root)
    if not isinstance(provider, ExternalFactorProvider):
        raise TypeError(f"provider for {src!r} does not satisfy ExternalFactorProvider contract")
    return provider
