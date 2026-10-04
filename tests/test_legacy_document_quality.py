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


def test_quarantine_overlay_preserves_original_state_and_old_values(monkeypatch, tmp_path):
    import hashlib
    state = tmp_path / "state.csv"
    ledger = tmp_path / "quarantine.csv"
    pd.DataFrame([{"rcept_no": "receipt", "status": "PARSED_PARTIAL", "metric_rows": "1",
                   "usable_metric_count": "1", "document_sha256": "damaged-sha",
                   "parser_version": legacy.PARSER_VERSION, "source_version": legacy.SOURCE_VERSION}]).to_csv(state, index=False)
    pd.DataFrame([{"rcept_no": "receipt", "document_sha256": "damaged-sha", "issues": "truncated",
                   "prior_status": "PARSED_PARTIAL"}]).to_csv(ledger, index=False)
    monkeypatch.setattr(legacy, "STATE_FILE", state)
    monkeypatch.setattr(legacy, "QUARANTINE_FILE", ledger)
    original = hashlib.sha256(state.read_bytes()).hexdigest()
    for _ in range(2):
        effective = legacy.current_state().iloc[0]
        assert effective.status == "SOURCE_GAP" and effective.prior_status == "PARSED_PARTIAL"
        assert effective.metric_rows == "0" and effective.usable_metric_count == "0"
    assert hashlib.sha256(state.read_bytes()).hexdigest() == original
    # A different, independently downloaded document is not blocked by stale evidence.
    pd.DataFrame([{"rcept_no": "receipt", "document_sha256": "other-sha", "issues": "truncated"}]).to_csv(ledger, index=False)
    assert legacy.current_state().iloc[0].status == "PARSED_PARTIAL"


def test_source_gap_prevents_collection_and_quality_completion(monkeypatch, tmp_path):
    monkeypatch.setattr(legacy, "STATUS_FILE", tmp_path / "status.csv")
    monkeypatch.setattr(legacy, "COVERAGE_FILE", tmp_path / "coverage.csv")
    monkeypatch.setattr(legacy, "build_index_tasks", lambda: pd.DataFrame([{"task_key": "complete"}]))
    monkeypatch.setattr(legacy, "load_index_state", lambda: pd.DataFrame([{"task_key": "complete", "status": "OK"}]))
    state = pd.DataFrame([{"rcept_no": "receipt", "status": "SOURCE_GAP", "usable_metric_count": "0",
                           "parser_version": legacy.PARSER_VERSION}])
    monkeypatch.setattr(legacy, "current_state", lambda: state)
    index = pd.DataFrame([{"rcept_no": "receipt", "stock_code": "000001", "fiscal_year": 2000,
                          "period": "FY", "rcept_dt": "2001-03-01"}])
    legacy.write_coverage(index)
    result = pd.read_csv(legacy.STATUS_FILE).iloc[0]
    assert result.processed_filings == 1 and result.source_gap_filings == 1
    assert result.usable_four_factor_filings == 0 and result.automatic_pending_filings == 0
    assert not result.collection_complete and not result.quality_complete
    assert result.mode == "REVIEW_REQUIRED"


def test_original_download_is_preserved_before_parsing(monkeypatch, tmp_path):
    import hashlib
    monkeypatch.setenv("LEGACY_DART_SOURCE_DIR", str(tmp_path))
    blob = b"immutable original"
    sha = hashlib.sha256(blob).hexdigest()
    legacy.preserve_document(blob, "receipt", sha)
    legacy.preserve_document(blob, "receipt", sha)
    assert (tmp_path / f"receipt-{sha}.zip").read_bytes() == blob
    assert len(list(tmp_path.iterdir())) == 1


def test_evidence_budget_stops_before_new_publication(monkeypatch, tmp_path):
    import pytest
    from scripts.legacy_backfill_runtime import CollectionPaused
    monkeypatch.setenv("LEGACY_DART_SOURCE_DIR", str(tmp_path))
    monkeypatch.setenv("LEGACY_DART_SOURCE_MAX_BYTES", "1")
    with pytest.raises(CollectionPaused):
        legacy.preserve_document(b"too large", "receipt", "sha")
    assert list(tmp_path.iterdir()) == []


def test_empty_compatible_state_is_not_mutated_by_unmatched_ledger(monkeypatch, tmp_path):
    path = tmp_path / "state.csv"
    pd.DataFrame([{"rcept_no": "old", "status": "ERROR", "metric_rows": "0",
                   "document_sha256": "sha", "parser_version": "previous-parser",
                   "source_version": legacy.SOURCE_VERSION}]).to_csv(path, index=False)
    monkeypatch.setattr(legacy, "STATE_FILE", path)
    assert legacy.current_state().empty


def test_probe_rate_limit_stops_following_downloads(monkeypatch, tmp_path):
    import json
    from scripts import legacy_batch_evidence as evidence
    monkeypatch.setenv("LEGACY_DART_EVIDENCE_DIR", str(tmp_path))
    monkeypatch.setenv("LEGACY_DART_RUN_REPORT", str(tmp_path / "run.json"))
    monkeypatch.setenv("LEGACY_DART_MAX_REQUESTS", "150")
    monkeypatch.setattr(evidence.legacy, "QUARANTINE_FILE", tmp_path / "ledger.csv")
    (tmp_path / "run.json").write_text(json.dumps({"requests": 100, "stop_reason": "BATCH_COMPLETE"}))
    (tmp_path / "plan.json").write_text(json.dumps({"old_source_samples": [
        {"rcept_no": "one"}, {"rcept_no": "two"}]}))
    calls = []
    def limited(receipt):
        calls.append(receipt)
        raise evidence.legacy.RateLimitExceeded("020")
    monkeypatch.setattr(evidence.legacy, "fetch_document", limited)
    evidence.probe()
    assert calls == ["one"]
    assert evidence.legacy.RUN_CONTROL is None


def test_source_sample_selection_is_frozen_diverse_and_excludes_original_seven():
    from scripts.legacy_batch_evidence import selected_samples
    state = pd.DataFrame([{"rcept_no": f"receipt-{i}", "status": "NO_METRICS" if i < 20 else "PARSED_PARTIAL",
                           "document_sha256": "sha", "metric_rows": "0"} for i in range(40)])
    index = pd.DataFrame([{"rcept_no": f"receipt-{i}", "corp_code": f"corp-{i}",
                          "fiscal_year": str(2000 + i % 3), "period": ["Q1", "H1", "Q3", "FY"][i % 4]}
                         for i in range(40)])
    a = selected_samples(state, index)
    assert a == selected_samples(state.iloc[::-1], index.iloc[::-1])
    assert len(a) == 24 and len({r["corp_code"] for r in a}) == 24
    assert len({r["period"] for r in a}) > 1 and len({r["fiscal_year"] for r in a}) > 1
