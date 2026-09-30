from __future__ import annotations

"""Generic Strategy DSL v1 runner.

v1 runtime scope: KRX equity cross-sectional ranking strategies whose factor
inputs are fields already present in the PIT KRX daily panel. DART/derived
factor adapters are intentionally not faked here; they are the next extension.
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
from factor_registry import (
    build_external_provider,
    external_sources,
    fields_for_source,
    panel_factor_fields,
)

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
    fields.update(panel_factor_fields(spec.factors))
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


def rank_cross_section(
    cross_section: pd.DataFrame,
    spec: StrategySpec,
    external_factors: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = cross_section.copy()
    if external_factors is not None and not external_factors.empty:
        f = external_factors.copy()
        f["Code"] = f["Code"].astype(str).str.zfill(6)
        if f["Code"].duplicated().any():
            raise AssertionError("external_factors must have one row per Code at a signal date")
        overlap = [c for c in f.columns if c != "Code" and c in x.columns]
        if overlap:
            raise ValueError(f"external factor columns collide with panel columns: {overlap}")
        x = x.merge(f, on="Code", how="left")
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
            raise KeyError(f"factor field not present in panel: {fac.field}")
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
        rank = v.rank(method="average", pct=True, ascending=(fac.direction == "low"))
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
    repo_root: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = panel.copy()
    p["Date"] = pd.to_datetime(p["Date"]).dt.normalize()
    p["Code"] = p["Code"].astype(str).str.zfill(6)
    if p.duplicated(["Date", "Code"]).any():
        raise AssertionError("panel contains duplicate Date+Code")
    assets = sorted(p["Code"].unique())
    rows: list[pd.Series] = []
    selection_rows: list[pd.DataFrame] = []
    sources = external_sources(spec.factors)
    if sources and repo_root is None:
        raise ValueError("repo_root is required when external factor providers are used")
    providers = {
        source: build_external_provider(source, repo_root)
        for source in sources
    }

    for dt in signal_dates_from_panel(p, spec):
        cs = p[p["Date"] == dt].copy()
        external_frames: list[pd.DataFrame] = []
        for source, provider in providers.items():
            requested = fields_for_source(spec.factors, source)
            frame = provider.factor_frame(pd.Timestamp(dt), cs, requested)
            if frame["Code"].duplicated().any():
                raise AssertionError(f"{source} provider returned duplicate Code rows")
            external_frames.append(frame)

        external = None
        if external_frames:
            external = external_frames[0]
            for frame in external_frames[1:]:
                overlap = sorted((set(external.columns) & set(frame.columns)) - {"Code"})
                if overlap:
                    raise ValueError(f"external provider column collision: {overlap}")
                external = external.merge(frame, on="Code", how="outer", validate="one_to_one")

        selected, _ = rank_cross_section(cs, spec, external_factors=external)
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



def factor_provider_coverage_audit(
    panel: pd.DataFrame,
    spec: StrategySpec,
    repo_root: Path,
) -> pd.DataFrame:
    sources = external_sources(spec.factors)
    if not sources:
        return pd.DataFrame()
    providers = {
        source: build_external_provider(source, repo_root)
        for source in sources
    }
    rows: list[dict[str, Any]] = []
    for dt in signal_dates_from_panel(panel, spec):
        for provider in providers.values():
            rows.extend(provider.coverage_report(pd.Timestamp(dt)))
    return pd.DataFrame(rows)


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
        name: engine.TradingCostAssumptions(**vars(cost))
        for name, cost in spec.cost_scenarios.items()
    }
    execution = engine.ExecutionAssumptions(
        execution_lag_sessions=spec.execution.lag_sessions,
        execution_price=spec.execution.price,
    )
    return cfg, costs, execution


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
    target_weights, selections = build_target_weights_from_panel(panel, spec, repo_root=repo_root)
    assets = list(target_weights.columns)
    close, tradable = close_and_tradable_matrices(panel, assets)
    cfg, costs, execution = engine_inputs(spec, engine)
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
    coverage = factor_provider_coverage_audit(panel, spec, repo_root)
    if not coverage.empty:
        coverage.to_csv(out / "factor_provider_coverage.csv", index=False, encoding="utf-8-sig")
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
