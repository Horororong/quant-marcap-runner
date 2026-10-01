"""Offline authoritative-state snapshot, not a live-process/PIT certificate."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
from contextlib import redirect_stdout

import pandas as pd
import backfill_dart_full_financials as full
import run_full_dart_backfill as coverage
from dart_collection_storage import atomic_csv, atomic_json, collector_lock, RAW_ROOT


def read_snapshot(path):
    if not path.exists():
        return pd.DataFrame(), None
    payload = path.read_bytes()
    frame = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)
    stamp = frame["updated_at_utc"].max() if "updated_at_utc" in frame and len(frame) else None
    return frame, {"file": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                   "latest_task_update_utc": stamp}


def run_observation(path, at, stale_hours):
    if not path.exists():
        return {"observation": "unknown", "reason": "no instrumented collector run record"}
    record = json.loads(path.read_text())
    age = (at - pd.Timestamp(record["heartbeat_at_utc"]).to_pydatetime()).total_seconds() / 3600
    return {"observation": "stale_heartbeat" if record["status"] == "running" and age > stale_hours else "recorded_status",
            "heartbeat_age_hours": round(age, 2), "record": record,
            "scope": "stored heartbeat only; not an independently observed live process"}


def health_snapshot(at=None, stale_hours=24):
    at = at or datetime.now(timezone.utc)
    mapping = pd.read_csv(full.MAP_FILE, dtype=str, keep_default_na=False)
    tasks = coverage.build_tasks_fixed(mapping, at + timedelta(hours=9))
    state, source = read_snapshot(full.TASK_FILE)
    progress = full.task_progress(tasks, state)
    latest = full.latest_task_state(state)
    missing = []
    if len(latest):
        for (year, period, fs), group in latest[latest["status"].eq("OK")].groupby(["year", "period", "fs_div"]):
            if not full.shard_path(int(year), period, fs).exists() and not list(full.FULL_DIR.glob(f"dart_full_{int(year)}_{period}_{fs}_*.csv.gz")):
                missing.append({"year": int(year), "period": period, "fs_div": fs, "ok_tasks": len(group)})
    legacy, legacy_source = read_snapshot(full.STATUS_DIR / "dart_legacy_backfill_state.csv")
    if len(legacy):
        legacy = legacy.sort_values("updated_at_utc", kind="stable").drop_duplicates("rcept_no", keep="last")
    legacy_counts = {str(k): int(v) for k, v in legacy["status"].value_counts().items()} if len(legacy) else {}
    return {"contract_version": "1", "generated_at_utc": at.isoformat(),
            "scope": "offline collection snapshot; task completion/parse success do not certify validated PIT factors",
            "full_history": {**progress, "state_status_counts": {str(k): int(v) for k, v in latest["status"].value_counts().items()} if len(latest) else {},
                "source_snapshot": source, "mapped_codes": int(mapping["corp_code"].str.fullmatch(r"\d{8}").sum()),
                "unresolved_codes": int((~mapping["corp_code"].str.fullmatch(r"\d{8}")).sum()),
                "missing_raw_groups": missing, "run": run_observation(full.RUN_FILE, at, stale_hours)},
            "legacy": {"source_snapshot": legacy_source, "receipt_status_counts": legacy_counts,
                "run": run_observation(full.STATUS_DIR / "dart_legacy_collection_run.json", at, stale_hours),
                "provider_connected": False},
            "fast_backfill": run_observation(full.STATUS_DIR / "dart_fast_collection_run.json", at, stale_hours),
            "raw_archives": {"directory": str(RAW_ROOT), "document_zip_count": len(list(RAW_ROOT.glob("documents/*/*/*.zip"))),
                "api_json_count": len(list(RAW_ROOT.glob("api/*/*.json.gz"))),
                "precontract_whole_account_coverage": "not_certified; some historical collectors filtered source accounts",
                "scope": "newly archived sources only; historical terminal states were not re-downloaded"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="atomically refresh full-history summaries from local state; no API calls")
    parser.add_argument("--stale-hours", type=float, default=24)
    args = parser.parse_args()
    if args.refresh:
        with collector_lock(full.STATUS_DIR / ".dart_full_collection.lock"):
            result = health_snapshot(stale_hours=args.stale_hours)
            progress = result["full_history"]
            old = pd.read_csv(full.STATUS_FILE).iloc[0].to_dict() if full.STATUS_FILE.exists() else {}
            old.update({key: progress[key] for key in full.task_progress(pd.DataFrame(), pd.DataFrame())})
            old.update(status="SNAPSHOT_ONLY", updated_at_utc=result["generated_at_utc"],
                       historical_codes=progress["mapped_codes"] + progress["unresolved_codes"],
                       mapped_codes=progress["mapped_codes"], unmatched_codes=progress["unresolved_codes"],
                       source_state_sha256=progress["source_snapshot"]["sha256"] if progress["source_snapshot"] else "")
            atomic_csv(pd.DataFrame([old]), full.STATUS_FILE)
            with redirect_stdout(sys.stderr):
                coverage.write_pit_coverage(coverage._latest_tasks)
            atomic_json(full.STATUS_DIR / "dart_collection_health.json", result)
    else:
        result = health_snapshot(stale_hours=args.stale_hours)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
