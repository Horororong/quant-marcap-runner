from __future__ import annotations

"""Source-history diagnostics only: never infer listings, cash flows or returns.

Calendar coverage is a hard gate shared by preflight and both DSL runners.
Per-code gaps and raw-close/reference-return differences are review candidates,
not verified corporate actions and never inputs to universe selection.
"""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xcals

from corporate_action_registry import CORPORATE_ACTION_FILE, load_corporate_actions
from execution_contract import HISTORY_AUDIT_CONTRACT_VERSION

PRICE_DIFFERENCE_THRESHOLD_BPS = 25.0
CANDIDATE_COLUMNS = ["kind", "Code", "Date", "previous_date", "missing_sessions",
                     "previous_close", "close", "close_return", "exchange_return",
                     "difference_bps"]


class HistoryCoverageError(RuntimeError):
    def __init__(self, audit: dict):
        self.history_coverage = audit
        problems = {market: {"missing": row["missing_sessions"][:12],
                             "unexpected": row["unexpected_dates"][:12]}
                    for market, row in audit["markets"].items() if row["status"] != "complete"}
        super().__init__(f"KRX session coverage failed; no period shortening or filling: {problems}")


def expected_krx_sessions(start: str, end: str) -> pd.DatetimeIndex:
    left, right = pd.Timestamp(start), pd.Timestamp(end)
    if left.tzinfo is not None or right.tzinfo is not None or left > right:
        raise ValueError("history audit requires ordered timezone-naive dates")
    # Explicit bounds avoid the library's moving default calendar range.
    calendar = xcals.get_calendar("XKRX", start=left - pd.Timedelta(days=7),
                                  end=right + pd.Timedelta(days=7))
    sessions = calendar.sessions_in_range(left.normalize(), right.normalize())
    sessions = pd.DatetimeIndex(sessions).tz_localize(None).normalize()
    if sessions.empty:
        raise ValueError("requested period has no XKRX sessions")
    return sessions


def _normalized_panel(panel: pd.DataFrame) -> pd.DataFrame:
    missing = {"Date", "Code", "Market"} - set(panel)
    if missing:
        raise KeyError(f"history audit missing columns: {sorted(missing)}")
    x = panel.copy()
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    if x["Date"].isna().any() or x["Date"].dt.tz is not None:
        raise ValueError("history audit requires valid timezone-naive Date rows")
    x["Date"] = x["Date"].dt.normalize()
    if x[["Code", "Market"]].isna().any().any():
        raise ValueError("history audit requires non-null Code and Market")
    x["Code"] = x["Code"].astype(str).str.strip().str.zfill(6)
    x["Market"] = x["Market"].astype(str).str.strip().str.upper()
    # KRX preferred-share codes can include letters (e.g. 005935, 33626K).
    if not x["Code"].str.fullmatch(r"[0-9A-Z]{6}").all():
        raise ValueError("history audit requires six-character KRX security codes")
    if x.duplicated(["Date", "Code"]).any():
        raise AssertionError("history audit duplicate Date + Code")
    return x.sort_values(["Code", "Date"]).reset_index(drop=True)


def session_coverage_audit(panel: pd.DataFrame, start: str, end: str,
                           markets: tuple[str, ...] | list[str]) -> dict:
    x = _normalized_panel(panel[["Date", "Code", "Market"]])
    expected = expected_krx_sessions(start, end)
    requested = sorted(set(markets))
    if not requested or not set(requested).issubset({"KOSPI", "KOSDAQ"}):
        raise ValueError("history audit requires KOSPI/KOSDAQ markets")
    if not set(x["Market"]).issubset(requested):
        raise ValueError("history audit panel contains unrequested markets")
    rows = {}
    for market in requested:
        actual = pd.DatetimeIndex(x.loc[x["Market"] == market, "Date"].unique()).sort_values()
        missing, unexpected = expected.difference(actual), actual.difference(expected)
        rows[market] = {
            "status": "complete" if missing.empty and unexpected.empty else "data_gap",
            "observed_sessions": len(actual),
            "missing_sessions": [d.date().isoformat() for d in missing],
            "unexpected_dates": [d.date().isoformat() for d in unexpected],
        }
    return {
        "history_audit_contract_version": HISTORY_AUDIT_CONTRACT_VERSION,
        "status": "complete" if all(r["status"] == "complete" for r in rows.values()) else "data_gap",
        "calendar": "XKRX", "calendar_package_version": version("exchange_calendars"),
        "requested_start": str(pd.Timestamp(start).date()), "requested_end": str(pd.Timestamp(end).date()),
        "expected_first_session": str(expected[0].date()), "expected_last_session": str(expected[-1].date()),
        "expected_sessions": len(expected), "markets": rows,
        "scope": "market-level session presence only; per-security history and corporate-action completeness are not certified",
    }


def require_session_coverage(panel: pd.DataFrame, start: str, end: str,
                              markets: tuple[str, ...] | list[str]) -> dict:
    audit = session_coverage_audit(panel, start, end, markets)
    if audit["status"] != "complete":
        raise HistoryCoverageError(audit)
    return audit


