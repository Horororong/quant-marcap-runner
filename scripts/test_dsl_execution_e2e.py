from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "config/strategies/super_value_dart_dsl.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "super_value_e2e"
        result = run_strategy(SPEC, ROOT, out, postprocess=False)

        daily = pd.read_csv(out / "daily_nav.csv", parse_dates=["Date"])
        weights = pd.read_csv(out / "target_weights.csv", parse_dates=["signal_date"])
        selections = pd.read_csv(out / "selections.csv", dtype={"Code": str})
        coverage = pd.read_csv(out / "factor_provider_coverage.csv", parse_dates=["signal_date"])

        assert len(daily) > 100
        nav_cols = [c for c in daily.columns if c.startswith("NAV_")]
        assert nav_cols == ["NAV_Gross", "NAV_Net_gross"], nav_cols
        assert np.isfinite(daily[nav_cols].to_numpy(float)).all()
        assert (daily[nav_cols] > 0).all().all()
        assert np.allclose(
            daily["NAV_Gross"].to_numpy(float),
            daily["NAV_Net_gross"].to_numpy(float),
            rtol=0,
            atol=1e-12,
        )

        assert len(weights) == 2
        asset_cols = [c for c in weights.columns if c != "signal_date"]
        assert np.allclose(weights[asset_cols].sum(axis=1).to_numpy(float), 1.0)
        assert selections.groupby("signal_date")["Code"].nunique().eq(20).all()
        assert coverage["ratio"].eq(1.0).all()
        assert coverage["raw_ok"].astype(bool).all()

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
            "execution_plan.json",
            "strategy_fingerprint.txt",
        ):
            assert (out / name).exists(), name

    print("STRATEGY DSL EXECUTION E2E: PASS")


if __name__ == "__main__":
    main()
