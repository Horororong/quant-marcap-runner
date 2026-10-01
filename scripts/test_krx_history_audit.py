from __future__ import annotations

from pathlib import Path
import json
import tempfile
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

from krx_history_audit import (
    HistoryCoverageError, audit_source_history, expected_krx_sessions,
    require_session_coverage, session_coverage_audit,
)
from strategy_dsl_preflight import preflight_strategy
from strategy_dsl_runner import run_strategy
from test_strategy_dsl_preflight import base_spec

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> pd.DataFrame:
    # Independent April 2024 oracle: weekends plus the April 10 election close.
    dates = pd.bdate_range("2024-04-01", "2024-04-30").difference(pd.DatetimeIndex(["2024-04-10"]))
    return pd.DataFrame([{"Date": d, "Code": f"{i:06d}", "Market": "KOSPI" if i <= 10 else "KOSDAQ",
                          "Close": 100.0, "ChangesRatio": 0.0}
                         for d in dates for i in range(1, 21)])


def coverage_tests() -> None:
    panel = fixture()
    dates = pd.DatetimeIndex(panel["Date"].unique())
    pd.testing.assert_index_equal(expected_krx_sessions("2024-04-01", "2024-04-30"), dates, check_names=False)
    ok = require_session_coverage(panel, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"])
    assert ok["expected_sessions"] == 21
    assert all(x["observed_sessions"] == 21 for x in ok["markets"].values())
    # Interior, first and last requested sessions cannot disappear silently.
    for day in ("2024-04-01", "2024-04-09", "2024-04-30"):
        bad = panel[panel["Date"] != pd.Timestamp(day)]
        try:
            require_session_coverage(bad, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"])
        except HistoryCoverageError as exc:
            assert exc.history_coverage["markets"]["KOSPI"]["missing_sessions"] == [day]
        else:
            raise AssertionError("missing requested session accepted")
    # The other market's presence cannot mask a whole-market gap.
    bad = panel[~((panel["Date"] == pd.Timestamp("2024-04-09")) & (panel["Market"] == "KOSDAQ"))]
    audit = session_coverage_audit(bad, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"])
    assert audit["markets"]["KOSPI"]["status"] == "complete"
    assert audit["markets"]["KOSDAQ"]["missing_sessions"] == ["2024-04-09"]
    extra = pd.concat([panel, panel.iloc[:1].assign(Date=pd.Timestamp("2024-04-06"))])
    assert session_coverage_audit(extra, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"])["markets"]["KOSPI"]["unexpected_dates"] == ["2024-04-06"]
    # Weekend request endpoints are valid: no calendar-day approximation.
    assert require_session_coverage(panel, "2024-03-30", "2024-04-30", ["KOSPI", "KOSDAQ"])["expected_first_session"] == "2024-04-01"
    # Requests older than the package's default range use explicit bounds.
    early = expected_krx_sessions("2000-01-01", "2000-01-10")
    assert early[0] == pd.Timestamp("2000-01-04")
    for bad, exc_type in (
        (pd.concat([panel, panel.iloc[:1].assign(Code="1")]), AssertionError),
        (panel.assign(Date=pd.NaT), ValueError),
        (panel.assign(Code=None), ValueError),
    ):
        try:
            session_coverage_audit(bad, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"])
        except exc_type:
            pass
        else:
            raise AssertionError("malformed history accepted")


def diagnostic_tests() -> None:
    panel = fixture()
    panel = panel[~((panel["Code"] == "000001") & (panel["Date"] == pd.Timestamp("2024-04-09")))].copy()
    panel.loc[(panel["Code"] == "000002") & (panel["Date"] >= pd.Timestamp("2024-04-08")), "Close"] = 50.0
    panel.loc[(panel["Code"] == "000003") & (panel["Date"] == pd.Timestamp("2024-04-08")), "Close"] = np.nan
    # A 0.54% rounded exchange return is consistent with 100 -> 100.543.
    panel.loc[(panel["Code"] == "000004") & (panel["Date"] >= pd.Timestamp("2024-04-08")), "Close"] = 100.543
    panel.loc[(panel["Code"] == "000004") & (panel["Date"] == pd.Timestamp("2024-04-08")), "ChangesRatio"] = 0.54
    panel = panel[~((panel["Code"] == "000005") & (panel["Date"] == pd.Timestamp("2024-04-30")))]
    panel = panel[~((panel["Code"] == "000006") & (panel["Date"] == pd.Timestamp("2024-04-01")))]
    original = panel.copy(deep=True)
    with tempfile.TemporaryDirectory() as td:
        summary, codes, candidates = audit_source_history(panel, "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"], Path(td))
        assert summary["session_coverage"]["status"] == "complete"
        assert summary["corporate_actions"]["history_completeness"] == "unverified"
        assert not summary["corporate_actions"]["registry_file_present"]
    counts = summary["candidate_counts"]
    assert counts == {"internal_observation_gap": 1, "close_reference_return_difference": 1,
                      "invalid_close": 1, "right_censored_observation_end": 1, "left_censored_observation_start": 1}, counts
    gap = candidates[candidates["kind"] == "internal_observation_gap"].iloc[0]
    assert gap.Code == "000001" and gap.missing_sessions == 1 and gap.Date == pd.Timestamp("2024-04-11")
    anomaly = candidates[candidates["kind"] == "close_reference_return_difference"].iloc[0]
    assert anomaly.Code == "000002" and anomaly.difference_bps == 5000.0
    assert codes.set_index("Code").loc["000001", "missing_internal_sessions"] == 1
    pd.testing.assert_frame_equal(original, panel)
    with tempfile.TemporaryDirectory() as td:
        shuffled = audit_source_history(panel.sample(frac=1, random_state=11), "2024-04-01", "2024-04-30", ["KOSPI", "KOSDAQ"], Path(td))
        assert summary == shuffled[0]
        pd.testing.assert_frame_equal(candidates, shuffled[2])
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        for name in ("security_observation_coverage.csv", "history_review_candidates.csv"):
            (out / name).write_text("stale source result")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/krx_history_audit.py"),
                               "--start", "1990-01-01", "--end", "1990-01-31",
                               "--output-dir", td], capture_output=True, text=True)
        assert proc.returncode == 3, proc.stderr
        report = json.loads((out / "history_audit.json").read_text())
        assert report["status"] == "data_gap" and report["error"]["type"] == "FileNotFoundError"
        assert not (out / "history_review_candidates.csv").exists()
        assert not (out / "security_observation_coverage.csv").exists()


def integration_tests() -> None:
    panel = fixture()
    bad = panel[panel["Date"] != pd.Timestamp("2024-04-09")]
    class PanelEngine:
        def load_krx_equity_panel(self, **kwargs):
            return bad.copy()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "strategy.json"
        raw = base_spec("2024-04-01", "2024-04-30")
        path.write_text(json.dumps(raw))
        with patch("strategy_dsl_preflight.load_project_engine", return_value=PanelEngine()), patch("strategy_dsl_preflight.factor_provider_coverage_audit", side_effect=AssertionError("provider must not run")):
            result = preflight_strategy(path, ROOT)
            assert result["status"] == "data_gap" and result["preflight_contract_version"] == "2"
            assert result["history_coverage"]["markets"]["KOSDAQ"]["missing_sessions"] == ["2024-04-09"]
        for selection, module in [("top_n", "strategy_dsl_runner"), ("deciles", "strategy_dsl_deciles")]:
            raw["portfolio"] = {"selection": selection, "weighting": "equal"}
            if selection == "top_n":
                raw["portfolio"]["number_of_positions"] = 5
            path.write_text(json.dumps(raw))
            out = Path(td) / selection
            with patch(f"{module}.load_project_engine", return_value=PanelEngine()):
                try:
                    run_strategy(path, ROOT, out, postprocess=False)
                except HistoryCoverageError:
                    pass
                else:
                    raise AssertionError(f"{selection} runner bypassed source coverage")
            assert not out.exists()


def real_history_test() -> None:
    panel = pd.read_parquet(ROOT / "data/krx_equities/yearly/marcap-2020.parquet", columns=["Date", "Code", "Market", "Close", "ChangesRatio"])
    panel = panel[panel["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
    summary, codes, candidates = audit_source_history(panel, "2020-01-01", "2020-12-31", ["KOSPI", "KOSDAQ"], ROOT)
    # Fixed 2020 regression count; exact date equality is checked separately.
    assert summary["session_coverage"]["expected_sessions"] == 248
    assert summary["session_coverage"]["status"] == "complete", summary["session_coverage"]
    assert len(codes) == panel["Code"].nunique()
    assert summary["corporate_actions"]["registered_events_in_period"] == 1
    assert summary["corporate_actions"]["history_completeness"] == "unverified"
    assert not candidates.empty
    print("REAL KRX 2020 HISTORY AUDIT:", json.dumps({"codes": len(codes), "candidate_counts": summary["candidate_counts"]}))


if __name__ == "__main__":
    coverage_tests()
    diagnostic_tests()
    integration_tests()
    real_history_test()
    print("KRX HISTORY COVERAGE AND DIAGNOSTICS: PASS")
