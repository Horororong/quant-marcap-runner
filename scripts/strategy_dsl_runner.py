from __future__ import annotations

"""Generic Strategy DSL v1 runner.

Runtime scope: KRX equity cross-sectional ranking strategies with registered
KRX, DART PIT, and technical providers. Optional price-index benchmarks share
the exact strategy dates; canonical performance remains in CURRENT postprocess.
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

from strategy_dsl import BenchmarkSpec, StrategySpec, compile_execution_plan, load_strategy_spec
from execution_contract import EXECUTION_ENGINE_VERSION, PROJECT_TEMPLATE_VERSION
from corporate_action_registry import load_corporate_actions, load_corporate_action_gaps
from krx_history_audit import require_session_coverage
from factor_registry import (
    build_external_provider,
    external_filter_sources,
    external_sources,
    fields_for_source,
    filter_fields_for_source,
    panel_factor_fields,
    panel_filter_fields,
)

ENGINE_FILE = "scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py"
POSTPROCESS_FILE = "scripts/quant_backtest_postprocess.py"
BASE_PANEL_COLUMNS = ["Date", "Code", "Name", "Market", "Close", "Volume", "Amount", "Marcap", "ChangesRatio"]
BENCHMARK_INDEX_DIR = "data/indices"


def _load_benchmark_close(
    repo_root: Path,
    benchmark: BenchmarkSpec,
    dates: pd.DatetimeIndex,
) -> pd.Series:
    if benchmark is None:
        raise ValueError("benchmark is required")
    # Validate direct callers too; the symbol may never become an arbitrary path.
    benchmark = BenchmarkSpec.from_dict({"source": benchmark.source, "symbol": benchmark.symbol})
    symbol = benchmark.symbol
    path = repo_root / BENCHMARK_INDEX_DIR / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"benchmark index file not found: {path}")

    x = pd.read_csv(path, usecols=["Date", "Close"])
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce").dt.normalize()
    x["Close"] = pd.to_numeric(x["Close"], errors="coerce")
    if x["Date"].isna().any():
        raise ValueError(f"benchmark {symbol}: invalid Date rows")
    x = x.sort_values("Date")
    if x["Date"].duplicated().any():
        raise AssertionError(f"benchmark {symbol}: duplicate Date rows")

    s = x.set_index("Date")["Close"]
    idx = pd.DatetimeIndex(dates).normalize()
    if idx.empty or idx.hasnans or idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError("benchmark strategy dates must be non-empty, valid, unique, and increasing")
    aligned = s.reindex(idx)
    if aligned.isna().any():
        missing = [d.date().isoformat() for d in aligned.index[aligned.isna()][:12]]
        raise RuntimeError(
            f"benchmark {symbol}: missing exact strategy dates; examples={missing}"
        )
    if not np.isfinite(aligned.to_numpy(float)).all() or not (aligned > 0).all():
        raise RuntimeError(f"benchmark {symbol}: non-positive or non-finite close values")

    return aligned


def load_benchmark_nav(
    repo_root: Path,
    benchmark: BenchmarkSpec,
    dates: pd.DatetimeIndex,
) -> pd.Series:
    aligned = _load_benchmark_close(repo_root, benchmark, dates)
    nav = aligned / float(aligned.iloc[0])
    nav.name = "NAV_Benchmark"
    return nav


def benchmark_coverage_audit(
    repo_root: Path,
    benchmark: BenchmarkSpec | None,
    dates: pd.DatetimeIndex,
) -> dict[str, Any] | None:
    if benchmark is None:
        return None
    close = _load_benchmark_close(repo_root, benchmark, dates)
    return {
        "source": benchmark.source,
        "symbol": benchmark.symbol,
        "start": close.index.min().date().isoformat(),
        "end": close.index.max().date().isoformat(),
        "observations": int(len(close)),
        "exact_date_alignment": True,
        "return_basis": "price_index_close",
        "includes_dividends": False,
        "path": f"{BENCHMARK_INDEX_DIR}/{benchmark.symbol}.csv",
    }


def load_project_engine(repo_root: Path):
    path = repo_root / ENGINE_FILE
    spec = importlib.util.spec_from_file_location("quant_project_v216", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load project engine: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if getattr(module, "TEMPLATE_VERSION", None) != PROJECT_TEMPLATE_VERSION:
        raise RuntimeError(
            f"DSL expects project template {PROJECT_TEMPLATE_VERSION}; "
            f"got {getattr(module, 'TEMPLATE_VERSION', None)}"
        )
    if getattr(module, "EXECUTION_ENGINE_VERSION", None) != EXECUTION_ENGINE_VERSION:
        raise RuntimeError(
            f"DSL expects execution engine {EXECUTION_ENGINE_VERSION}; "
            f"got {getattr(module, 'EXECUTION_ENGINE_VERSION', None)}"
        )
    return module


def required_panel_columns(spec: StrategySpec) -> list[str]:
    fields = set(BASE_PANEL_COLUMNS)
    fields.update(panel_filter_fields(spec.universe.filters))
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


def score_cross_section(
    cross_section: pd.DataFrame,
    spec: StrategySpec,
    external_factors: pd.DataFrame | None = None,
) -> pd.DataFrame:
    x = cross_section.copy()
    x["Code"] = x["Code"].astype(str).str.zfill(6)
    if x["Code"].duplicated().any():
        raise AssertionError("cross_section must have one row per Code")
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
    return x


def _select_top_n(ranked: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    if spec.portfolio.selection != "top_n":
        raise ValueError("top_n selection required; use the decile execution path for deciles")
    n = spec.portfolio.number_of_positions
    if n is None or len(ranked) < n:
        raise RuntimeError(f"eligible universe {len(ranked)} is smaller than number_of_positions={n}")
    selected = ranked.head(n).copy()
    selected["target_weight"] = 1.0 / n
    return selected


def rank_cross_section(
    cross_section: pd.DataFrame,
    spec: StrategySpec,
    external_factors: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = score_cross_section(cross_section, spec, external_factors)
    factor_columns = [f"factor_rank__{f.name}" for f in spec.factors]
    return _select_top_n(ranked, spec), ranked[["Date", "Code", "Name", "Market", "composite_score", *factor_columns]].copy()


def scored_signals_from_panel(
    panel: pd.DataFrame,
    spec: StrategySpec,
    repo_root: Path | None = None,
):
    """Share PIT providers, filters and composite ranks across selection modes."""
    p = panel.copy()
    p["Date"] = pd.to_datetime(p["Date"]).dt.normalize()
    p["Code"] = p["Code"].astype(str).str.zfill(6)
    if p.duplicated(["Date", "Code"]).any():
        raise AssertionError("panel contains duplicate Date+Code")
    sources = sorted(
        set(external_sources(spec.factors))
        | set(external_filter_sources(spec.universe.filters))
    )
    if sources and repo_root is None:
        raise ValueError("repo_root is required when external factor providers are used")
    providers = {
        source: build_external_provider(source, repo_root, spec.rebalance.dart_period_policy)
        for source in sources
    }

    for dt in signal_dates_from_panel(p, spec):
        cs = p[p["Date"] == dt].copy()
        external_frames: list[pd.DataFrame] = []
        for source, provider in providers.items():
            requested = sorted(
                set(fields_for_source(spec.factors, source))
                | set(filter_fields_for_source(spec.universe.filters, source))
            )
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

        yield dt, score_cross_section(cs, spec, external_factors=external)


def build_target_weights_from_panel(
    panel: pd.DataFrame,
    spec: StrategySpec,
    repo_root: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    assets = sorted(panel["Code"].astype(str).str.zfill(6).unique())
    rows: list[pd.Series] = []
    selection_rows: list[pd.DataFrame] = []
    for dt, ranked in scored_signals_from_panel(panel, spec, repo_root):
        selected = _select_top_n(ranked, spec)
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
    sources = sorted(
        set(external_sources(spec.factors))
        | set(external_filter_sources(spec.universe.filters))
    )
    if not sources:
        return pd.DataFrame()
    providers = {
        source: build_external_provider(source, repo_root, spec.rebalance.dart_period_policy)
        for source in sources
    }
    rows: list[dict[str, Any]] = []
    for dt in signal_dates_from_panel(panel, spec):
        for source, provider in providers.items():
            requested = sorted(
                set(fields_for_source(spec.factors, source))
                | set(filter_fields_for_source(spec.universe.filters, source))
            )
            rows.extend(provider.coverage_report(pd.Timestamp(dt), requested))
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


def return_reference_matrix(panel: pd.DataFrame, assets: list[str]) -> pd.DataFrame:
    x = panel[["Date", "Code", "ChangesRatio"]].copy()
    x["Date"] = pd.to_datetime(x["Date"]).dt.normalize()
    x["Code"] = x["Code"].astype(str).str.zfill(6)
    x["ChangesRatio"] = pd.to_numeric(x["ChangesRatio"], errors="coerce") / 100.0
    return x.pivot(index="Date", columns="Code", values="ChangesRatio").reindex(columns=assets).sort_index()


def save_return_reference_audit(result: dict[str, Any], out: Path) -> tuple[dict, pd.DataFrame]:
    summaries = {}
    rows = []
    for scenario, execution in result["execution_scenarios"].items():
        summaries[scenario] = execution["return_reference_check"]
        fields = ["held_return_checked_assets", "verified_return_override_assets", "max_held_return_difference_bps"]
        rows.append(execution["daily_detail"][fields].reset_index().assign(cost_scenario=scenario))
    (out / "return_reference_audit.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = pd.concat(rows, ignore_index=True)
    checks.to_csv(out / "held_return_checks.csv", index=False)
    return summaries, checks



def execute_daily_nav(
    engine,
    close_prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_scenarios: dict[str, Any],
    execution_assumptions: Any,
    initial_capital: float,
    tradable_mask: pd.DataFrame | None = None,
    corporate_action_events: pd.DataFrame | None = None,
    reference_returns: pd.DataFrame | None = None,
    source_volumes: pd.DataFrame | None = None,
    corporate_action_gaps: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Convert deterministic target weights into full daily NAV only.

    Strategy DSL owns strategy interpretation and portfolio construction.
    PROJECT v2-16 owns execution, turnover and costs. Canonical performance
    metrics remain a separate CURRENT postprocess step.
    """
    if not cost_scenarios:
        raise ValueError("cost_scenarios must not be empty")

    combined_daily: pd.DataFrame | None = None
    gross_reference: pd.Series | None = None
    executions: dict[str, Any] = {}

    for name, cost in cost_scenarios.items():
        exout = engine.simulate_target_weight_portfolio(
            close_prices=close_prices,
            target_weights=target_weights,
            cost_assumptions=cost,
            execution_assumptions=execution_assumptions,
            tradable_mask=tradable_mask,
            initial_capital=initial_capital,
            corporate_action_events=corporate_action_events,
            reference_returns=reference_returns,
            source_volumes=source_volumes,
            corporate_action_gaps=corporate_action_gaps,
        )
        executions[name] = exout
        d = exout["daily_nav"]
        if gross_reference is None:
            gross_reference = d["Gross"].copy()
            combined_daily = pd.DataFrame({"Gross": gross_reference})
        elif not np.allclose(
            gross_reference.to_numpy(),
            d["Gross"].to_numpy(),
            rtol=0,
            atol=1e-12,
        ):
            raise AssertionError("Gross NAV changed across cost scenarios")
        combined_daily[f"Net_{name}"] = d["Net"]

    if combined_daily is None or combined_daily.empty:
        raise RuntimeError("execution produced no daily NAV")
    return {
        "daily_nav": combined_daily,
        "execution_scenarios": executions,
    }


