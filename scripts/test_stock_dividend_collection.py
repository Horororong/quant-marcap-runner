"""Offline tests: no real credential/network used."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from collect_stock_dividend_metadata import acquire, transport


class TransportTests(unittest.TestCase):
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
