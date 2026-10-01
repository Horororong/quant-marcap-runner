"""Collector durability tests. Fixtures validate software, not financial data."""
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import gzip
import io
import json
import os
import tempfile
import zipfile

import pandas as pd
import backfill_dart_full_financials as full
import backfill_dart_legacy_2000_2014 as legacy
import backfill_dart_legacy_quarterly as older
import dart_backfill_health as health
import dart_collection_storage as storage
import run_full_dart_backfill as coverage
import backfill_super_value_fast as fast
import backfill_super_value_signals as signals


def expect_error(function, kind):
    try:
        function()
    except kind:
        return
    raise AssertionError(f"expected {kind.__name__}")


def task(index=0):
    return {"stock_code": f"{index+1:06d}", "corp_code": f"{index+1:08d}", "year": 2020,
            "period": "Q1", "period_end": "2020-03-31", "reprt_code": "11013", "fs_div": "CFS"}


def account(amount="100"):
    return {"rcept_no": "20200515000001", "sj_div": "BS", "account_id": "future_account",
            "account_nm": "fixture account", "thstrm_nm": "current", "thstrm_amount": amount,
            "future_unknown_field": "preserve all source columns"}


def fixture(root):
    stack = ExitStack()
    paths = {"FULL_DIR": root / "full_history", "STATUS_DIR": root / "status", "MAP_FILE": root / "map.csv",
             "TASK_FILE": root / "state.csv", "STATUS_FILE": root / "summary.csv", "RUN_FILE": root / "status/run.json"}
    for key, value in paths.items():
        stack.enter_context(patch.object(full, key, value))
    stack.enter_context(patch.object(storage, "RAW_ROOT", root / "raw"))
    stack.enter_context(patch.object(health, "RAW_ROOT", root / "raw"))
    stack.enter_context(patch.object(coverage, "COVERAGE_FILE", root / "coverage.csv"))
    stack.enter_context(patch.object(coverage, "COVERAGE_STATUS_FILE", root / "coverage-summary.csv"))
    full.FULL_DIR.mkdir(parents=True)
    stack.enter_context(patch.object(full, "WORKERS", 1))
    stack.enter_context(patch.object(full, "CHECKPOINT_TASKS", 1))
    stack.enter_context(patch.object(full, "API_KEY", "fixture-key"))
    return stack


def storage_test(root):
    with fixture(root):
        params = {"corp_code": "00000001", "bsns_year": "2020", "reprt_code": "11013", "fs_div": "CFS", "crtfc_key": "DO_NOT_PERSIST"}
        response = {"status": "000", "list": [account()], "unknown_response_field": "keep me"}
        path, digest = storage.archive_api_response(params, response)
        old_bytes = path.read_bytes()
        assert storage.archive_api_response(params, response) == (path, digest)
        assert path.read_bytes() == old_bytes
        data = gzip.decompress(old_bytes)
        assert b"DO_NOT_PERSIST" not in data and b"crtfc_key" not in data
        assert json.loads(data)["response"] == response
        response["list"][0]["thstrm_amount"] = "200"
        changed, _ = storage.archive_api_response(params, response)
        assert changed != path and path.read_bytes() == old_bytes
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("statement.xml", "fixture: all accounts, not just four metrics")
            archive.writestr("attachment.pdf", b"fixture attachment")
        blob = payload.getvalue(); receipt = "20010331000001"
        zip_path, _ = storage.archive_document(receipt, blob)
        assert storage.cached_document(receipt)[0] == blob
        storage.archive_document(receipt, blob)
        assert len(list(storage.RAW_ROOT.glob("documents/*/*/*.zip"))) == 1
        with patch.object(legacy.requests, "get", side_effect=AssertionError("cache must not download")):
            assert legacy.fetch_document(receipt)[0] == blob
            assert older.download_document(receipt)[0][0] == "statement.xml"
        zip_path.write_bytes(b"corrupted")
        expect_error(lambda: storage.cached_document(receipt), ValueError)
        expect_error(lambda: storage.archive_document("../invalid", blob), ValueError)
        expect_error(lambda: storage.archive_document("20010331000002", b"PKbroken"), ValueError)
        safe = root / "atomic.json"
        storage.atomic_json(safe, {"previous": True})
        with patch.object(storage.os, "replace", side_effect=OSError("fixture write failure")):
            expect_error(lambda: storage.atomic_json(safe, {"previous": False}), OSError)
        assert json.loads(safe.read_text()) == {"previous": True}
        assert not list(root.glob(".pending-*"))
        with storage.collector_lock(root / "lock"):
            expect_error(lambda: storage.collector_lock(root / "lock").__enter__(), RuntimeError)
        with patch.dict(os.environ, {"DART_API_KEY": "fixture-private-key"}):
            message = storage.redacted_error(RuntimeError("url?crtfc_key=fixture-private-key&corp_code=123"))
        assert "fixture-private-key" not in message and "[REDACTED]" in message
        with patch.object(storage, "PROCESS_DEADLINE", -1), patch.object(legacy.requests, "get") as network:
            expect_error(lambda: list(storage.bounded_results(lambda item: legacy.requests.get(item), ["unused"], 1, lambda result, error: False)), storage.TimeBudgetExceeded)
            network.assert_not_called()


