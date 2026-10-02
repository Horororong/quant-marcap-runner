from __future__ import annotations

from pathlib import Path
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator, ValidationError

from export_strategy_dsl_contract import build_strategy_json_schema
from execution_contract import DECILE_RESEARCH_CONTRACT
from krx_history_audit import expected_krx_sessions
from strategy_dsl import StrategySpec, compile_execution_plan
from strategy_dsl_deciles import (
    DECILE_LABELS, build_decile_target_weights_from_panel, execute_decile_nav,
    partition_deciles,
)
from strategy_dsl_runner import load_project_engine, run_strategy, score_cross_section

ROOT = Path(__file__).resolve().parents[1]


def make_spec() -> StrategySpec:
    return StrategySpec.from_dict({
        "schema_version": "1.0", "strategy_id": "deciles_regression",
        "title": "synthetic decile contract test", "asset_class": "kr_equity",
        "universe": {"markets": ["KOSPI"], "require_tradable_on_signal": True, "filters": []},
        "factors": [{"name": "size", "source": "krx", "field": "Marcap", "direction": "low"}],
        "portfolio": {"selection": "deciles", "weighting": "equal"},
        "rebalance": {"frequency": "months", "months": [4, 10], "trading_day": "last"},
        "execution": {"lag_sessions": 1, "price": "next_close"},
        "cost_scenarios": {"zero": {}, "cost": {"commission_bps": 100, "sell_tax_bps": 100}},
        "period": {"start": "2024-04-01", "end": "2024-11-08", "book_start": "2024-04-01", "book_end": "2024-11-08", "as_of_date": "2024-11-08"},
    })


def make_panel(n: int = 20) -> pd.DataFrame:
    dates = pd.bdate_range("2024-04-01", "2024-11-08")
    rows = []
    for date in dates:
        for i in range(1, n + 1):
            # April execution-day jump belongs to cash, not the new positions.
            price = 100.0 if date < pd.Timestamp("2024-05-01") else 200.0
            if date >= pd.Timestamp("2024-05-02"):
                price = 220.0
            rows.append({
                "Date": date, "Code": f"{i:06d}", "Name": f"S{i}", "Market": "KOSPI",
                "Close": price, "Volume": 1000.0, "Amount": 100_000.0,
                "Marcap": float(i if date < pd.Timestamp("2024-10-31") else n + 1 - i),
            })
    return pd.DataFrame(rows)


def expect_error(fn, kind, text: str) -> None:
    try:
        fn()
    except kind as exc:
        assert text in str(exc), exc
    else:
        raise AssertionError(f"expected {kind.__name__}: {text}")


