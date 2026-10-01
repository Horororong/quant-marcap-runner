from pathlib import Path
from unittest.mock import patch
import json
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from strategy_dsl import load_strategy_spec
from strategy_dsl_run import run_checked_strategy
from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "config/strategies"


def same_component_outputs(direct, checked):
    for path in direct.rglob("*"):
        if path.is_file():
            relative = path.relative_to(direct)
            assert path.read_bytes() == (checked / "artifacts" / relative).read_bytes(), relative
    assert not (checked / "_execution").exists() and not (checked / "report").exists()
    result = json.loads((checked / "run_status.json").read_text())
    assert result["status"] == "ok" and result["nav_ready"] and not result["report_ready"], result
    assert result["versions"]["preflight_contract_version"] == "3"
    assert result["strategy_fingerprint"] == load_strategy_spec(checked / "strategy_normalized.json").fingerprint()
    return result


def cli(tmp):
    for name in ("kr_equity_split_research.json", "kr_equity_size_deciles_research.json"):
        direct = tmp / (name + "_direct")
        checked = tmp / (name + "_checked")
        run_strategy(EXAMPLES / name, ROOT, direct, postprocess=False)
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/strategy_dsl_runner.py"), str(EXAMPLES / name),
                               "--execution-only", "--output-dir", str(checked)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)  # CURRENT/logs cannot contaminate machine-readable stdout.
        assert summary["status"] == "ok" and summary["nav_ready"] and not summary["report_ready"]
        result = same_component_outputs(direct, checked)
        assert result["run_id"] == summary["run_id"]
        saved = (checked / "run_status.json").read_bytes()
        retry = subprocess.run([sys.executable, str(ROOT / "scripts/strategy_dsl_runner.py"), str(EXAMPLES / name),
                                "--execution-only", "--output-dir", str(checked)], capture_output=True, text=True)
        assert retry.returncode == 4 and json.loads(retry.stdout)["phase"] == "output"
        assert (checked / "run_status.json").read_bytes() == saved


def real_gaps(tmp):
    raw = json.loads((EXAMPLES / "kr_equity_split_research.json").read_text())
    raw["strategy_id"] = "checked_known_event_gap"
    raw["universe"]["filters"] = [{"field": "Close", "op": "gte", "value": 12000},
                                    {"field": "Close", "op": "lte", "value": 14000}]
    raw["factors"] = [{"name": "size", "source": "krx", "field": "Marcap", "direction": "high"}]
    raw["rebalance"]["months"] = [9]
    raw["period"] = {"start": "2024-09-02", "end": "2024-10-24", "book_start": "2024-09-02",
                     "book_end": "2024-10-24", "as_of_date": "2024-10-24"}
    raw["cost_scenarios"] = {"zero": {}}
    source = tmp / "gaps.json"
    for mode in ("top_n", "deciles"):
        raw["portfolio"] = {"selection": mode, "weighting": "equal"}
        if mode == "top_n":
            raw["portfolio"]["number_of_positions"] = 3
        source.write_text(json.dumps(raw))
        with patch("strategy_dsl_run.run_strategy") as execution:
            result = run_checked_strategy(source, ROOT, tmp / (mode + "_blocked"), postprocess=False)
            execution.assert_not_called()
        assert result["status"] == "data_gap" and result["gap_phase"] == "corporate_actions", result
        assert not result["nav_ready"] and not (Path(result["output_dir"]) / "artifacts").exists()
        preflight = json.loads((Path(result["output_dir"]) / "preflight.json").read_text())
        assert preflight["corporate_action_audit"]["exposures"][0]["Code"] == "287410"
    raw["period"] = {"start": "1990-04-01", "end": "1990-04-30", "book_start": "1990-04-01",
                     "book_end": "1990-04-30", "as_of_date": "1990-04-30"}
    raw["portfolio"] = {"number_of_positions": 1, "weighting": "equal"}
    source.write_text(json.dumps(raw))
    with patch("strategy_dsl_run.run_strategy") as execution:
        result = run_checked_strategy(source, ROOT, tmp / "missing_year", postprocess=False)
        execution.assert_not_called()
    assert result["status"] == "data_gap" and result["gap_phase"] == "data", result


def real_dart(tmp):
    source = EXAMPLES / "super_value_dart_benchmark_dsl.json"
    result = run_checked_strategy(source, ROOT, tmp / "dart", postprocess=False)
    assert result["status"] == "ok" and result["nav_ready"] and not result["report_ready"], result
    out = Path(result["output_dir"])
    daily = pd.read_csv(out / "artifacts/daily_nav.csv", parse_dates=["Date"]).set_index("Date")
    selections = pd.read_csv(out / "artifacts/selections.csv", dtype={"Code": str})
    assert len(daily) == 165 and np.isfinite(daily.to_numpy()).all() and (daily > 0).all().all()
    assert selections.groupby("signal_date")["Code"].nunique().eq(20).all()
    close = pd.read_csv(ROOT / "data/indices/KOSPI.csv", parse_dates=["Date"]).set_index("Date")["Close"].reindex(daily.index)
    assert np.allclose(daily["NAV_Benchmark"], close / close.iloc[0], rtol=0, atol=1e-12)
    coverage = pd.read_csv(out / "artifacts/factor_provider_coverage.csv")
    assert coverage["ratio"].eq(1.0).all() and coverage["raw_ok"].astype(bool).all()
    references = json.loads((out / "artifacts/return_reference_audit.json").read_text())
    assert references["gross"]["enabled"] is True and references["gross"]["checked_observations"] > 0
    assert not (out / "report").exists() and not (out / "_execution").exists()
    assert result == json.loads((out / "run_status.json").read_text())


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cli(tmp)
        real_gaps(tmp)
        real_dart(tmp)
    print("CHECKED DSL REAL E2E: PASS (CLI top_n/deciles unchanged, no overwrite, known-event/data gaps before NAV, DART/benchmark/audits)")


if __name__ == "__main__":
    main()