def archive_and_digest_test(root):
    with fixture(root), patch.object(full.requests, "get") as get:
        get.return_value = Mock(json=lambda: {"status": "000", "list": [account()]}, raise_for_status=lambda: None)
        state, rows = full.process_task(task())
        assert state["status"] == "OK" and rows[0]["future_unknown_field"]
        assert len(list(storage.RAW_ROOT.glob("api/*/*.json.gz"))) == 1
        full.merge_full_rows(rows)
        first = next(full.FULL_DIR.glob("*.gz")); before = first.read_bytes()
        repeated = [{**r, "_collected_at_utc": "2027-01-01T00:00:00Z"} for r in rows]
        full.merge_full_rows(repeated)
        assert len(list(full.FULL_DIR.glob("*.gz"))) == 1
        full.merge_full_rows([{**r, "thstrm_amount": "999"} for r in rows])
        assert len(list(full.FULL_DIR.glob("*.gz"))) == 2 and first.read_bytes() == before
        values = [pd.read_csv(p, dtype=str)["thstrm_amount"].iloc[0] for p in full.FULL_DIR.glob("*.gz")]
        assert set(values) == {"100", "999"}
        for status in ("013", "014"):
            get.return_value.json = lambda status=status: {"status": status, "message": "no data"}
            assert full.process_task(task())[0]["status"] == "NO_DATA"
        get.return_value.json = lambda: {"status": "000", "list": []}
        expect_error(lambda: full.process_task(task()), ValueError)


def progress_test(root):
    with fixture(root):
        tasks = pd.DataFrame([task(), task(1), task(2)])
        records = [{**task(), "status": "OK", "updated_at_utc": "2020-01-01"},
                   {**task(), "status": "ERROR", "updated_at_utc": "2020-02-01"},
                   {**task(1), "status": "NO_DATA", "updated_at_utc": "2020-01-01"},
                   {**task(99), "status": "OK", "updated_at_utc": "2020-01-01"}]
        state = pd.DataFrame(records)
        progress = full.task_progress(tasks, state)
        assert progress["completed_tasks"] == 1 and progress["remaining_tasks_estimate"] == 2
        assert progress["error_tasks"] == 1 and progress["ok_tasks"] == 0 and progress["state_tasks_outside_current_plan"] == 1
        full.save_state(records)
        assert len(full.read_done_keys()) == 1  # Missing OK source group resumes; NO_DATA stays terminal.
        coverage.write_pit_coverage(tasks)
        table = pd.read_csv(coverage.COVERAGE_FILE)
        assert table["completed_tasks"].sum() == progress["completed_tasks"]
        assert table["codes_with_data"].sum() == 0
        coverage.write_pit_coverage(pd.DataFrame())
        assert pd.read_csv(coverage.COVERAGE_STATUS_FILE)["expected_tasks"].iloc[0] == 0


