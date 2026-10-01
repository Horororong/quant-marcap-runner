from __future__ import annotations

from pathlib import Path
import json
import tempfile

import numpy as np
import pandas as pd

from strategy_dsl import StrategySpec, compile_execution_plan
from strategy_dsl_runner import build_target_weights_from_panel, load_project_engine, engine_inputs

ROOT = Path(__file__).resolve().parents[1]


def make_spec() -> StrategySpec:
    raw = {
        "schema_version": "1.0",
        "strategy_id": "dsl_smoke_rank",
        "title": "DSL smoke rank",
        "asset_class": "kr_equity",
        "universe": {
            "markets": ["KOSPI", "KOSDAQ"],
            "filters": [{"field": "Amount", "op": "gt", "value": 0}],
        },
        "factors": [
            {"name": "small", "source": "krx", "field": "Marcap", "direction": "low", "weight": 1.0},
            {"name": "liquid", "source": "krx", "field": "Amount", "direction": "high", "weight": 0.25, "transform": "log1p"},
        ],
        "portfolio": {"number_of_positions": 2, "weighting": "equal"},
        "rebalance": {"frequency": "months", "months": [4, 10], "trading_day": "last"},
        "execution": {"lag_sessions": 1, "price": "next_close"},
        "cost_scenarios": {"base": {"commission_bps": 1, "sell_tax_bps": 0, "spread_bps": 0, "slippage_bps": 0}},
        "period": {"start": "2024-04-01", "end": "2024-11-15", "book_start": "2024-04-01", "book_end": "2024-11-15", "as_of_date": "2024-11-15"},
        "initial_capital": 10000000,
    }
    return StrategySpec.from_dict(raw)


def make_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-04-01", "2024-11-15")
    codes = ["000001", "000002", "000003", "000004"]
    rows = []
    for i, dt in enumerate(dates):
        for j, code in enumerate(codes):
            rows.append({
                "Date": dt, "Code": code, "Name": f"S{j+1}",
                "Market": "KOSPI" if j < 2 else "KOSDAQ",
                "Close": 100.0 * (1.0 + 0.0005 * (j + 1)) ** i,
                "Volume": 1000 + 100 * j,
                "Amount": float((j + 1) * 1_000_000),
                "Marcap": float((j + 1) * 10_000_000_000),
            })
    return pd.DataFrame(rows)


def main() -> None:
    spec = make_spec()
    assert spec.fingerprint() == StrategySpec.from_dict(spec.to_dict()).fingerprint()
    plan = compile_execution_plan(spec)
    assert plan["project_engine"].endswith("v2-16_CURRENT.py")
    assert plan["strategy_fingerprint"] == spec.fingerprint()
    assert plan["factor_registry_version"] == "2"
    assert plan["execution_engine_version"] == "v2-16-exec-1"
    assert plan["corporate_action_registry_version"] == "1"
    assert plan["dsl_machine_contract_version"] == "3"
    assert plan["preflight_contract_version"] == "1"
    assert plan["project_template_version"] == "v2-16"
    assert [x["source"] for x in plan["factor_contracts"]] == ["krx", "krx"]
    assert [x["storage"] for x in plan["factor_contracts"]] == ["panel", "panel"]

    panel = make_panel()
    tw, selections = build_target_weights_from_panel(panel, spec)
    assert len(tw) == 2
    assert np.allclose(tw.sum(axis=1).to_numpy(), 1.0)
    assert set(selections["signal_date"].dt.month) == {4, 10}

    engine = load_project_engine(ROOT)
    cfg, costs, execution = engine_inputs(spec, engine)
    close = panel.pivot(index="Date", columns="Code", values="Close").reindex(columns=tw.columns)
    out = engine.simulate_target_weight_portfolio(
        close_prices=close,
        target_weights=tw,
        cost_assumptions=costs["base"],
        execution_assumptions=execution,
        initial_capital=cfg.initial_capital,
    )
    sched = out["execution_schedule"]
    assert len(sched) == 2
    for _, row in sched.iterrows():
        assert pd.Timestamp(row["execution_date"]) > pd.Timestamp(row["signal_date"])
    assert (out["daily_nav"] > 0).all().all()
    assert abs(float(out["weights"].iloc[-1].drop("Cash").sum()) - 1.0) < 1e-12

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "plan.json"
        p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        assert json.loads(p.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    print("STRATEGY DSL TEST: PASS")


if __name__ == "__main__":
    main()