def partition_and_schema_test() -> None:
    spec = make_spec()
    plan = compile_execution_plan(spec)
    assert plan["decile_contract"] == DECILE_RESEARCH_CONTRACT
    assert spec.fingerprint() == StrategySpec.from_dict(spec.to_dict()).fingerprint()
    validator = Draft202012Validator(build_strategy_json_schema())
    validator.validate(json.loads(json.dumps(spec.to_dict())))
    for malformed in (None, [], "deciles"):
        raw = spec.to_dict()
        raw["portfolio"] = malformed
        expect_error(lambda: StrategySpec.from_dict(raw), TypeError, "portfolio must be an object")
    for portfolio in (
        {"selection": "deciles", "number_of_positions": 20, "weighting": "equal"},
        {"selection": "quintiles", "weighting": "equal"},
        {"selection": "deciles", "weighting": "equal", "bucket_count": 5},
        {"selection": "top_n", "weighting": "equal"},
        {"selection": "top_n", "weighting": "equal", "number_of_positions": True},
        {"selection": "top_n", "weighting": "equal", "number_of_positions": 2.5},
    ):
        raw = spec.to_dict()
        raw["portfolio"] = portfolio
        expect_error(lambda: validator.validate(json.loads(json.dumps(raw))), ValidationError, "")
        expect_error(lambda: StrategySpec.from_dict(raw), ValueError, "portfolio" if portfolio["selection"] == "top_n" else ("number_of_positions" if "number_of_positions" in portfolio else "unsupported"))

    panel = make_panel(23)
    targets, members, audits = build_decile_target_weights_from_panel(panel, spec)
    first = members[members["signal_date"] == pd.Timestamp("2024-04-30")]
    # Independent expected contiguous partition: 23 = 3+3+3+2+2+2+2+2+2+2.
    expected_sizes = [3, 3, 3, 2, 2, 2, 2, 2, 2, 2]
    assert first["Code"].tolist() == [f"{i:06d}" for i in range(1, 24)]
    assert first.groupby("decile").size().tolist() == expected_sizes
    assert not members.duplicated(["signal_date", "Code"]).any()
    for label in DECILE_LABELS:
        assert np.allclose(targets[label].sum(axis=1), 1.0)
    shuffled = panel.sample(frac=1, random_state=781)
    shuffled_targets, shuffled_members, _ = build_decile_target_weights_from_panel(shuffled, spec)
    for label in DECILE_LABELS:
        pd.testing.assert_frame_equal(targets[label], shuffled_targets[label])
    pd.testing.assert_frame_equal(members, shuffled_members)
    assert audits["maximum_bucket_size"].sub(audits["minimum_bucket_size"]).le(1).all()

    # Explicit score ties can span buckets, deterministically by Code.
    tied = panel.copy()
    tied["Marcap"] = 1.0
    _, tie_members, tie_audit = build_decile_target_weights_from_panel(tied, spec)
    assert tie_audit["ties_split_at_boundaries"].eq(9).all()
    assert tie_members[tie_members["signal_date"] == pd.Timestamp("2024-04-30")]["Code"].tolist() == first["Code"].tolist()

    # The all-factor finite intersection happens before ranks and partitioning.
    raw = spec.to_dict()
    raw["factors"] = list(raw["factors"])
    raw["factors"].append({"name": "liquidity", "source": "krx", "field": "Amount", "direction": "high"})
    mixed = StrategySpec.from_dict(raw)
    missing = panel.copy()
    missing.loc[missing["Code"] == "000001", "Amount"] = np.nan
    missing.loc[missing["Code"] == "000002", "Amount"] = np.inf
    _, clean, _ = build_decile_target_weights_from_panel(missing, mixed)
    assert set(clean["Code"]).isdisjoint({"000001", "000002"})
    assert clean.groupby("signal_date").size().eq(21).all()
    expect_error(lambda: build_decile_target_weights_from_panel(make_panel(9), spec), RuntimeError, "at least 10")
    expect_error(lambda: build_decile_target_weights_from_panel(pd.concat([panel, panel.iloc[:1]]), spec), AssertionError, "duplicate")

    # Post-signal changes may affect later signals, never earlier membership.
    future = panel.copy()
    future.loc[future["Date"] > pd.Timestamp("2024-04-30"), "Marcap"] *= -1e6
    future_targets, _, _ = build_decile_target_weights_from_panel(future, spec)
    for label in DECILE_LABELS:
        pd.testing.assert_series_equal(targets[label].loc["2024-04-30"], future_targets[label].loc["2024-04-30"])

    bad = score_cross_section(panel[panel["Date"] == pd.Timestamp("2024-04-30")], spec)
    bad.loc[bad.index[0], "composite_score"] = np.nan
    expect_error(lambda: partition_deciles(bad), ValueError, "finite")


def execution_test() -> None:
    spec = make_spec()
    panel = make_panel()
    targets, _, _ = build_decile_target_weights_from_panel(panel, spec)
    engine = load_project_engine(ROOT)
    result = execute_decile_nav(panel, spec, targets, engine, pd.DataFrame())
    daily = result["daily_nav"]
    assert len(daily.columns) == 30  # gross plus two net scenarios for each bucket
    for label in DECILE_LABELS:
        assert daily.loc["2024-05-01", f"NAV_{label}_Gross"] == 1.0
        assert np.isclose(daily.loc["2024-05-02", f"NAV_{label}_Gross"], 1.1)
        assert np.allclose(daily[f"NAV_{label}_Gross"], daily[f"NAV_{label}_Net_zero"])
        # 1% initial buy + 3% full buy/sell turnover at November execution.
        assert np.isclose(daily.loc["2024-11-01", f"NAV_{label}_Net_cost"], 1.1 * 0.99 * 0.97)
        for ex in result["decile_results"][label]["execution_scenarios"].values():
            assert (ex["execution_schedule"]["execution_date"] > ex["execution_schedule"]["signal_date"]).all()

    blocked = panel.copy()
    blocked.loc[(blocked["Date"] == pd.Timestamp("2024-05-01")) & (blocked["Code"] == "000001"), "Volume"] = 0.0
    expect_error(lambda: execute_decile_nav(blocked, spec, targets, engine, pd.DataFrame()), RuntimeError, "D01")
    broken = panel.copy()
    broken.loc[(broken["Date"] == pd.Timestamp("2024-05-02")) & (broken["Code"] == "000001"), "Close"] = np.nan
    expect_error(lambda: execute_decile_nav(broken, spec, targets, engine, pd.DataFrame()), RuntimeError, "D01")

    # A failing bucket cannot create a successful-looking partial output.
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "strategy.json"
        path.write_text(json.dumps(spec.to_dict()))
        out = Path(td) / "failure"
        valid_dates = expected_krx_sessions(spec.period.start, spec.period.end)
        broken_calendar_panel = broken[broken["Date"].isin(valid_dates)]
        # Keep the held-price failure after the actual first execution session.
        broken_calendar_panel = broken_calendar_panel.copy()
        broken_calendar_panel.loc[(broken_calendar_panel["Date"] == pd.Timestamp("2024-05-03")) & (broken_calendar_panel["Code"] == "000001"), "Close"] = np.nan
        # May 2 is the buy session in XKRX, so its source price must be valid.
        broken_calendar_panel.loc[broken_calendar_panel["Date"] == pd.Timestamp("2024-05-02"), "Close"] = 220.0
        broken_calendar_panel["ChangesRatio"] = broken_calendar_panel.groupby("Code")["Close"].pct_change(fill_method=None) * 100.0
        with patch("strategy_dsl_deciles.load_project_engine", return_value=engine), patch.object(engine, "load_krx_equity_panel", return_value=broken_calendar_panel):
            expect_error(lambda: run_strategy(path, ROOT, out, postprocess=False), RuntimeError, "D01")
        assert not out.exists()