def checkpoint_test(root, error_type):
    with fixture(root):
        tasks = pd.DataFrame([task(i) for i in range(4)])
        mapping = pd.DataFrame([{"mapping_method": "stock_code"}])
        process = full.process_task
        seen = []
        def fail_on_second(item):
            seen.append(item["stock_code"])
            if len(seen) == 2:
                # First completed source/state must already be durable.
                stored = pd.read_csv(full.TASK_FILE)
                assert stored["status"].eq("OK").sum() == 1
                raise error_type("fixture stop")
            with patch.object(full, "api_call", return_value=[account()]):
                return process(item)
        with patch.object(full, "load_all_dart_corps", return_value=pd.DataFrame()), patch.object(full, "build_historical_code_map", return_value=mapping), patch.object(full, "build_tasks", return_value=tasks), patch.object(full, "process_task", side_effect=fail_on_second):
            expect_error(full.main, error_type)
        assert len(seen) == 2  # Never dispatch remaining tasks after quota/fatal failure.
        state = pd.read_csv(full.TASK_FILE)
        assert set(state["status"]) == {"OK", "ERROR"}
        run = json.loads(full.RUN_FILE.read_text())
        assert run["processed_this_run"] == 2 and run["status"] != "running"
        assert len(full.read_done_keys()) == 1
        assert pd.read_csv(full.STATUS_FILE)["completed_tasks"].iloc[0] == 1
        # Resuming skips durable first task and retries failed/unsubmitted tasks.
        with patch.object(full, "load_all_dart_corps", return_value=pd.DataFrame()), patch.object(full, "build_historical_code_map", return_value=mapping), patch.object(full, "build_tasks", return_value=tasks), patch.object(full, "api_call", return_value=[]):
            full.main()
        assert pd.read_csv(full.STATUS_FILE)["completed_tasks"].iloc[0] == 4
        assert json.loads(full.RUN_FILE.read_text())["status"] == "ok"


def legacy_checkpoint_test(root):
    root.mkdir()
    with ExitStack() as stack:
        for key, value in {"STATE_FILE": root / "state.csv", "NORM_DIR": root / "normalized", "WORKERS": 1, "CHECKPOINT_DOCS": 1}.items():
            stack.enter_context(patch.object(legacy, key, value))
        legacy.NORM_DIR.mkdir()
        index = pd.DataFrame([{"rcept_no": f"2001033100000{i}", "rcept_dt": "2001-03-31", "stock_code": "000001"} for i in range(1, 4)])
        def parse(meta):
            receipt = meta["rcept_no"]
            if receipt.endswith("2"):
                assert pd.read_csv(legacy.STATE_FILE)["status"].iloc[0] == "PARSED_PARTIAL"
                return [], {"rcept_no": receipt, "status": "RATE_LIMIT", "parser_version": legacy.PARSER_VERSION}
            return [{"rcept_no": receipt, "metric": "equity", "scope": "OFS", "fiscal_year": 2001, "amount_krw": 100}], {"rcept_no": receipt, "status": "PARSED_PARTIAL", "parser_version": legacy.PARSER_VERSION}
        with patch.object(legacy, "process_filing", side_effect=parse) as parse_call:
            expect_error(lambda: legacy.process_pending(index), legacy.RateLimitExceeded)
            assert parse_call.call_count == 2
        assert (legacy.NORM_DIR / "legacy_metrics_2001.csv.gz").exists()
        assert len(pd.read_csv(legacy.STATE_FILE)) == 2


