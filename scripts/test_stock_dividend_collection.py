"""Offline tests: no real credential/network used."""
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile
import importlib.util
import sys
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
from collect_stock_dividend_metadata import acquire, transport
from collect_stock_dividend_documents import fetch_and_quarantine, original


class TransportTests(unittest.TestCase):
    def test_deferred_native_incident_cannot_produce_green_ci(self):
        location = Path(__file__).resolve().parents[1] / "docs/research/stage12-stock-dividend-20261016/validate.py"
        spec = importlib.util.spec_from_file_location("stage12_validation_gate", location)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        with TemporaryDirectory() as td:
            output = Path(td) / "out"
            argv = ["validate", "--output", str(output), "--defer-dart-e2e-after-native-crash"]
            with patch.object(sys, "argv", argv), patch.object(validator.subprocess, "run", return_value=SimpleNamespace(stdout=b"synthetic command pass", stderr=b"", returncode=0)) as run, redirect_stdout(io.StringIO()):
                result = validator.main()
            rows = json.loads((output / "results.json").read_text())
            self.assertEqual(result, 2)
            self.assertEqual(sum(r["status"] == "UNVERIFIED" for r in rows), 1)
            self.assertEqual(run.call_count, len(validator.TESTS))
            self.assertEqual(next(r for r in rows if r["status"] == "UNVERIFIED")["exit_code"], None)

    def archive(self, corp, text=""):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("notice.xml", f'<DOCUMENT><COMPANY-NAME AREGCIK="{corp}">{text}</COMPANY-NAME></DOCUMENT>')
        return stream.getvalue()

    def test_identity_rejection_keeps_safe_raw_bytes_unverified(self):
        payload = self.archive("00000001", "SYNTHETIC different issuer")
        with TemporaryDirectory() as td:
            folder = Path(td)
            with self.assertRaises(original.Stop) as caught:
                fetch_and_quarantine("20191226900748", "x" * 40, folder, "00554024", lambda *a: (200, payload))
            self.assertEqual(caught.exception.kind, "DOCUMENT_CORP_MISMATCH")
            self.assertEqual((folder / "quarantine/20191226900748.zip").read_bytes(), payload)
            self.assertEqual(json.loads((folder / "quarantine/20191226900748.json").read_text())["verdict"], "UNVERIFIED")

    def test_credential_echo_is_not_quarantined(self):
        with TemporaryDirectory() as td:
            folder = Path(td)
            with self.assertRaises(original.Stop) as caught:
                fetch_and_quarantine("20191226900748", "x" * 40, folder, "00554024", lambda *a: (200, self.archive("00000001", "x" * 40)))
            self.assertEqual(caught.exception.kind, "CREDENTIAL_ECHO_BLOCKED")
            self.assertEqual(list(folder.iterdir()), [])

    def test_valid_identity_returns_original_bytes(self):
        payload = self.archive("00554024", "SYNTHETIC issuer")
        with TemporaryDirectory() as td:
            self.assertEqual(fetch_and_quarantine("20191226900748", "x" * 40, Path(td), "00554024", lambda *a: (200, payload)), (200, payload))
            self.assertEqual(list(Path(td).iterdir()), [])

    def run_capture(self, key, fetch):
        with TemporaryDirectory() as td:
            output = Path(td) / "out"
            result = acquire(output, key, fetch)
            contents = b"".join(p.read_bytes() for p in output.iterdir())
            self.assertNotIn(key.encode(), contents) if key else None
            return result

    def test_missing_auth_no_requests(self):
        r = self.run_capture("", lambda *a: self.fail("network forbidden"))
        self.assertEqual((r["requests"], r["status"]), (0, "UNVERIFIED"))

    def test_http_failure_no_retry(self):
        def fail(*a):
            raise transport.Stop("HTTP_FAILURE", 403)
        r = self.run_capture("x" * 40, fail)
        self.assertEqual((r["requests"], r["retries"], r["error"]["http_status"]), (1, 0, 403))

    def test_key_echo_not_saved(self):
        key = "x" * 40
        r = self.run_capture(key, lambda *a: (200, json.dumps({"status": "000", "message": key}).encode()))
        self.assertEqual(r["error"]["kind"], "CREDENTIAL_ECHO_BLOCKED")

    def test_empty_scoped_search_is_not_event_certification(self):
        r = self.run_capture("x" * 40, lambda *a: (200, b'{"status":"013"}'))
        self.assertEqual(r["requests"], 2)
        self.assertEqual(r["status"], "COMPLETE_LIMITED_METADATA_ONLY")
        self.assertFalse(r["backtest_eligible"])

    def test_valid_limited_response_preserves_raw_and_candidate_identity(self):
        def reply(params, key):
            security = "068270" if params["corp_code"] == "00413046" else "091990"
            row = dict(corp_code=params["corp_code"], stock_code=security,
                       rcept_no="20201228000001", rcept_dt="20201228", report_nm="배당락 안내")
            return 200, json.dumps(dict(status="000", total_count=1, total_page=1,
                                       page_no=1, page_count=100, list=[row])).encode()
        r = self.run_capture("x" * 40, reply)
        self.assertEqual((r["requests"], len(r["responses"]), len(r["candidates"])), (2, 2, 2))
        self.assertTrue(all(len(x["sha256"]) == 64 for x in r["responses"]))
        self.assertNotIn("crtfc_key", r["responses"][0]["parameters"])

    def test_page_budget_stops_before_additional_requests(self):
        def reply(params, key):
            rows = [dict(corp_code=params["corp_code"], stock_code="068270",
                         rcept_no=f"20201228{i:06d}", rcept_dt="20201228", report_nm="기타") for i in range(100)]
            return 200, json.dumps(dict(status="000", total_count=201, total_page=3,
                                       page_no=1, page_count=100, list=rows)).encode()
        r = self.run_capture("x" * 40, reply)
        self.assertEqual(r["requests"], 1)
        self.assertEqual(r["error"]["kind"], "DECLARED_PAGE_BUDGET_EXCEEDED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
