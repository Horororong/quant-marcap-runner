from __future__ import annotations

"""Generic Strategy DSL v1 runner.

v1 runtime scope: KRX equity cross-sectional ranking strategies using PIT KRX
panel fields and the standardized DART value-factor adapter. Unsupported factor
families fail explicitly instead of being approximated.
"""

from pathlib import Path
from typing import Any
import argparse
import importlib.util
import json
import subprocess
import sys

import numpy as np
import pandas as pd

from strategy_dsl import StrategySpec, compile_execution_plan, load_strategy_spec
from dart_factor_adapter import DartValueFactorAdapter

ENGINE_FILE = "scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py"
POSTPROCESS_FILE = "scripts/quant_backtest_postprocess.py"
BASE_PANEL_COLUMNS = ["Date", "Code", "Name", "Market", "Close", "Volume", "Amount", "Marcap"]


def load_project_engine(repo_root: Path):
    path = repo_root / ENGINE_FILE
    spec = importlib.util.spec_from_file_location("quant_project_v216", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load project engine: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if getattr(module, "TEMPLATE_VERSION", None) != "v2-16":
        raise RuntimeError(f"DSL v1 expects project engine v2-16; got {getattr(module, 'TEMPLATE_VERSION', None)}")
    return module


def required_panel_columns(spec: StrategySpec) -> list[str]:
    fields = set(BASE_PANEL_COLUMNS)
    fields.update(x.field for x in spec.universe.filters)
    fields.update(x.field for x in spec.factors if x.source == "krx")
    return sorted(fields)


def _apply_filter(frame: pd.DataFrame, field: str, op: str, value: Any) -> pd.DataFrame:
    if field not in frame.columns:
        raise KeyError(f"filter field not present in panel: {field}")
    s = frame[field]
    if op == "notnull":
        mask = s.notna()
    elif op in {"gt", "gte", "lt", "lte"}:
        n = pd.to_numeric(s, errors="coerce")
        v = float(value)
        mask = {"gt": n > v, "gte": n >= v, "lt": n < v, "lte": n <= v}[op]
    elif op == "eq":
        mask = s == value
    elif op == "ne":
        mask = s != value
    elif op == "in":
        mask = s.isin(list(value))
    elif op == "not_in":
        mask = ~s.isin(list(value))
    elif op in {"top_pct", "bottom_pct", "exclude_top_pct", "exclude_bottom_pct"}:
        n = pd.to_numeric(s, errors="coerce")
        pct = float(value) / 100.0
        rank_asc = n.rank(method="average", pct=True, ascending=True)
        if op == "top_pct":
            mask = rank_asc > (1.0 - pct)
        elif op == "bottom_pct":
            mask = rank_asc <= pct
        elif op == "exclude_top_pct":
            mask = rank_asc <= (1.0 - pct)
        else:
            mask = rank_asc > pct
    else:
        raise ValueError(f"unsupported filter op: {op}")
    return frame.loc[mask.fillna(False)].copy()


def _transform_factor(values: pd.Series, transform: str) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    if transform == "identity":
        return x
    if transform == "inverse":
        return 1.0 / x.replace(0.0, np.nan)
    if transform == "log1p":
        return np.log1p(x.where(x >= 0.0))
    raise ValueError(f"unsupported transform: {transform}")


def signal_dates_from_panel(panel: pd.DataFrame, spec: StrategySpec) -> list[pd.Timestamp]:
    dates = pd.DatetimeIndex(pd.to_datetime(panel["Date"]).dropna().unique()).sort_values()
    start = pd.Timestamp(spec.period.start).normalize()
    end = pd.Timestamp(spec.period.end).normalize()
    dates = dates[(dates >= start) & (dates <= end)]
    out: list[pd.Timestamp] = []
    for year in range(start.year, end.year + 1):
        for month in spec.rebalance.months:
            m = dates[(dates.year == year) & (dates.month == month)]
            if len(m):
                out.append(pd.Timestamp(m[-1]).normalize())
    if not out:
        raise RuntimeError("no rebalance signal dates in requested period")
    return sorted(set(out))


def rank_cross_section(cross_section: pd.DataFrame, spec: StrategySpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = cross_section.copy()
    if spec.universe.require_tradable_on_signal:
        close = pd.to_numeric(x["Close"], errors="coerce")
        volume = pd.to_numeric(x["Volume"], errors="coerce")
        x = x[(close > 0) & (volume > 0)].copy()
    for flt in spec.universe.filters:
        x = _apply_filter(x, flt.field, flt.op, flt.value)
    if x.empty:
        raise RuntimeError("universe empty after filters")

    # All factor ranks must be calculated on the identical eligible universe.
    transformed: dict[str, pd.Series] = {}
    valid_all = pd.Series(True, index=x.index)
    for fac in spec.factors:
        if fac.field not in x.columns:
            raise KeyError(
                f"factor field not present after source adapters: source={fac.source}, field={fac.field}"
            )
        v = _transform_factor(x[fac.field], fac.transform)
        transformed[fac.name] = v
        valid_all &= v.notna() & np.isfinite(v)

    x = x.loc[valid_all].copy()
    if x.empty:
        raise RuntimeError("universe empty after factor missing-value intersection")

    total_weight = sum(f.weight for f in spec.factors)
    score = pd.Series(0.0, index=x.index)
    factor_columns: list[str] = []
    for fac in spec.factors:
        v = transformed[fac.name].reindex(x.index)
        # Use raw ordinal ranks, not pct=True. All factors share the same
        # missing-value intersection, so ordinal ranks are directly comparable
        # and preserve exact ties without floating-point tie drift.
        rank = v.rank(method="average", ascending=(fac.direction == "low"))
        col = f"factor_rank__{fac.name}"
        x[col] = rank
        factor_columns.append(col)
        score = score + rank * (fac.weight / total_weight)

    x["composite_score"] = score
    x = x.sort_values(["composite_score", "Code"], ascending=[True, True]).copy()
    n = spec.portfolio.number_of_positions
    if len(x) < n:
        raise RuntimeError(f"eligible universe {len(x)} is smaller than number_of_positions={n}")
    selected = x.head(n).copy()
    selected["target_weight"] = 1.0 / n
    return selected, x[["Date", "Code", "Name", "Market", "composite_score", *factor_columns]].copy()

def build_target_weights_from_panel(
    panel: pd.DataFrame,
    spec: StrategySpec,
    dart_adapter: DartValueFactorAdapter | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = panel.copy()
    p["Date"] = pd.to_datetime(p["Date"]).dt.normalize()
    p["Code"] = p["Code"].astype(str).str.zfill(6)
    if p.duplicated(["Date", "Code"]).any():
        raise AssertionError("panel contains duplicate Date+Code")

    dart_fields = [f.field for f in spec.factors if f.source == "dart"]
    if dart_fields and dart_adapter is None:
        raise ValueError("strategy requires DART factors but dart_adapter was not supplied")

    assets = sorted(p["Code"].unique())
    rows: list[pd.Series] = []
    selection_rows: list[pd.DataFrame] = []
    for dt in signal_dates_from_panel(p, spec):
        cs = p[p["Date"] == dt].copy()
        if dart_fields:
            cs = dart_adapter.enrich_cross_section(cs, dt, dart_fields)
        selected, _ = rank_cross_section(cs, spec)
        w = pd.Series(0.0, index=assets, name=dt)
        w.loc[selected["Code"].astype(str).str.zfill(6)] = selected["target_weight"].to_numpy(float)
        rows.append(w)
        s = selected.copy()
        s["signal_date"] = dt
        selection_rows.append(s)

    tw = pd.DataFrame(rows)
    tw.index = pd.to_datetime(tw.index).normalize()
    tw = tw.sort_index().fillna(0.0)
    selections = pd.concat(selection_rows, ignore_index=True) if selection_rows else pd.DataFrame()
    return tw, selections


def close_and_tradable_matrices(panel: pd.DataFrame, assets: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = panel.copy()
    p["Date"] = pd.to_datetime(p["Date"]).dt.normalize()
    p["Code"] = p["Code"].astype(str).str.zfill(6)
    close = p.pivot(index="Date", columns="Code", values="Close").reindex(columns=assets).sort_index()
    vol = p.pivot(index="Date", columns="Code", values="Volume").reindex(index=close.index, columns=assets)
    tradable = close.notna() & (close > 0) & vol.notna() & (vol > 0)
    return close, tradable.astype(bool)


def engine_inputs(spec: StrategySpec, engine) -> tuple[Any, dict[str, Any], Any]:
    cfg = engine.BacktestConfig(
        title=spec.title,
        initial_capital=spec.initial_capital,
        book_start=spec.period.book_start,
        book_end=spec.period.book_end,
        as_of_date=spec.period.as_of_date or spec.period.end,
        market_calendar="XKRX",
    )
    costs = {
        name: engine.TradingCostAssumptions(
            commission_bps=cost.commission_bps,
            sell_tax_bps=cost.sell_tax_bps,
            spread_bps=cost.spread_bps,
            slippage_bps=cost.slippage_bps,
            market_impact_bps=cost.market_impact_bps,
        )
        for name, cost in spec.cost_scenarios.items()
    }
    execution = engine.ExecutionAssumptions(
        execution_lag_sessions=spec.execution.lag_sessions,
        execution_price=spec.execution.price,
    )
    return cfg, costs, execution


def _scheduled_sell_tax_bps(cost_spec, dates: pd.DatetimeIndex) -> pd.Series:
    """Resolve dated sell-tax bands; fixed sell_tax_bps is the fallback outside bands."""
    out = pd.Series(float(cost_spec.sell_tax_bps), index=pd.DatetimeIndex(dates), dtype=float)
    for band in cost_spec.sell_tax_schedule:
        start = pd.Timestamp(band.start).normalize()
        end = pd.Timestamp(band.end).normalize() if band.end is not None else None
        mask = out.index >= start
        if end is not None:
            mask &= out.index < end
        out.loc[mask] = float(band.bps)
    return out


def run_execution_with_dsl_costs(
    engine,
    close_prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    config,
    strategy_spec: StrategySpec,
    execution_assumptions,
    tradable_mask: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Run one deterministic execution path and apply fixed or dated DSL costs.

    Portfolio returns/turnover are independent of transaction-cost magnitude in
    the current target-weight engine, so a zero-cost execution is the canonical
    source for holdings, drift and turnover. Each named cost scenario is then
    applied to that same trade path, including historical sell-tax schedules.
    """
    base = engine.simulate_target_weight_portfolio(
        close_prices=close_prices,
        target_weights=target_weights,
        cost_assumptions=engine.TradingCostAssumptions(),
        execution_assumptions=execution_assumptions,
        tradable_mask=tradable_mask,
        initial_capital=config.initial_capital,
    )
    detail = base["daily_detail"].copy()
    trades = base["trades"].copy()
    idx = pd.DatetimeIndex(detail.index)
    portfolio_return = pd.to_numeric(
        detail["portfolio_return_before_cost"], errors="raise"
    ).astype(float)

    combined = pd.DataFrame({"Gross": base["daily_nav"]["Gross"].astype(float)}, index=idx)
    scenarios: dict[str, Any] = {}
    cost_meta: dict[str, Any] = {}

    for name, cost in strategy_spec.cost_scenarios.items():
        common_bps = (
            float(cost.commission_bps)
            + float(cost.spread_bps)
            + float(cost.slippage_bps)
            + float(cost.market_impact_bps)
        )
        tax_bps = _scheduled_sell_tax_bps(cost, idx)
        buy = trades["buy_turnover"].astype(float).reindex(idx)
        sell = trades["sell_turnover"].astype(float).reindex(idx)
        cost_fraction = (
            (buy + sell) * (common_bps / 10_000.0)
            + sell * (tax_bps / 10_000.0)
        )
        if (cost_fraction >= 1.0).any():
            raise RuntimeError(f"cost scenario {name} consumes >=100% of NAV on a trading day")
        net_return = (1.0 + portfolio_return) * (1.0 - cost_fraction) - 1.0
        net_nav = (1.0 + net_return).cumprod()
        combined[f"Net_{name}"] = net_nav

        trade_audit = trades.copy()
        trade_audit["sell_tax_bps"] = tax_bps
        trade_audit["cost_fraction"] = cost_fraction
        trade_audit["net_return"] = net_return
        trade_audit["net_nav"] = net_nav
        scenarios[name] = {
            "daily_nav": pd.DataFrame({"Gross": combined["Gross"], "Net": net_nav}),
            "daily_detail": detail.assign(cost_fraction=cost_fraction, net_return=net_return),
            "weights": base["weights"],
            "trades": trade_audit,
            "execution_schedule": base["execution_schedule"],
            "annualized_one_way_turnover": base["annualized_one_way_turnover"],
        }
        cost_meta[name] = {
            "commission_bps": cost.commission_bps,
            "sell_tax_bps": cost.sell_tax_bps,
            "spread_bps": cost.spread_bps,
            "slippage_bps": cost.slippage_bps,
            "market_impact_bps": cost.market_impact_bps,
            "sell_tax_schedule": [
                {"start": b.start, "end": b.end, "bps": b.bps}
                for b in cost.sell_tax_schedule
            ],
        }

    formal_daily, monthly, latest_meta = engine.complete_monthly_nav_from_daily(
        combined, as_of_date=config.as_of_date
    )
    formal_daily.attrs["market_calendar"] = config.market_calendar
    monthly.attrs["market_calendar"] = config.market_calendar
    period_results = engine.run_four_periods(monthly, config, formal_daily)
    return {
        "period_results": period_results,
        "formal_daily_nav": formal_daily,
        "formal_monthly_nav": monthly,
        "latest_daily_snapshot": latest_meta,
        "execution_scenarios": scenarios,
        "cost_scenarios": cost_meta,
    }


def run_strategy(spec_path: Path, repo_root: Path, output_dir: Path | None = None, *, postprocess: bool = True) -> dict[str, Any]:
    spec = load_strategy_spec(spec_path)
    plan = compile_execution_plan(spec)
    engine = load_project_engine(repo_root)
    panel = engine.load_krx_equity_panel(
        start=spec.period.start,
        end=spec.period.end,
        markets=spec.universe.markets,
        columns=required_panel_columns(spec),
        repo_root=repo_root,
    )
    dart_adapter = (
        DartValueFactorAdapter(repo_root)
        if any(f.source == "dart" for f in spec.factors)
        else None
    )
    target_weights, selections = build_target_weights_from_panel(
        panel, spec, dart_adapter=dart_adapter
    )
    assets = list(target_weights.columns)
    close, tradable = close_and_tradable_matrices(panel, assets)
    cfg, costs, execution = engine_inputs(spec, engine)
    if any(cost.sell_tax_schedule for cost in spec.cost_scenarios.values()):
        result = run_execution_with_dsl_costs(
            engine=engine,
            close_prices=close,
            target_weights=target_weights,
            config=cfg,
            strategy_spec=spec,
            execution_assumptions=execution,
            tradable_mask=tradable,
        )
    else:
        result = engine.run_execution_backtest(
            close_prices=close,
            target_weights=target_weights,
            config=cfg,
            cost_scenarios=costs,
            execution_assumptions=execution,
            tradable_mask=tradable,
        )

    out = output_dir or (repo_root / "results" / "dsl" / spec.strategy_id)
    out.mkdir(parents=True, exist_ok=True)
    daily = result["formal_daily_nav"].rename(columns=lambda c: f"NAV_{c}")
    daily.to_csv(out / "daily_nav.csv", index_label="Date")
    target_weights.to_csv(out / "target_weights.csv", index_label="signal_date")
    selections.to_csv(out / "selections.csv", index=False, encoding="utf-8-sig")
    (out / "execution_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "strategy_fingerprint.txt").write_text(spec.fingerprint() + "\n", encoding="utf-8")

    if postprocess:
        series = ",".join(daily.columns)
        cmd = [
            sys.executable, str(repo_root / POSTPROCESS_FILE),
            "--daily-csv", str(out / "daily_nav.csv"),
            "--series", series,
            "--title", spec.title,
            "--book-start", spec.period.book_start,
            "--book-end", spec.period.book_end,
            "--output-dir", str(out),
            "--initial-capital", str(spec.initial_capital),
            "--as-of-date", spec.period.as_of_date or spec.period.end,
        ]
        subprocess.run(cmd, cwd=repo_root, check=True)
    return {"spec": spec, "plan": plan, "engine_result": result, "output_dir": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy_json", type=Path)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    spec = load_strategy_spec(args.strategy_json)
    plan = compile_execution_plan(spec)
    if args.validate_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    run_strategy(args.strategy_json, args.repo_root.resolve(), args.output_dir)


if __name__ == "__main__":
    main()
