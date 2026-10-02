"""Collection safety tests. Synthetic amounts here are NOT financial audit evidence."""
import pandas as pd
import pytest

from scripts import backfill_dart_legacy_2000_2014 as legacy
from scripts.legacy_backfill_runtime import CollectionControl, CollectionPaused, collect_bounded


@pytest.fixture
def store(tmp_path, monkeypatch):
    for name, path in {
        "NORM_DIR": tmp_path / "normalized", "STATE_FILE": tmp_path / "state.csv",
        "INDEX_FILE": tmp_path / "index.csv.gz", "INDEX_STATE_FILE": tmp_path / "index-state.csv",
        "STATUS_FILE": tmp_path / "status.csv", "COVERAGE_FILE": tmp_path / "coverage.csv",
    }.items():
        monkeypatch.setattr(legacy, name, path)
    legacy.NORM_DIR.mkdir()
    monkeypatch.setenv("LEGACY_DART_CHECKPOINT_SIZE", "1")
    monkeypatch.delenv("LEGACY_DART_RUN_REPORT", raising=False)
    monkeypatch.setattr(legacy, "RUN_CONTROL", None)
    return tmp_path


def index(n=3):
    return pd.DataFrame([{"rcept_no": f"20010101{i:06}", "rcept_dt": "2001-01-01",
                         "fiscal_year": 2000, "period": "Q3", "stock_code": "000001"}
                        for i in range(n)])


def result(meta, *, version=None, status="PARSED_PARTIAL"):
    version = version or legacy.PARSER_VERSION
    rows = [{"rcept_no": meta["rcept_no"], "fiscal_year": 2000, "stock_code": "000001",
             "corp_code": "00000001", "metric": "equity", "scope": "OFS",
             "amount_krw": 123000.0, "document_sha256": "source-hash", "parser_version": version}]
    if status not in {"PARSED_4F", "PARSED_PARTIAL"}:
        rows = []
    state = {"rcept_no": meta["rcept_no"], "status": status, "metric_rows": len(rows),
             "usable_metric_count": 1, "best_scope": "OFS", "document_sha256": "source-hash",
             "parser_version": version, "updated_at_utc": "2001-01-01T00:00:00Z", "error": ""}
    return rows, state


def control(**overrides):
    return CollectionControl(**{"max_requests": 100, "max_seconds": 60, "min_interval": 0, **overrides})


def test_checkpoint_survives_interruption_and_resume_skips_durable_receipt(store, monkeypatch):
    calls = []

    def interrupted(meta):
        calls.append(meta["rcept_no"])
        if len(calls) == 2:
            raise RuntimeError("unexpected worker failure")
        return result(meta)

    monkeypatch.setattr(legacy, "process_filing", interrupted)
    with pytest.raises(RuntimeError, match="worker failure"):
        legacy.process_pending(index(), workers=1, control=control())
    saved = pd.read_csv(legacy.STATE_FILE, dtype=str)
    assert saved.rcept_no.tolist() == [index().iloc[0].rcept_no]
    assert len(legacy.durable_done_receipts(legacy.current_state())) == 1
    calls.clear()
    monkeypatch.setattr(legacy, "process_filing", lambda meta: (calls.append(meta["rcept_no"]) or result(meta)))
    summary = legacy.process_pending(index(), workers=1, control=control())
    assert summary["completed"] == 2
    assert calls == index().rcept_no.tolist()[1:]
    assert len(legacy.durable_done_receipts(legacy.current_state())) == 3


def test_data_publication_failure_never_marks_receipt_complete(store, monkeypatch):
    monkeypatch.setattr(legacy, "process_filing", result)
    monkeypatch.setattr(legacy, "append_normalized", lambda rows: (_ for _ in ()).throw(OSError("disk failure")))
    with pytest.raises(OSError, match="disk failure"):
        legacy.process_pending(index(1), workers=1, control=control())
    assert not legacy.STATE_FILE.exists()


@pytest.mark.parametrize("damage", ["missing_file", "wrong_hash", "wrong_row_count"])
def test_state_cannot_skip_missing_or_mismatched_normalized_data(store, damage):
    rows, state = result(index(1).iloc[0])
    if damage != "missing_file":
        if damage == "wrong_hash":
            rows[0]["document_sha256"] = "wrong-source"
        legacy.append_normalized(rows)
    if damage == "wrong_row_count":
        state["metric_rows"] = 2
    legacy.upsert_state(legacy.STATE_FILE, [state], "rcept_no")
    pending, _ = legacy.pending_receipts(index(1), legacy.current_state())
    assert len(pending) == 1


