from __future__ import annotations

"""Input failures must never disappear during DSL normalization or reach data."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator, FormatChecker

from export_strategy_dsl_contract import build_capabilities
from strategy_dsl import StrategySpec, build_strategy_json_schema, load_strategy_spec
from strategy_dsl_preflight import EXIT_CAPABILITY_GAP, exit_code_for, preflight_strategy
from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "config/strategies"
# Captured from unchanged main b763c5c before implementing the input gate.
BASELINE_FINGERPRINTS = {
    "kr_equity_autumn_splits_research.json": "1222032e0a2a0c197d12e26bd0377f90b7658c228c198c3d586e959d2b33a796",
    "kr_equity_market_segment_research.json": "0cd7371539dc8c177029c60011e174dfd189ead1b084e6a23821375fee1511f6",
    "kr_equity_rank_demo.json": "b5f95edca5a159de97ff24437496578210a21c6a6afc6c6ca3cca38cf2d67fff",
    "kr_equity_size_deciles_research.json": "fc1db45bda8afee95fb05681c4500176ebcb4fc699094de182e89da6b17873c8",
    "kr_equity_split_classes_research.json": "5abff6a98f3c0734a512a6a5f391bc71193a30a83889e103ecb5e3e47bcf268c",
    "kr_equity_split_research.json": "08f6ddfbd5ba39575ca71cb66dc4173e423e0e00879acdd91a9a3317f1eaa0e3",
    "super_value_dart_benchmark_dsl.json": "ae45125a95e513c4996f4111355297bfc3c53ed65b072138e435857a9e093159",
    "super_value_dart_dsl.json": "6401144337f863ea586717d1f736b8416f1890c83b16994f6f8866e8522f85db",
}


def expect_rejection(fn, text: str) -> None:
    try:
        fn()
    except (TypeError, ValueError) as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError(f"invalid input accepted: {text}")


def base_spec() -> dict:
    return json.loads((EXAMPLES / "kr_equity_rank_demo.json").read_text(encoding="utf-8"))


def change(raw: dict, path: tuple, value) -> dict:
    raw = deepcopy(raw)
    parent = raw
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    return raw


def invalid_inputs():
    raw = base_spec()
    raw["benchmark"] = {"source": "index", "symbol": "KOSPI"}
    cost_name = next(iter(raw["cost_scenarios"]))
    objects = [(), ("universe",), ("universe", "filters", 0), ("factors", 0),
               ("portfolio",), ("rebalance",), ("execution",),
               ("cost_scenarios", cost_name), ("benchmark",), ("period",)]
    for path in objects:
        target = deepcopy(raw)
        obj = target
        for key in path:
            obj = obj[key]
        obj["unsupported_condition"] = {"sector_neutral": True}
        yield target, "unsupported_condition", False
    for path in objects[1:]:
        for value in (None, [], "object", 1, True):
            if path == ("benchmark",) and value is None:
                continue
            yield change(raw, path, value), "." + str(path[0]), False
    for path in (("universe", "markets"), ("universe", "filters"), ("factors",), ("rebalance", "months")):
        for value in (None, {}, "array", 1, True):
            yield change(raw, path, value), "." + str(path[0]), False
    for key in ("schema_version", "strategy_id", "title", "asset_class", "universe", "factors", "portfolio", "rebalance", "execution", "cost_scenarios", "period"):
        target = deepcopy(raw)
        del target[key]
        yield target, key, False
    for path in (("initial_capital",), ("factors", 0, "weight"), ("cost_scenarios", cost_name, "commission_bps")):
        for value in (True, False, "1", None, float("nan"), float("inf"), -float("inf"), 10 ** 400):
            # Standard JSON Schema does not enforce floating-point finiteness.
            semantic = isinstance(value, (int, float)) and not isinstance(value, bool) and (value != value or value in (float("inf"), -float("inf")) or value == 10 ** 400)
            yield change(raw, path, value), "." + str(path[0]), semantic
    for path in (("portfolio", "number_of_positions"), ("execution", "lag_sessions")):
        for value in (True, "1", 1.0, 1.5, 0, -1):
            yield change(raw, path, value), "." + str(path[0]), value == 1.0 and type(value) is float
    for value in ([4.0, 10], [4.5], [True], ["4"], [], [0], [13], [4, 4]):
        yield change(raw, ("rebalance", "months"), value), "rebalance", value == [4.0, 10]
    for value in ("false", 0, 1, None):
        yield change(raw, ("universe", "require_tradable_on_signal"), value), "require_tradable_on_signal", False
    for key in ("start", "end", "book_start", "book_end", "as_of_date"):
        for value in ("2024-02-30", "2024-13-01", "2024-1-01", "20240101", "2024-01-01T00:00:00", 20240101):
            yield change(raw, ("period", key), value), f"period.{key}", False
    yield change(raw, ("period", "start"), "2099-01-01"), "period.start", True
    yield change(raw, ("period", "book_start"), "2099-01-01"), "period.book_start", True
    for op in ("gt", "gte", "lt", "lte", "top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct"):
        for value in (True, "10", None, [], {}):
            yield change(raw, ("universe", "filters"), [{"field": "Marcap", "op": op, "value": value}]), "filters", False
    for op in ("eq", "ne", "in", "not_in", "top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct"):
        yield change(raw, ("universe", "filters"), [{"field": "Marcap", "op": op}]), "filters", False
    for op in ("in", "not_in"):
        for value in ("123", 1, [], [[1]], [None], [{}]):
            yield change(raw, ("universe", "filters"), [{"field": "Marcap", "op": op, "value": value}]), "filters", False
    for op in ("top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct"):
        for value in (0, -1, 100, 101):
            yield change(raw, ("universe", "filters"), [{"field": "Marcap", "op": op, "value": value}]), "filters", False
    yield change(raw, ("universe", "filters"), [{"field": "Marcap", "op": "notnull", "value": 1}]), "filters", False
    yield change(raw, ("factors", 0, "source"), "unsupported"), "unsupported factor", False
    yield change(raw, ("factors", 0, "field"), "roe"), "unsupported factor", False
    yield change(raw, ("factors", 0, "weight"), 0), "weight", False
    yield change(raw, ("initial_capital",), -1), "initial_capital", False
    yield change(raw, ("cost_scenarios", cost_name, "commission_bps"), -1), "commission_bps", False
    yield change(raw, ("cost_scenarios",), {}), "cost_scenarios", False
    yield change(raw, ("cost_scenarios",), {"": {}}), "cost_scenarios", False
    yield change(raw, ("universe", "markets"), ["KOSPI", "KOSPI"]), "markets", False
    for path in (("title",), ("factors", 0, "name")):
        yield change(raw, path, " "), str(path[0]), False
        for value in (1, True, None):
            yield change(raw, path, value), str(path[0]), False
    for value in (None, [], "metadata", True):
        yield change(raw, ("metadata",), value), "metadata", False
    target = deepcopy(raw)
    duplicate = deepcopy(target["factors"][0])
    duplicate["name"] = " " + duplicate["name"] + " "
    target["factors"].append(duplicate)
    yield target, "factor names must be unique", True
    yield change(raw, ("metadata",), {"nested": [float("nan")]}), "metadata.nested[0]", True
    yield change(raw, ("metadata",), {1: "non-string key"}), "metadata", True
    target = change(raw, ("factors", 0, "weight"), 1e308)
    target["factors"].append({"name": "other", "source": "krx", "field": "Amount", "direction": "high", "weight": 1e308})
    yield target, "total factor weight", True
    yield change(raw, ("cost_scenarios", cost_name), {"commission_bps": 1e308, "slippage_bps": 1e308}), "total cost", True
    for value in (None, [], "strategy", True, 1):
        yield value, "$", False


def rejection_test(directory: Path) -> int:
    validator = Draft202012Validator(build_strategy_json_schema(), format_checker=FormatChecker())
    path = directory / "invalid.json"
    out = directory / "must_not_exist"
    count = 0
    for raw, message, runtime_semantic in invalid_inputs():
        expect_rejection(lambda: StrategySpec.from_dict(raw), message)
        if not runtime_semantic:
            assert not validator.is_valid(raw), (message, raw)
        # Non-string Python mapping keys cannot exist in a JSON file; test above
        # ensures they cannot be stringified by from_dict either.
        if isinstance(raw, dict) and isinstance(raw.get("metadata"), dict) and 1 in raw["metadata"]:
            continue
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        expect_rejection(lambda: load_strategy_spec(path), message)
        with patch("strategy_dsl_preflight.load_project_engine") as engine:
            result = preflight_strategy(path, ROOT)
            assert result["status"] == "capability_gap", result
            assert result["phase"] == "compile", result
            assert exit_code_for(result) == EXIT_CAPABILITY_GAP
            engine.assert_not_called()
        with patch("strategy_dsl_runner.load_project_engine") as engine:
            expect_rejection(lambda: run_strategy(path, ROOT, out), message)
            engine.assert_not_called()
        assert not out.exists()
        count += 1
    return count


def duplicate_and_cli_test(directory: Path) -> None:
    path = directory / "duplicate.json"
    raw = base_spec()
    raw.pop("metadata", None)
    valid = json.dumps(raw)
    for document in (
        valid[:-1] + ', "strategy_id": "different_strategy"}',
        valid.replace('"lag_sessions": 1', '"lag_sessions": 1, "lag_sessions": 2'),
        valid[:-1] + ', "metadata": {"request": "first", "request": "second"}}',
        valid[:-1] + ', "metadata": {"nested": {"x": 1, "x": 2}}}',
    ):
        assert document != valid
        path.write_text(document, encoding="utf-8")
        expect_rejection(lambda: load_strategy_spec(path), "duplicate JSON key")
        with patch("strategy_dsl_preflight.load_project_engine") as engine:
            result = preflight_strategy(path, ROOT)
            assert result["status"] == "capability_gap", result
            engine.assert_not_called()
    raw["execution"]["stop_loss_pct"] = 10
    path.write_text(json.dumps(raw), encoding="utf-8")
    out = directory / "cli_must_not_exist"
    for flag in ("--validate-only", "--execution-only"):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/strategy_dsl_runner.py"), str(path), flag, "--output-dir", str(out)], capture_output=True, text=True)
        assert proc.returncode != 0
        assert "stop_loss_pct" in proc.stderr
        assert not out.exists()
    for flag, code in (([], EXIT_CAPABILITY_GAP), (["--always-zero"], 0)):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/strategy_dsl_preflight.py"), str(path), *flag], capture_output=True, text=True)
        assert proc.returncode == code, proc.stderr
        result = json.loads(proc.stdout)
        assert result["status"] == "capability_gap" and result["phase"] == "compile", result
        assert result["error"]["path"] == "$.execution", result


def compatibility_test() -> None:
    schema = build_strategy_json_schema()
    Draft202012Validator.check_schema(schema)
    assert build_capabilities()["input_validation"] == schema["x-input-validation"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for name, fingerprint in BASELINE_FINGERPRINTS.items():
        spec = load_strategy_spec(EXAMPLES / name)
        assert spec.fingerprint() == fingerprint, name
        assert StrategySpec.from_dict(spec.to_dict()).fingerprint() == fingerprint, name
        validator.validate(json.loads(spec.canonical_json()))
    raw = base_spec()
    for key in ("initial_capital", "metadata", "benchmark"):
        raw.pop(key, None)
    for key in ("filters", "require_tradable_on_signal"):
        raw["universe"].pop(key, None)
    raw["portfolio"].pop("selection", None)
    raw["factors"] = [{"name": "size", "source": "krx", "field": "Marcap", "direction": "low"}]
    raw["cost_scenarios"] = {"gross": {}}
    spec = StrategySpec.from_dict(raw)
    assert spec.universe.filters == () and spec.universe.require_tradable_on_signal is True
    assert spec.factors[0].weight == 1 and spec.factors[0].transform == "identity"
    assert spec.initial_capital == 10_000_000 and spec.benchmark is None
    assert spec.portfolio.selection == "top_n" and spec.cost_scenarios["gross"].commission_bps == 0
    for op, value in (("notnull", None), ("gt", 0), ("gte", 1), ("lt", 10), ("lte", 10), ("eq", 1), ("ne", 2), ("in", [1, 2]), ("not_in", [1]), ("top_pct", 0.1), ("bottom_pct", 99.9), ("exclude_top_pct", 10), ("exclude_bottom_pct", 20)):
        target = change(raw, ("universe", "filters"), [{"field": "Marcap", "op": op, "value": value}])
        validator.validate(target)
        StrategySpec.from_dict(target)
    raw["metadata"] = {"arbitrary": {"notes": [None, True, "한국어", 1, 1.5]}}
    raw["universe"]["require_tradable_on_signal"] = False
    raw["period"]["as_of_date"] = "2099-01-01"  # Report cutoff may follow the simulation window.
    raw["rebalance"]["months"] = [10, 4]  # Existing deterministic sorting remains.
    spec = StrategySpec.from_dict(raw)
    assert spec.rebalance.months == (4, 10)
    assert spec.universe.require_tradable_on_signal is False
    assert spec.metadata == raw["metadata"]
    for key in ("start", "end", "book_start", "book_end", "as_of_date"):
        raw["period"][key] = "2024-02-29"
    StrategySpec.from_dict(raw)  # Valid leap day and same-day periods.


def main() -> None:
    compatibility_test()
    with tempfile.TemporaryDirectory() as td:
        count = rejection_test(Path(td))
        duplicate_and_cli_test(Path(td))
    print(f"STRATEGY DSL INPUT CONTRACT: PASS ({count} invalid cases; 8 unchanged fingerprints; CLI/data guards)")


if __name__ == "__main__":
    main()
