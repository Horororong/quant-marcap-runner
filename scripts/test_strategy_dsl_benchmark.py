from __future__ import annotations

from pathlib import Path
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from strategy_dsl import BenchmarkSpec, StrategySpec, compile_execution_plan
from strategy_dsl_runner import benchmark_coverage_audit, load_benchmark_nav
from strategy_dsl_preflight import preflight_strategy


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
        {},
        {"source": "index"},
        {"symbol": "KOSPI"},
        {"source": "index", "symbol": "KOSPI", "return_basis": "total_return"},
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
        assert meta["return_basis"] == "price_index_close"
        assert meta["includes_dividends"] is False

        # Coverage checks source prices, never a normalized NAV calculation.
        with patch("strategy_dsl_runner.load_benchmark_nav", side_effect=AssertionError("NAV in preflight")):
            assert benchmark_coverage_audit(root, spec.benchmark, dates) == meta

        # Future observations cannot change any requested benchmark date.
        pd.DataFrame({
            "Date": list(dates) + [pd.Timestamp("2024-05-01")],
            "Close": list(close) + [1e12],
        }).to_csv(p / "KOSPI.csv", index=False)
        pd.testing.assert_series_equal(load_benchmark_nav(root, spec.benchmark, dates), nav)

        # Validate error classification without calculating holdings or NAV.
        panel = pd.DataFrame({"Date": dates, "Code": "000001", "Market": "KOSPI"})
        class PanelEngine:
            def load_krx_equity_panel(self, **kwargs):
                return panel.copy()
        strategy_path = root / "strategy.json"
        strategy_path.write_text(json.dumps(spec.to_dict()), encoding="utf-8")
        with patch("strategy_dsl_preflight.load_project_engine", return_value=PanelEngine()):
            ready = preflight_strategy(strategy_path, root)
            assert ready["status"] == "ok", ready
            assert ready["benchmark"]["return_basis"] == "price_index_close"

            (p / "KOSPI.csv").rename(p / "unavailable.csv")
            gap = preflight_strategy(strategy_path, root)
            assert gap["status"] == "data_gap", gap
            assert "benchmark index file not found" in gap["error"]["message"]
            (p / "unavailable.csv").rename(p / "KOSPI.csv")

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

        with patch("strategy_dsl_preflight.load_project_engine", return_value=PanelEngine()):
            gap = preflight_strategy(strategy_path, root)
            assert gap["status"] == "data_gap", gap
            assert "missing exact strategy dates" in gap["error"]["message"]

        for value in (0.0, -1.0, np.inf, np.nan):
            corrupt = close.to_numpy().copy()
            corrupt[3] = value
            pd.DataFrame({"Date": dates, "Close": corrupt}).to_csv(p / "KOSPI.csv", index=False)
            try:
                load_benchmark_nav(root, spec.benchmark, dates)
                raise AssertionError(f"invalid close accepted: {value}")
            except RuntimeError:
                pass

        for broken_dates in (list(dates) + [dates[0]], list(dates[:-1]) + ["invalid"]):
            pd.DataFrame({"Date": broken_dates, "Close": 100.0}).to_csv(p / "KOSPI.csv", index=False)
            try:
                load_benchmark_nav(root, spec.benchmark, dates)
                raise AssertionError("duplicate/invalid source dates accepted")
            except (ValueError, AssertionError) as exc:
                assert "Date rows" in str(exc), exc

        pd.DataFrame({"Date": dates, "Close": close.to_numpy()}).to_csv(p / "KOSPI.csv", index=False)
        for broken_index in (dates[:0], dates[::-1], dates.append(dates[:1]), pd.DatetimeIndex([pd.NaT])):
            try:
                load_benchmark_nav(root, spec.benchmark, broken_index)
                raise AssertionError("invalid requested dates accepted")
            except ValueError as exc:
                assert "strategy dates" in str(exc), exc

    print("STRATEGY DSL BENCHMARK TEST: PASS")


if __name__ == "__main__":
    main()