def test_parser_version_resume_keeps_old_observations_and_does_not_reparse_current(store, monkeypatch):
    metas = index(2).to_dict("records")
    for meta, version in zip(metas, ["legacy-v3-book", legacy.PARSER_VERSION]):
        rows, state = result(meta, version=version)
        legacy.append_normalized(rows)
        legacy.upsert_state(legacy.STATE_FILE, [state], "rcept_no")
    calls = []
    monkeypatch.setattr(legacy, "process_filing", lambda meta: (calls.append(meta["rcept_no"]) or result(meta)))
    legacy.process_pending(index(2), workers=1, control=control())
    assert calls == [metas[0]["rcept_no"]]
    stored = pd.read_csv(next(legacy.NORM_DIR.glob("*.gz")), dtype=str)
    assert len(stored) == 3
    assert set(stored.parser_version) == {"legacy-v3-book", legacy.PARSER_VERSION}


def test_rate_limit_stops_replenishment_and_flushes_completed_work():
    called, checkpoints = [], []

    def process(meta):
        called.append(meta)
        return [], {"rcept_no": str(meta), "status": "RATE_LIMIT"}

    summary = collect_bounded(range(1000), process, lambda rows, states: checkpoints.extend(states),
                              control(), workers=1, checkpoint_size=25)
    assert called == [0]
    assert summary["rate_limited"] and summary["stop_reason"] == "RATE_LIMIT"
    assert len(checkpoints) == 1


def test_request_budget_counts_every_attempt_and_deferred_is_not_source_gap(store, monkeypatch):
    guard = control(max_requests=2)
    monkeypatch.setattr(legacy, "RUN_CONTROL", guard)
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise legacy.requests.Timeout("temporary failure")

    monkeypatch.setattr(legacy.requests, "get", timeout)
    monkeypatch.setattr(legacy.time, "sleep", lambda seconds: None)
    rows, state = legacy.process_filing(index(1).iloc[0].to_dict())
    assert not rows and state["status"] == "DEFERRED"
    assert len(calls) == guard.requests == 2
    assert guard.stop_reason == "REQUEST_BUDGET"


def test_deadline_and_signal_stop_have_no_new_requests_and_flush_work():
    now = [0.0]
    guard = control(max_seconds=1, clock=lambda: now[0])
    now[0] = 2.0
    with pytest.raises(CollectionPaused, match="DEADLINE"):
        guard.before_request()
    assert guard.requests == 0
    guard = control()
    checkpoints = []

    def process(meta):
        guard.stop("SIGNAL")
        return [], {"rcept_no": "one", "status": "NO_METRICS"}

    collect_bounded(range(1000), process, lambda rows, states: checkpoints.extend(states), guard, workers=1)
    assert len(checkpoints) == 1


def test_error_retry_quarantine_does_not_starve_other_receipts(store, monkeypatch):
    legacy.upsert_state(legacy.INDEX_STATE_FILE, [{"task_key": key, "status": "OK"}
                         for key in legacy.build_index_tasks().task_key], "task_key")
    monkeypatch.setattr(legacy, "process_filing", lambda meta: result(meta, status="ERROR"))
    for _ in range(3):
        legacy.process_pending(index(1), workers=1, control=control())
    pending, quarantined = legacy.pending_receipts(index(2), legacy.current_state())
    assert quarantined == 1 and pending.rcept_no.tolist() == [index(2).iloc[1].rcept_no]
    legacy.write_coverage(index(1))
    status = pd.read_csv(legacy.STATUS_FILE).iloc[0]
    assert status["mode"] == "REVIEW_REQUIRED" and not status["quality_complete"]


def test_retry_count_survives_state_migration_and_mixed_empty_attempts(store, monkeypatch):
    _, old = result(index(2).iloc[1], version="legacy-v3-book", status="ERROR")
    legacy.upsert_state(legacy.STATE_FILE, [old], "rcept_no")
    monkeypatch.setattr(legacy, "process_filing", lambda meta: result(meta, status="ERROR"))
    for _ in range(3):
        legacy.process_pending(index(1), workers=1, control=control())
    pending, held = legacy.pending_receipts(index(2), legacy.current_state())
    assert held == 1 and pending.rcept_no.tolist() == [index(2).iloc[1].rcept_no]


