"""Read-only arithmetic probe. No event registration, NAV, or price adjustment.

Run with the verified original kit. All entitlement/base scenarios below are
hypotheses; they do not certify an exchange price or a realizable holder return.
"""
from decimal import Decimal, localcontext
from pathlib import Path
import csv
import hashlib
import json
import sys


def main():
    repo = Path(__file__).resolve().parents[3]
    source = repo / "docs/research/stage8-2019-2020-20261015/evidence/deciles-blocking-source-rows.csv"
    rows = list(csv.DictReader(source.read_text(encoding="utf-8").splitlines()))
    d = {r["Date"]: r for r in rows}
    with localcontext() as ctx:
        ctx.prec = 40
        D = Decimal
        previous = D(d["2019-12-26"]["Close"])
        close = D(d["2019-12-27"]["Close"])
        reference = D(d["2019-12-27"]["ChangesRatio"]) / 100
        raw = close / previous - 1
        hypothetical_base = D(54600)
        base_return = close / hypothetical_base - 1
        ratio = D("0.05")
        holder = close * (1 + ratio) / previous - 1
        # Later AGM proposal quantities; NOT certified historical inputs.
        total, eligible, proposed_new = D(143928048), D(142322962), D(7116148)
        next_close = D(d["2019-12-30"]["Close"])
        next_return = next_close / close - 1
        result = {
            "classification": "DIAGNOSTIC_HYPOTHESES_ONLY_NOT_EXECUTABLE_EVENTS",
            "source": str(source.relative_to(repo)),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_provenance": "preserved secondary FinanceData/marcap observations; not an independent KRX tape",
            "raw_source_rows": rows,
            "percent_returns": {
                "2019-12-27_raw_close": str(raw * 100),
                "2019-12-27_reported_ChangesRatio": str(reference * 100),
                "2019-12-27_assumed_54600_base": str(base_return * 100),
                "2019-12-27_assumed_1_05_equivalent_holder_value": str(holder * 100),
                "2019-12-30_raw_close": str(next_return * 100),
                "2019-12-30_reported_ChangesRatio": d["2019-12-30"]["ChangesRatio"],
            },
            "absolute_difference_bps": {
                "2019-12-27_raw_vs_reported": str(abs(raw - reference) * 10000),
                "2019-12-27_assumed_54600_vs_reported": str(abs(base_return - reference) * 10000),
                "2019-12-27_assumed_1_05_vs_reported": str(abs(holder - reference) * 10000),
                "2019-12-27_assumed_holder_vs_assumed_base": str(abs(holder - base_return) * 10000),
                "2019-12-30_raw_vs_reported": str(abs(next_return - D(d["2019-12-30"]["ChangesRatio"]) / 100) * 10000),
            },
            "unverified_base_hypotheses_KRW": {
                "previous_close_divided_by_1_05": str(previous / (1 + ratio)),
                "aggregate_share_count_dilution": str(previous * total / (total + proposed_new)),
                "user_suggested_rounded_base": str(hypothetical_base),
            },
            "later_proposal_quantities": {
                "total_old_shares": str(total),
                "eligible_old_shares_excluding_treasury": str(eligible),
                "proposed_new_shares": str(proposed_new),
                "proposed_new_over_total": str(proposed_new / total),
            },
            "hypothetical_per_old_share_value_KRW": {
                "tradable_stock": str(close),
                "unpaid_0_05_share_claim_marked_at_same_close": str(ratio * close),
                "combined_value": str((1 + ratio) * close),
            },
            "cautions": [
                "54600 is a hypothesis, not an official observed base price.",
                "Two different unrounded base hypotheses exist; no rounding/tick rule is selected.",
                "1.05 assumes a full gross entitlement marked at the ordinary-share price; no legal entitlement, delivery, tax, fraction, liquidity or NAV certification follows.",
                "A reference-price return and an entitled holder's economic return need separate validation contracts.",
                "No official 2019-12-26 return comparison is possible from these three rows alone.",
            ],
            "guard_tolerance_bps_unchanged": 1,
            "operating_data_modified": False,
            "decile_rerun_performed": False,
        }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
