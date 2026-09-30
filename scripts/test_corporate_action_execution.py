from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("corp_action_test_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    engine = load_engine()
    idx = pd.bdate_range("2026-01-05", periods=5)
    px = pd.DataFrame({
        "000001": [100.0, 100.0, np.nan, np.nan, np.nan],
        "000002": [50.0, 55.0, 58.0, 60.0, 66.0],
    }, index=idx)
    target = pd.DataFrame({
        "000001": [1.0],
        "000002": [0.0],
    }, index=[idx[0]])
    events = pd.DataFrame([{
        "event_date": idx[3],
        "event_type": "stock_merger",
        "predecessor_code": "000001",
        "successor_code": "000002",
        "share_ratio": 2.0,
        "cash_per_share": 0.0,
        "source": "synthetic-test",
    }])

    out = engine.simulate_target_weight_portfolio(
        close_prices=px,
        target_weights=target,
        cost_assumptions=engine.TradingCostAssumptions(),
        execution_assumptions=engine.ExecutionAssumptions(execution_lag_sessions=1),
        initial_capital=1.0,
        corporate_action_events=events,
    )

    nav = out["daily_nav"]["Gross"]
    # signal day cash -> next close buys predecessor at 100
    assert abs(float(nav.loc[idx[1]]) - 1.0) < 1e-12
    # verified merger suspension is explicitly held flat, not generic NaN filling
    assert abs(float(nav.loc[idx[2]]) - 1.0) < 1e-12
    # event value = 2 successor shares * 60 / predecessor 100 = +20%
    assert abs(float(nav.loc[idx[3]]) - 1.2) < 1e-12
    # after transfer the portfolio receives successor 60 -> 66 = +10%
    assert abs(float(nav.loc[idx[4]]) - 1.32) < 1e-12

    weights = out["weights"]
    assert abs(float(weights.loc[idx[3], "000001"])) < 1e-12
    assert abs(float(weights.loc[idx[3], "000002"]) - 1.0) < 1e-12

    trades = out["trades"]
    assert abs(float(trades.loc[idx[3], "buy_turnover"])) < 1e-12
    assert abs(float(trades.loc[idx[3], "sell_turnover"])) < 1e-12

    ca = out["corporate_actions"]
    assert len(ca) == 1
    assert ca.iloc[0]["predecessor_code"] == "000001"
    assert ca.iloc[0]["successor_code"] == "000002"
    assert abs(float(ca.iloc[0]["event_return"]) - 0.2) < 1e-12
    assert abs(float(ca.iloc[0]["transferred_weight"]) - 1.0) < 1e-12

    print("CORPORATE ACTION EXECUTION TEST: PASS")


if __name__ == "__main__":
    main()
