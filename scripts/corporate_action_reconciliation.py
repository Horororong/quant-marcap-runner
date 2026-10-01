from __future__ import annotations

"""Reconcile manually evidenced splits with source data, without changing execution."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from corporate_action_registry import load_corporate_actions
from execution_contract import (
    CORPORATE_ACTION_RECONCILIATION_VERSION, CORPORATE_ACTION_REGISTRY_VERSION,
    HELD_RETURN_TOLERANCE_BPS,
)
from krx_history_audit import (
    _normalized_panel, audit_source_history, expected_krx_sessions, source_file_provenance,
)

EVENT_COLUMNS = ["event_date", "event_type", "Code", "source", "source_url", "status", "reason",
                 "share_ratio", "last_trade_date", "last_trade_close", "event_close",
                 "effective_return", "exchange_return", "difference_bps"]


def reconcile_registered_events(panel: pd.DataFrame, events: pd.DataFrame,
                                candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Only an exact code/date match with a consistent registered split is explained.

    Sources in the registry were reviewed manually. Price agreement alone is not
    evidence of an event, historical completeness or a valid strategy holding.
    """
    x = _normalized_panel(panel)
    if "Volume" not in x:
        raise KeyError("split reconciliation requires Volume to identify actual trades")
    if events.duplicated(["event_date", "predecessor_code"]).any():
        raise ValueError("duplicate registry event date/security")
    records = []
    for event in events.sort_values(["event_date", "predecessor_code"]).to_dict("records"):
        date = pd.Timestamp(event["event_date"]).normalize()
        code = str(event["predecessor_code"]).zfill(6)
        rec = {"event_date": date, "event_type": event["event_type"], "Code": code,
               "source": event.get("source", ""), "source_url": event.get("source_url", ""),
               "share_ratio": event["share_ratio"], "status": "unsupported", "reason": "event value is not a same-code split"}
        records.append(rec)
        if event["event_type"] != "stock_split":
            continue
        rec.update(status="data_gap", reason="missing/non-finite source data or evidence metadata")
        ratio = pd.to_numeric(event["share_ratio"], errors="coerce")
        cash = pd.to_numeric(event["cash_per_share"], errors="coerce")
        if (code != str(event["successor_code"]).zfill(6) or not np.isfinite(ratio) or ratio <= 0
                or not np.isfinite(cash) or cash != 0):
            rec.update(status="invalid_event", reason="split requires same code, finite positive ratio and zero cash")
            continue
        if any(pd.isna(rec[f]) or not str(rec[f]).strip() for f in ("source", "source_url")):
            continue
        security = x[x["Code"].eq(code)].set_index("Date").sort_index()
        volume = pd.to_numeric(security["Volume"], errors="coerce")
        prior = security[(security.index < date) & (volume > 0)]
        if prior.empty or date not in security.index:
            continue
        last = prior.index[-1]
        previous = pd.to_numeric(prior.iloc[-1]["Close"], errors="coerce")
        close = pd.to_numeric(security.loc[date, "Close"], errors="coerce")
        reference = pd.to_numeric(security.loc[date, "ChangesRatio"], errors="coerce") / 100.0
        rec.update(last_trade_date=last, last_trade_close=previous, event_close=close, exchange_return=reference)
        if (not np.isfinite([previous, close, reference, volume.loc[last], volume.loc[date]]).all()
                or previous <= 0 or close <= 0 or volume.loc[date] <= 0):
            continue
        # Verify the observed suspension interval; do not synthesize missing rows.
        interval = expected_krx_sessions(str(last.date()), str(date.date()))
        observed = security.loc[last:date]
        if observed.index.tolist() != interval.tolist():
            rec["reason"] = "missing or unexpected observations between last trade and resumption"
            continue
        suspended = observed.iloc[1:-1]
        if not pd.to_numeric(suspended["Volume"], errors="coerce").eq(0).all():
            rec["reason"] = "suspension observations require explicit zero volume"
            continue
        suspended_close = pd.to_numeric(suspended["Close"], errors="coerce")
        suspended_ref = pd.to_numeric(suspended["ChangesRatio"], errors="coerce")
        if (not suspended_close.eq(previous).all() or not (suspended_ref.isna() | suspended_ref.eq(0)).all()):
            rec["reason"] = "suspension prices/references are inconsistent with unchanged holding value"
            continue
        effective = float(ratio * close / previous - 1.0)
        difference = abs(effective - reference) * 10000.0
        rec.update(effective_return=effective, difference_bps=difference,
                   status="reference_consistent" if np.isfinite(difference) and difference <= HELD_RETURN_TOLERANCE_BPS else "reference_mismatch",
                   reason="registered split agrees with exchange reference" if np.isfinite(difference) and difference <= HELD_RETURN_TOLERANCE_BPS else "registered split does not agree with exchange reference")
    checks = pd.DataFrame(records, columns=EVENT_COLUMNS)
    reviewed = candidates.copy(deep=True)
    reviewed["registry_match_status"] = "unresolved"
    reviewed["registry_source_url"] = ""
    for event in checks.itertuples():
        match = (reviewed["kind"].eq("close_reference_return_difference")
                 & reviewed["Code"].astype(str).str.zfill(6).eq(event.Code)
                 & pd.to_datetime(reviewed["Date"]).dt.normalize().eq(event.event_date))
        reviewed.loc[match, "registry_match_status"] = "registered_split_" + event.status if event.event_type == "stock_split" else "unsupported_registered_event"
        reviewed.loc[match, "registry_source_url"] = event.source_url
    return checks, reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    markets = ["KOSPI", "KOSDAQ"]
    from strategy_dsl_runner import load_project_engine
    outputs = ("registry_event_checks.csv", "candidate_reconciliation.csv")
    try:
        engine = load_project_engine(args.repo_root)
        panel = engine.load_krx_equity_panel(start=args.start, end=args.end, markets=markets,
            columns=["Date", "Code", "Market", "Close", "ChangesRatio", "Volume"], repo_root=args.repo_root)
        history, _, candidates = audit_source_history(panel, args.start, args.end, markets, args.repo_root)
        events = load_corporate_actions(args.repo_root, start=args.start, end=args.end)
        checks, reviewed = reconcile_registered_events(panel, events, candidates)
        price_candidates = reviewed[reviewed["kind"].eq("close_reference_return_difference")]
        status = "data_gap" if history["status"] != "complete" or checks["status"].eq("data_gap").any() else "event_mismatch" if (~checks["status"].isin(["reference_consistent", "unsupported"])).any() else "ok"
        summary = {"status": status, "requested_start": args.start, "requested_end": args.end,
                   "corporate_action_reconciliation_version": CORPORATE_ACTION_RECONCILIATION_VERSION,
                   "corporate_action_registry_version": CORPORATE_ACTION_REGISTRY_VERSION,
                   "files": source_file_provenance(args.repo_root, args.start, args.end),
                   "session_coverage": history["session_coverage"],
                   "event_check_counts": {str(k): int(v) for k, v in checks["status"].value_counts().sort_index().items()},
                   "price_candidate_status_counts": {str(k): int(v) for k, v in price_candidates["registry_match_status"].value_counts().sort_index().items()},
                   "source_candidate_counts": history["candidate_counts"], "tolerance_bps": HELD_RETURN_TOLERANCE_BPS,
                   "history_completeness": "unverified",
                   "scope": "source diagnostics only; exact code/date registered split agreement does not change candidates, eligibility, prices, holdings, NAV or registry. Merger disposal values require separate reconciliation."}
    except (FileNotFoundError, RuntimeError, OSError, KeyError, TypeError, ValueError, AssertionError) as exc:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for filename in outputs:
            (args.output_dir / filename).unlink(missing_ok=True)
        summary = {"status": "data_gap", "corporate_action_reconciliation_version": CORPORATE_ACTION_RECONCILIATION_VERSION,
                   "error": {"type": type(exc).__name__, "message": str(exc)}}
        (args.output_dir / "corporate_action_reconciliation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(3)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checks.to_csv(args.output_dir / outputs[0], index=False)
    reviewed.to_csv(args.output_dir / outputs[1], index=False)
    (args.output_dir / "corporate_action_reconciliation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["status"] == "ok" else 3)


if __name__ == "__main__":
    main()