def save_cash_exchange_audits(result: dict[str, Any], out: Path) -> None:
    # Clear only these generated artifacts after successful execution. A shorter
    # rerun must not retain an old receipt or another scenario's cash balances.
    for pattern in ("cash_entitlements.csv", "cash_payments.csv", "cash_balances_gross_*.csv", "cash_balances_net_*.csv"):
        for path in out.glob(pattern):
            if path.is_file():
                path.unlink()
    for key in ("cash_entitlements", "cash_payments"):
        rows = [execution[key].assign(cost_scenario=scenario)
                for scenario, execution in result["execution_scenarios"].items()
                if not execution[key].empty]
        if rows:
            pd.concat(rows, ignore_index=True).to_csv(out / f"{key}.csv", index=False)
    for scenario, execution in result["execution_scenarios"].items():
        if "CashReceivable" in execution["weights"]:
            for book, key in (("gross", "weights"), ("net", "net_weights")):
                execution[key][["Cash", "CashReceivable"]].to_csv(
                    out / f"cash_balances_{book}_{scenario}.csv", index_label="Date")


def run_current_postprocess(spec: StrategySpec, repo_root: Path, out: Path, daily: pd.DataFrame, *,
                            capture_output: bool = False, daily_csv: Path | None = None, report_periods: Path | None = None):
    series = ",".join(daily.columns)
    cmd = [
        sys.executable, str(repo_root / POSTPROCESS_FILE),
        "--daily-csv", str(daily_csv if daily_csv is not None else out / "daily_nav.csv"),
        "--series", series,
        "--title", spec.title,
        "--book-start", spec.period.book_start,
        "--book-end", spec.period.book_end,
        "--output-dir", str(out),
        "--initial-capital", str(spec.initial_capital),
        "--as-of-date", spec.period.as_of_date or spec.period.end,
    ]
    cmd.extend(["--market-calendar", "XKRX"])
    if report_periods is not None:
        cmd.extend(["--report-periods", str(report_periods)])
    if spec.benchmark is not None:
        cmd.extend(["--benchmark-series", "NAV_Benchmark"])
    return subprocess.run(cmd, cwd=repo_root, check=True, capture_output=capture_output, text=capture_output, timeout=300)


