"""Bound the extra October legacy batches before dependencies or API calls."""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DAILY_CRON = "30 15 * * *"
BURST_CRON = "30 7,23 * 10 *"
BURST_END_KST = date(2026, 10, 31)
KST = timezone(timedelta(hours=9))
STATUS_FILE = Path("data/status/dart_legacy_backfill_status.csv")


def batch_decision(event: str, schedule: str, now: datetime, status_file: Path):
    if event != "schedule" or schedule == DAILY_CRON:
        return True, "REGULAR_BATCH"
    if schedule != BURST_CRON:
        raise ValueError("Unknown extra-batch schedule")
    if now.tzinfo is None:
        raise ValueError("Timezone-aware execution time required")
    # Actual start time also prevents a delayed October trigger running in November.
    if now.astimezone(KST).date() > BURST_END_KST:
        return False, "OCTOBER_BURST_EXPIRED"
    with status_file.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError("One durable legacy coverage row required")
    pending = int(rows[0]["automatic_pending_filings"])
    if pending < 0:
        raise ValueError("Invalid automatic pending count")
    return (True, "OCTOBER_LEGACY_BATCH") if pending else (False, "NO_AUTOMATIC_PENDING")


def main():
    allowed, reason = batch_decision(
        os.environ["GITHUB_EVENT_NAME"], os.getenv("BATCH_SCHEDULE", ""),
        datetime.now(timezone.utc), STATUS_FILE,
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write(f"run={'true' if allowed else 'false'}\n")
    print(f"Legacy batch: {reason}; run={allowed}", flush=True)


if __name__ == "__main__":
    main()
