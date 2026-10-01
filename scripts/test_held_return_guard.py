from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from corporate_action_registry import load_corporate_actions
from krx_history_audit import expected_krx_sessions
from strategy_dsl import StrategySpec
from strategy_dsl_deciles import build_decile_target_weights_from_panel, execute_decile_nav
from strategy_dsl_runner import load_project_engine, return_reference_matrix, run_strategy
from test_strategy_dsl_deciles import make_panel, make_spec

ROOT = Path(__file__).resolve().parents[1]


def fails(call, text="held-return reference check") -> None:
    try:
        call()
    except (RuntimeError, ValueError, AssertionError) as exc:
        assert text in str(exc), exc
    else:
        raise AssertionError(f"expected failure: {text}")


def guard_and_split_tests() -> None:
    engine = load_project_engine(ROOT)
    dates = pd.bdate_range("2024-04-01", periods=5)
    prices = pd.DataFrame({"000001": [100., 200., 200., 202., 204.],
                           "000002": [1., 1., 0.5, 0.5, 0.5]}, index=dates)
    weights = pd.DataFrame({"000001": [1.], "000002": [0.]}, index=[dates[0]])
    ref = prices.pct_change(fill_method=None)
    ref.loc[dates[1], "000001"] = 0.0  # buy date: existing cash earns no stock return
    ref["000002"] = np.nan  # unheld missing references do not change the universe
    def run(px=prices, references=ref, targets=weights, actions=None, mask=None):
        return engine.simulate_target_weight_portfolio(px, targets, reference_returns=references,
            corporate_action_events=actions, tradable_mask=mask)
    good = run()
    assert np.allclose(good["daily_nav"]["Gross"], [1., 1., 1., 1.01, 1.02])
    assert good["return_reference_check"]["checked_observations"] == 3
    assert good["return_reference_check"]["enabled"]
    for bad_value in (np.nan, np.inf, 0.0):
        bad = ref.copy()
        bad.loc[dates[3], "000001"] = bad_value
        fails(lambda: run(references=bad))
    # 1bp guard allows ordinary half-bp exchange rounding, not larger discrepancies.
    rounded = ref.copy()
    rounded.loc[dates[3], "000001"] += 0.00005
    assert np.allclose(run(references=rounded)["daily_nav"], good["daily_nav"])
    excessive = ref.copy()
    excessive.loc[dates[3], "000001"] += 0.00011
    fails(lambda: run(references=excessive))
    # A sale at this close cannot hide the already-held asset's return.
    sale = pd.concat([weights, pd.DataFrame({"000001": [0.], "000002": [0.]}, index=[dates[2]])])
    fails(lambda: run(references=excessive, targets=sale))

    split_prices = pd.DataFrame({"000001": [100., 100., 100., 22., 24.2], "000002": 1.}, index=dates)
    split_ref = pd.DataFrame({"000001": [0., 0., 0., 0.1, 0.1], "000002": np.nan}, index=dates)
    event = pd.DataFrame([{"event_date": dates[3], "event_type": "stock_split", "predecessor_code": "000001",
        "successor_code": "000001", "share_ratio": 5., "cash_per_share": 0., "source": "synthetic verified split"}])
    fails(lambda: run(split_prices, split_ref))
    split = run(split_prices, split_ref, actions=event)
    assert np.allclose(split["daily_nav"]["Gross"], [1., 1., 1., 1.1, 1.21])
    assert split["weights"].iloc[0]["Cash"] == 1.
    assert split["weights"].loc[dates[3], "000001"] == 1.
    assert split["trades"].loc[dates[3], ["buy_turnover", "sell_turnover", "cost_fraction"]].eq(0).all()
    assert split["return_reference_check"]["verified_override_observations"] == 0  # split reference still checked
    wrong = event.copy()
    wrong["share_ratio"] = 4.
    fails(lambda: run(split_prices, split_ref, actions=wrong))
    for field, value in [("share_ratio", np.inf), ("cash_per_share", np.nan), ("cash_per_share", 1.), ("successor_code", "000002")]:
        bad = event.copy()
        bad[field] = value
        fails(lambda: run(split_prices, split_ref, actions=bad), "")
    # Registered missing-price suspension is allowed; resume still needs reference.
    suspended = split_prices.copy()
    suspended.loc[dates[2], "000001"] = np.nan
    missing_ref = split_ref.copy()
    missing_ref.loc[dates[2], "000001"] = np.nan
    mask = suspended.notna()
    suspended_out = run(suspended, missing_ref, actions=event, mask=mask)
    assert np.allclose(suspended_out["daily_nav"]["Gross"], split["daily_nav"]["Gross"])
    assert suspended_out["return_reference_check"]["verified_override_observations"] == 1
    corrupt_ref = missing_ref.copy()
    corrupt_ref.loc[dates[2], "000001"] = np.inf
    fails(lambda: run(suspended, corrupt_ref, actions=event, mask=mask))
    missing_ref.loc[dates[3], "000001"] = np.nan
    fails(lambda: run(suspended, missing_ref, actions=event, mask=mask))

    # Merger disposal value has its own explicit override, without exempting successor returns.
    merger = event.copy()
    merger["event_type"] = "stock_merger"
    merger["successor_code"] = "000002"
    merger["share_ratio"] = 110.
    merger_ref = split_ref.copy()
    merger_ref["000002"] = 0.
    merged = run(split_prices, merger_ref, actions=merger)
    assert np.isclose(merged["daily_nav"].loc[dates[3], "Gross"], 1.1)
    assert merged["return_reference_check"]["verified_override_observations"] == 1
    wrong_succ = merger_ref.copy()
    wrong_succ.loc[dates[4], "000002"] = 0.02
    fails(lambda: run(split_prices, wrong_succ, actions=merger))
    # An account first funded at the event close does not need pre-window event prices.
    post_event_prices = split_prices.loc[dates[3]:]
    post_event_target = pd.DataFrame({"000001": [1.], "000002": [0.]}, index=[dates[3]])
    post_event = run(post_event_prices, split_ref.loc[dates[3]:], post_event_target, event)
    assert post_event["daily_nav"]["Gross"].eq(1.).all()
    assert post_event["corporate_actions"].empty


