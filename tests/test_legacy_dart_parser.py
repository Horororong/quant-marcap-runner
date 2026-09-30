from scripts.backfill_dart_legacy_2000_2014 import parse_number, table_candidates, PARSER_VERSION

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
    assert PARSER_VERSION == "legacy-v4-book"
