from __future__ import annotations

from strategy_dsl_aliases import (
    ALIAS_RULES,
    alias_catalog,
    resolve_direction_alias,
    resolve_factor_alias,
    supported_alias_terms,
)
from factor_registry import get_factor_definition


def main() -> None:
    assert resolve_direction_alias("낮은") == "low"
    assert resolve_direction_alias("높은") == "high"

    per = resolve_factor_alias("PER", "낮은")
    assert per["source"] == "dart"
    assert per["field"] == "earnings_yield"
    assert per["direction"] == "high"

    pbr = resolve_factor_alias("주가순자산비율", "낮은")
    assert pbr["field"] == "book_to_price"
    assert pbr["direction"] == "high"

    ep = resolve_factor_alias("E/P", "high")
    assert ep["field"] == "earnings_yield"
    assert ep["direction"] == "high"

    small = resolve_factor_alias("소형주")
    assert small["source"] == "krx"
    assert small["field"] == "Marcap"
    assert small["direction"] == "low"

    large = resolve_factor_alias("large cap")
    assert large["field"] == "Marcap"
    assert large["direction"] == "high"

    amount = resolve_factor_alias("거래대금", "높은")
    assert amount["field"] == "Amount"
    assert amount["direction"] == "high"

    try:
        resolve_factor_alias("PER")
        raise AssertionError("PER without high/low direction was accepted")
    except ValueError:
        pass

    try:
        resolve_factor_alias("소형주", "high")
        raise AssertionError("fixed small-cap direction conflict was accepted")
    except ValueError:
        pass

    try:
        resolve_factor_alias("없는팩터", "low")
        raise AssertionError("unknown alias was accepted")
    except ValueError:
        pass

    terms = supported_alias_terms()
    assert "PER" in terms
    assert "소형주" in terms

    for row in alias_catalog():
        get_factor_definition(row["source"], row["field"])

    assert len(alias_catalog()) == len(ALIAS_RULES)
    print("STRATEGY DSL ALIAS TEST: PASS")


if __name__ == "__main__":
    main()
