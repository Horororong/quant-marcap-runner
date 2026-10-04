"""Independent literal-primary-cell comparator; no collector/adapter imports.

Manually entered expectations and original pre-change cell spans are preserved
separately from the versioned adapter. This compares persisted staging, not
production/PIT data. It does not infer financial periods or publication dates.
"""
import argparse
import csv
from decimal import Decimal
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class LiteralText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def literal_lines(cell):
    # Split the original BR tokens first; never remove interior empty lines.
    lines = []
    for part in re.split(r"<br\s*/?\s*>", cell, flags=re.I):
        reader = LiteralText()
        reader.feed(part)
        lines.append(re.sub(r"\s+", " ", "".join(reader.text)).strip())
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive output directory creation preserves all earlier audit results.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    plan = json.loads((HERE / "ADDITIONAL_SAMPLE_PLAN.json").read_text())
    review = json.loads((HERE / "SOURCE_REVIEW_BEFORE_CHANGE.json").read_text())["reviews"]
    fixtures = ROOT / "tests/fixtures/legacy_dart/viewer_primary"
    manifest = json.loads((fixtures / "manifest.json").read_text())["records"]
    staging = [r for capture in json.loads((HERE / "replay/source_replay.json").read_text()) for r in capture["rows"]]
    prior_audit = json.loads((ROOT / "docs/audits/data-readiness-20261004/financial_audit.json").read_text())
    audit = []
    for sample in plan["records"]:
        source = next(r for r in review if r["rcept_no"] == sample["rcept_no"])
        fixture = next(r for r in manifest if r["capture"]["rcept_no"] == sample["rcept_no"] and r["request"]["scope"] == "OFS")
        packed = (fixtures / fixture["file"]).read_bytes()
        assert hashlib.sha256(packed).hexdigest() == fixture["gzip_sha256"]
        with gzip.open(fixtures / fixture["file"], "rb") as stream:
            body = stream.read(2_000_001)
        assert len(body) <= 2_000_000
        assert hashlib.sha256(body).hexdigest() == source["source_sha256"]
        text = body.decode(fixture["capture"]["source_encoding"], errors="strict")
        verified = []
        for ci in (0, sample["cell_index"]):
            cell = source["cells"][ci]
            literal = text[cell["start_character"]:cell["end_character"]]
            assert hashlib.sha256(literal.encode()).hexdigest() == cell["literal_sha256"]
            verified.append(literal_lines(literal)[sample["line_index"]])
        assert verified == [sample["source_account"], sample["source_token"]]
        amount = Decimal(sample["source_token"].replace(",", ""))  # Explicit KRW unit; signed token.
        matching = [r for r in staging if r["rcept_no"] == sample["rcept_no"] and r["metric"] == sample["metric"]]
        assert len(matching) == 1
        row = matching[0]
        # The same source IS header was manually audited in the prior revenue
        # sample. Reuse its period/identifier metadata, never its financial value.
        header = next(r for r in prior_audit if r["rcept_no"] == sample["rcept_no"] and r["scope"] == "OFS" and r["metric"] == "revenue")
        match = (row["raw_amount"] == sample["source_token"] and row["account_name"] == sample["source_account"]
                 and row["unit"] == sample["unit"] and row["scope"] == "OFS"
                 and row["period_end"] == source["request"]["period_end"] and row["period_kind"] == source["request"]["kind"]
                 and row["period_start"] == header["source_period_start"]
                 and Decimal(str(row["amount_krw"])) == amount
                 and all(row[k] == sample[k] for k in ("table_index", "row_index", "cell_index", "line_index")))
        audit.append(dict(**sample, company=source["company"], stock_code=source["stock_code"],
                          corp_code=header["corp_code"], period_start=header["source_period_start"],
                          scope="OFS", period_end=source["request"]["period_end"], period_kind=source["request"]["kind"],
                          source_url=source["source_url"], source_sha256=source["source_sha256"], source_amount_krw=str(amount),
                          staging_amount_krw=row["amount_krw"], result="MATCH" if match else "MISMATCH",
                          production_value_checked=False, production_value=None, actual_filing_date_verified=False,
                          actual_filing_date=None, recorded_receipt_day=header["actual_filing_date"],
                          correction_indicator_as_indexed=header["correction_indicator"], correction_status="chain_unverified",
                          correction_chain_verified=False, strategy_usable_date=None, pit_ready=False))
    summary = dict(additional_independent_samples=len(audit), matches=sum(r["result"] == "MATCH" for r in audit),
                   mismatches=sum(r["result"] != "MATCH" for r in audit), original_golden_matches=22,
                   total_independently_matched_staging_rows=32, total_staging_rows=78, remaining_unreviewed_staging_rows=46,
                   verified_pit_items=0, production_rows_changed=0, full_data_quality_complete=False,
                   selection_plan_sha256=hashlib.sha256((HERE / "ADDITIONAL_SAMPLE_PLAN.json").read_bytes()).hexdigest())
    for filename, value in (("audit.json", audit), ("summary.json", summary)):
        (args.output_dir / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(audit[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(audit)
    (args.output_dir / "audit.csv").write_text(stream.getvalue())
    print(json.dumps(summary))
    if summary["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
