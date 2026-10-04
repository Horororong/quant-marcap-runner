"""Bounded offline recovery of source-backed NO_METRICS, without PIT promotion.

Requires previously archived native ZIPs and public viewer snapshots. Each
receipt is written once; --resume processes only unpublished receipts. The
native checkpoints and original normalized rows remain immutable inputs.
"""
import argparse
from collections import Counter
import csv
import hashlib
import gzip
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import zipfile
try:
    from scripts.legacy_document_quality import inspect_member, empty_parse_status, DIAGNOSTIC_VERSION
    from scripts.replay_legacy_viewer_sources import replay
except ModuleNotFoundError:
    from legacy_document_quality import inspect_member, empty_parse_status, DIAGNOSTIC_VERSION
    from replay_legacy_viewer_sources import replay

ROOT = Path(__file__).resolve().parents[1]


class Families(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.family = False
        self.option = None
        self.options = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.family = attrs.get("id") == "family"
        if tag == "option" and self.family:
            self.option = {"attrs": attrs, "text": ""}

    def handle_data(self, text):
        if self.option is not None:
            self.option["text"] += text

    def handle_endtag(self, tag):
        if tag == "option" and self.option is not None:
            if self.option["attrs"].get("value", "").startswith("rcpNo="):
                self.options.append(self.option)
            self.option = None
        if tag == "select":
            self.family = False


def publication_evidence(body, receipt):
    text = body.decode("utf-8", errors="strict")
    parser = Families(); parser.feed(text)
    own = [o for o in parser.options if o["attrs"].get("value") == "rcpNo=" + receipt]
    dates = re.findall(r"\b(\d{4})\.(\d{2})\.(\d{2})\b", own[0]["text"]) if len(own) == 1 else []
    displayed = "-".join(dates[0]) if len(dates) == 1 else None
    literal = re.search(r'<select\b[^>]*id="family"[\s\S]*?</select>', text)
    return {"viewer_sha256": hashlib.sha256(body).hexdigest(),
            "displayed_publication_date": displayed,
            "date_evidence": "archived DART public viewer family option, not receipt-derived",
            "family_options": parser.options, "literal_family": literal.group() if literal else None,
            "publication_time": None, "original_version_preserved_at_publication": False,
            "correction_chain_complete": False, "changed_values": None,
            "strategy_usable_date": None, "pit_ready": False,
            "limitation": "Current viewer lists one family receipt; this does not prove no historical amendments or original value immutability."}


def inputs():
    paths = [ROOT / "data/status/dart_legacy_backfill_state.csv",
             ROOT / "data/financials/legacy_2000_2014/legacy_filings.csv.gz"]
    paths += sorted((ROOT / "data/financials/legacy_2000_2014/normalized").glob("*.gz"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run(source_dir, output, limit, resume=False):
    if limit < 1:
        raise ValueError("positive bounded batch size required")
    if output.exists() and not resume:
        raise FileExistsError("existing recovery is preserved; explicitly --resume")
    output.mkdir(parents=True, exist_ok=resume)
    lock = output / ".writer.lock"
    with lock.open("x"):
        pass
    try:
        before = inputs()
        with (ROOT / "data/status/dart_legacy_backfill_state.csv").open(encoding="utf-8-sig") as stream:
            states = list(csv.DictReader(stream))
        by_receipt = {r["rcept_no"]: r for r in states if r["parser_version"] == "legacy-v5-single-amount"}
        _, captures, _ = replay()
        staging = [r for c in captures for r in c["rows"]]
        receipts = sorted({r["rcept_no"] for r in staging})
        plan = {"receipts": receipts, "source_diagnostic_version": DIAGNOSTIC_VERSION,
                "adapter_version": captures[0]["adapter_version"], "input_sha256": before}
        plan_file = output / "plan.json"
        if plan_file.exists():
            if json.loads(plan_file.read_text()) != plan:
                raise ValueError("recovery inputs changed; create a new evidence directory")
        else:
            plan_file.write_text(json.dumps(plan, indent=2) + "\n")
        completed = []
        for receipt in receipts:
            target = output / (receipt + ".json")
            if target.exists():
                old = json.loads(target.read_text())
                if old["before_state"] != by_receipt[receipt]:
                    raise ValueError("existing receipt checkpoint differs")
                continue
            if len(completed) >= limit:
                break
            state = by_receipt[receipt]
            if state["status"] != "NO_METRICS":
                raise ValueError("fixed recovery target no longer NO_METRICS")
            paths = sorted(source_dir.glob(receipt + "-*.zip"))
            if len(paths) != 1:
                raise ValueError("one archived native ZIP required")
            packed = paths[0].read_bytes()
            if hashlib.sha256(packed).hexdigest() != state["document_sha256"]:
                raise ValueError("native source/current checkpoint SHA mismatch")
            with zipfile.ZipFile(io.BytesIO(packed)) as archive:
                diagnostics = [inspect_member(archive.read(n), n) for n in archive.namelist() if not n.endswith("/")]
            viewer_path = source_dir / (receipt + "-viewer.html")
            viewer = viewer_path.read_bytes() if viewer_path.exists() else gzip.decompress(viewer_path.with_suffix(".html.gz").read_bytes())
            probe = json.loads((ROOT / f"docs/audits/legacy/source_probes/{receipt}.json").read_text())
            if hashlib.sha256(viewer).hexdigest() != probe["public_viewer_response_sha256"]:
                raise ValueError("archived viewer SHA mismatch")
            recovered = [r for r in staging if r["rcept_no"] == receipt]
            record = {"rcept_no": receipt, "before_state": state,
                      "diagnostics": diagnostics, "after_source_classification": empty_parse_status(diagnostics),
                      "staging_rows": recovered, "staging_rows_recovered": len(recovered),
                      "publication_evidence": publication_evidence(viewer, receipt),
                      "production_rows_recovered": 0, "pit_ready": False,
                      "reprocess_status": "STAGING_RECOVERED_PIT_BLOCKED", "requests": 0}
            with target.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            completed.append(receipt)
        after = inputs()
        if after != before:
            raise RuntimeError("production inputs changed during recovery")
        records = [json.loads((output / (r + ".json")).read_text()) for r in receipts if (output / (r + ".json")).exists()]
        summary = {"target_receipts": len(receipts), "processed_this_batch": len(completed),
                   "processed_receipts": len(records), "remaining_receipts": len(receipts) - len(records),
                   "staging_rows_recovered": sum(r["staging_rows_recovered"] for r in records),
                   "after_source_classifications": dict(Counter(r["after_source_classification"] for r in records)),
                   "production_valid_rows_recovered": 0, "verified_pit_items": 0, "requests": 0,
                   "inputs_unchanged": True, "status": "COMPLETED" if len(records) == len(receipts) else "CHECKPOINTED"}
        batch_file = output / f"batch-{len(records):03d}-{len(completed):03d}.json"
        if not batch_file.exists():
            batch_file.write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    finally:
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "tests/fixtures/legacy_dart/recovery_primary")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-receipts", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.source_dir, args.output_dir, args.max_receipts, args.resume), ensure_ascii=False))
