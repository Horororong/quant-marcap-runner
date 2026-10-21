"""Offline failure boundaries; actual requests integration runs in existing CI."""
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import zipfile
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dart_corp_code import CorpCodeError, fetch_corp_code, parse_corp_code
from csv_storage import atomic_write_if_changed

XML = b'<result><list><corp_code>00126380</corp_code><corp_name>Samsung</corp_name><stock_code>005930</stock_code><modify_date>20260101</modify_date></list></result>'


def archive(payload=XML, member="CORPCODE.xml"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(member, payload)
    return stream.getvalue()


def response(payload, status=200):
    return SimpleNamespace(content=payload, status_code=status)


def source_function(file, name, namespace):
    # Execute the real function body under controlled transport/dependency doubles,
    # without installing requests/pytest into the immutable offline kit.
    path = ROOT / file if file == "update_dart_financials.py" else ROOT / "scripts" / file
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class CorpCodeTests(unittest.TestCase):
    def fetch(self, *items):
        self.get = Mock(side_effect=items)
        self.sleep = Mock()
        return fetch_corp_code(self.get, "https://example.invalid/corpCode.xml", "private-test-key", sleep=self.sleep)

    def test_valid_zip(self):
        self.assertEqual(parse_corp_code(archive())[0]["stock_code"], "005930")

    def test_non_xml_first_member_is_not_chosen(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("README.txt", b"not financial data")
            z.writestr("CORPCODE.xml", XML)
        self.assertEqual(parse_corp_code(stream.getvalue())[0]["corp_code"], "00126380")

    def test_timeout_recovers_with_bounded_attempts(self):
        rows = self.fetch(TimeoutError("private-test-key in URL"), response(archive()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.get.call_count, 2)
        self.sleep.assert_called_once_with(1.)

    def test_transient_http_retry_recovers(self):
        self.fetch(response(b"bad gateway", 502), response(archive()))
        self.assertEqual(self.get.call_count, 2)

    def test_timeout_exhaustion_redacts_transport(self):
        with self.assertRaises(CorpCodeError) as caught:
            self.fetch(*[TimeoutError("private-test-key") for _ in range(3)])
        self.assertEqual(caught.exception.attempts, 3)
        self.assertNotIn("private-test-key", str(caught.exception))
        self.assertEqual(self.sleep.call_count, 2)

    def test_quota_and_auth_and_maintenance_do_not_retry(self):
        for status, kind in [("020", "rate_limit"), ("010", "fatal_api"), ("011", "fatal_api"),
                             ("012", "fatal_api"), ("901", "fatal_api"), ("800", "api_error"), ("900", "api_error")]:
            with self.subTest(status=status), self.assertRaises(CorpCodeError) as caught:
                self.fetch(response(f'<result><status>{status}</status><message>private-test-key</message></result>'.encode()))
            self.assertEqual(caught.exception.kind, kind)
            self.assertEqual(caught.exception.status, status)
            self.assertNotIn("private-test-key", str(caught.exception))
            self.assertEqual(self.get.call_count, 1)
            self.sleep.assert_not_called()

    def test_html_body_is_not_assumed_transient(self):
        with self.assertRaises(CorpCodeError) as caught:
            self.fetch(response(b"<html>private-test-key</html>"))
        self.assertEqual(caught.exception.kind, "invalid_response")
        self.assertEqual(self.get.call_count, 1)

    def test_http_quota_and_forbidden_do_not_retry(self):
        for status in (429, 403):
            with self.subTest(status=status), self.assertRaises(CorpCodeError):
                self.fetch(response(b"private-test-key", status))
            self.assertEqual(self.get.call_count, 1)

    def test_truncated_zip_and_xml_and_empty_list_fail(self):
        for content in [archive()[:20], archive(b"<result>"), archive(b"<result/>")]:
            with self.subTest(size=len(content)), self.assertRaises(CorpCodeError):
                parse_corp_code(content)

    def test_invalid_mapping_never_becomes_empty_success(self):
        with self.assertRaises(CorpCodeError):
            parse_corp_code(archive(XML.replace(b"00126380", b"broken")))

    def test_ambiguous_archive_fails(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("a.xml", XML)
            z.writestr("b.xml", XML)
        with self.assertRaises(CorpCodeError):
            parse_corp_code(stream.getvalue())

    def loader(self, payload):
        self.get = Mock(return_value=response(payload))
        self.rate = type("RateLimitExceeded", (RuntimeError,), {})
        self.fatal = type("FatalDartError", (RuntimeError,), {})
        namespace = {"pd": pd, "requests": SimpleNamespace(get=self.get, Timeout=TimeoutError, ConnectionError=ConnectionError),
                     "BASE": "https://example.invalid", "API_KEY": "private-test-key",
                     "fetch_corp_code": fetch_corp_code, "CorpCodeError": CorpCodeError,
                     "RateLimitExceeded": self.rate, "FatalDartError": self.fatal, "normalize_name": str.lower}
        return source_function("backfill_dart_full_financials.py", "load_all_dart_corps", namespace)

    def test_actual_loader_retains_dataframe_contract(self):
        frame = self.loader(archive())()
        self.assertEqual(frame.iloc[0].corp_code, "00126380")
        self.assertEqual(frame.iloc[0].stock_code, "005930")
        self.assertEqual(frame.iloc[0].norm_name, "samsung")

    def test_actual_loader_typed_quota_and_fatal_errors(self):
        for code in ("020", "010"):
            load = self.loader(f"<result><status>{code}</status></result>".encode())
            with self.assertRaises(self.rate if code == "020" else self.fatal) as caught:
                load()
            self.assertEqual(caught.exception.status, code)
            self.assertEqual(self.get.call_count, 1)

    def test_recent_loader_uses_same_checked_response_and_keeps_filter(self):
        for payload, valid in [(archive(), True), (b'<result><status>020</status></result>', False)]:
            get = Mock(return_value=response(payload))
            namespace = {"pd": pd, "requests": SimpleNamespace(get=get, Timeout=TimeoutError, ConnectionError=ConnectionError),
                         "BASE": "https://example.invalid", "API_KEY": "private-test-key", "fetch_corp_code": fetch_corp_code}
            load = source_function("update_dart_financials.py", "get_corp_codes", namespace)
            if valid:
                self.assertEqual(load().iloc[0].stock_code, "005930")
            else:
                with self.assertRaises(CorpCodeError):
                    load()
            self.assertEqual(get.call_count, 1)

    def main(self, path, modern_call, legacy_result=None):
        namespace = {"os": os, "datetime": datetime, "timezone": timezone, "pd": pd,
                     "time": time, "json": json, "LEGACY_LIMIT": 1,
                     "MODERN_LIMIT": 1, "STATUS_FILE": path,
                     "legacy_fast": Mock(return_value=legacy_result or {"legacy_run_docs": 1475, "legacy_stop_reason": "BATCH_COMPLETE"}),
                     "modern_fast": modern_call, "modern": SimpleNamespace(RateLimitExceeded=RuntimeError),
                     "legacy": SimpleNamespace(atomic_write_if_changed=atomic_write_if_changed)}
        return source_function("backfill_super_value_fast.py", "main", namespace)

    def test_current_status_published_before_modern_failure(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DART_API_KEY": "private-test-key"}):
            path = Path(tmp) / "status.csv"
            modern_call = Mock(side_effect=CorpCodeError("invalid_response"))
            with self.assertRaisesRegex(RuntimeError, "current failure status preserved"):
                self.main(path, modern_call)()
            row = pd.read_csv(path).iloc[0]
            self.assertEqual(row.legacy_run_docs, 1475)
            self.assertTrue(row.modern_failed)
            self.assertEqual(row.modern_failure_kind, "invalid_response")
            self.assertTrue(pd.isna(row.modern_run_tasks))
            self.assertNotIn("private-test-key", path.read_text())
            modern_call.assert_called_once()

    def test_generic_exception_details_not_published(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DART_API_KEY": "private-test-key"}):
            path = Path(tmp) / "status.csv"
            with self.assertRaises(RuntimeError) as caught:
                self.main(path, Mock(side_effect=ValueError("private-test-key")))()
            self.assertNotIn("private-test-key", str(caught.exception) + path.read_text())

    def test_no_modern_calls_after_legacy_quota(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DART_API_KEY": "private-test-key"}):
            modern_call = Mock(side_effect=AssertionError("unexpected network"))
            path = Path(tmp) / "status.csv"
            self.main(path, modern_call, {"legacy_rate_limited": True})()
            modern_call.assert_not_called()
            self.assertTrue(pd.read_csv(path).iloc[0].modern_skipped)

    def test_success_path_still_preserves_both_counts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DART_API_KEY": "private-test-key"}):
            path = Path(tmp) / "status.csv"
            self.main(path, Mock(return_value={"modern_run_tasks": 1000}))()
            self.assertEqual(pd.read_csv(path).iloc[0].modern_run_tasks, 1000)

    def test_unknown_or_deadline_legacy_stop_never_starts_modern(self):
        for result in ({"legacy_run_docs": 2}, {"legacy_run_docs": 2, "legacy_stop_reason": "DEADLINE"}):
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DART_API_KEY": "private-test-key"}):
                modern_call = Mock(side_effect=AssertionError("unexpected network"))
                path = Path(tmp) / "status.csv"
                self.main(path, modern_call, result)()
                modern_call.assert_not_called()
                self.assertTrue(pd.read_csv(path).iloc[0].modern_skipped)


if __name__ == "__main__":
    unittest.main()
