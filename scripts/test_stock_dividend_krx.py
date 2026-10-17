"""Synthetic transport tests; no KRX credential/network is used."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from collect_stock_dividend_krx import acquire, Stop


class KrxTests(unittest.TestCase):
    def test_missing_auth_no_requests(self):
        with TemporaryDirectory() as td:
            r = acquire(Path(td) / "out", "", lambda *a: self.fail("unexpected request"))
            self.assertEqual((r["requests"], r["status"]), (0, "UNVERIFIED"))

    def test_http_failure_stops_once(self):
        def fail(*a):
            raise Stop("HTTP_FAILURE", 403)
        with TemporaryDirectory() as td:
            r = acquire(Path(td) / "out", "synthetic-key", fail)
            self.assertEqual((r["requests"], r["retries"], r["error"]["http_status"]), (1, 0, 403))

    def test_echo_is_not_saved(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "out"
            r = acquire(p, "synthetic-key", lambda *a: (200, b'{"message":"synthetic-key"}'))
            self.assertEqual(r["error"]["kind"], "CREDENTIAL_ECHO_BLOCKED")
            self.assertEqual([f.name for f in p.iterdir()], ["state.json"])

    def test_eight_scoped_replies_preserve_exact_target_rows(self):
        def fetch(endpoint, dt, key):
            security = "068270" if endpoint == "stk_bydd_trd" else "091990"
            return 200, json.dumps({"OutBlock_1": [{"BAS_DD": dt, "ISU_CD": security, "TDD_CLSPRC": "100", "FLUC_RT": "0.00"}]}).encode()
        with TemporaryDirectory() as td:
            r = acquire(Path(td) / "out", "synthetic-key", fetch)
            self.assertEqual((r["requests"], len(r["responses"]), len(r["target_rows"])), (8, 8, 8))
            self.assertEqual(r["status"], "COMPLETE_OFFICIAL_PRICE_ROWS_ONLY")
            self.assertFalse(r["investment_approved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
