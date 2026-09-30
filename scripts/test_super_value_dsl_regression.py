from __future__ import annotations

"""Real-data parity test: Strategy DSL DART adapter vs legacy super-value selection."""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

from dart_factor_adapter import DartValueFactorAdapter, metric_priority
from strategy_dsl import load_strategy_spec
from strategy_dsl_runner import rank_cross_section, _scheduled_sell_tax_bps

ROOT = Path(__file__).resolve().parents[1]
SIGNAL = pd.Timestamp("2020-04-29")
TOP_N = 20


def load_legacy():
    path = ROOT / "scripts/backtest_super_value_v216.py"
    spec = importlib.util.spec_from_file_location("legacy_super_value_v216", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_close_frame(left: pd.DataFrame, right: pd.DataFrame, cols: list[str]) -> None:
    a = left.set_index("Code")[cols].sort_index()
    b = right.set_index("Code")[cols].sort_index()
    common = a.index.intersection(b.index)
    if len(common) == 0:
        raise AssertionError("no common factor rows")
    for col in cols:
        av = pd.to_numeric(a.loc[common, col], errors="coerce").to_numpy(float)
        bv = pd.to_numeric(b.loc[common, col], errors="coerce").to_numpy(float)
        if not np.allclose(av, bv, rtol=0, atol=1e-9, equal_nan=True):
            diff = np.nanmax(np.abs(av - bv))
            raise AssertionError(f"factor mismatch {col}: max_abs_diff={diff}")


def main() -> None:
    legacy = load_legacy()
    spec = load_strategy_spec(ROOT / "config/strategies/super_value_original_dsl.json")
    exact_cases = [
        ("ifrs_ProfitLoss", "IS", "net_income"),
        ("ifrs-full_ProfitLoss", "CIS", "net_income"),
        ("ifrs_ProfitLossBeforeTax", "IS", None),
        ("ifrs-full_ProfitLossAttributableToOwnersOfParent", "IS", None),
        ("ifrs_Equity", "BS", "equity"),
        ("ifrs-full_EquityAndLiabilities", "BS", None),
    ]
    for account_id, sj_div, wanted in exact_cases:
        got, _ = metric_priority(pd.Series({
            "account_id": account_id,
            "sj_div": sj_div,
            "account_nm": "",
        }))
        if got != wanted:
            raise AssertionError(f"exact account mapping failed: {account_id} -> {got}, want={wanted}")

    adapter = DartValueFactorAdapter(ROOT)

    # The DSL cost schedule must reproduce the legacy dated sell-tax function.
    sample_dates = pd.DatetimeIndex([
        "2018-12-31", "2019-06-03", "2020-12-31", "2021-01-01",
        "2023-01-01", "2024-01-01", "2025-01-01", "2026-01-01",
    ])
    for scenario_name in ("minimum", "base", "conservative"):
        tax = _scheduled_sell_tax_bps(spec.cost_scenarios[scenario_name], sample_dates)
        expected = pd.Series([legacy.sell_tax_bps(x) for x in sample_dates], index=sample_dates)
        if not np.allclose(tax.to_numpy(float), expected.to_numpy(float), rtol=0, atol=0):
            raise AssertionError(f"sell-tax schedule mismatch: {scenario_name}")

    period_cache = {}
    for y, p in legacy.required_periods(SIGNAL):
        period_cache[(y, p)] = legacy.report_snapshots(legacy.load_financial_raw(y, p))
    old_factors = legacy.build_factor_table(SIGNAL, period_cache)
    new_factors = adapter.base_metrics(SIGNAL)

    assert_close_frame(
        old_factors,
        new_factors,
        ["equity", "revenue_q", "net_income_q", "ocf_q"],
    )

    panel = legacy.load_krx(SIGNAL.date().isoformat(), SIGNAL.date().isoformat())
    old_sel, old_audit = legacy.build_selection(panel, SIGNAL, old_factors, TOP_N)

    cs = panel[panel["Date"] == SIGNAL][
        ["Date", "Code", "Name", "Market", "Marcap", "Amount", "Volume", "Close"]
    ].copy()
    cs = adapter.enrich_cross_section(
        cs,
        SIGNAL,
        ["earnings_yield", "book_to_price", "cashflow_yield", "sales_yield"],
    )
    new_sel, _ = rank_cross_section(cs, spec)

    old_codes = old_sel["Code"].astype(str).str.zfill(6).tolist()
    new_codes = new_sel["Code"].astype(str).str.zfill(6).tolist()
    if old_codes != new_codes:
        pairs = list(zip(old_codes, new_codes))
        raise AssertionError(f"top20 order mismatch: {pairs}")

    old_compare = old_sel.set_index("Code")
    new_compare = new_sel.set_index("Code")
    mapping = {
        "EY_1_PER": "earnings_yield",
        "BY_1_PBR": "book_to_price",
        "CFY_1_PCR": "cashflow_yield",
        "SY_1_PSR": "sales_yield",
    }
    for old_col, new_col in mapping.items():
        a = pd.to_numeric(old_compare.loc[old_codes, old_col], errors="coerce").to_numpy(float)
        b = pd.to_numeric(new_compare.loc[old_codes, new_col], errors="coerce").to_numpy(float)
        if not np.allclose(a, b, rtol=0, atol=1e-12, equal_nan=True):
            raise AssertionError(f"selected factor values differ: {old_col} vs {new_col}")

    print("SUPER VALUE DSL REAL-DATA PARITY: PASS")
    print(f"signal={SIGNAL.date()} valid_four_factor={old_audit['valid_four_factor']} top_n={TOP_N}")
    print("top20=" + ",".join(old_codes))


if __name__ == "__main__":
    main()
