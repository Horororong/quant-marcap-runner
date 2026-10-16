"""Four existing-case arithmetic only. No NAV, fitted base, or event treatment."""
from pathlib import Path
from decimal import Decimal, localcontext
import argparse
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

def main(output):
    if output.exists():
        raise FileExistsError("Use a new output path; preserve prior results")
    source = REPO / "docs/research/stage10-return-diagnostic-20261016/results/planned_holding_mismatches.csv"
    manifest = json.loads((source.parents[1] / "artifact_manifest.json").read_text())
    raw = source.read_bytes()
    expected = manifest["results/planned_holding_mismatches.csv"]
    if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise ValueError("Stage10 input integrity mismatch")
    rows = {(r["Code"],r["Date"]):r for r in csv.DictReader(raw.decode().splitlines())}
    facts = json.loads((HERE / "evidence.json").read_text())
    keys = {(c["code"], c["date"]) for c in facts["cases"]}
    if keys != set(rows) or len(keys) != 4:
        raise ValueError("Case set changed")
    result = []
    with localcontext() as ctx:
        ctx.prec = 40
        D = Decimal
        for case in facts["cases"]:
            row = rows[(case["code"],case["date"])]
            previous, close, reported = map(D, (row["previous_close"],row["Close"],row["ChangesRatio"]))
            rate = D(case["rate"])
            raw_return = close / previous - 1
            # Hypothetical gross valuation only: the unpaid right is marked at
            # ordinary-share close, with no fraction/tax/approval/liquidity risk.
            equivalent = close * (1 + rate) / previous - 1
            base = D(case["official_base"]) if case["official_base"] is not None else None
            reference = close / base - 1 if base is not None else None
            result.append(dict(
                case_id=case["id"], code=case["code"], date=case["date"],
                prior_close_secondary=str(previous), close_secondary=str(close),
                reported_ChangesRatio_secondary_percent=str(reported),
                dividend_rate_retrospective=str(rate),
                raw_close_return_percent=str(raw_return*100),
                raw_vs_reported_absolute_bps=str(abs(raw_return-reported/100)*10000),
                official_base_KRW=str(base) if base is not None else None,
                official_base_evidence=case.get("official_base_evidence"),
                mixed_primary_base_secondary_close_return_percent=str(reference*100) if reference is not None else None,
                mixed_reference_vs_reported_absolute_bps=str(abs(reference-reported/100)*10000) if reference is not None else None,
                assumed_equivalent_holder_return_percent=str(equivalent*100),
                assumed_holder_vs_reported_absolute_bps=str(abs(equivalent-reported/100)*10000),
                assumed_holder_vs_mixed_reference_bps=str((equivalent-reference)*10000) if reference is not None else None,
                hypothetical_per_old_share_claim_value_KRW=str(rate*close),
                actual_holder_return=None, actual_holder_return_verdict="UNVERIFIED",
                prices_independently_certified=False))
    report = dict(scope="Four preserved cases; diagnostic algebra, not an executed backtest",
        source=str(source.relative_to(REPO)), source_sha256=expected["sha256"],
        decimal_precision=40, formulas=dict(raw="P_t/P_previous - 1",
        exchange_reference="P_t/B_t - 1 (only when B_t directly evidenced)",
        economic_identity="(q_old*P_t + V_unpaid_claim_t + settled_cash_t - costs_t)/V_previous - 1",
        gross_equivalent_hypothesis="(1+rate)*P_t/P_previous - 1"),
        limitations=["Only one official base; no unknown base estimated or reverse-fitted",
        "Mixed primary base and secondary close is a consistency calculation, not independent official return certification",
        "Claim-value hypothesis assumes equal mark, full gross rights, no cash fraction/tax or liquidity discount",
        "Actual credit/trading and record-date proof remain missing; no change to any1bp guard"],
        rows=result, operating_changes=False, NAV_generated=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    main(p.parse_args().output)
