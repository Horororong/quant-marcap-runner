from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from strategy_dsl import load_strategy_spec
from strategy_dsl_runner import build_target_weights_from_panel, load_project_engine
from dart_value_factor_adapter import DartValueFactorAdapter

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config/strategies/super_value_dart_dsl.json"


def assert_close(a: pd.Series, b: pd.Series, label: str) -> None:
    aa = pd.to_numeric(a, errors="coerce")
    bb = pd.to_numeric(b, errors="coerce")
    mask = aa.notna() & bb.notna()
    if not mask.any():
        raise AssertionError(f"{label}: no comparable observations")
    if not np.allclose(aa[mask].to_numpy(float), bb[mask].to_numpy(float), rtol=1e-12, atol=1e-12):
        raise AssertionError(f"{label}: formula mismatch")


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
    panel["Date"] = pd.to_datetime(panel["Date"]).dt.normalize()
    panel["Code"] = panel["Code"].astype(str).str.zfill(6)

    target_weights, selections = build_target_weights_from_panel(panel, strategy, repo_root=ROOT)
    assert len(target_weights) == 2, target_weights.index
    assert set(target_weights.index.month) == {4, 10}
    assert np.allclose(target_weights.sum(axis=1).to_numpy(float), 1.0)

    selections["signal_date"] = pd.to_datetime(selections["signal_date"]).dt.normalize()
    counts = selections.groupby("signal_date")["Code"].nunique()
    assert (counts == 20).all(), counts.to_dict()
    assert not selections.duplicated(["signal_date", "Code"]).any()

    adapter = DartValueFactorAdapter(ROOT)
    for signal in target_weights.index:
        signal = pd.Timestamp(signal).normalize()
        cs = panel[panel["Date"] == signal].copy()
        coverage = adapter.coverage_report(signal)
        assert coverage
        assert all(r["ratio"] == 1.0 and r["raw_ok"] for r in coverage), coverage

        factors = adapter.factor_frame(signal, cs)
        assert not factors.empty
        assert factors["available_date"].notna().any()
        if (pd.to_datetime(factors["available_date"].dropna()) > signal).any():
            raise AssertionError(f"{signal.date()}: look-ahead filing detected")

        merged = factors.merge(cs[["Code", "Marcap"]], on="Code", how="inner")
        mc = pd.to_numeric(merged["Marcap"], errors="coerce")
        valid = mc > 0
        z = merged.loc[valid].copy()
        mc = mc.loc[valid]
        assert_close(z["earnings_yield"], z["net_income_q"] / mc, "earnings_yield")
        assert_close(z["book_to_price"], z["equity"] / mc, "book_to_price")
        assert_close(z["cashflow_yield"], z["ocf_q"] / mc, "cashflow_yield")
        assert_close(z["sales_yield"], z["revenue_q"] / mc, "sales_yield")

        chosen = selections[selections["signal_date"] == signal].copy()
        assert set(chosen["Code"]).issubset(set(factors["Code"]))
        for col in ("factor_rank__EP", "factor_rank__BP", "factor_rank__CFP", "factor_rank__SP", "composite_score"):
            if chosen[col].isna().any():
                raise AssertionError(f"{signal.date()}: selected row has missing {col}")

        # Independently reconstruct the four-factor rank from standardized
        # DART fields. This verifies the adapter+DSL contract, not legacy code.
        independent = factors.merge(
            cs[["Code", "Name", "Market", "Close", "Volume", "Amount", "Marcap"]],
            on="Code",
            how="inner",
        )
        independent = independent[
            (pd.to_numeric(independent["Close"], errors="coerce") > 0)
            & (pd.to_numeric(independent["Volume"], errors="coerce") > 0)
            & (pd.to_numeric(independent["Marcap"], errors="coerce") > 0)
        ].copy()
        cols = ["earnings_yield", "book_to_price", "cashflow_yield", "sales_yield"]
        independent = independent.dropna(subset=cols).copy()
        for col in cols:
            independent[col + "_rank"] = pd.to_numeric(
                independent[col], errors="coerce"
            ).rank(method="average", ascending=False, pct=True)
        independent["score"] = independent[[x + "_rank" for x in cols]].mean(axis=1)
        expected_codes = (
            independent.sort_values(["score", "Code"], ascending=[True, True])
            .head(20)["Code"].astype(str).str.zfill(6).tolist()
        )
        actual_codes = (
            chosen.sort_values(["composite_score", "Code"], ascending=[True, True])
            ["Code"].astype(str).str.zfill(6).tolist()
        )
        if actual_codes != expected_codes:
            raise AssertionError(
                f"{signal.date()}: DSL selection does not match independent four-factor rank"
            )

    print("DART DSL SUPER VALUE INTEGRATION: PASS")
    print("signals:", [x.date().isoformat() for x in target_weights.index])


if __name__ == "__main__":
    main()
