"""Bounded, offline replay of archived primary sources into an audit directory.

No collection checkpoint, production data or financial capability is changed.
The independent golden cells were selected before this adapter was implemented.
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

try:
    from scripts.legacy_viewer_source import adapt_viewer, ADAPTER_VERSION, MAX_BODY_BYTES
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from legacy_viewer_source import adapt_viewer, ADAPTER_VERSION, MAX_BODY_BYTES

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/legacy_dart/viewer_primary"


def replay(fixtures=FIXTURES):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    golden = json.loads((fixtures / "golden.json").read_text())["records"]
    if len(manifest["records"]) != 12 or len(golden) != 49:
        raise ValueError("frozen primary-sample contract changed")
    captures, staging = [], []
    for item in manifest["records"]:
        path = fixtures / item["file"]
        if path.name != item["file"]:
            raise ValueError("fixture path escape")
        packed = path.read_bytes()
        if hashlib.sha256(packed).hexdigest() != item["gzip_sha256"]:
            raise ValueError("fixture archive SHA mismatch")
        with gzip.open(path, "rb") as stream:
            body = stream.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("fixture body budget exceeded")
        parsed = adapt_viewer(body, item["capture"], item["request"])
        if any(g["reason"].startswith("SOURCE_") for g in parsed["gaps"]):
            raise ValueError("primary fixture identity failed")
        # Prove saved character offsets reference the exact original cells.
        text = body.decode(item["capture"]["source_encoding"])
        for row in parsed["rows"]:
            literal = text[row["cell_start_character"]:row["cell_end_character"]]
            if not literal.lower().startswith(("<td", "<th")) or not literal.lower().endswith(("</td>", "</th>")):
                raise ValueError("source provenance offset mismatch")
            staging.append(row)
        captures.append(dict(file=item["file"], request=item["request"], **parsed))
    audited = []
    for sample in golden:
        matching = [r for r in staging if r["rcept_no"] == sample["rcept_no"] and r["metric"] == sample["metric"]
                    and r["scope"] == sample["scope"] and r["period_end"] == sample["source_period_end"]
                    and r["period_kind"] == sample["source_period_kind"]]
        request = next(i["request"] for i in manifest["records"] if i["file"] == sample["file"] + ".gz")
        parsed = next(p for p in captures if p["file"] == sample["file"] + ".gz")
        if sample["source_period_end"] != request["period_end"] or sample["source_period_kind"] != request["kind"]:
            status = "WITHHELD_PRIOR_PERIOD"
        elif sample["unit"] == "확인불가":
            status = "WITHHELD_UNKNOWN_UNIT"
        elif not matching:
            status = "WITHHELD_LAYOUT_GUARD"
        else:
            status = "MATCH" if len(matching) == 1 and Decimal(str(matching[0]["amount_krw"])) == Decimal(sample["source_amount_krw"]) and matching[0]["unit"] == sample["unit"] and matching[0]["raw_amount"] == sample["source_token"] else "MISMATCH"
        if status.startswith("WITHHELD") and matching:
            status = "GUARD_FAILURE"
        audited.append(dict(**sample, status=status, extracted_amount_krw=matching[0]["amount_krw"] if len(matching) == 1 else None,
                            pit_ready=False, strategy_usable_date=None, source_gaps=parsed["gaps"]))
    summary = dict(adapter_version=ADAPTER_VERSION, primary_bodies=len(captures), receipts=6, independent_golden_items=len(audited),
                   results=dict(Counter(r["status"] for r in audited)), staging_rows=len(staging),
                   independently_matched_staging_rows=sum(r["status"] == "MATCH" for r in audited),
                   unreviewed_staging_rows=len(staging) - sum(r["status"] == "MATCH" for r in audited),
                   production_rows_written=0, checkpoint_rows_changed=0, verified_pit_items=0,
                   collection_complete=False, financial_quality_complete=False, strategy_validation_complete=False,
                   source_verification="archived primary body SHA, original cell spans, independent manual golden values",
                   manifest_sha256=hashlib.sha256((fixtures / "manifest.json").read_bytes()).hexdigest(),
                   golden_sha256=hashlib.sha256((fixtures / "golden.json").read_bytes()).hexdigest())
    if any(r["status"] in {"MISMATCH", "GUARD_FAILURE"} for r in audited):
        raise ValueError("source audit disagreement; do not promote staging")
    return summary, captures, audited


def write_once(path, content):
    raw = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"preserve existing checkpoint; choose a new output directory: {path}")
        return
    # Exclusive creation prevents two replays from overwriting each other.
    with path.open("xb") as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary, captures, audited = replay()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, value in (("summary.json", summary), ("source_replay.json", captures), ("golden_audit.json", audited)):
        write_once(args.output_dir / filename, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    import io
    stream = io.StringIO(newline="")
    fields = [k for k in audited[0] if k != "source_gaps"]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: r[k] for k in fields} for r in audited)
    write_once(args.output_dir / "golden_audit.csv", stream.getvalue())
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
