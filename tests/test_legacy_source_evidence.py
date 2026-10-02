"""Evidence-storage and certification boundaries; these are not real-data audits."""
import hashlib
import gzip
import io
import zipfile

import pandas as pd
import pytest

from scripts import audit_legacy_pit_sample as audit
from scripts import probe_dart_legacy_sources as probe


def archive(text):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as output:
        output.writestr("original.xml", text.encode("cp949"))
    return stream.getvalue()


def test_literal_source_spans_preserve_native_tags_heading_unit_and_column_order():
    text = '<?xml version="1.0" encoding="euc-kr"?><TITLE>손익계산서</TITLE><P>단위: 천원</P><TABLE><TR><TE>매출액</TE><TE>10,000</TE><TE>8,000</TE></TR></TABLE>'
    original = archive(text)
    members = probe.source_excerpts(original)
    member = members[0]
    span = member["excerpts"][0]
    assert span["source_text"] == text[span["start_character"]:span["end_character"]]
    assert "<TE>10,000</TE><TE>8,000</TE>" in span["source_text"]
    assert "손익계산서" in span["source_text"] and "단위: 천원" in span["source_text"]
    assert member["member_sha256"] == hashlib.sha256(text.encode("cp949")).hexdigest()


def test_excerpt_budget_marks_clipping_without_changing_source(monkeypatch):
    monkeypatch.setattr(probe, "MAX_EXCERPT_CHARS", 100)
    text = "<table><tr><td>매출액</td><td>" + "1" * 200 + "</td></tr></table>"
    span = probe.source_excerpts(archive(text))[0]["excerpts"][0]
    assert span["clipped"] and span["source_text"] == text[:100]


def test_probe_api_014_and_viewer_403_do_not_certify_source_absence(tmp_path, monkeypatch):
    def unavailable(receipt):
        raise probe.legacy.DocumentUnavailable("API status 014")

    class Response:
        status_code = 403
        content = b"Forbidden"

    monkeypatch.setattr(probe.legacy, "fetch_document", unavailable)
    monkeypatch.setattr(probe.legacy.requests, "get", lambda *a, **k: Response())
    guard = probe.legacy.CollectionControl(min_interval=0)
    record = probe.probe("20000814000085", tmp_path, guard)
    assert record["download_status"] == "API_014" and record["public_viewer_http_status"] == 403
    assert record["source_absence_confirmed"] is False
    assert record["independent_source_audit_status"] == "NOT_RUN"


def test_rate_limit_stops_public_probe_too(tmp_path, monkeypatch):
    def limited(receipt):
        raise probe.legacy.RateLimitExceeded("020")

    monkeypatch.setattr(probe.legacy, "fetch_document", limited)
    monkeypatch.setattr(probe.legacy.requests, "get", lambda *a, **k: pytest.fail("request after 020"))
    guard = probe.legacy.CollectionControl(min_interval=0)
    assert probe.probe("20000814000085", tmp_path, guard)["download_status"] == "RATE_LIMIT"


def test_same_parser_reparse_success_cannot_certify_financial_correctness(monkeypatch):
    row = {"metric": "equity", "scope": "OFS", "statement": "BS", "unit": "천원",
           "amount_reported": 123.0, "unit_multiplier": 1000.0, "amount_krw": 123000.0,
           "account_name": "자본총계", "stock_code": "000001"}
    stored = pd.DataFrame([row])
    monkeypatch.setattr(audit.legacy, "process_filing", lambda meta: ([row], {"status": "PARSED_PARTIAL"}))
    result = audit.audit_one({"rcept_no": "20010101000001", "stock_code": "000001"}, stored,
                             pd.Series({"status": "PARSED_PARTIAL", "best_scope": "OFS"}))
    assert result["structural_checks_ok"] and result["fresh_reparse_ok"]
    assert result["reparse_consistency_ok"]
    assert not result["audit_ok"] and result["independent_source_audit_status"] == "NOT_RUN"


def test_corrupt_normalized_data_is_an_explicit_audit_failure(tmp_path, monkeypatch):
    (tmp_path / "legacy_metrics_2000.csv.gz").write_bytes(b"broken ZIP/CSV")
    monkeypatch.setattr(audit.legacy, "NORM_DIR", tmp_path)
    with pytest.raises(gzip.BadGzipFile):
        audit.load_normalized()