def test_index_data_is_published_before_ok_state(store, monkeypatch):
    task = legacy.build_index_tasks().iloc[0]
    monkeypatch.setattr(legacy, "build_index_tasks", lambda: pd.DataFrame([task]))
    monkeypatch.setattr(legacy, "fetch_index_task", lambda task: (index(1).to_dict("records"),
                       {"task_key": task["task_key"], "status": "OK", "error": ""}))
    monkeypatch.setattr(legacy, "prepare_filing_index", lambda frame: frame)
    monkeypatch.setattr(legacy, "save_index", lambda frame: (_ for _ in ()).throw(OSError("index publish failure")))
    with pytest.raises(OSError, match="index publish failure"):
        legacy.update_filing_index()
    assert not legacy.INDEX_STATE_FILE.exists()


def test_collection_complete_requires_independent_audit_and_noop_preserves_bytes(store, monkeypatch):
    rows, state = result(index(1).iloc[0], status="NO_DOCUMENT")
    legacy.upsert_state(legacy.STATE_FILE, [state], "rcept_no")
    tasks = legacy.build_index_tasks()
    legacy.upsert_state(legacy.INDEX_STATE_FILE, [{"task_key": key, "status": "OK"}
                         for key in tasks.task_key], "task_key")
    legacy.save_index(index(1))
    monkeypatch.setattr(legacy.requests, "get", lambda *a, **k: pytest.fail("no-op called DART"))
    before_index = legacy.INDEX_FILE.read_bytes()
    legacy.update_filing_index()
    legacy.write_coverage(index(1))
    saved = legacy.STATUS_FILE.read_bytes(), legacy.COVERAGE_FILE.read_bytes()
    legacy.write_coverage(index(1))
    assert saved == (legacy.STATUS_FILE.read_bytes(), legacy.COVERAGE_FILE.read_bytes())
    assert legacy.INDEX_FILE.read_bytes() == before_index
    status = pd.read_csv(legacy.STATUS_FILE).iloc[0]
    assert status["collection_complete"] and not status["quality_complete"]
    assert status["mode"] == "COLLECTION_COMPLETE_REVIEW_REQUIRED"


def test_error_diagnostics_never_persist_api_key(monkeypatch):
    monkeypatch.setattr(legacy, "API_KEY", "test-secret-not-real")
    error = RuntimeError("https://opendart.fss.or.kr/api/document.xml?crtfc_key=test-secret-not-real&rcept_no=20000101000001")
    assert "test-secret-not-real" not in legacy.safe_error(error)
    assert "rcept_no=20000101000001" in legacy.safe_error(error)


def test_missing_key_does_not_overwrite_progress(store, monkeypatch):
    legacy.STATUS_FILE.write_text("existing checkpoint", encoding="utf-8")
    monkeypatch.setattr(legacy, "API_KEY", "")
    with pytest.raises(RuntimeError, match="DART_API_KEY missing"):
        legacy.main()
    assert legacy.STATUS_FILE.read_text() == "existing checkpoint"


def test_index_rate_limit_blocks_following_document_requests(store, monkeypatch):
    guard = control()
    guard.stop("RATE_LIMIT")
    monkeypatch.setattr(legacy, "process_filing", lambda *args: pytest.fail("call after index API 020"))
    summary = legacy.process_pending(index(1), control=guard)
    assert summary["completed"] == 0 and summary["rate_limited"]


def test_authentication_failure_stops_without_classifying_source_as_missing(store, monkeypatch):
    guard = control()
    monkeypatch.setattr(legacy, "RUN_CONTROL", guard)

    class Response:
        content = b"<result><status>010</status></result>"
        text = content.decode()
        def raise_for_status(self):
            pass

    monkeypatch.setattr(legacy.requests, "get", lambda *args, **kwargs: Response())
    _, state = legacy.process_filing(index(1).iloc[0].to_dict())
    assert state["status"] == "DEFERRED" and guard.stop_reason == "FATAL_API"
    assert guard.requests == 1
