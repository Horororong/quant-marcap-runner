"""Independent primary-to-staging and stored-value audit for fixed 46 cells.

Uses manual literal expectations and original body/cell/header SHA chains.
Imports no collector, viewer adapter, financial alias or performance code.
Production observations are recorded by parser version, never rewritten.
"""
import argparse
import calendar
from collections import Counter
import csv
from datetime import date
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


class LiteralText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def literal_lines(raw):
    lines = []
    for part in re.split(r"<br\s*/?\s*>", raw, flags=re.I):
        reader = LiteralText()
        reader.feed(part)
        lines.append(re.sub(r"\s+", " ", "".join(reader.parts)).strip())
    return lines


def exact_amount(token):
    # Only the explicitly inspected source syntaxes; no sign from parentheses.
    require(bool(re.fullmatch(r"(?:\(-\)|-)?(?:\d{1,3}(?:,\d{3})+|\d+)", token)), "unsupported manual amount token")
    return Decimal(token.replace("(-)", "-").replace(",", ""))


def checked_literal(text, cell):
    raw = text[cell["start_character"]:cell["end_character"]]
    require(raw == cell["literal_cell"], "original literal span mismatch")
    if "literal_sha256" in cell:
        require(hashlib.sha256(raw.encode()).hexdigest() == cell["literal_sha256"], "original literal SHA mismatch")
    return raw


def compact(text):
    return re.sub(r"\s+", "", text)


def header_dates(text):
    return [date(int(y), int(m), int(d)).isoformat()
            for y, m, d in re.findall(r"(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})", text)]


def validate_header(text, source, sample, flow_contract):
    require(sample["source_unit"] == "원", "unsupported manual source unit")
    flow_header = source["headers"][str(flow_contract["is_table"])]["date_unit_cells"][0]
    flow_text = " ".join(literal_lines(checked_literal(text, flow_header)))
    require(header_dates(flow_text) == [flow_contract["start"], flow_contract["end"]], "companion flow dates mismatch")
    require(f"제{sample['source_term']}기" in compact(flow_text), "companion flow term mismatch")
    start, end = date.fromisoformat(flow_contract["start"]), date.fromisoformat(flow_contract["end"])
    months = (end.year-start.year)*12 + end.month-start.month+1
    require(sample["source_period_kind"] == flow_contract["kind"]
            and sample["source_period_end"] == flow_contract["end"]
            and months == {"Q1":3,"H1":6,"Q3":9,"FY":12}.get(sample["source_period_kind"])
            and start.day == 1 and end.day == calendar.monthrange(end.year,end.month)[1], "quarter/annual source span mismatch")
    header = source["headers"][str(sample["table_index"])]
    rendered = [" ".join(literal_lines(checked_literal(text, c))) for c in header["date_unit_cells"]]
    expected_dates = ([sample["source_period_start"], sample["source_period_end"]]
                      if sample["statement"] == "IS" else [sample["source_period_end"]])
    require(header_dates(rendered[0]) == expected_dates, "manual current source dates mismatch")
    require(f"제{sample['source_term']}기" in compact(rendered[0]), "manual current source term mismatch")
    unit_cells = [compact(s) for s in rendered if "단위" in s]
    require(len(unit_cells) == 1 and unit_cells[0] in {"(단위:원)", "(단위：원)"}, "manual source unit unproven")
    cursor, matching = 0, []
    for cell in header["numeric_column_cells"]:
        label = compact(" ".join(literal_lines(checked_literal(text, cell))))
        span = int(cell["attrs"].get("colspan", "1"))
        if f"제{sample['source_term']}기" in label:
            matching.append(list(range(cursor, cursor + span)))
        cursor += span
    require(matching == [sample["source_current_columns"]], "manual current numeric columns mismatch")
    require(compact(source["capture"]["heading"]) == "3.재무제표"
            and "3.재무제표" in compact(text[:2000]), "source OFS heading unproven")


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            require(index < 500_000, "CSV row budget exceeded")
            yield row


def input_paths(root):
    paths = [root / "data/financials/legacy_2000_2014/legacy_filings.csv.gz",
             root / "data/status/dart_legacy_backfill_state.csv"]
    paths.extend(sorted((root / "data/financials/legacy_2000_2014/normalized").glob("*.csv.gz")))
    require(2 < len(paths) <= 66, "missing or excessive production input shards")
    require(all(p.is_file() and p.stat().st_size <= 32_000_000 for p in paths), "production input budget exceeded")
    return paths


