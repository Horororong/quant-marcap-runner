from __future__ import annotations

"""Ten independent long-only research portfolios on the shared DSL/PIT engine.

Only membership, target weights and daily NAV are produced here. CURRENT is
the sole performance calculator. D01 is best, D10 is worst; no long-short NAV
or one-account combination is inferred from these independent portfolios.
"""

from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd

from corporate_action_registry import load_corporate_actions
from execution_contract import DECILE_RESEARCH_CONTRACT
from strategy_dsl import StrategySpec, compile_execution_plan
from strategy_dsl_runner import (
    benchmark_coverage_audit,
    close_and_tradable_matrices,
    engine_inputs,
    execute_daily_nav,
    factor_provider_coverage_audit,
    load_benchmark_nav,
    load_project_engine,
    required_panel_columns,
    run_current_postprocess,
    scored_signals_from_panel,
)

DECILE_LABELS = tuple(f"D{i:02d}" for i in range(1, 11))


def partition_deciles(ranked: pd.DataFrame) -> pd.DataFrame:
    """Contiguous balanced partition of already filtered/scored eligible rows."""
    x = ranked.copy()
    x["Code"] = x["Code"].astype(str).str.zfill(6)
    if x["Code"].duplicated().any():
        raise AssertionError("decile universe has duplicate Code rows")
    score = pd.to_numeric(x["composite_score"], errors="coerce")
    if not np.isfinite(score.to_numpy(float)).all():
        raise ValueError("decile composite scores must be finite")
    n = len(x)
    if n < 10:
        raise RuntimeError(f"deciles requires at least 10 eligible codes; actual={n}")
    x["composite_score"] = score
    x = x.sort_values(["composite_score", "Code"]).reset_index(drop=True)
    quotient, remainder = divmod(n, 10)
    sizes = [quotient + int(i < remainder) for i in range(10)]
    x["decile"] = np.repeat(DECILE_LABELS, sizes)
    x["bucket_size"] = np.repeat(sizes, sizes)
    x["target_weight"] = 1.0 / x["bucket_size"]
    x["eligible_count"] = n
    return x


