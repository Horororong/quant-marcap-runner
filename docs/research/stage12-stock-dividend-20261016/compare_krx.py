"""Independent exact field comparison: official API rows versus immutable Stage10.

No engine, registry, factors, NAV, guessed reference price or data writes.
The whole original KRX replies are in the referenced Actions artifact; the
transferred exact target rows and original-response hashes are in state.json.
"""
import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

HOME = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    assert not a.output.exists(), "refuse result overwrite"
    raw = (HOME / "official_krx/state.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "9ed9a7158caeec2d020391e47bde9195f9cf70a6fe93e0d0c845f46998a1c711"
    state = json.loads(raw)
    assert state["status"] == "COMPLETE_OFFICIAL_PRICE_ROWS_ONLY" and state["requests"] == 8
    rows = {(x["security"], x["date"]): x for x in state["target_rows"]}
    assert len(rows) == len(state["target_rows"]) == 8
    with (HOME.parent / "stage10-return-diagnostic-20261016/results/planned_holding_mismatches.csv").open(encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))
    with (HOME / "stage12_details.csv").open() as f:
        known = {(r["Code"], r["event_date"]): r for r in csv.DictReader(f)}
    out = {"scope": "official current historical API observations versus preserved source; not PIT/rights certification",
           "fields": [], "cases": [], "investment_approved": False}
    def n(value):
        result = Decimal(str(value).replace(",", ""))
        assert result.is_finite()
        return result
    for case in cases:
        security, dt = case["Code"], case["Date"]
        current = rows[(security, dt.replace("-", ""))]
        prior = rows[(security, case["previous_date"].replace("-", ""))]
        for row in [current, prior]:
            assert row["raw_api_row"]["ISU_CD"] == security
            assert row["raw_api_row"]["BAS_DD"] == row["date"]
        fields = [("previous_close", prior, "TDD_CLSPRC"), ("Close", current, "TDD_CLSPRC"),
                  ("ChangesRatio", current, "FLUC_RT")]
        for field, official, key in fields:
            out["fields"].append({"Code": security, "event_date": dt, "field": field,
                "official_value": str(n(official["raw_api_row"][key])), "preserved_value": str(n(case[field])),
                "verdict": "PASS" if n(official["raw_api_row"][key]) == n(case[field]) else "FAIL",
                "source_file": official["source_file"], "source_row_index": official["source_row_index"], "source_key": key})
        with localcontext() as ctx:
            ctx.prec = 50
            before, after = n(prior["raw_api_row"]["TDD_CLSPRC"]), n(current["raw_api_row"]["TDD_CLSPRC"])
            assert before > 0 and after > 0
            reported = n(current["raw_api_row"]["FLUC_RT"]) / 100
            base = known[(security, dt)]["official_reference_price"]
            price_check = None if not base else {"official_reference_price": base,
                "reference_price_return": str(after / n(base) - 1),
                "difference_from_reported_bps": str(abs(after / n(base) - 1 - reported) * 10000)}
            out["cases"].append({"Code": security, "date": dt, "raw_price_return": str(after / before - 1),
                "official_reported_return": str(reported), "known_reference_price_check": price_check,
                "actual_economic_holding_return": None, "real_event_verdict": "UNVERIFIED"})
    assert len(out["fields"]) == 12 and len(out["cases"]) == 4
    out["field_summary"] = {v: sum(r["verdict"] == v for r in out["fields"]) for v in ["PASS", "FAIL", "UNVERIFIED"]}
    out["source_response_hashes"] = {r["file"]: r["sha256"] for r in state["responses"]}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(out["field_summary"]))
    return int(out["field_summary"]["FAIL"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
