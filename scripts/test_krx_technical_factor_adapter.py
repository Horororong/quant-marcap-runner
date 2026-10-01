from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from krx_technical_factor_adapter import KrxTechnicalFactorAdapter
from strategy_dsl import StrategySpec
from strategy_dsl_runner import build_target_weights_from_panel, required_panel_columns


def write_yearly_history(root: Path) -> tuple[pd.DatetimeIndex, pd.Timestamp]:
    dates = pd.bdate_range("2023-01-02", "2025-03-31")
    signal = pd.Timestamp("2025-02-28")
    assert signal in dates
    rows = []
    for dt in dates:
        future = dt > signal
        rows.append({
            "Date": dt,
            "Code": "000001",
            "ChangesRatio": 50.0 if future else 1.0,
        })
        rows.append({
            "Date": dt,
            "Code": "000002",
            "ChangesRatio": 0.5,
        })

    x = pd.DataFrame(rows)
    past_dates = dates[dates <= signal]
    # Missing observation inside the 12-1 window but outside the 6-1 window.
    missing_date = past_dates[-200]
    x.loc[(x["Date"] == missing_date) & (x["Code"] == "000002"), "ChangesRatio"] = np.nan

    out = root / "data/krx_equities/yearly"
    out.mkdir(parents=True, exist_ok=True)
    for year, chunk in x.groupby(x["Date"].dt.year):
        chunk.to_parquet(out / f"marcap-{int(year)}.parquet", index=False)
    return dates, signal


def synthetic_panel(signal: pd.Timestamp) -> pd.DataFrame:
    dates = pd.bdate_range(signal.to_period("M").start_time.normalize(), signal)
    rows = []
    for dt in dates:
        for code, marcap in (("000001", 100.0), ("000002", 200.0)):
            rows.append({
                "Date": dt,
                "Code": code,
                "Name": code,
                "Market": "KOSPI",
                "Close": 100.0,
                "Volume": 1000.0,
                "Amount": 1_000_000.0,
                "Marcap": marcap,
            })
    return pd.DataFrame(rows)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, signal = write_yearly_history(root)
        adapter = KrxTechnicalFactorAdapter(root)
        cs = synthetic_panel(signal)
        cross_section = cs[cs["Date"] == signal].copy()

        fields = ["momentum_3_1", "momentum_6_1", "momentum_12_1", "momentum_12_0"]
        out = adapter.factor_frame(signal, cross_section, fields).set_index("Code")

        assert abs(float(out.loc["000001", "momentum_3_1"]) - ((1.01 ** 42) - 1.0)) < 1e-12
        assert abs(float(out.loc["000001", "momentum_6_1"]) - ((1.01 ** 105) - 1.0)) < 1e-12
        assert abs(float(out.loc["000001", "momentum_12_1"]) - ((1.01 ** 231) - 1.0)) < 1e-12
        assert abs(float(out.loc["000001", "momentum_12_0"]) - ((1.01 ** 252) - 1.0)) < 1e-12
        # The 50% future returns written after the signal must not affect any value.
        assert float(out.loc["000001", "momentum_12_0"]) < 20.0

        assert pd.isna(out.loc["000002", "momentum_12_1"])
        assert pd.notna(out.loc["000002", "momentum_6_1"])

        coverage = adapter.coverage_report(signal, fields)
        assert len(coverage) == 4
        assert all(x["ratio"] == 1.0 and x["raw_ok"] for x in coverage)

        strategy = StrategySpec.from_dict({
            "schema_version": "1.0",
            "strategy_id": "technical_momentum_smoke",
            "title": "technical momentum smoke",
            "asset_class": "kr_equity",
            "universe": {
                "markets": ["KOSPI"],
                "filters": [{"field": "Marcap", "op": "gt", "value": 0}],
                "require_tradable_on_signal": False,
            },
            "factors": [
                {
                    "name": "mom12_1",
                    "source": "technical",
                    "field": "momentum_12_1",
                    "direction": "high",
                    "weight": 1.0,
                }
            ],
            "portfolio": {"number_of_positions": 1, "weighting": "equal"},
            "rebalance": {
                "frequency": "months",
                "months": [2],
                "trading_day": "last",
            },
            "execution": {"lag_sessions": 1, "price": "next_close"},
            "cost_scenarios": {"gross": {}},
            "period": {
                "start": "2025-02-01",
                "end": "2025-02-28",
                "book_start": "2025-02-01",
                "book_end": "2025-02-28",
                "as_of_date": "2025-02-28",
            },
        })
        assert "momentum_12_1" not in required_panel_columns(strategy)
        weights, selections = build_target_weights_from_panel(cs, strategy, repo_root=root)
        assert len(weights) == 1
        assert selections.iloc[0]["Code"] == "000001", selections
        assert float(weights.iloc[0]["000001"]) == 1.0

    print("KRX TECHNICAL FACTOR ADAPTER TEST: PASS")


if __name__ == "__main__":
    main()