def audit_source_history(panel: pd.DataFrame, start: str, end: str,
                         markets: tuple[str, ...] | list[str], repo_root: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    coverage = session_coverage_audit(panel, start, end, markets)
    x = _normalized_panel(panel)
    expected = expected_krx_sessions(start, end)
    positions = pd.Series(np.arange(len(expected)), index=expected)
    x["session"] = x["Date"].map(positions)
    grouped = x.groupby("Code", sort=True)
    previous_date = grouped["Date"].shift()
    previous_session = grouped["session"].shift()
    distance = x["session"] - previous_session
    code_rows = grouped.agg(first_observation=("Date", "min"), last_observation=("Date", "max"),
                            observations=("Date", "size"))
    code_rows["sessions_before_first"] = code_rows["first_observation"].map(positions)
    code_rows["sessions_after_last"] = len(expected) - 1 - code_rows["last_observation"].map(positions)
    code_rows["missing_internal_sessions"] = (distance - 1).clip(lower=0).groupby(x["Code"]).sum()
    code_rows = code_rows.reset_index()
    candidates = []

    def append_rows(mask: pd.Series, kind: str, **fields) -> None:
        if mask.any():
            rows = x.loc[mask, ["Code", "Date"]].copy()
            rows["kind"] = kind
            for field, values in fields.items():
                rows[field] = values.loc[mask]
            candidates.append(rows)

    append_rows(distance > 1, "internal_observation_gap", previous_date=previous_date,
                missing_sessions=distance - 1)
    for field, date_field, kind in (
        ("sessions_before_first", "first_observation", "left_censored_observation_start"),
        ("sessions_after_last", "last_observation", "right_censored_observation_end"),
    ):
        rows = code_rows.loc[code_rows[field] > 0, ["Code", date_field, field]].rename(
            columns={date_field: "Date", field: "missing_sessions"})
        rows["kind"] = kind
        candidates.append(rows)

    close = pd.to_numeric(x["Close"], errors="coerce")
    invalid = ~np.isfinite(close) | (close <= 0)
    append_rows(invalid, "invalid_close", close=close)
    previous_close = close.groupby(x["Code"]).shift()
    exchange_return = pd.to_numeric(x["ChangesRatio"], errors="coerce") / 100.0
    close_return = close / previous_close - 1.0
    difference = (close_return - exchange_return).abs() * 10_000.0
    compare = distance.eq(1) & ~invalid & np.isfinite(previous_close) & (previous_close > 0) & np.isfinite(exchange_return)
    append_rows(compare & (difference > PRICE_DIFFERENCE_THRESHOLD_BPS), "close_reference_return_difference",
                previous_date=previous_date, previous_close=previous_close, close=close,
                close_return=close_return, exchange_return=exchange_return, difference_bps=difference)
    rows = pd.concat(candidates, ignore_index=True).reindex(columns=CANDIDATE_COLUMNS)
    rows = rows.sort_values(["Date", "Code", "kind"]).reset_index(drop=True)
    events = load_corporate_actions(repo_root, start=start, end=end)
    summary = {
        "status": coverage["status"],
        "history_audit_contract_version": HISTORY_AUDIT_CONTRACT_VERSION,
        "source": {"path_template": "data/krx_equities/yearly/marcap-YYYY.parquet",
                   "origin": "FinanceData/marcap via repository", "markets": sorted(set(markets))},
        "session_coverage": coverage, "rows": len(x), "distinct_codes": int(x["Code"].nunique()),
        "candidate_counts": {str(k): int(v) for k, v in rows["kind"].value_counts().sort_index().items()},
        "price_comparison": {"changes_ratio_unit": "percent", "absolute_difference_threshold_bps": PRICE_DIFFERENCE_THRESHOLD_BPS,
                             "compared_consecutive_observations": int(compare.sum()),
                             "policy": "review candidates only; no inferred split, merger, delisting or dividend"},
        "corporate_actions": {"registry": CORPORATE_ACTION_FILE,
                              "registry_file_present": (repo_root / CORPORATE_ACTION_FILE).exists(),
                              "registered_events_in_period": len(events), "history_completeness": "unverified",
                              "events": [{"event_date": str(r.event_date.date()), "event_type": r.event_type,
                                          "predecessor_code": r.predecessor_code, "successor_code": r.successor_code,
                                          "source": r.source} for r in events.itertuples()]},
        "interpretation": "observed starts/ends are censored by the requested window; gaps can reflect source defects or security events. Candidates never change universe, weights, NAV or registry.",
    }
    return summary, code_rows, rows


def source_file_provenance(root: Path, start: str, end: str) -> list[dict]:
    paths = [root / f"data/krx_equities/yearly/marcap-{y}.parquet"
             for y in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1)]
    if (root / CORPORATE_ACTION_FILE).exists():
        paths.append(root / CORPORATE_ACTION_FILE)
    rows = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        rows.append({"path": str(path.relative_to(root)), "sha256": digest.hexdigest()})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--markets", nargs="+", default=["KOSPI", "KOSDAQ"])
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    from strategy_dsl_runner import load_project_engine
    engine = load_project_engine(args.repo_root)
    try:
        panel = engine.load_krx_equity_panel(start=args.start, end=args.end, markets=args.markets,
            columns=["Date", "Code", "Market", "Close", "ChangesRatio"], repo_root=args.repo_root)
        summary, codes, candidates = audit_source_history(panel, args.start, args.end, args.markets, args.repo_root)
        summary["source"]["files"] = source_file_provenance(args.repo_root, args.start, args.end)
    except (FileNotFoundError, RuntimeError, OSError, KeyError, TypeError, ValueError, AssertionError) as exc:
        summary = {"history_audit_contract_version": HISTORY_AUDIT_CONTRACT_VERSION,
                   "status": "data_gap", "requested_start": args.start, "requested_end": args.end,
                   "error": {"type": type(exc).__name__, "message": str(exc)}}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("security_observation_coverage.csv", "history_review_candidates.csv"):
            (args.output_dir / filename).unlink(missing_ok=True)
        (args.output_dir / "history_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(3)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "history_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    codes.to_csv(args.output_dir / "security_observation_coverage.csv", index=False)
    candidates.to_csv(args.output_dir / "history_review_candidates.csv", index=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["session_coverage"]["status"] == "complete" else 3)


if __name__ == "__main__":
    main()
