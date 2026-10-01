from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd

import factor_registry as registry
from factor_registry import FactorDefinition
from strategy_dsl import StrategySpec
from strategy_dsl_runner import build_target_weights_from_panel, required_panel_columns


class SyntheticProvider:
    source = "synthetic"

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)

    def factor_frame(self, signal: pd.Timestamp, cross_section: pd.DataFrame, fields):
        if list(fields) != ["score"]:
            raise AssertionError(fields)
        out = cross_section[["Code"]].copy()
        out["score"] = out["Code"].astype(int).astype(float)
        return out

    def coverage_report(self, signal: pd.Timestamp):
        return [{"source": self.source, "signal_date": pd.Timestamp(signal), "ratio": 1.0, "raw_ok": True}]


def make_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-04-01", "2024-04-30")
    rows = []
    for dt in dates:
        for code in ("000001", "000002", "000003"):
            rows.append({
                "Date": dt,
                "Code": code,
                "Name": code,
                "Market": "KOSPI",
                "Close": 100.0,
                "Volume": 1000.0,
                "Amount": 1_000_000.0,
                "Marcap": int(code) * 1_000_000_000.0,
            })
    return pd.DataFrame(rows)


def main() -> None:
    assert registry.get_factor_definition("krx", "Marcap").storage == "panel"
    assert registry.get_factor_definition("dart", "earnings_yield").storage == "external"
    assert "dart" in registry.supported_sources()
    assert "book_to_price" in registry.supported_fields("dart")
    assert registry.FACTOR_REGISTRY_VERSION == "3"
    constraints = registry.factor_source_constraints()
    assert constraints["dart"]["rebalance_months"] == [4, 10]

    dart_factor = type("F", (), {"source": "dart", "field": "book_to_price"})()
    registry.validate_factor_strategy_constraints([dart_factor], [4, 10])
    try:
        registry.validate_factor_strategy_constraints([dart_factor], [1])
        raise AssertionError("unsupported DART rebalance month was accepted")
    except ValueError as exc:
        assert "supports rebalance months" in str(exc)

    try:
        registry.get_factor_definition("dart", "not_a_factor")
        raise AssertionError("unsupported factor reference was accepted")
    except ValueError:
        pass

    key = ("synthetic", "score")
    old_def = registry.FACTOR_DEFINITIONS.get(key)
    old_factory = registry.PROVIDER_FACTORIES.get("synthetic")
    try:
        registry.register_factor(FactorDefinition("synthetic", "score", "external", "test factor"))
        registry.PROVIDER_FACTORIES["synthetic"] = SyntheticProvider

        spec = StrategySpec.from_dict({
            "schema_version": "1.0",
            "strategy_id": "provider_registry_smoke",
            "title": "provider registry smoke",
            "asset_class": "kr_equity",
            "universe": {"markets": ["KOSPI"], "require_tradable_on_signal": False},
            "factors": [
                {"name": "synthetic_score", "source": "synthetic", "field": "score", "direction": "high"}
            ],
            "portfolio": {"number_of_positions": 1, "weighting": "equal"},
            "rebalance": {"frequency": "months", "months": [4], "trading_day": "last"},
            "execution": {"lag_sessions": 1, "price": "next_close"},
            "cost_scenarios": {"gross": {}},
            "period": {
                "start": "2024-04-01",
                "end": "2024-04-30",
                "book_start": "2024-04-01",
                "book_end": "2024-04-30",
                "as_of_date": "2024-04-30"
            }
        })
        cols = required_panel_columns(spec)
        assert "score" not in cols
        assert "Marcap" in cols

        panel = make_panel()
        with tempfile.TemporaryDirectory() as td:
            weights, selections = build_target_weights_from_panel(panel, spec, repo_root=Path(td))

        assert len(weights) == 1
        selected = selections.iloc[0]
        assert selected["Code"] == "000003", selections[["Code", "composite_score"]]
        assert float(weights.iloc[0]["000003"]) == 1.0

        # External fields can also define the eligible universe, even when the
        # ranking factor itself is a KRX panel field.
        filtered_spec = StrategySpec.from_dict({
            "schema_version": "1.0",
            "strategy_id": "provider_filter_smoke",
            "title": "provider filter smoke",
            "asset_class": "kr_equity",
            "universe": {
                "markets": ["KOSPI"],
                "require_tradable_on_signal": False,
                "filters": [{"field": "score", "op": "gte", "value": 2}],
            },
            "factors": [
                {"name": "small", "source": "krx", "field": "Marcap", "direction": "low"}
            ],
            "portfolio": {"number_of_positions": 1, "weighting": "equal"},
            "rebalance": {"frequency": "months", "months": [4], "trading_day": "last"},
            "execution": {"lag_sessions": 1, "price": "next_close"},
            "cost_scenarios": {"gross": {}},
            "period": {
                "start": "2024-04-01",
                "end": "2024-04-30",
                "book_start": "2024-04-01",
                "book_end": "2024-04-30",
                "as_of_date": "2024-04-30"
            }
        })
        filtered_cols = required_panel_columns(filtered_spec)
        assert "score" not in filtered_cols
        with tempfile.TemporaryDirectory() as td:
            filtered_weights, filtered_selections = build_target_weights_from_panel(
                panel, filtered_spec, repo_root=Path(td)
            )
        assert filtered_selections.iloc[0]["Code"] == "000002", filtered_selections
        assert float(filtered_weights.iloc[0]["000002"]) == 1.0
    finally:
        registry.FACTOR_DEFINITIONS.pop(key, None)
        registry.PROVIDER_FACTORIES.pop("synthetic", None)
        if old_def is not None:
            registry.FACTOR_DEFINITIONS[key] = old_def
        if old_factory is not None:
            registry.PROVIDER_FACTORIES["synthetic"] = old_factory

    print("FACTOR PROVIDER REGISTRY TEST: PASS")


if __name__ == "__main__":
    main()
