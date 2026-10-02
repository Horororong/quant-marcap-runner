from scripts.backfill_dart_legacy_2000_2014 import parse_number, table_candidates, PARSER_VERSION
import json
import math
from pathlib import Path
import pytest

def test_legacy_negative_symbols():
    assert parse_number("△78,304") == -78304
    assert parse_number("▲78,304") == -78304
    assert parse_number("Δ78,304") == -78304
    assert parse_number("(78,304)") == -78304

def test_loss_label_normalizes_positive_magnitude():
    html = """
    <h2>손익계산서</h2><p>단위: 천원</p>
    <table><tr><td>당기순손실</td><td>5,787</td></tr></table>
    """
    rows = table_candidates(html)
    row = next(r for r in rows if r["metric"] == "net_income")
    assert row["amount_reported"] == -5787
    assert row["amount_krw"] == -5_787_000

def test_parser_version_requires_reprocessing():
    assert PARSER_VERSION == "legacy-v5-single-amount"


@pytest.mark.parametrize("text", ["751,637 22,35416,940", "670,000200,0001,500,000", "83 15,787 13,418 100", "12,34", "1.5%", "1 (주2)", "-", "—", "–"])
def test_ambiguous_or_missing_numeric_cells_are_not_invented_amounts(text):
    assert math.isnan(parse_number(text))


def test_real_source_combined_annual_summary_is_not_current_quarter_income():
    fixture = json.loads((Path(__file__).parent / "fixtures/legacy_dart/merged_annual_stats_20000515000887.json").read_text())
    assert fixture["rcept_no"] == "20000515000887"
    assert "751,637 22,35416,940" in fixture["source_text"]
    # Independent observation: three account labels and three amounts occur in
    # the same historical business-summary row. No single quarter metric exists.
    assert table_candidates(fixture["source_text"]) == []


def test_explicit_valid_amounts_and_zero_remain_supported():
    assert parse_number("9,573,422") == 9_573_422
    assert parse_number("104,519,807") == 104_519_807
    assert parse_number("0") == 0
    assert parse_number("+1,234.50") == 1234.5


def test_unknown_statement_and_partial_alias_do_not_become_financial_metrics():
    unknown = "<p>단위: 천원</p><table><tr><td>당기순이익</td><td>123</td></tr></table>"
    assert not table_candidates(unknown)
    combined = "<h2>손익계산서</h2>" + unknown.replace("당기순이익", "매출액영업이익당기순이익")
    assert not table_candidates(combined)


def test_nonfinite_scaled_value_cannot_be_usable_money():
    amount = "1" + "0" * 308
    rows = table_candidates("<h2>손익계산서</h2><p>단위: 백만원</p><table><tr><td>당기순이익</td><td>" + amount + "</td></tr></table>")
    assert rows and math.isnan(rows[0]["amount_krw"])


@pytest.mark.parametrize("text,expected", [
    ("(-1,170,019,230)", -1_170_019_230),
    ("(-482,479,885)", -482_479_885),
    ("(△62,175,514)", -62_175_514),
])
def test_parentheses_and_negative_sign_do_not_double_flip(text, expected):
    assert parse_number(text) == expected
