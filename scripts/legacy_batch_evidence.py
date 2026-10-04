"""Immutable before/after and primary-source evidence for existing legacy jobs.

This captures evidence, not independently certified amounts or PIT. Selection
is frozen before download/value inspection. No viewer values enter production.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
import pandas as pd
# The fast wrapper sets these only inside its own process. Evidence steps run
# separately and must inherit the actual existing-job limits before import.
os.environ.setdefault("LEGACY_DART_MAX_DOCS", os.getenv("SUPER_VALUE_FAST_LEGACY_DOCS", "20"))
os.environ.setdefault("LEGACY_DART_WORKERS", os.getenv("SUPER_VALUE_FAST_LEGACY_WORKERS", "4"))
try:
    from scripts import backfill_dart_legacy_2000_2014 as legacy
    from scripts.legacy_document_quality import inspect_member, DIAGNOSTIC_VERSION
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import backfill_dart_legacy_2000_2014 as legacy
    from legacy_document_quality import inspect_member, DIAGNOSTIC_VERSION


def identity(path):
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def root():
    return Path(os.environ["LEGACY_DART_EVIDENCE_DIR"])


def selected_samples(state, index):
    # 12 additional NO_METRICS + 12 predeployment parsed receipts: stratified
    # round-robin by fiscal-year/period/status, distinct companies, SHA ranking.
    known = {p.name[:14] for folder in ("native_primary", "recovery_primary")
             for p in Path("tests/fixtures/legacy_dart", folder).glob("*.zip")}
    x = state.merge(index.drop_duplicates("rcept_no"), on="rcept_no", suffixes=("", "_index"))
    x = x[~x.rcept_no.isin(known)].copy()
    x["rank"] = x.rcept_no.map(lambda r: hashlib.sha256(("sourcegap-production-v1:" + r).encode()).hexdigest())
    result = []
    for statuses in ({"NO_METRICS"}, {"PARSED_4F", "PARSED_PARTIAL"}):
        groups = [g.sort_values("rank").to_dict("records") for _, g in
                  x[x.status.isin(statuses)].groupby(["fiscal_year", "period", "status"], dropna=False, sort=True)]
        seen = set()
        count = 0
        while groups and count < 12:
            remaining = []
            for group in groups:
                while group and group[0].get("corp_code", "") in seen:
                    group.pop(0)
                if group and count < 12:
                    row = group.pop(0)
                    seen.add(row.get("corp_code", ""))
                    result.append({k: row.get(k, "") for k in
                                   ("rcept_no", "status", "document_sha256", "metric_rows", "corp_code", "corp_name", "fiscal_year", "period", "rcept_dt", "report_nm")})
                    count += 1
                if group:
                    remaining.append(group)
            groups = remaining
    return result


def begin():
    folder = root()
    folder.mkdir(parents=True, exist_ok=False)
    before = folder / "before"
    before.mkdir()
    paths = [legacy.STATE_FILE, legacy.INDEX_FILE, legacy.STATUS_FILE, legacy.QUARANTINE_FILE]
    paths += sorted(legacy.NORM_DIR.glob("*.csv.gz"))
    manifest = []
    for path in paths:
        if path.exists():
            destination = before / str(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            manifest.append(identity(path))
    index = legacy.load_csv(legacy.INDEX_FILE, dtype=str).fillna("")
    plan = {"selection_version": "sourcegap-production-v1", "pre_value_selection": True,
            "new_numeric_selection": "first available distinct-company receipts by sorted fiscal_year/period/scope; >=30 items if available; independent literal/header comparison required",
            "old_source_samples": selected_samples(legacy.current_state(), index),
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "actions_run_id": os.getenv("GITHUB_RUN_ID", ""), "actions_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
            "parser_version": legacy.PARSER_VERSION, "source_version": legacy.SOURCE_VERSION,
            "diagnostic_version": DIAGNOSTIC_VERSION, "inputs": manifest,
            "numeric_audit_complete": False, "pit_complete": False}
    (folder / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")


def probe():
    folder = root()
    plan = json.loads((folder / "plan.json").read_text())
    run_report = Path(os.environ["LEGACY_DART_RUN_REPORT"])
    report = json.loads(run_report.read_text()) if run_report.exists() else {}
    remaining_requests = int(os.getenv("LEGACY_DART_MAX_REQUESTS", "150")) - int(report.get("requests", 0))
    if report.get("stop_reason") in {"RATE_LIMIT", "FATAL_API"} or remaining_requests < 1:
        (folder / "old-source-probes.json").write_text(json.dumps({"status": "SKIPPED", "reason": "BATCH_STOP_OR_SHARED_BUDGET"}) + "\n")
        return
    guard = legacy.CollectionControl(max_requests=min(100, remaining_requests), max_seconds=600, min_interval=0.5)
    legacy.RUN_CONTROL = guard
    records = []
    ledger = legacy.load_csv(legacy.QUARANTINE_FILE, dtype=str).fillna("").to_dict("records")
    with guard.signals():
        for item in plan["old_source_samples"]:
            if guard.should_stop():
                break
            record = dict(item)
            try:
                blob, sha = legacy.fetch_document(item["rcept_no"])
                legacy.preserve_document(blob, item["rcept_no"], sha)
                with zipfile.ZipFile(__import__("io").BytesIO(blob)) as archive:
                    diagnostics = [inspect_member(archive.read(n), n) for n in archive.namelist() if not n.endswith("/")]
                record.update(download_sha256=sha, diagnostics=diagnostics,
                              same_as_checkpoint=sha == item["document_sha256"])
                if any(d["issues"] for d in diagnostics) and record["same_as_checkpoint"]:
                    ledger.append({"rcept_no": item["rcept_no"], "document_sha256": sha,
                                   "prior_status": item["status"], "issues": json.dumps(diagnostics, ensure_ascii=False),
                                   "evidence": f"actions:{os.getenv('GITHUB_RUN_ID', '')}/{os.getenv('GITHUB_RUN_ATTEMPT', '')}",
                                   "diagnostic_version": DIAGNOSTIC_VERSION})
                # Preserve actual displayed family/date evidence; HTTP response
                # is never interpreted as an original publication clock/version.
                guard.before_request()
                response = legacy.requests.get(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item['rcept_no']}", timeout=20)
                record["viewer_http_status"] = response.status_code
                if response.status_code == 200 and len(response.content) <= 500000:
                    path = folder / f"{item['rcept_no']}-viewer.html"
                    path.write_bytes(response.content)
                    record["viewer"] = identity(path)
            except Exception as error:
                record["error"] = legacy.safe_error(error)
                if isinstance(error, legacy.RateLimitExceeded):
                    guard.stop("RATE_LIMIT")
            records.append(record)
            (folder / "old-source-probes.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    if ledger:
        out = pd.DataFrame(ledger).drop_duplicates(["rcept_no", "document_sha256", "diagnostic_version"], keep="last")
        legacy.atomic_write_if_changed(out, legacy.QUARANTINE_FILE)
    legacy.RUN_CONTROL = None


def end():
    folder = root()
    index = legacy.load_csv(legacy.INDEX_FILE, dtype=str).fillna("")
    legacy.write_coverage(index)
    before = legacy.load_csv(folder / "before" / legacy.STATE_FILE, dtype=str).fillna("")
    after = legacy.load_csv(legacy.STATE_FILE, dtype=str).fillna("")
    old = before.set_index("rcept_no").updated_at_utc.to_dict()
    changed = after[after.apply(lambda r: old.get(r.rcept_no) != r.updated_at_utc, axis=1)]
    changed.to_csv(folder / "changed-state.csv", index=False)
    effective = legacy.current_state()
    effective.to_csv(folder / "effective-state.csv", index=False)
    paths = [legacy.STATE_FILE, legacy.STATUS_FILE, legacy.QUARANTINE_FILE]
    paths += sorted(legacy.NORM_DIR.glob("*.csv.gz"))
    for path in paths:
        if path.exists():
            dest = folder / "after" / str(path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    frames = [legacy.load_csv(p, dtype=str).fillna("") for p in sorted(legacy.NORM_DIR.glob("*.csv.gz"))]
    metrics = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not metrics.empty:
        metrics[metrics.rcept_no.isin(changed.rcept_no) & metrics.parser_version.eq(legacy.PARSER_VERSION)].to_csv(folder / "new-metrics.csv", index=False)
        samples = {r["rcept_no"] for r in json.loads((folder / "plan.json").read_text())["old_source_samples"]}
        metrics[metrics.rcept_no.isin(samples)].to_csv(folder / "old-sample-metrics.csv", index=False)
    # Small downloadable review subset; the full original artifact remains intact.
    # Selection criteria were fixed in plan.json before collection/value inspection.
    subset = folder / "audit-subset"
    subset.mkdir(exist_ok=True)
    for name in ("plan.json", "old-source-probes.json", "new-metrics.csv", "old-sample-metrics.csv", "changed-state.csv", "effective-state.csv"):
        path = folder / name
        if path.exists():
            shutil.copyfile(path, subset / name)
    receipts = {r["rcept_no"] for r in json.loads((folder / "plan.json").read_text())["old_source_samples"]}
    fresh = metrics[metrics.rcept_no.isin(changed.rcept_no) & metrics.parser_version.eq(legacy.PARSER_VERSION)] if not metrics.empty else pd.DataFrame()
    selected = []
    if not fresh.empty:
        queues = [g.sort_values(["corp_code", "rcept_no", "metric"]).to_dict("records")
                  for _, g in fresh.groupby(["fiscal_year", "period", "scope"], dropna=False, sort=True)]
        seen = set()
        while queues and len(selected) < 12:
            rest = []
            for queue in queues:
                while queue and (queue[0]["corp_code"], queue[0]["scope"]) in seen:
                    queue.pop(0)
                if queue and len(selected) < 12:
                    item = queue.pop(0)
                    selected.append(item["rcept_no"])
                    seen.add((item["corp_code"], item["scope"]))
                if queue:
                    rest.append(queue)
            queues = rest
    receipts.update(selected)
    # Inspect representative blocked NEW downloads too, without assigning
    # financial absence or generalizing these findings to the full population.
    receipts.update(changed[changed.status.eq("SOURCE_GAP")].sort_values("rcept_no").head(5).rcept_no)
    source_manifest = []
    for receipt in sorted(receipts):
        for path in sorted((folder / "native").glob(receipt + "-*.zip")):
            shutil.copyfile(path, subset / path.name)
            source_manifest.append(identity(path))
        viewer = folder / f"{receipt}-viewer.html"
        if viewer.exists():
            shutil.copyfile(viewer, subset / viewer.name)
    (subset / "numeric-selection.json").write_text(json.dumps({"receipt_order": selected, "source_identities": source_manifest,
        "selection": "round-robin fiscal_year/period/scope, lexical corp_code/rcept_no, unique company/scope, at most12 receipts; independent audit required"}, indent=2) + "\n")
    summary = {"changed_receipts": len(changed), "changed_status_counts": changed.status.value_counts().to_dict(),
               "effective_status_counts": effective.status.value_counts().to_dict(),
               "numeric_audit_complete": False, "pit_complete": False}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    shutil.copyfile(folder / "summary.json", subset / "summary.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["begin", "probe", "end"])
    args = parser.parse_args()
    globals()[args.mode]()