def build_decile_target_weights_from_panel(
    panel: pd.DataFrame,
    spec: StrategySpec,
    repo_root: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    if spec.portfolio.selection != "deciles":
        raise ValueError("portfolio.selection must be deciles")
    assets = sorted(panel["Code"].astype(str).str.zfill(6).unique())
    rows: dict[str, list[pd.Series]] = {label: [] for label in DECILE_LABELS}
    memberships = []
    audits = []
    for signal, ranked in scored_signals_from_panel(panel, spec, repo_root):
        membership = partition_deciles(ranked)
        membership["signal_date"] = signal
        memberships.append(membership)
        for label, group in membership.groupby("decile", sort=True):
            weights = pd.Series(0.0, index=assets, name=signal)
            weights.loc[group["Code"]] = group["target_weight"].to_numpy(float)
            rows[label].append(weights)
        boundary = membership["decile"].ne(membership["decile"].shift())
        tied_boundary = boundary & membership["composite_score"].eq(membership["composite_score"].shift())
        audits.append({
            "signal_date": signal,
            "eligible_count": len(membership),
            "bucket_count": 10,
            "minimum_bucket_size": int(membership["bucket_size"].min()),
            "maximum_bucket_size": int(membership["bucket_size"].max()),
            "ties_split_at_boundaries": int(tied_boundary.sum()),
        })
    weights = {label: pd.DataFrame(values).sort_index() for label, values in rows.items()}
    return weights, pd.concat(memberships, ignore_index=True), pd.DataFrame(audits)


def execute_decile_nav(
    panel: pd.DataFrame,
    spec: StrategySpec,
    targets: dict[str, pd.DataFrame],
    engine,
    corporate_actions: pd.DataFrame,
) -> dict[str, Any]:
    """Use the unchanged PROJECT execution and cost engine for every bucket."""
    assets = sorted(panel["Code"].astype(str).str.zfill(6).unique())
    close, tradable = close_and_tradable_matrices(panel, assets)
    cfg, costs, execution = engine_inputs(spec, engine)
    daily = pd.DataFrame(index=close.index)
    results = {}
    for label in DECILE_LABELS:
        tw = targets[label]
        used = set(tw.columns[tw.ne(0).any(axis=0)])
        # Retain verified successors even when never selected by this bucket.
        while not corporate_actions.empty:
            successors = set(corporate_actions.loc[
                corporate_actions["predecessor_code"].isin(used), "successor_code"
            ])
            if successors.issubset(used):
                break
            used.update(successors)
        missing = used - set(assets)
        if missing:
            raise RuntimeError(f"{label}: corporate-action successor missing from panel: {sorted(missing)}")
        codes = sorted(used)
        events = corporate_actions
        if not events.empty:
            events = events[events["predecessor_code"].isin(used)].copy()
        try:
            result = execute_daily_nav(
                engine=engine,
                close_prices=close.reindex(columns=codes),
                target_weights=tw.reindex(columns=codes, fill_value=0.0),
                cost_scenarios=costs,
                execution_assumptions=execution,
                initial_capital=cfg.initial_capital,
                tradable_mask=tradable.reindex(columns=codes),
                corporate_action_events=events,
            )
        except (RuntimeError, ValueError, AssertionError, KeyError) as exc:
            raise RuntimeError(f"{label}: decile execution failed; no price gaps are filled: {exc}") from exc
        results[label] = result
        for col in result["daily_nav"]:
            daily[f"NAV_{label}_{col}"] = result["daily_nav"][col]
    return {"daily_nav": daily, "decile_results": results}


def run_decile_strategy(
    spec: StrategySpec,
    repo_root: Path,
    output_dir: Path | None = None,
    *,
    postprocess: bool = True,
) -> dict[str, Any]:
    engine = load_project_engine(repo_root)
    panel = engine.load_krx_equity_panel(
        start=spec.period.start, end=spec.period.end,
        markets=spec.universe.markets, columns=required_panel_columns(spec),
        repo_root=repo_root,
    )
    targets, membership, audit = build_decile_target_weights_from_panel(panel, spec, repo_root)
    dates = pd.DatetimeIndex(pd.to_datetime(panel["Date"]).unique()).sort_values()
    benchmark_meta = benchmark_coverage_audit(repo_root, spec.benchmark, dates)
    events = load_corporate_actions(repo_root, start=dates.min(), end=dates.max(), asset_codes=set(panel["Code"]))
    result = execute_decile_nav(panel, spec, targets, engine, events)
    daily = result["daily_nav"]
    if spec.benchmark is not None:
        daily["NAV_Benchmark"] = load_benchmark_nav(repo_root, spec.benchmark, daily.index)
    coverage = factor_provider_coverage_audit(panel, spec, repo_root)
    plan = compile_execution_plan(spec)

    # Fail before writing a partial research result if any of the ten fails.
    out = output_dir or (repo_root / "results" / "dsl" / spec.strategy_id)
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "daily_nav.csv", index_label="Date")
    membership.to_csv(out / "decile_membership.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(out / "decile_partition_audit.csv", index=False)
    membership[["signal_date", "decile", "Code", "target_weight"]].to_csv(out / "target_weights.csv", index=False)
    (out / "execution_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "strategy_fingerprint.txt").write_text(spec.fingerprint() + "\n", encoding="utf-8")
    (out / "decile_contract.json").write_text(json.dumps(DECILE_RESEARCH_CONTRACT, ensure_ascii=False, indent=2), encoding="utf-8")
    if benchmark_meta is not None:
        (out / "benchmark_coverage.json").write_text(json.dumps(benchmark_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if not coverage.empty:
        coverage.to_csv(out / "factor_provider_coverage.csv", index=False)
    trade_rows, schedule_rows, action_rows = [], [], []
    for label, execution_result in result["decile_results"].items():
        bucket_dir = out / label
        bucket_dir.mkdir(exist_ok=True)
        targets[label].to_csv(bucket_dir / "target_weights.csv", index_label="signal_date")
        execution_result["daily_nav"].rename(columns=lambda c: f"NAV_{c}").to_csv(bucket_dir / "daily_nav.csv", index_label="Date")
        for scenario, execution in execution_result["execution_scenarios"].items():
            trade_rows.append(execution["trades"].reset_index().assign(decile=label, cost_scenario=scenario))
            schedule_rows.append(execution["execution_schedule"].assign(decile=label, cost_scenario=scenario))
            actions = execution["corporate_actions"]
            if not actions.empty:
                action_rows.append(actions.assign(decile=label, cost_scenario=scenario))
    pd.concat(trade_rows, ignore_index=True).to_csv(out / "execution_trades.csv", index=False)
    pd.concat(schedule_rows, ignore_index=True).to_csv(out / "execution_schedule.csv", index=False)
    if action_rows:
        pd.concat(action_rows, ignore_index=True).to_csv(out / "corporate_actions_applied.csv", index=False)
    if postprocess:
        run_current_postprocess(spec, repo_root, out, daily)
    return {"spec": spec, "plan": plan, "engine_result": result, "benchmark": benchmark_meta, "output_dir": out}
