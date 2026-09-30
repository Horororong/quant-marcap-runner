from __future__ import annotations

"""Deterministic natural-language factor aliases for Strategy DSL compilation.

This module does not perform free-form NLP. It resolves common Korean/English
factor names into canonical registry fields and encodes whether ranking
direction is preserved or inverted.
"""

from dataclasses import dataclass, asdict
from typing import Iterable
import re
import unicodedata

from factor_registry import get_factor_definition


@dataclass(frozen=True)
class FactorAliasRule:
    terms: tuple[str, ...]
    source: str
    field: str
    direction_relation: str = "same"  # same | inverse
    fixed_direction: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        get_factor_definition(self.source, self.field)
        if self.direction_relation not in {"same", "inverse"}:
            raise ValueError(f"invalid direction_relation: {self.direction_relation}")
        if self.fixed_direction not in {None, "high", "low"}:
            raise ValueError(f"invalid fixed_direction: {self.fixed_direction}")
        if not self.terms:
            raise ValueError("alias rule requires at least one term")


def normalize_alias_term(value: str) -> str:
    s = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    # Ignore whitespace and common separators while preserving Korean/letters/numbers.
    return re.sub(r"[\s_\-./]+", "", s)


DIRECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "low": ("low", "lower", "낮은", "낮게", "작은", "적은", "저"),
    "high": ("high", "higher", "높은", "높게", "큰", "많은", "고"),
}


def resolve_direction_alias(term: str) -> str:
    key = normalize_alias_term(term)
    matches = [
        direction
        for direction, terms in DIRECTION_ALIASES.items()
        if key in {normalize_alias_term(x) for x in terms}
    ]
    if len(matches) != 1:
        raise ValueError(f"unsupported or ambiguous direction alias: {term!r}")
    return matches[0]


def direction_alias_catalog() -> dict[str, list[str]]:
    return {direction: list(terms) for direction, terms in DIRECTION_ALIASES.items()}


ALIAS_RULES: tuple[FactorAliasRule, ...] = (
    FactorAliasRule(
        terms=("PER", "P/E", "주가수익비율"),
        source="dart",
        field="earnings_yield",
        direction_relation="inverse",
        note="PER low is equivalent to earnings_yield high.",
    ),
    FactorAliasRule(
        terms=("EP", "E/P", "earnings yield", "이익수익률"),
        source="dart",
        field="earnings_yield",
    ),
    FactorAliasRule(
        terms=("PBR", "P/B", "주가순자산비율"),
        source="dart",
        field="book_to_price",
        direction_relation="inverse",
        note="PBR low is equivalent to book_to_price high.",
    ),
    FactorAliasRule(
        terms=("BP", "B/P", "book to price", "장부가치수익률"),
        source="dart",
        field="book_to_price",
    ),
    FactorAliasRule(
        terms=("PCR", "P/CF", "주가현금흐름비율"),
        source="dart",
        field="cashflow_yield",
        direction_relation="inverse",
        note="PCR low is equivalent to cashflow_yield high.",
    ),
    FactorAliasRule(
        terms=("CFP", "CF/P", "cash flow yield", "현금흐름수익률"),
        source="dart",
        field="cashflow_yield",
    ),
    FactorAliasRule(
        terms=("PSR", "P/S", "주가매출비율"),
        source="dart",
        field="sales_yield",
        direction_relation="inverse",
        note="PSR low is equivalent to sales_yield high.",
    ),
    FactorAliasRule(
        terms=("SP", "S/P", "sales yield", "매출수익률"),
        source="dart",
        field="sales_yield",
    ),
    FactorAliasRule(
        terms=("시가총액", "시총", "market cap", "marketcap", "size"),
        source="krx",
        field="Marcap",
    ),
    FactorAliasRule(
        terms=("소형주", "소형주식", "small cap", "smallcap"),
        source="krx",
        field="Marcap",
        fixed_direction="low",
        note="Small-cap preference means lower market capitalization.",
    ),
    FactorAliasRule(
        terms=("대형주", "대형주식", "large cap", "largecap"),
        source="krx",
        field="Marcap",
        fixed_direction="high",
        note="Large-cap preference means higher market capitalization.",
    ),
    FactorAliasRule(
        terms=("거래대금", "trading amount", "turnover amount"),
        source="krx",
        field="Amount",
    ),
    FactorAliasRule(
        terms=("거래량", "volume"),
        source="krx",
        field="Volume",
    ),
    FactorAliasRule(
        terms=("종가", "close", "close price"),
        source="krx",
        field="Close",
    ),
)


def _alias_index() -> dict[str, FactorAliasRule]:
    out: dict[str, FactorAliasRule] = {}
    for rule in ALIAS_RULES:
        for term in rule.terms:
            key = normalize_alias_term(term)
            previous = out.get(key)
            if previous is not None and previous != rule:
                raise ValueError(f"conflicting normalized factor alias: {term!r}")
            out[key] = rule
    return out


ALIAS_INDEX = _alias_index()


def supported_alias_terms() -> list[str]:
    return sorted({term for rule in ALIAS_RULES for term in rule.terms}, key=str.casefold)


def resolve_factor_alias(term: str, requested_direction: str | None = None) -> dict[str, str | None]:
    key = normalize_alias_term(term)
    try:
        rule = ALIAS_INDEX[key]
    except KeyError as exc:
        raise ValueError(f"unsupported factor alias: {term!r}") from exc

    direction = resolve_direction_alias(requested_direction) if requested_direction is not None else None

    if rule.fixed_direction is not None:
        if direction is not None and direction != rule.fixed_direction:
            raise ValueError(
                f"{term!r} has fixed canonical direction={rule.fixed_direction}; "
                f"requested={direction}"
            )
        canonical_direction = rule.fixed_direction
    else:
        if direction is None:
            raise ValueError(f"{term!r} requires an explicit high/low direction")
        canonical_direction = direction
        if rule.direction_relation == "inverse":
            canonical_direction = "low" if direction == "high" else "high"

    return {
        "source": rule.source,
        "field": rule.field,
        "direction": canonical_direction,
        "transform": "identity",
        "matched_alias": term,
        "direction_relation": rule.direction_relation,
        "note": rule.note or None,
    }


def alias_catalog() -> list[dict]:
    rows = []
    for rule in ALIAS_RULES:
        row = asdict(rule)
        row["terms"] = list(rule.terms)
        rows.append(row)
    return rows