def hashes(paths, root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def audit(repo_root=ROOT, evidence_dir=HERE, staging_path=None):
    plan = json.loads((evidence_dir / "SAMPLE_PLAN.json").read_text())
    expectations = json.loads((evidence_dir / "EXPECTED_PRIMARY_CELLS.json").read_text())
    evidence = json.loads((evidence_dir / "PRIMARY_CELL_EVIDENCE.json").read_text())
    require(hashlib.sha256((evidence_dir / "SAMPLE_PLAN.json").read_bytes()).hexdigest()
            == expectations["sample_plan_sha256"], "selection plan SHA mismatch")
    require(len(plan["records"]) == len(expectations["records"]) == 46, "fixed sample count changed")
    require({r["sample_id"] for r in plan["records"]} == {r["sample_id"] for r in expectations["records"]}, "sample selection changed")
    selected = {r["sample_id"]: r for r in plan["records"]}
    for sample in expectations["records"]:
        require(all(sample[k] == selected[sample["sample_id"]][k]
                    for k in ("rcept_no","metric","scope","table_index","row_index","cell_index","line_index")), "fixed sample identity changed")
    staging_path = staging_path or repo_root / "docs/audits/viewer-line-alignment-20261004/replay/source_replay.json"
    packed_staging = staging_path.read_bytes()
    require(hashlib.sha256(packed_staging).hexdigest() == plan["staging_sha256"], "persisted staging snapshot SHA mismatch")
    staging = [r for capture in json.loads(packed_staging) for r in capture["rows"]]
    require(len(staging) == 78, "staging population changed")
    paths = input_paths(repo_root)
    before = hashes(paths, repo_root)
    receipts = {s["rcept_no"] for s in expectations["records"]}
    filings = {r["rcept_no"]: r for r in read_csv(paths[0]) if r["rcept_no"] in receipts}
    state = {r["rcept_no"]: r for r in read_csv(paths[1]) if r["rcept_no"] in receipts}
    production = [r for p in paths[2:] for r in read_csv(p) if r["rcept_no"] in receipts]
    sources = {}
    fixture_root = repo_root / "tests/fixtures/legacy_dart/viewer_primary"
    for receipt, source in evidence["sources"].items():
        packed = (fixture_root / source["file"]).read_bytes()
        require(hashlib.sha256(packed).hexdigest() == source["gzip_sha256"], "original gzip SHA mismatch")
        with gzip.open(fixture_root / source["file"], "rb") as stream:
            body = stream.read(2_000_001)
        capture = source["capture"]
        require(len(body) <= 2_000_000 and len(body) == capture["body_bytes"]
                and hashlib.sha256(body).hexdigest() == capture["body_sha256"], "original body identity mismatch")
        text = body.decode(capture["source_encoding"], errors="strict")
        for contexts in source["semantic_context"].values():
            for cell in contexts:
                checked_literal(text, cell)
        sources[receipt] = text
    records = []
    for sample in expectations["records"]:
        receipt = sample["rcept_no"]
        source = evidence["sources"][receipt]
        text = sources[receipt]
        validate_header(text, source, sample, expectations["source_contracts"][receipt])
        key = f"{sample['table_index']}/{sample['row_index']}/"
        account_cell = source["cells"][key + "0"]
        amount_cell = source["cells"][key + str(sample["cell_index"])]
        account = literal_lines(checked_literal(text, account_cell))[sample["line_index"]]
        token = literal_lines(checked_literal(text, amount_cell))[sample["line_index"]]
        require((account, token) == (sample["source_account"], sample["source_token"]), "manual account/token disagrees with primary")
        present = []
        for ci in sample["source_current_columns"]:
            ls = literal_lines(checked_literal(text, source["cells"][key + str(ci)]))
            value = ls[sample["line_index"]] if sample["line_index"] < len(ls) else ""
            if value:
                present.append((ci, value))
        require(present == [(sample["cell_index"], token)], "primary current amount is missing/ambiguous")
        value = exact_amount(token)  # All inspected source headers explicitly KRW.
        matched = [r for r in staging if r["rcept_no"] == receipt and r["metric"] == sample["metric"] and r["scope"] == sample["scope"]]
        require(len(matched) == 1, "staging metric is missing or ambiguous")
        row = matched[0]
        money_match = Decimal(str(row["amount_krw"])) == value and row["raw_amount"] == token
        contract_match = (row["account_name"] == account and row["unit"] == sample["source_unit"]
                          and row["statement"] == sample["statement"] and row["scope"] == "OFS"
                          and row["period_start"] == sample["source_period_start"]
                          and row["period_end"] == sample["source_period_end"]
                          and row["period_kind"] == sample["source_period_kind"]
                          and all(row[k] == sample[k] for k in ("table_index", "row_index", "cell_index", "line_index"))
                          and row["cell_start_character"] == amount_cell["start_character"]
                          and row["cell_end_character"] == amount_cell["end_character"])
        stored = [r for r in production if r["metric"] == sample["metric"] and r["scope"] == sample["scope"] and r["rcept_no"] == receipt]
        stored = list({json.dumps(r, sort_keys=True): r for r in stored}.values())
        stored_checks = []
        for observation in stored:
            numeric_equal = Decimal(observation["amount_krw"]) == value
            period_equal = observation.get("period_end") == sample["source_period_end"] and observation.get("period") == sample["source_period_kind"]
            stored_checks.append(dict(observation=observation,amount_equal=numeric_equal,period_equal=period_equal,
                                      current_parser_observation=observation.get("parser_version") == state.get(receipt, {}).get("parser_version"),
                                      pit_ready=False))
        filing = filings[receipt]
        require(filing["corp_code"] == sample["corp_code"] and filing["stock_code"] == sample["stock_code"], "production filing identifier mismatch")
        status = "MISMATCH" if not (money_match and contract_match) else "MATCH_SOURCE_COMPONENT" if sample["semantic_qualification"] else "MATCH"
        records.append(dict(**sample,source_url=source["capture"]["url"],source_sha256=source["capture"]["body_sha256"],
                            cell_start_character=amount_cell["start_character"],cell_end_character=amount_cell["end_character"],
                            source_amount_krw=str(value),staging_amount_krw=row["amount_krw"],numeric_match=money_match,
                            source_contract_match=contract_match,result=status,production_values_checked=True,production_values=stored_checks,
                            production_result="stored_missing" if not stored else "stored_mismatch" if any(not s["amount_equal"] or not s["period_equal"] for s in stored_checks) else "stored_numeric_period_match_only",
                            indexed_name=filing["corp_name"],recorded_receipt_day=filing["rcept_dt"],actual_filing_date=None,
                            actual_filing_date_verified=False,correction_indicator_as_indexed=any(t in filing["report_nm"] for t in ("기재정정","첨부정정")),
                            correction_chain_verified=False,strategy_usable_date=None,corrected_values_used_in_strategy="not_executed_or_promoted",
                            native_state=state.get(receipt, {}).get("status"),native_parser=state.get(receipt, {}).get("parser_version"),
                            pit_ready=False,production_ready=False))
    after = hashes(paths, repo_root)
    require(before == after, "production/checkpoint inputs changed during read-only audit")
    summary = dict(selected_items=46,companies=len(receipts),numeric_matches=sum(r["numeric_match"] for r in records),
                   source_contract_matches=sum(r["source_contract_match"] for r in records),results=dict(Counter(r["result"] for r in records)),
                   production_results=dict(Counter(r["production_result"] for r in records)),
                   previously_matched_staging_rows=32,total_numeric_matched_staging_rows=32+sum(r["numeric_match"] for r in records),
                   total_staging_rows=78,remaining_selected_staging_unreviewed=0,verified_pit_items=0,full_data_quality_complete=False,
                   production_rows_changed=0,inputs_unchanged=True,sample_plan_sha256=expectations["sample_plan_sha256"])
    provenance = dict(input_sha256=before,inputs_unchanged=True,staging_sha256=plan["staging_sha256"],
                      primary_bodies={r:s["capture"]["body_sha256"] for r,s in evidence["sources"].items()},
                      expected_sha256=hashlib.sha256((evidence_dir/"EXPECTED_PRIMARY_CELLS.json").read_bytes()).hexdigest(),
                      primary_cell_evidence_sha256=hashlib.sha256((evidence_dir/"PRIMARY_CELL_EVIDENCE.json").read_bytes()).hexdigest(),
                      method="manual primary literals, independent BR decoding/Decimal comparison; no collector/adapter imports; parser versions preserved")
    return summary, records, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output_dir.exists(), "preserve existing audit; choose a new output directory")
    summary, records, provenance = audit(args.repo_root)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json",summary),("audit.json",records),("provenance.json",provenance)):
        (args.output_dir/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator="\n")
    writer.writeheader()
    writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in records)
    (args.output_dir/"audit.csv").write_text(stream.getvalue())
    print(json.dumps(summary,ensure_ascii=False))
    if summary["results"].get("MISMATCH",0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
