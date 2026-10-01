from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from corporate_action_reconciliation import reconcile_registered_events
from corporate_action_registry import load_corporate_actions
from krx_history_audit import audit_source_history
from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]


def reconciliation_tests() -> None:
    dates = pd.to_datetime(["2024-04-05", "2024-04-08", "2024-04-09", "2024-04-11"])
    panel = pd.DataFrame({"Date": dates, "Code": "000001", "Market": "KOSPI",
                          "Close": [100., 100., 100., 9.], "Volume": [10., 10., 0., 20.],
                          "ChangesRatio": [0., 0., 0., -10.]})
    events = pd.DataFrame([{"event_date": dates[-1], "event_type": "stock_split",
        "predecessor_code": "000001", "successor_code": "000001", "share_ratio": 10., "cash_per_share": 0.,
        "source": "independent synthetic fixture", "source_url": "https://example.test/fixture"}])
    candidates = pd.DataFrame({"Date": [dates[-1], dates[-1], dates[1], dates[-1]],
        "Code": ["000001", "000002", "000001", "000001"],
        "kind": ["close_reference_return_difference"] * 3 + ["internal_observation_gap"]})
    original = [x.copy(deep=True) for x in (panel, events, candidates)]
    checks, reviewed = reconcile_registered_events(panel, events, candidates)
    assert checks.status.tolist() == ["reference_consistent"]
    assert np.isclose(checks.effective_return.iloc[0], -.1)  # true economic loss retained
    assert reviewed.registry_match_status.tolist() == ["registered_split_reference_consistent", "unresolved", "unresolved", "unresolved"]
    for changed in (events.assign(share_ratio=5.), events.assign(share_ratio=10.5)):
        c, r = reconcile_registered_events(panel, changed, candidates)
        assert c.status.tolist() == ["reference_mismatch"]
        assert not r.registry_match_status.eq("registered_split_reference_consistent").any()
    for changed in (events.assign(cash_per_share=1.), events.assign(share_ratio=np.inf)):
        assert reconcile_registered_events(panel, changed, candidates)[0].status.tolist() == ["invalid_event"]
    for changed_panel, changed_events in (
        (panel, events.assign(source_url="")),
        (panel, events.assign(predecessor_code="000003", successor_code="000003")),
        (panel[panel.Date != dates[2]], events),
        (panel.assign(ChangesRatio=[0., 0., 0., np.nan]), events),
        (panel.assign(Close=[100., 100., 101., 9.]), events),
        (panel.assign(Volume=[10., 10., 0., 0.]), events),
        (panel.assign(Volume=[10., np.inf, 0., 20.]), events),
        (panel.assign(ChangesRatio=[0., 0., np.inf, -10.]), events),
    ):
        c, r = reconcile_registered_events(changed_panel, changed_events, candidates)
        assert c.status.tolist() == ["data_gap"]
        assert not r.registry_match_status.eq("registered_split_reference_consistent").any()
    # Unsupported disposal values and empty registries never resolve a candidate.
    unsupported = events.assign(event_type="stock_merger", successor_code="000002")
    assert reconcile_registered_events(panel, unsupported, candidates)[0].status.tolist() == ["unsupported"]
    empty, unchanged = reconcile_registered_events(panel, events.iloc[:0], candidates)
    assert empty.empty and unchanged.registry_match_status.eq("unresolved").all()
    shuffled = reconcile_registered_events(panel.sample(frac=1, random_state=9), events, candidates)
    pd.testing.assert_frame_equal(checks, shuffled[0])
    for before, after in zip(original, (panel, events, candidates)):
        pd.testing.assert_frame_equal(before, after)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        for filename in ("registry_event_checks.csv", "candidate_reconciliation.csv"):
            (out / filename).write_text("stale")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/corporate_action_reconciliation.py"),
            "--start", "1990-01-01", "--end", "1990-01-31", "--output-dir", td], capture_output=True, text=True)
        assert proc.returncode == 3, proc.stderr
        assert json.loads((out / "corporate_action_reconciliation.json").read_text())["status"] == "data_gap"
        assert not (out / "registry_event_checks.csv").exists()
        assert not (out / "candidate_reconciliation.csv").exists()