def public_runner_failure_tests() -> None:
    engine = load_project_engine(ROOT)
    panel = make_panel()
    panel["ChangesRatio"] = panel.groupby("Code")["Close"].pct_change(fill_method=None) * 100.
    references = return_reference_matrix(panel, sorted(panel["Code"].unique()))
    spec = make_spec()
    targets, _, _ = build_decile_target_weights_from_panel(panel, spec)
    references.loc[pd.Timestamp("2024-05-02"), "000001"] = 0.
    fails(lambda: execute_decile_nav(panel, spec, targets, engine, pd.DataFrame(), references), "D01")
    # Both public modes stop before writing outputs with inconsistent held returns.
    raw = json.loads((ROOT / "config/strategies/kr_equity_split_research.json").read_text())
    source = pd.DataFrame([{"Date": d, "Code": f"{i:06d}", "Market": "KOSDAQ", "Close": 110. if i == 1 and d >= pd.Timestamp("2024-04-02") else 100.,
                           "ChangesRatio": 0., "Volume": 1000., "Amount": 100000., "Marcap": i * 1000000.}
                          for d in expected_krx_sessions(raw["period"]["start"], raw["period"]["end"]) for i in range(1, 21)])
    with tempfile.TemporaryDirectory() as td:
        for mode, module in [("top_n", "strategy_dsl_runner"), ("deciles", "strategy_dsl_deciles")]:
            raw["portfolio"] = {"selection": mode, "weighting": "equal"}
            if mode == "top_n":
                raw["portfolio"]["number_of_positions"] = 1
            path = Path(td) / f"{mode}.json"
            path.write_text(json.dumps(raw))
            out = Path(td) / mode
            with patch(f"{module}.load_project_engine", return_value=engine), patch.object(engine, "load_krx_equity_panel", return_value=source):
                fails(lambda: run_strategy(path, ROOT, out, postprocess=False), "held-return reference check")
            assert not out.exists()


def real_split_e2e() -> None:
    path = ROOT / "config/strategies/kr_equity_split_research.json"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        result = run_strategy(path, ROOT, out, postprocess=False)
        daily = pd.read_csv(out / "daily_nav.csv", parse_dates=["Date"]).set_index("Date")
        selected = pd.read_csv(out / "selections.csv", dtype={"Code": str})
        assert selected["Code"].tolist() == ["086520"]
        execution = result["engine_result"]["execution_scenarios"]["zero"]
        buy = pd.Timestamp(execution["execution_schedule"].iloc[0]["execution_date"])
        assert buy == pd.Timestamp("2024-04-01")
        raw = pd.read_parquet(ROOT / "data/krx_equities/yearly/marcap-2024.parquet")
        close = raw[raw["Code"] == "086520"].set_index("Date")["Close"].reindex(daily.index)
        # Independent share-count oracle: same original holding becomes five shares.
        expected = pd.Series(1., index=daily.index)
        after = daily.index >= buy
        expected.loc[after] = close.loc[after] / close.loc[buy]
        expected.loc[expected.index >= pd.Timestamp("2024-04-25")] *= 5.
        assert np.allclose(daily["NAV_Gross"], expected, atol=1e-12, rtol=0)
        net = expected.copy()
        net.loc[after] *= 1. - 9.5 / 10000.
        assert np.allclose(daily["NAV_Net_fixed"], net, atol=1e-12, rtol=0)
        action = execution["corporate_actions"].iloc[0]
        assert action.event_type == "stock_split" and action.share_ratio == 5.
        assert action.last_trade_date == pd.Timestamp("2024-04-08")
        assert np.isclose(action.event_return, 5 * 108100 / 517000 - 1.)
        assert execution["trades"].loc["2024-04-25", "cost_fraction"] == 0.
        assert execution["return_reference_check"]["enabled"]
        assert json.loads((out / "return_reference_audit.json").read_text())["zero"]["checked_observations"] > 0
        assert (out / "held_return_checks.csv").exists()
        # Removing the verified registry event stops the artificial ~79% drop.
        with patch("strategy_dsl_runner.load_corporate_actions", return_value=pd.DataFrame()):
            fails(lambda: run_strategy(path, ROOT, Path(td) / "unregistered", postprocess=False))
        assert not (Path(td) / "unregistered").exists()
    print("HELD RETURN GUARD AND REAL ECOPRO SPLIT E2E: PASS")


if __name__ == "__main__":
    guard_and_split_tests()
    public_runner_failure_tests()
    real_split_e2e()
