from __future__ import annotations

from pathlib import Path
import json
import tempfile

import numpy as np
import pandas as pd

from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "config/strategies/super_value_dart_dsl.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        out = td / "super_value_e2e"
        raw = json.loads(SPEC.read_text(encoding="utf-8"))
        raw["strategy_id"] = "super_value_dart_dsl_benchmark_e2e"
        raw["benchmark"] = {"source": "index", "symbol": "KOSPI"}
        spec_path = td / "strategy.json"
        spec_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        result = run_strategy(spec_path, ROOT, out, postprocess=False)

        daily = pd.read_csv(out / "daily_nav.csv", parse_dates=["Date"])
        weights = pd.read_csv(out / "target_weights.csv", parse_dates=["signal_date"])
        selections = pd.read_csv(out / "selections.csv", dtype={"Code": str})
        coverage = pd.read_csv(out / "factor_provider_coverage.csv", parse_dates=["signal_date"])
        corporate_actions = pd.read_csv(out / "corporate_actions_applied.csv", parse_dates=["Date", "last_trade_date"])

        assert len(daily) > 100
        nav_cols = [c for c in daily.columns if c.startswith("NAV_")]
        assert nav_cols == ["NAV_Gross", "NAV_Net_gross", "NAV_Benchmark"], nav_cols
        assert np.isfinite(daily[nav_cols].to_numpy(float)).all()
        assert (daily[nav_cols] > 0).all().all()
        assert np.allclose(
            daily["NAV_Gross"].to_numpy(float),
            daily["NAV_Net_gross"].to_numpy(float),
            rtol=0,
            atol=1e-12,
        )
        assert abs(float(daily["NAV_Benchmark"].iloc[0]) - 1.0) < 1e-12
        assert result["benchmark"]["symbol"] == "KOSPI"
        assert result["benchmark"]["observations"] == len(daily)
        assert result["benchmark"]["exact_date_alignment"] is True

        assert len(weights) == 2
        asset_cols = [c for c in weights.columns if c != "signal_date"]
        assert np.allclose(weights[asset_cols].sum(axis=1).to_numpy(float), 1.0)
        assert selections.groupby("signal_date")["Code"].nunique().eq(20).all()
        assert coverage["ratio"].eq(1.0).all()
        assert coverage["raw_ok"].astype(bool).all()
        assert len(corporate_actions) >= 1
        kp = corporate_actions[
            (corporate_actions["predecessor_code"].astype(str).str.zfill(6) == "002300")
            & (corporate_actions["successor_code"].astype(str).str.zfill(6) == "034810")
        ]
        assert len(kp) == 1, corporate_actions
        assert abs(float(kp.iloc[0]["share_ratio"]) - 1.6661460) < 1e-12
        assert float(kp.iloc[0]["transferred_weight"]) > 0

        execution = result["engine_result"]["execution_scenarios"]["gross"]
        sched = execution["execution_schedule"]
        assert len(sched) == 2
        assert (
            pd.to_datetime(sched["execution_date"])
            > pd.to_datetime(sched["signal_date"])
        ).all()
        assert execution["annualized_one_way_turnover"] >= 0

        for name in (
            "daily_nav.csv",
            "target_weights.csv",
            "selections.csv",
            "factor_provider_coverage.csv",
            "corporate_actions_applied.csv",
            "execution_plan.json",
            "strategy_fingerprint.txt",
        ):
            assert (out / name).exists(), name

    print("STRATEGY DSL EXECUTION E2E: PASS")


if __name__ == "__main__":
    main()
