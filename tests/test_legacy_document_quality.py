"""Source-backed collector failures and normal/absent-source boundaries."""
import io
import zipfile
import pandas as pd
from scripts import backfill_dart_legacy_2000_2014 as legacy


def collect(monkeypatch, xml):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("20010103000052.xml", xml)
    monkeypatch.setattr(legacy, "fetch_document", lambda receipt: (stream.getvalue(), "test-source-sha"))
    return legacy.process_filing({"rcept_no": "20010103000052", "rcept_dt": "2001-01-03",
                                  "period_end": "2000-09-30", "period": "Q3", "fiscal_year": 2000})


def test_broken_source_cannot_be_recorded_as_no_metrics(monkeypatch):
    rows, state = collect(monkeypatch, '<DOCUMENT><P>\ufffd</P>')
    assert not rows
    assert state["status"] == "SOURCE_GAP"
    assert "SOURCE_XML_INCOMPLETE_OR_INVALID" in state["error"]
    assert "SOURCE_REPLACEMENT_CHARACTERS" in state["error"]


def test_valid_absent_metric_keeps_distinct_status(monkeypatch):
    rows, state = collect(monkeypatch, '<DOCUMENT><P>no current financial items</P></DOCUMENT>')
    assert not rows and state["status"] == "NO_METRICS"


def test_truncated_source_cannot_publish_tolerantly_parsed_amounts(monkeypatch):
    rows, state = collect(monkeypatch, '<DOCUMENT><H2>손익계산서</H2><P>단위: 원</P><TABLE><TR><TD>매출액</TD><TD>123</TD></TR></TABLE>')
    assert rows == [] and state["status"] == "SOURCE_GAP"


def test_five_actual_no_metrics_sources_are_source_gaps_and_archives_match_checkpoints(monkeypatch):
    from pathlib import Path
    import csv
    with open("data/status/dart_legacy_backfill_state.csv", encoding="utf-8-sig") as stream:
        states = list(csv.DictReader(stream))
    for p in Path("tests/fixtures/legacy_dart/recovery_primary").glob("*.zip"):
        receipt = p.name[:14]
        state = next(r for r in states if r["rcept_no"] == receipt and r["parser_version"] == legacy.PARSER_VERSION)
        monkeypatch.setattr(legacy, "fetch_document", lambda r, p=p, state=state: (p.read_bytes(), state["document_sha256"]))
        rows, actual = legacy.process_filing({"rcept_no": receipt, "rcept_dt": "2001-01-03", "period_end": "2000-09-30"})
        assert rows == [] and actual["status"] == "SOURCE_GAP"


def test_valid_existing_normal_amount_and_parser_version_are_preserved(monkeypatch):
    rows, state = collect(monkeypatch, '<DOCUMENT><H2>손익계산서</H2><P>단위: 천원</P><TABLE><TR><TD>매출액</TD><TD>1,234</TD></TR></TABLE></DOCUMENT>')
    assert state["status"] == "PARSED_PARTIAL"
    assert rows[0]["amount_krw"] == 1234000
    assert rows[0]["parser_version"] == "legacy-v5-single-amount"


def test_source_gap_is_quarantined_without_infinite_retries(monkeypatch):
    state = pd.DataFrame([{"rcept_no": "20010103000052", "status": "SOURCE_GAP"}])
    assert legacy.durable_done_receipts(state) == {"20010103000052"}


def test_real_native_archives_reproduce_source_gaps():
    from pathlib import Path
    from scripts.legacy_document_quality import inspect_member, empty_parse_status
    for path in Path("tests/fixtures/legacy_dart/native_primary").glob("*.zip"):
        with zipfile.ZipFile(path) as archive:
            diagnostics = [inspect_member(archive.read(n), n) for n in archive.namelist()]
        assert empty_parse_status(diagnostics) == "SOURCE_GAP"
