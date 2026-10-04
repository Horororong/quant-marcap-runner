"""Scheduled execution must share the same resumable legacy queue."""
from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts import backfill_super_value_fast as fast


def test_daily_wrapper_uses_whole_index_and_generic_checkpoint(monkeypatch, tmp_path):
    # Both the initial receipt and its correction must be collected. Neither
    # signal cutoffs nor a strategy-specific last-receipt selection may drop one.
    idx = pd.DataFrame([{"rcept_no": "20010101000001", "stock_code": "000001"},
                        {"rcept_no": "20010201000002", "stock_code": "000001"}])
    calls = []
    monkeypatch.setattr(fast, "LEGACY_LIMIT", 100)
    monkeypatch.setattr(fast.legacy, "update_filing_index", lambda: idx)
    monkeypatch.setattr(fast.legacy, "load_csv", lambda *args, **kwargs: idx)
    monkeypatch.setattr(fast.legacy, "write_coverage", lambda frame: None)
    monkeypatch.setattr(fast, "legacy_target_index", lambda *args: pytest.fail("strategy subset used"))

    def collect(frame, **kwargs):
        calls.extend(frame.rcept_no)
        assert kwargs["max_docs"] == 100 and kwargs["control"] is fast.legacy.RUN_CONTROL
        return {"completed": 2, "eligible_before_run": 2, "rate_limited": False,
                "stop_reason": "BATCH_COMPLETE", "requests": 2, "quarantined_errors": 0}

    monkeypatch.setattr(fast.legacy, "process_pending", collect)
    result = fast.legacy_fast()
    assert calls == idx.rcept_no.tolist()
    assert result["legacy_scope"] == "ALL_MAPPED_RECEIPTS"
    assert fast.legacy.RUN_CONTROL is None


def test_legacy_runs_first_and_rate_limit_blocks_modern_calls(monkeypatch, tmp_path):
    order = []
    monkeypatch.setenv("DART_API_KEY", "test-not-real")
    monkeypatch.setattr(fast, "MODERN_LIMIT", 100)
    monkeypatch.setattr(fast, "STATUS_FILE", tmp_path / "status.csv")
    monkeypatch.setattr(fast, "legacy_fast", lambda: (order.append("legacy") or {"legacy_rate_limited": True}))
    monkeypatch.setattr(fast, "modern_fast", lambda: pytest.fail("modern API after 020"))
    fast.main()
    assert order == ["legacy"]
    saved = pd.read_csv(fast.STATUS_FILE).iloc[0]
    assert saved["modern_skipped"] and saved["modern_run_tasks"] == 0


def test_zero_legacy_limit_makes_no_api_or_index_calls(monkeypatch):
    monkeypatch.setattr(fast, "LEGACY_LIMIT", 0)
    monkeypatch.setattr(fast.legacy, "update_filing_index", lambda: pytest.fail("disabled legacy called API"))
    assert fast.legacy_fast()["legacy_run_docs"] == 0


def workflow(name):
    # BaseLoader keeps the GitHub 'on' key as text rather than YAML 1.1 True.
    return yaml.load((Path(".github/workflows") / name).read_text(), Loader=yaml.BaseLoader)


def test_scheduled_and_manual_writers_share_lock_without_cancellation():
    names = ["backfill-super-value-fast.yml", "backfill-dart-legacy-2000-2014.yml",
             "backfill-dart-value-factors.yml", "backfill-super-value-signals.yml"]
    specs = [workflow(name) for name in names]
    assert len({spec["concurrency"]["group"] for spec in specs}) == 1
    assert all(spec["concurrency"]["cancel-in-progress"] == "false" for spec in specs)
    daily = specs[0]
    assert daily["on"]["schedule"] == [{"cron": "30 15 * * *"}, {"cron": "30 7,23 * 10 *"}]
    assert "schedule" not in specs[1]["on"]
    assert daily["on"]["push"]["branches"] == ["main"]
    # Self-generated data commits must not trigger catch-up again.
    assert not any(path.startswith("data/") for path in daily["on"]["push"]["paths"])


