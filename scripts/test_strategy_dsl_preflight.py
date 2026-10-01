from __future__ import annotations

from pathlib import Path
import json
import tempfile

from strategy_dsl_preflight import (
    EXIT_CAPABILITY_GAP,
    EXIT_DATA_GAP,
    EXIT_OK,
    exit_code_for,
    preflight_strategy,
)

ROOT = Path(__file__).resolve().parents[1]


def base_spec(start: str, end: str) -> dict:
    return {
        "schema_version": "1.0",
        "strategy_id": "preflight_test_strategy",
        "title": "preflight test",
        "asset_class": "kr_equity",
        "universe": {
            "markets": ["KOSPI", "KOSDAQ"],
            "require_tradable_on_signal": True,
            "filters": [{"field": "Amount", "op": "gt", "value": 0}],
        },
        "factors": [
            {"name": "small", "source": "krx", "field": "Marcap", "direction": "low"}
        ],
        "portfolio": {"number_of_positions": 20, "weighting": "equal"},
        "rebalance": {"frequency": "months", "months": [4], "trading_day": "last"},
        "execution": {"lag_sessions": 1, "price": "next_close"},
        "cost_scenarios": {"gross": {}},
        "period": {
            "start": start,
            "end": end,
            "book_start": start,
            "book_end": end,
            "as_of_date": end,
        },
        "initial_capital": 10_000_000,
    }


def write_spec(path: Path, raw: dict) -> None:
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # 1) Supported strategy + available KRX data => ready.
        ok_path = td / "ok.json"
        write_spec(ok_path, base_spec("2024-04-01", "2024-04-30"))
        ok = preflight_strategy(ok_path, ROOT)
        assert ok["status"] == "ok", ok
        assert ok["ready_for_execution"] is True
        assert len(ok["signal_dates"]) == 1
        assert ok["krx_panel"]["rows"] > 0
        assert exit_code_for(ok) == EXIT_OK

        # 2) Unsupported factor => capability gap before any data execution.
        bad_factor = base_spec("2024-04-01", "2024-04-30")
        bad_factor["strategy_id"] = "preflight_capability_gap"
        bad_factor["factors"] = [
            {"name": "roe", "source": "dart", "field": "roe", "direction": "high"}
        ]
        cap_path = td / "capability_gap.json"
        write_spec(cap_path, bad_factor)
        cap = preflight_strategy(cap_path, ROOT)
        assert cap["status"] == "capability_gap", cap
        assert cap["phase"] == "compile"
        assert "unsupported factor" in cap["error"]["message"]
        assert exit_code_for(cap) == EXIT_CAPABILITY_GAP

        # 2-B) Registered DART factor with unsupported rebalance month is a capability gap,
        # not a data gap.
        bad_month = base_spec("2024-01-01", "2024-01-31")
        bad_month["strategy_id"] = "preflight_dart_month_capability_gap"
        bad_month["factors"] = [
            {"name": "bp", "source": "dart", "field": "book_to_price", "direction": "high"}
        ]
        bad_month["rebalance"] = {"frequency": "months", "months": [1], "trading_day": "last"}
        bad_month_path = td / "dart_month_capability_gap.json"
        write_spec(bad_month_path, bad_month)
        month_gap = preflight_strategy(bad_month_path, ROOT)
        assert month_gap["status"] == "capability_gap", month_gap
        assert month_gap["phase"] == "compile"
        assert "supports rebalance months" in month_gap["error"]["message"]
        assert exit_code_for(month_gap) == EXIT_CAPABILITY_GAP

        # 3) Valid DSL but unavailable historical KRX file => data gap.
        missing_data = base_spec("1990-04-01", "1990-04-30")
        missing_data["strategy_id"] = "preflight_data_gap"
        data_path = td / "data_gap.json"
        write_spec(data_path, missing_data)
        gap = preflight_strategy(data_path, ROOT)
        assert gap["status"] == "data_gap", gap
        assert gap["phase"] in {"data", "data_contract"}
        assert gap["strategy_id"] == "preflight_data_gap"
        assert exit_code_for(gap) == EXIT_DATA_GAP

    # 4) Real DART strategy preflight: check PIT coverage metadata, not raw factor calculation.
    dart = preflight_strategy(ROOT / "config/strategies/super_value_dart_dsl.json", ROOT)
    assert dart["status"] == "ok", dart
    assert dart["factor_sources"] == ["dart"]
    assert len(dart["provider_coverage"]) == 4
    assert all(row["ratio"] == 1.0 and row["raw_ok"] for row in dart["provider_coverage"])
    assert len(dart["signal_dates"]) == 2

    print("STRATEGY DSL PREFLIGHT TEST: PASS")


if __name__ == "__main__":
    main()