def real_source_and_public_modes() -> None:
    raw = pd.read_parquet(ROOT / "data/krx_equities/yearly/marcap-2024.parquet")
    panel = raw[raw.Market.isin(["KOSPI", "KOSDAQ"])]
    events = load_corporate_actions(ROOT, start="2024-01-01", end="2024-12-31")
    _, _, candidates = audit_source_history(panel, "2024-01-01", "2024-12-31", ["KOSPI", "KOSDAQ"], ROOT)
    checks, reviewed = reconcile_registered_events(panel, events, candidates)
    assert len(candidates[candidates.kind.eq("close_reference_return_difference")]) == 257
    assert set(checks.Code) == {"001460", "001465", "086520", "003920", "003925", "278470"}
    assert checks.status.eq("reference_consistent").all()
    assert reviewed.registry_match_status.eq("registered_split_reference_consistent").sum() == 6
    assert (reviewed.kind.eq("close_reference_return_difference") & reviewed.registry_match_status.eq("unresolved")).sum() == 251
    assert reviewed.kind.eq("internal_observation_gap").sum() == 0
    byc = checks[checks.Code.isin(["001460", "001465"])].set_index("Code")
    assert byc.last_trade_date.eq(pd.Timestamp("2024-04-08")).all()
    assert np.isclose(byc.loc["001460", "effective_return"], 10 * 42400 / 489500 - 1)
    assert np.isclose(byc.loc["001465", "effective_return"], 10 * 17100 / 198900 - 1)
    assert byc.effective_return.lt(-.13).all()
    spec = json.loads((ROOT / "config/strategies/kr_equity_split_classes_research.json").read_text())
    # Independent signal-date universe/rank oracle, without event/survival filters.
    signal = panel[(panel.Date == "2024-03-29") & (panel.Market == "KOSPI")
                   & (panel.Volume > 0) & panel.Close.between(100000, 600000)]
    ranked_codes = signal.sort_values(["Close", "Code"], ascending=[False, True]).Code.tolist()
    assert {"001460", "001465"}.issubset(ranked_codes[:40])
    with tempfile.TemporaryDirectory() as td:
        for mode in ("top_n", "deciles"):
            spec["portfolio"] = {"selection": mode, "weighting": "equal"}
            if mode == "top_n":
                spec["portfolio"]["number_of_positions"] = 40
            path = Path(td) / f"{mode}.json"
            path.write_text(json.dumps(spec))
            out = Path(td) / mode
            result = run_strategy(path, ROOT, out, postprocess=False)
            groups = {"top_n": ranked_codes[:40]} if mode == "top_n" else {
                f"D{i+1:02d}": list(codes) for i, codes in enumerate(np.array_split(ranked_codes, 10))}
            daily = pd.read_csv(out / "daily_nav.csv", parse_dates=["Date"]).set_index("Date")
            applied = pd.read_csv(out / "corporate_actions_applied.csv", dtype={"predecessor_code": str})
            assert set(applied.predecessor_code) == {"001460", "001465"}
            assert applied.event_return.lt(-.13).all()
            assert applied.share_ratio.eq(10).all()
            for label, codes in groups.items():
                oracle_close = panel[panel.Code.isin(codes)].pivot(index="Date", columns="Code", values="Close").reindex(daily.index)[codes]
                buy = pd.Timestamp("2024-04-01")
                stock_values = oracle_close.loc[buy:] / oracle_close.loc[buy]
                for code in ("001460", "001465"):
                    if code in codes:
                        stock_values.loc["2024-04-17":, code] *= 10.
                assert np.isfinite(stock_values).all().all()
                oracle = pd.Series(1., index=daily.index)
                oracle.loc[buy:] = stock_values.mean(axis=1)
                net = oracle.copy()
                net.loc[buy:] *= 1 - 9.5 / 10000.
                prefix = "NAV_" if mode == "top_n" else f"NAV_{label}_"
                assert np.allclose(daily[prefix + "Gross"], oracle, atol=1e-12, rtol=0), label
                assert np.allclose(daily[prefix + "Net_fixed"], net, atol=1e-12, rtol=0), label
            if mode == "top_n":
                for execution in result["engine_result"]["execution_scenarios"].values():
                    assert execution["trades"].loc["2024-04-17", "cost_fraction"] == 0
            else:
                trades = pd.read_csv(out / "execution_trades.csv")
                assert trades[trades.Date.eq("2024-04-17")].cost_fraction.eq(0).all()
            # One missing preferred-share event must not inherit the common event.
            def without_preferred(*args, **kwargs):
                return load_corporate_actions(*args, **kwargs).query("predecessor_code != '001465'")
            module = "strategy_dsl_runner" if mode == "top_n" else "strategy_dsl_deciles"
            blocked = Path(td) / f"{mode}_missing_preferred"
            with patch(f"{module}.load_corporate_actions", side_effect=without_preferred):
                try:
                    run_strategy(path, ROOT, blocked, postprocess=False)
                except RuntimeError as exc:
                    assert "held-return reference check" in str(exc) and "001465" in str(exc), exc
                else:
                    raise AssertionError("preferred split event inherited from common stock")
            assert not blocked.exists()
    print("CORPORATE ACTION RECONCILIATION AND REAL SHARE-CLASS E2E: PASS")


if __name__ == "__main__":
    reconciliation_tests()
    real_source_and_public_modes()