def external_provider_and_merger_test() -> None:
    raw = make_spec().to_dict()
    raw["factors"] = [{"name": "value", "source": "dart", "field": "book_to_price", "direction": "high"}]
    raw["universe"]["filters"] = [{"field": "quarterly_roe", "op": "gt", "value": 0}]
    spec = StrategySpec.from_dict(raw)
    class Provider:
        def factor_frame(self, signal, cross_section, fields):
            assert fields == ["book_to_price", "quarterly_roe"]
            codes = cross_section["Code"].astype(int)
            return pd.DataFrame({"Code": cross_section["Code"], "book_to_price": 1.0 / codes, "quarterly_roe": np.where(codes <= 3, -1.0, 1.0)})
    with patch("strategy_dsl_runner.build_external_provider", return_value=Provider()) as factory:
        _, members, _ = build_decile_target_weights_from_panel(make_panel(), spec, ROOT)
        factory.assert_called_once_with("dart", ROOT, "legacy_april_october")
    first = members[members["signal_date"] == pd.Timestamp("2024-04-30")]
    assert first["Code"].tolist() == [f"{i:06d}" for i in range(4, 21)]

    # Verified successor need not be selected by the predecessor's bucket.
    raw = make_spec().to_dict()
    raw["rebalance"]["months"] = [4]
    raw["period"].update(end="2024-05-10", book_end="2024-05-10", as_of_date="2024-05-10")
    spec = StrategySpec.from_dict(raw)
    panel = make_panel()
    panel = panel[panel["Date"] <= pd.Timestamp("2024-05-10")].copy()
    panel["Close"] = 100.0
    successor = panel["Code"] == "000020"
    panel.loc[successor, "Close"] = 50.0
    panel.loc[successor & (panel["Date"] >= pd.Timestamp("2024-05-08")), "Close"] = 60.0
    panel.loc[successor & (panel["Date"] >= pd.Timestamp("2024-05-09")), "Close"] = 66.0
    panel.loc[(panel["Code"] == "000001") & (panel["Date"] > pd.Timestamp("2024-05-03")), "Close"] = np.nan
    events = pd.DataFrame([{"event_date": pd.Timestamp("2024-05-08"), "event_type": "stock_merger", "predecessor_code": "000001", "successor_code": "000020", "share_ratio": 2.0, "cash_per_share": 0.0, "source": "synthetic verified-event regression"}])
    targets, _, _ = build_decile_target_weights_from_panel(panel, spec)
    result = execute_decile_nav(panel, spec, targets, load_project_engine(ROOT), events)
    assert np.isclose(result["daily_nav"].loc["2024-05-08", "NAV_D01_Gross"], 1.1)
    assert np.isclose(result["daily_nav"].loc["2024-05-09", "NAV_D01_Gross"], 1.16)
    transferred = result["decile_results"]["D01"]["execution_scenarios"]["zero"]["corporate_actions"]
    assert len(transferred) == 1 and float(transferred.iloc[0]["transferred_weight"]) > 0


def main() -> None:
    partition_and_schema_test()
    execution_test()
    external_provider_and_merger_test()
    print("STRATEGY DSL DECILE CONTRACT AND EXECUTION: PASS")


if __name__ == "__main__":
    main()