def real_snapshot_test():
    # Repository state only; no live API, source mutation or fabricated coverage.
    with patch("requests.get", side_effect=AssertionError("offline health must not request data")):
        report = health.health_snapshot()
    full_report = report["full_history"]
    assert full_report["completed_tasks"] == full_report["ok_tasks"] + full_report["no_data_tasks"]
    assert full_report["completed_tasks"] <= full_report["total_available_tasks"]
    assert full_report["source_snapshot"]["sha256"]
    assert report["legacy"]["provider_connected"] is False
    assert report["raw_archives"]["scope"].startswith("newly archived")
    assert full_report["run"]["observation"] in ("unknown", "recorded_status", "stale_heartbeat")


def priority_path_test(root):
    with fixture(root / "modern"), patch.object(fast, "modern", full), patch.object(fast, "STATEMENT_SCOPE", "both"), patch.object(fast, "MODERN_WORKERS", 1):
        cfs = task(); ofs = {**cfs, "fs_div": "OFS"}
        tasks = pd.DataFrame([cfs, ofs, {**task(9), "year": 2015, "period": "Q1"}])
        mapping = pd.DataFrame([{"mapping_method": "stock_code"}])
        with patch.object(full, "load_all_dart_corps", return_value=pd.DataFrame()), patch.object(full, "build_historical_code_map", return_value=mapping), patch.object(full, "build_tasks", return_value=tasks), patch.object(full, "api_call", return_value=[account()]):
            result = fast.modern_fast()
        assert result["modern_total_cfs"] == 1 and result["modern_run_tasks"] == 2
        stored = pd.read_csv(full.TASK_FILE)
        assert set(stored["fs_div"]) == {"CFS", "OFS"} and stored["year"].eq(2020).all()
    with fixture(root / "signal"), patch.object(signals, "modern", full), patch.object(signals, "WORKERS", 1), patch.object(full, "api_call", return_value=[account()]):
        assert signals.process_chunk(pd.DataFrame([task()])) == (1, False)
        rows = pd.read_csv(next(full.FULL_DIR.glob("*.gz")))
        assert rows["account_id"].iloc[0] == "future_account"  # The old four-factor filter dropped this.
    for scope, expected in (("all_filings", 2), ("signal_priority", 1)):
        directory = root / scope; directory.mkdir(parents=True)
        index = pd.DataFrame([{"rcept_no": f"2001033100000{i}", "rcept_dt": pd.Timestamp("2001-03-31"),
                               "stock_code": "000001", "period": "Q1", "signal_cutoff": pd.Timestamp("2001-10-31")} for i in (1, 2)])
        with patch.object(fast, "legacy", legacy), patch.object(fast, "COLLECTION_SCOPE", scope), patch.object(fast, "LEGACY_LIMIT", 2), patch.object(fast, "LEGACY_WORKERS", 1), patch.object(legacy, "STATE_FILE", directory / "state.csv"), patch.object(legacy, "INDEX_FILE", directory / "absent.csv"), patch.object(legacy, "update_filing_index", return_value=index), patch.object(fast, "legacy_target_index", return_value=index.tail(1)):
            def empty_metrics(meta):
                return [], {"rcept_no": meta["rcept_no"], "status": "NO_METRICS", "parser_version": legacy.PARSER_VERSION,
                            "updated_at_utc": storage.now_utc()}
            with patch.object(legacy, "process_filing", side_effect=empty_metrics) as parsing:
                result = fast.legacy_fast()
            assert result["legacy_target_docs"] == expected and parsing.call_count == expected


def main():
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        storage_test(root / "storage")
        archive_and_digest_test(root / "digest")
        progress_test(root / "progress")
        checkpoint_test(root / "fatal", full.FatalDartError)
        checkpoint_test(root / "quota", full.RateLimitExceeded)
        legacy_checkpoint_test(root / "legacy")
        priority_path_test(root / "priority")
    real_snapshot_test()
    print("DART COLLECTION: PASS (all-account sources, immutable ZIP/cache/checksum, atomic writes, current-plan counts, checkpoint/resume, bounded quota stop, offline real-state health)")


if __name__ == "__main__":
    main()
