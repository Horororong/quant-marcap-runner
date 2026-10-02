"""Offline boundaries for expiring extra collection without breaking daily resume."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from legacy_schedule_gate import BURST_CRON, DAILY_CRON, batch_decision


class ScheduleGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.status = Path(self.directory.name) / "status.csv"
        self.now = datetime(2026, 10, 31, 14, 59, 59, tzinfo=timezone.utc)

    def write_pending(self, value):
        self.status.write_text(f"automatic_pending_filings\n{value}\n", encoding="utf-8-sig")

    def test_last_second_of_october_allows_pending_batch(self):
        self.write_pending(113719)
        self.assertEqual(batch_decision("schedule", BURST_CRON, self.now, self.status),
                         (True, "OCTOBER_LEGACY_BATCH"))

    def test_kst_expiry_skips_even_without_status(self):
        start = datetime(2026, 10, 31, 15, tzinfo=timezone.utc)
        self.assertEqual(batch_decision("schedule", BURST_CRON, start, self.status),
                         (False, "OCTOBER_BURST_EXPIRED"))

    def test_queue_completion_skips_extra_batch(self):
        self.write_pending(0)
        self.assertEqual(batch_decision("schedule", BURST_CRON, self.now, self.status),
                         (False, "NO_AUTOMATIC_PENDING"))

    def test_regular_daily_push_and_manual_do_not_depend_on_coverage(self):
        after = datetime(2026, 11, 1, tzinfo=timezone.utc)
        for event, cron in (("schedule", DAILY_CRON), ("push", ""), ("workflow_dispatch", "")):
            with self.subTest(event=event):
                self.assertEqual(batch_decision(event, cron, after, self.status),
                                 (True, "REGULAR_BATCH"))

    def test_missing_or_corrupt_status_fails_before_collection(self):
        with self.assertRaises(FileNotFoundError):
            batch_decision("schedule", BURST_CRON, self.now, self.status)
        for text in ("wrong_column\n1\n", "automatic_pending_filings\n", "automatic_pending_filings\n1\n2\n",
                     "automatic_pending_filings\nNaN\n", "automatic_pending_filings\n-1\n"):
            with self.subTest(text=text):
                self.status.write_text(text, encoding="utf-8")
                with self.assertRaises((ValueError, KeyError)):
                    batch_decision("schedule", BURST_CRON, self.now, self.status)

    def test_unknown_schedule_and_naive_time_fail_closed(self):
        with self.assertRaises(ValueError):
            batch_decision("schedule", "unexpected", self.now, self.status)
        with self.assertRaises(ValueError):
            batch_decision("schedule", BURST_CRON, self.now.replace(tzinfo=None), self.status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
