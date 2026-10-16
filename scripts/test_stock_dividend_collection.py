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


if __name__ == "__main__":
    unittest.main(verbosity=2)
