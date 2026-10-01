from __future__ import annotations

from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from strategy_dsl import BenchmarkSpec, StrategySpec, compile_execution_plan
from strategy_dsl_runner import benchmark_coverage_audit, load_benchmark_nav


def make_spec() -> StrategySpec:
    return StrategySpec.from_dict({
        "schema_version": "1.0",
        "strategy_id": "benchmark_contract_smoke",
        "title": "benchmark contract smoke",
        "asset_class": "kr_equity",
        "universe": {"markets": ["KOSPI"], "filters": []},
        "factors": [
            {"name": "size", "source": "krx", "field": "Marcap", "direction": "low"}
        ],
        "portfolio": {"number_of_positions": 10, "weighting": "equal"},
        "rebalance": {"frequency": "months", "months": [4], "trading_day": "last"},
        "execution": {"lag_sessions": 1, "price": "next_close"},
        "cost_scenarios": {"gross": {}},
        "period": {
            "start": "2024-04-01",
            "end": "2024-04-30",
            "book_start": "2024-04-01",
            "book_end": "2024-04-30",
            "as_of_date": "2024-04-30",
        },
        "benchmark": {"source": "index", "symbol": "KOSPI"},
    })


def main() -> None:
    spec = make_spec()
    assert spec.benchmark == BenchmarkSpec(source="index", symbol="KOSPI")
    plan = compile_execution_plan(spec)
    assert plan["benchmark"] == {"source": "index", "symbol": "KOSPI"}

    for bad in (
        {"source": "index", "symbol": "NOT_AN_INDEX"},
        {"source": "other", "symbol": "KOSPI"},
    ):
        raw = spec.to_dict()
        raw["benchmark"] = bad
        try:
            StrategySpec.from_dict(raw)
            raise AssertionError(f"unsupported benchmark was accepted: {bad}")
        except ValueError:
            pass

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p = root / "data/indices"
        p.mkdir(parents=True)
        dates = pd.bdate_range("2024-04-01", "2024-04-30")
        close = pd.Series(np.linspace(100.0, 110.0, len(dates)), index=dates)
        pd.DataFrame({"Date": dates, "Close": close.to_numpy()}).to_csv(
            p / "KOSPI.csv", index=False
        )

        nav = load_benchmark_nav(root, spec.benchmark, dates)
        assert len(nav) == len(dates)
        assert abs(float(nav.iloc[0]) - 1.0) < 1e-12
        assert abs(float(nav.iloc[-1]) - 1.1) < 1e-12

        meta = benchmark_coverage_audit(root, spec.benchmark, dates)
        assert meta["symbol"] == "KOSPI"
        assert meta["observations"] == len(dates)
        assert meta["exact_date_alignment"] is True

        missing = dates.delete(5)
        pd.DataFrame({
            "Date": missing,
            "Close": np.linspace(100.0, 110.0, len(missing)),
        }).to_csv(p / "KOSPI.csv", index=False)
        try:
            load_benchmark_nav(root, spec.benchmark, dates)
            raise AssertionError("benchmark missing an exact strategy date was accepted")
        except RuntimeError as exc:
            assert "missing exact strategy dates" in str(exc)

    print("STRATEGY DSL BENCHMARK TEST: PASS")


if __name__ == "__main__":
    main()
