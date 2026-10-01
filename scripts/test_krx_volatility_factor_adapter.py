from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from krx_technical_factor_adapter import KrxTechnicalFactorAdapter
from strategy_dsl import StrategySpec
from strategy_dsl_runner import build_target_weights_from_panel, required_panel_columns


def write_history(root: Path) -> tuple[pd.DataFrame, pd.Timestamp]:
    dates = pd.bdate_range("2023-01-02", "2025-03-31")
    signal = pd.Timestamp("2025-02-28")
    rows = []
    for i, dt in enumerate(dates):
        future = dt > signal
        rows.extend([
            {"Date": dt, "Code": "000001", "ChangesRatio": 50.0 if future else 1.0},
            {"Date": dt, "Code": "000002", "ChangesRatio": 50.0 if future else (2.0 if i % 2 == 0 else -2.0)},
            {"Date": dt, "Code": "000003", "ChangesRatio": 50.0 if future else (0.25 if i % 2 == 0 else -0.25)},
        ])
    x = pd.DataFrame(rows)
    past_dates = dates[dates <= signal]
    # Missing inside the 12m window but outside the 3m window.
    missing_date = past_dates[-180]
    x.loc[(x["Date"] == missing_date) & (x["Code"] == "000003"), "ChangesRatio"] = np.nan

    out = root / "data/krx_equities/yearly"
    out.mkdir(parents=True, exist_ok=True)
    for year, chunk in x.groupby(x["Date"].dt.year):
        chunk.to_parquet(out / f"marcap-{int(year)}.parquet", index=False)
    return x, signal


def signal_panel(signal: pd.Timestamp) -> pd.DataFrame:
    dates = pd.bdate_range(signal.to_period("M").start_time.normalize(), signal)
    rows = []
    for dt in dates:
        for code, marcap in (("000001", 100.0), ("000002", 200.0), ("000003", 300.0)):
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


def expected_volatility(history: pd.DataFrame, signal: pd.Timestamp, code: str, sessions: int) -> float:
    x = history[
        (history["Code"] == code)
        & (history["Date"] <= signal)
    ].sort_values("Date").tail(sessions)
    assert len(x) == sessions
    daily = pd.to_numeric(x["ChangesRatio"], errors="coerce") / 100.0
    return float(daily.std(ddof=1) * np.sqrt(252.0))


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        history, signal = write_history(root)
        panel = signal_panel(signal)
        cs = panel[panel["Date"] == signal].copy()
        adapter = KrxTechnicalFactorAdapter(root)

        fields = ["volatility_3m", "volatility_6m", "volatility_12m"]
        out = adapter.factor_frame(signal, cs, fields).set_index("Code")

        # Constant 1% daily return has zero realized volatility. Future 50%
        # observations must not leak into the signal-date calculation.
        assert abs(float(out.loc["000001", "volatility_3m"])) < 1e-15
        assert abs(float(out.loc["000001", "volatility_12m"])) < 1e-15

        for field, sessions in (("volatility_3m", 63), ("volatility_6m", 126), ("volatility_12m", 252)):
            expected = expected_volatility(history, signal, "000002", sessions)
            assert abs(float(out.loc["000002", field]) - expected) < 1e-12

        assert pd.notna(out.loc["000003", "volatility_3m"])
        assert pd.isna(out.loc["000003", "volatility_12m"])

        coverage = adapter.coverage_report(signal, fields)
        assert len(coverage) == 3
        assert all(x["ratio"] == 1.0 and x["raw_ok"] for x in coverage)

        strategy = StrategySpec.from_dict({
            "schema_version": "1.0",
            "strategy_id": "low_volatility_smoke",
            "title": "low volatility smoke",
            "asset_class": "kr_equity",
            "universe": {
                "markets": ["KOSPI"],
                "require_tradable_on_signal": False,
                "filters": [{"field": "Marcap", "op": "gt", "value": 0}],
            },
            "factors": [
                {
                    "name": "LOWVOL",
                    "source": "technical",
                    "field": "volatility_3m",
                    "direction": "low",
                    "weight": 1.0,
                }
            ],
            "portfolio": {"number_of_positions": 1, "weighting": "equal"},
            "rebalance": {"frequency": "months", "months": [2], "trading_day": "last"},
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
        assert "volatility_3m" not in required_panel_columns(strategy)
        weights, selections = build_target_weights_from_panel(panel, strategy, repo_root=root)
        assert len(weights) == 1
        assert selections.iloc[0]["Code"] == "000001", selections
        assert float(weights.iloc[0]["000001"]) == 1.0

    print("KRX VOLATILITY FACTOR ADAPTER TEST: PASS")


if __name__ == "__main__":
    main()