def run_strategy(spec_path: Path, repo_root: Path, output_dir: Path | None = None, *, postprocess: bool = True) -> dict[str, Any]:
    spec = load_strategy_spec(spec_path)
    if spec.portfolio.selection == "deciles":
        from strategy_dsl_deciles import run_decile_strategy
        return run_decile_strategy(spec, repo_root, output_dir, postprocess=postprocess)
    plan = compile_execution_plan(spec)
    engine = load_project_engine(repo_root)
    panel = engine.load_krx_equity_panel(
        start=spec.period.start,
        end=spec.period.end,
        markets=spec.universe.markets,
        columns=required_panel_columns(spec),
        repo_root=repo_root,
    )
    history_coverage = require_session_coverage(panel, spec.period.start, spec.period.end, spec.universe.markets)
    target_weights, selections = build_target_weights_from_panel(panel, spec, repo_root=repo_root)
    assets = list(target_weights.columns)
    close, tradable = close_and_tradable_matrices(panel, assets)
    cfg, costs, execution = engine_inputs(spec, engine)
    corporate_actions = load_corporate_actions(
        repo_root,
        start=close.index.min(),
        end=close.index.max(),
        asset_codes=set(assets),
    )
    result = execute_daily_nav(
        engine=engine,
        close_prices=close,
        target_weights=target_weights,
        cost_scenarios=costs,
        execution_assumptions=execution,
        initial_capital=cfg.initial_capital,
        tradable_mask=tradable,
        corporate_action_events=corporate_actions,
        corporate_action_gaps=load_corporate_action_gaps(repo_root),
        reference_returns=return_reference_matrix(panel, assets),
        source_volumes=panel.pivot(index="Date", columns="Code", values="Volume").reindex(index=close.index, columns=assets),
    )

    out = output_dir or (repo_root / "results" / "dsl" / spec.strategy_id)
    out.mkdir(parents=True, exist_ok=True)
    save_return_reference_audit(result, out)
    (out / "history_coverage.json").write_text(json.dumps(history_coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    daily = result["daily_nav"].rename(columns=lambda c: f"NAV_{c}")
    benchmark_meta = None
    if spec.benchmark is not None:
        benchmark_nav = load_benchmark_nav(repo_root, spec.benchmark, daily.index)
        daily["NAV_Benchmark"] = benchmark_nav.reindex(daily.index).to_numpy(float)
        benchmark_meta = benchmark_coverage_audit(repo_root, spec.benchmark, daily.index)
        (out / "benchmark_coverage.json").write_text(
            json.dumps(benchmark_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    daily.to_csv(out / "daily_nav.csv", index_label="Date")
    target_weights.to_csv(out / "target_weights.csv", index_label="signal_date")
    selections.to_csv(out / "selections.csv", index=False, encoding="utf-8-sig")
    first_execution = next(iter(result["execution_scenarios"].values()))
    ca_applied = first_execution.get("corporate_actions", pd.DataFrame())
    if isinstance(ca_applied, pd.DataFrame) and not ca_applied.empty:
        ca_applied.to_csv(out / "corporate_actions_applied.csv", index=False, encoding="utf-8-sig")
    save_cash_exchange_audits(result, out)
    coverage = factor_provider_coverage_audit(panel, spec, repo_root)
    if not coverage.empty:
        coverage.to_csv(out / "factor_provider_coverage.csv", index=False, encoding="utf-8-sig")
    (out / "execution_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "strategy_fingerprint.txt").write_text(spec.fingerprint() + "\n", encoding="utf-8")

    if postprocess:
        run_current_postprocess(spec, repo_root, out, daily)
    return {
        "spec": spec,
        "plan": plan,
        "engine_result": result,
        "benchmark": benchmark_meta,
        "output_dir": out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy_json", type=Path)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument(
        "--execution-only",
        action="store_true",
        help="build selections and daily NAV but skip canonical performance postprocess",
    )
    ap.add_argument("--report-periods", type=Path, help="official requested-period report JSON; incompatible with --execution-only")
    args = ap.parse_args()
    if args.validate_only:
        spec = load_strategy_spec(args.strategy_json)
        plan = compile_execution_plan(spec)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    from strategy_dsl_run import run_checked_strategy, exit_code_for_run
    try:
        result = run_checked_strategy(args.strategy_json, args.repo_root, args.output_dir,
                                      postprocess=not args.execution_only, report_periods=args.report_periods)
    except OSError as exc:
        # Output reservation errors must never modify a previous run.
        result = {"status": "failed", "phase": "output", "nav_ready": False, "report_ready": False,
                  "error": {"type": type(exc).__name__, "message": str(exc)}}
    print(json.dumps({key: value for key, value in result.items() if key != "artifacts"},
                     ensure_ascii=False, indent=2, allow_nan=False))
    if result["status"] != "ok":
        print(result["error"]["message"], file=sys.stderr)
    raise SystemExit(exit_code_for_run(result))


if __name__ == "__main__":
    main()
