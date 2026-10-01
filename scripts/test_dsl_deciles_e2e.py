from __future__ import annotations

from pathlib import Path
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from strategy_dsl import load_strategy_spec
from strategy_dsl_deciles import DECILE_LABELS
from strategy_dsl_preflight import preflight_strategy
from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "config/strategies/kr_equity_size_deciles_research.json"


def main() -> None:
    spec = load_strategy_spec(SPEC)
    preflight = preflight_strategy(SPEC, ROOT)
    assert preflight["status"] == "ok", preflight
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "research"
        # Capture the canonical handoff: this short execution regression must
        # not invent 2001-present performance from 24 real daily observations.
        with patch("strategy_dsl_deciles.run_current_postprocess") as postprocess:
            result = run_strategy(SPEC, ROOT, out, postprocess=True)
            postprocess.assert_called_once()
            assert postprocess.call_args.args[0] == spec
            assert postprocess.call_args.args[2] == out
        daily = pd.read_csv(out / "daily_nav.csv", parse_dates=["Date"]).set_index("Date")
        members = pd.read_csv(out / "decile_membership.csv", parse_dates=["signal_date"], dtype={"Code": str})
        schedule = pd.read_csv(out / "execution_schedule.csv", parse_dates=["signal_date", "execution_date"])
        audit = pd.read_csv(out / "decile_partition_audit.csv")
        contract = json.loads((out / "decile_contract.json").read_text())
        references = json.loads((out / "return_reference_audit.json").read_text())
        assert set(references) == set(DECILE_LABELS)
        assert all(s["enabled"] and s["tolerance_bps"] == 1.0 for b in references.values() for s in b.values())
        assert contract["bucket_count"] == 10
        assert "independently" in contract["capital"]
        assert len(daily.columns) == 31
        history = json.loads((out / "history_coverage.json").read_text())
        assert history["status"] == "complete" and history["expected_sessions"] == 24
        assert np.isfinite(daily.to_numpy()).all() and (daily > 0).all().all()
        assert set(members["decile"]) == set(DECILE_LABELS)
        assert not members.duplicated(["signal_date", "Code"]).any()
        assert (schedule["execution_date"] > schedule["signal_date"]).all()
        assert schedule["decile"].nunique() == 10
        assert audit["maximum_bucket_size"].sub(audit["minimum_bucket_size"]).le(1).all()

        # Independent raw-data oracle: signal-day capitalization order and
        # equal initial shares valued from the actual next session's close.
        raw = pd.read_parquet(ROOT / "data/krx_equities/yearly/marcap-2020.parquet")
        raw["Code"] = raw["Code"].astype(str).str.zfill(6)
        signal = pd.Timestamp("2020-04-29")
        signal_rows = raw[(raw["Date"] == signal) & raw["Market"].isin(["KOSPI", "KOSDAQ"]) & (raw["Marcap"] >= 10_000_000_000_000) & (raw["Volume"] > 0) & (raw["Close"] > 0)]
        codes = signal_rows.sort_values(["Marcap", "Code"])["Code"].tolist()
        assert members["Code"].tolist() == codes
        quotient, remainder = divmod(len(codes), 10)
        sizes = [quotient + (i < remainder) for i in range(10)]
        assert members.groupby("decile").size().tolist() == sizes
        execution_date = daily.index[daily.index > signal][0]
        assert schedule["execution_date"].eq(execution_date).all()
        close = raw.pivot(index="Date", columns="Code", values="Close")
        cursor = 0
        for label, size in zip(DECILE_LABELS, sizes):
            bucket = codes[cursor:cursor + size]
            cursor += size
            expected = pd.Series(1.0, index=daily.index)
            after = daily.index[daily.index >= execution_date]
            expected.loc[after] = close.loc[after, bucket].div(close.loc[execution_date, bucket]).mean(axis=1)
            assert np.allclose(daily[f"NAV_{label}_Gross"], expected, rtol=0, atol=1e-12)
            assert np.allclose(daily[f"NAV_{label}_Net_zero"], expected, rtol=0, atol=1e-12)
            # Buy only: (1.5 commission + 3 spread + 5 slippage) / 10000.
            expected_net = expected.copy()
            expected_net.loc[after] *= 1.0 - 9.5 / 10_000.0
            assert np.allclose(daily[f"NAV_{label}_Net_fixed_cost"], expected_net, rtol=0, atol=1e-12)
            bucket_targets = pd.read_csv(out / label / "target_weights.csv")
            assert np.allclose(bucket_targets.drop(columns="signal_date").sum(axis=1), 1.0)
            assert (out / label / "daily_nav.csv").exists()
        index_close = pd.read_csv(ROOT / "data/indices/KOSPI.csv", parse_dates=["Date"]).set_index("Date")["Close"].reindex(daily.index)
        assert np.allclose(daily["NAV_Benchmark"], index_close / index_close.iloc[0], atol=1e-12, rtol=0)
        assert result["benchmark"]["observations"] == len(daily)
        assert not (out / "metrics_CURRENT.csv").exists()
        assert set(pd.read_csv(out / "target_weights.csv")["decile"]) == set(DECILE_LABELS)
    print("STRATEGY DSL REAL KRX DECILE E2E: PASS")


if __name__ == "__main__":
    main()
