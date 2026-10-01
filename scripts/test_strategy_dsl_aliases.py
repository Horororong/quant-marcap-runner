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

    per = resolve_factor_alias("슈퍼가치 PER", "낮은")
    assert per["source"] == "dart"
    assert per["field"] == "earnings_yield"
    assert per["direction"] == "high"

    pbr = resolve_factor_alias("주가순자산비율", "낮은")
    assert pbr["field"] == "book_to_price"
    assert pbr["direction"] == "high"

    ep = resolve_factor_alias("분기 E/P", "높은")
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

    mom = resolve_factor_alias("12-1 모멘텀", "높은")
    assert mom["source"] == "technical"
    assert mom["field"] == "momentum_12_1"
    assert mom["direction"] == "high"

    vol = resolve_factor_alias("3개월 변동성", "낮은")
    assert vol["source"] == "technical"
    assert vol["field"] == "volatility_3m"
    assert vol["direction"] == "low"

    lowvol = resolve_factor_alias("3개월 저변동성")
    assert lowvol["field"] == "volatility_3m"
    assert lowvol["direction"] == "low"

    qroe = resolve_factor_alias("분기 ROE", "높은")
    assert qroe["source"] == "dart"
    assert qroe["field"] == "quarterly_roe"
    assert qroe["direction"] == "high"

    try:
        resolve_factor_alias("ROE", "높은")
        raise AssertionError("generic ROE was incorrectly mapped to quarterly ROE")
    except ValueError:
        pass

    try:
        resolve_factor_alias("PER", "낮은")
        raise AssertionError("generic PER was incorrectly mapped to standalone-quarter earnings yield")
    except ValueError:
        pass

    try:
        resolve_factor_alias("슈퍼가치 PER")
        raise AssertionError("Super Value PER without high/low direction was accepted")
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
    assert "슈퍼가치 PER" in terms
    assert "소형주" in terms

    for row in alias_catalog():
        get_factor_definition(row["source"], row["field"])

    assert len(alias_catalog()) == len(ALIAS_RULES)
    print("STRATEGY DSL ALIAS TEST: PASS")


if __name__ == "__main__":
    main()
