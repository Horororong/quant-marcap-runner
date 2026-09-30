from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import pandas as pd

from strategy_dsl import load_strategy_spec
from strategy_dsl_runner import build_target_weights_from_panel, load_project_engine

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config/strategies/super_value_dart_dsl.json"
LEGACY_PATH = ROOT / "scripts/backtest_super_value_v216.py"


def load_legacy():
    spec = importlib.util.spec_from_file_location("legacy_super_value_v216_for_regression", LEGACY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(LEGACY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    strategy = load_strategy_spec(SPEC_PATH)
    engine = load_project_engine(ROOT)
    panel = engine.load_krx_equity_panel(
        start=strategy.period.start,
        end=strategy.period.end,
        markets=strategy.universe.markets,
        columns=["Date", "Code", "Name", "Market", "Close", "Volume", "Amount", "Marcap"],
        repo_root=ROOT,
    )
    tw, dsl_sel = build_target_weights_from_panel(panel, strategy, repo_root=ROOT)
    assert len(tw) == 2, tw.index
    dsl_sel["signal_date"] = pd.to_datetime(dsl_sel["signal_date"]).dt.normalize()

    legacy = load_legacy()
    legacy_panel = legacy.load_krx(strategy.period.start, strategy.period.end)
    cache = {}
    for signal in tw.index:
        for key in legacy.required_periods(pd.Timestamp(signal)):
            if key not in cache:
                cache[key] = legacy.report_snapshots(legacy.load_financial_raw(*key))

    for signal in tw.index:
        signal = pd.Timestamp(signal).normalize()
        factors = legacy.build_factor_table(signal, cache)
        legacy_selected, _ = legacy.build_selection(legacy_panel, signal, factors, 20)
        old_codes = legacy_selected["Code"].astype(str).str.zfill(6).tolist()

        new = dsl_sel[dsl_sel["signal_date"] == signal].sort_values("composite_score")
        new_codes = new["Code"].astype(str).str.zfill(6).tolist()

        if old_codes != new_codes:
            pairs = pd.DataFrame({
                "legacy": pd.Series(old_codes),
                "dsl": pd.Series(new_codes),
            })
            raise AssertionError(f"{signal.date()} selection mismatch\n{pairs.to_string(index=False)}")

        weights = tw.loc[signal]
        chosen = set(weights[weights > 0].index)
        assert chosen == set(old_codes)
        assert abs(float(weights.sum()) - 1.0) < 1e-12

    print("DART DSL SUPER VALUE REGRESSION: PASS")
    print("signals:", [x.date().isoformat() for x in tw.index])


if __name__ == "__main__":
    main()