def test_extra_batches_gate_all_api_and_publish_steps_and_skip_modern():
    daily = workflow("backfill-super-value-fast.yml")
    job = daily["jobs"]["fast"]
    steps = job["steps"]
    gate = next(step for step in steps if step.get("id") == "batch")
    assert steps.index(gate) == 1  # Immediately after the checkout of current main.
    assert gate["run"] == "python scripts/legacy_schedule_gate.py"
    assert gate["env"]["BATCH_SCHEDULE"] == "${{ github.event.schedule }}"
    for step in steps[2:]:
        assert "steps.batch.outputs.run == 'true'" in step["if"]
    modern = job["env"]["SUPER_VALUE_FAST_MODERN_TASKS"]
    assert "github.event_name == 'schedule'" in modern
    assert "github.event.schedule != '30 15 * * *'" in modern
    # Increase batches, preserving per-run throttling and deployment size.
    assert "'2000'" in job["env"]["SUPER_VALUE_FAST_LEGACY_DOCS"]
    assert "'100'" in job["env"]["SUPER_VALUE_FAST_LEGACY_DOCS"]
    assert job["env"]["SUPER_VALUE_FAST_LEGACY_WORKERS"] == "3"


@pytest.mark.parametrize("name", ["backfill-super-value-fast.yml", "backfill-dart-legacy-2000-2014.yml"])
def test_workflow_saves_checkpoint_after_failure_and_has_time_to_publish(name):
    spec = workflow(name)
    job = next(iter(spec["jobs"].values()))
    assert job["if"] == "github.ref == 'refs/heads/main'"
    collector = next(step for step in job["steps"] if step.get("run", "").startswith("python scripts/backfill"))
    commit = next(step for step in job["steps"] if step.get("name", "").startswith("Commit"))
    assert "always()" in commit["if"] and "steps.checkout.outcome" in commit["if"]
    assert int(job["timeout-minutes"]) - int(collector["timeout-minutes"]) >= 15
    assert float(job["env"]["LEGACY_DART_REQUEST_INTERVAL"]) >= 0.5
    assert job["env"]["LEGACY_DART_CHECKPOINT_SIZE"] == "25"
    assert any(step.get("with", {}).get("name") == "legacy-recovery-checkpoint" for step in job["steps"])


def test_source_capture_reuses_existing_audit_workflow_without_new_schedule():
    spec = workflow("audit-legacy-pit.yml")
    assert "schedule" not in spec["on"]
    assert spec["concurrency"] == workflow("backfill-super-value-fast.yml")["concurrency"]
    assert spec["on"]["push"]["branches"] == ["main"]
    assert not any(path.startswith(("data/", "docs/audits/")) for path in spec["on"]["push"]["paths"])
    job = spec["jobs"]["audit"]
    artifact = next(step for step in job["steps"] if step.get("with", {}).get("name") == "legacy-original-source-evidence")
    assert artifact["with"]["retention-days"] == "90"
    commit = next(step for step in job["steps"] if step.get("name") == "Commit audit report")
    assert "always()" in commit["if"]


def test_verified_operator_batch_is_explicit_and_uses_existing_bounded_job():
    spec = workflow("backfill-super-value-fast.yml")
    job = spec["jobs"]["fast"]
    for key in ("SUPER_VALUE_FAST_LEGACY_DOCS", "LEGACY_DART_MAX_REQUESTS", "LEGACY_DART_MAX_SECONDS"):
        assert "[legacy-verified-batch-2000]" in job["env"][key]
    assert "'100'" in job["env"]["SUPER_VALUE_FAST_LEGACY_DOCS"]
    assert "'2500'" in job["env"]["LEGACY_DART_MAX_REQUESTS"]
    assert "'3300'" in job["env"]["LEGACY_DART_MAX_SECONDS"]
    assert spec["on"]["schedule"] == [{"cron": "30 15 * * *"}, {"cron": "30 7,23 * 10 *"}]
