from __future__ import annotations

"""
Canonical post-processor for quant backtests.

Strategy-specific code should calculate DAILY NAV only.
This script is the single path for:
- monthly NAV derivation
- 4 standard periods
- CAGR / volatility / Sharpe
- daily MDD / recovery
- compact ChatGPT chart payload
- 9-chart render manifest

Example
-------
python scripts/quant_backtest_postprocess.py \
  --daily-csv results/my_strategy/daily_nav.csv \
  --series NAV_Gross,NAV_Net,NAV_Benchmark \
  --title "My strategy" \
  --book-start 2000-01-01 \
  --book-end 2021-12-31 \
  --output-dir results/my_strategy
"""

from pathlib import Path
import argparse
import json
from dataclasses import replace
from importlib.metadata import version

import numpy as np
import pandas as pd

from quant_backtest_template_CURRENT import (
    BacktestConfig,
    TEMPLATE_VERSION,
    combine_period_payloads,
    run_four_periods,
    assert_daily_session_coverage,
    calculate_benchmark_statistics,
    standard_period_windows_from_dates,
    run_requested_periods, validate_report_periods, dashboard_period_data,
    REQUESTED_REPORT_CONTRACT_VERSION,
)
from quant_report_dashboard import write_dashboard


PERIOD_CHART_ORDER = [
    ("from_2001", "cumulative_wealth"),
    ("from_2001", "log2_wealth"),
    ("from_2001", "drawdown"),
    ("from_2021", "cumulative_wealth"),
    ("from_2021", "log2_wealth"),
    ("from_2021", "drawdown"),
    ("longest", "cumulative_wealth"),
    ("longest", "log2_wealth"),
    ("longest", "drawdown"),
]


def _parse_series_arg(raw: str | None, columns: list[str]) -> list[str]:
    if raw:
        cols = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        cols = [c for c in columns if c == "NAV" or c.startswith("NAV_")]
    if not cols:
        raise ValueError(
            "--series를 지정하거나 CSV에 NAV / NAV_* 열을 두어야 합니다. "
            "Turnover/Cost 같은 보조열을 NAV로 오인하지 않도록 자동선택 범위를 제한합니다."
        )
    missing = [c for c in cols if c not in columns]
    if missing:
        raise ValueError(f"daily CSV에 요청한 NAV 열이 없습니다: {missing}")
    return cols


def load_daily_nav(path: Path, date_col: str, series_arg: str | None, *, preserve_origin: bool = False) -> pd.DataFrame:
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise ValueError(f"날짜 열 '{date_col}'이 없습니다. 실제 열={list(df.columns)}")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    if df[date_col].isna().any():
        raise ValueError("날짜 파싱 실패 행이 있습니다.")

    df = df.set_index(date_col).sort_index()
    if df.index.duplicated().any():
        dup = df.index[df.index.duplicated()][0]
        raise ValueError(f"중복 날짜가 있습니다: {dup}")

    cols = _parse_series_arg(series_arg, list(df.columns))
    x = df[cols].apply(pd.to_numeric, errors="coerce")

    # 모든 비교 시리즈가 실제로 동시에 존재하는 첫 날부터 사용한다.
    if preserve_origin and x.isna().any().any():
        raise ValueError("requested report NAV has missing values; no silent common-start shift")
    common = x.dropna(how="any")
    if common.empty:
        raise ValueError("모든 NAV 시리즈가 동시에 존재하는 구간이 없습니다.")
    common_start = common.index[0]
    x = x.loc[common_start:].copy()
    if x.isna().any().any():
        bad = x.isna().sum()
        bad = {k: int(v) for k, v in bad.items() if v}
        raise ValueError(f"공통 시작일 이후 NAV 결측치가 있습니다: {bad}")

    if not np.isfinite(x.to_numpy(dtype=float)).all():
        raise ValueError("NAV에 무한대/비정상 값이 있습니다.")
    if not (x > 0).all().all():
        raise ValueError("NAV는 전 구간에서 0보다 커야 합니다.")

    # 전략별 스크립트의 10,000/100/1 등 임의 기준을 제거한다.
    # 이후 성과 계산은 CURRENT 템플릿의 1.0 누적배수 계약만 사용한다.
    base = x.iloc[0].astype(float)
    if not preserve_origin:
        x = x.div(base, axis=1)
    x.index = pd.to_datetime(x.index).normalize()
    return x


def last_complete_month_end(as_of: pd.Timestamp) -> pd.Timestamp:
    as_of = pd.Timestamp(as_of).normalize()
    this_month_end = as_of.to_period("M").to_timestamp("M").normalize()
    if this_month_end <= as_of:
        return this_month_end
    return (as_of.to_period("M") - 1).to_timestamp("M").normalize()


def canonical_report_readiness(dates: pd.DatetimeIndex, config: BacktestConfig) -> dict:
    """Check canonical date/period requirements without fabricating a NAV."""
    dates = pd.DatetimeIndex(dates).normalize()
    if dates.empty or dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("report source dates must be nonempty, unique and ordered")
    if config.as_of_date is None:
        raise ValueError("report readiness requires an explicit as_of_date")
    as_of = pd.Timestamp(config.as_of_date).normalize()
    dates = dates[dates <= last_complete_month_end(as_of)]
    if dates.empty:
        raise ValueError("no source dates before the last complete month")
    monthly_dates = dates.to_period("M").unique().to_timestamp("M")
    windows = standard_period_windows_from_dates(monthly_dates, config)
    for name, (start, end, _) in windows.items():
        if start > end:
            raise ValueError(f"canonical period {name} has no available source history")
    if config.market_calendar:
        # This frame contains only actual/coverage-verified dates, no NAV values.
        assert_daily_session_coverage(pd.DataFrame(index=dates), dates[0], monthly_dates[-1], config.market_calendar)
    return {
        "ready": True,
        "performance_template_version": TEMPLATE_VERSION,
        "as_of_date": as_of.date().isoformat(),
        "periods": {key: {"start": start.date().isoformat(), "end": end.date().isoformat()}
                    for key, (start, end, _) in windows.items()},
        "scope": "date requirements only; NAV and canonical report still require runtime validation",
    }


def derive_complete_monthly(daily: pd.DataFrame, as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = last_complete_month_end(as_of)
    d = daily.loc[daily.index <= cutoff].copy()
    if d.empty:
        raise ValueError(f"완결 월말 {cutoff.date()} 이전 일별 NAV가 없습니다.")

    monthly = d.groupby(d.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    monthly = monthly.sort_index()

    expected = pd.period_range(monthly.index[0].to_period("M"), monthly.index[-1].to_period("M"), freq="M")
    actual = monthly.index.to_period("M")
    if len(actual) != len(expected):
        missing = expected.difference(actual)
        raise ValueError(f"월별 NAV 중간 월 누락: {[str(x) for x in missing[:12]]}")

    return d, monthly


def flatten_metrics(results: dict) -> pd.DataFrame:
    rows = []
    for period_key, result in results.items():
        m = result["metrics"].reset_index().rename(columns={"index": "전략"})
        m.insert(0, "period", period_key)
        m.insert(1, "period_label", result["label"])
        rows.append(m)
    return pd.concat(rows, ignore_index=True)


def report_context(daily_csv: Path, repo_root: Path, title: str) -> tuple[str, dict, list[str]]:
    run_dir = daily_csv.parent.parent
    diagnostics = {}
    for name in ("strategy_normalized.json", "execution_plan.json", "preflight.json", "report_readiness.json"):
        path = run_dir / name
        if path.is_file():
            diagnostics[name] = json.loads(path.read_text())
    kit = repo_root / "kit_manifest.json"
    if kit.is_file():
        manifest = json.loads(kit.read_text())
        diagnostics.update(kit_id=manifest['kit_id'], source_revision=manifest['source_revision'])
    raw = diagnostics.get("strategy_normalized.json")
    limits = ["$10,000은 NAV에 적용한 표준화 비교값입니다. 환율 미반영이며 추가 납입은 없습니다.",
              "벤치마크와 기업행동의 반영 범위는 입력 자료 계약을 따릅니다. 과거 성과는 미래 수익을 보장하지 않습니다."]
    if raw:
        factors = ', '.join(f"{f['name']}({f['direction']})" for f in raw['factors'])
        summary = f"{', '.join(raw['universe']['markets'])} · {factors} · {raw['portfolio'].get('number_of_positions', '10분위')} · 선택 월 {raw['rebalance']['months']} 말 신호 · {raw['execution']['lag_sessions']} 거래일 뒤 {raw['execution']['price']} 체결"
        limits.append("고정 비용은 요청 DSL의 가정이며 실제 과거 세율·시장충격을 모두 검증한 결과가 아닙니다.")
        if raw.get('metadata'):
            diagnostics['strategy_scope'] = raw['metadata']
    else:
        summary = title
    return summary, diagnostics, limits


def dashboard_payload(periods: dict, columns: list[str], config: BacktestConfig, *, benchmark: str | None,
                      mode: str, complete: bool, daily_csv: Path, repo_root: Path) -> dict:
    meta, portfolios, costs = {}, set(), {'gross': '비용 전'}
    for name in columns:
        if name == benchmark:
            meta[name] = {'kind': 'benchmark', 'portfolio': None, 'cost': None, 'label': '벤치마크'}
            continue
        short = name.removeprefix('NAV_')
        portfolio = short.split('_', 1)[0] if short.startswith('D') and short[:3][1:].isdigit() else 'strategy'
        if portfolio != 'strategy':
            short = short[4:]
        cost = 'gross' if short == 'Gross' else short.removeprefix('Net_')
        label = '비용 전' if cost == 'gross' else '비용 후: ' + cost
        costs[cost] = label
        portfolios.add(portfolio)
        meta[name] = {'kind': 'strategy', 'portfolio': portfolio, 'cost': cost,
                      'label': (portfolio + ' · ' if portfolio != 'strategy' else '') + label}
    summary, diagnostics, limits = report_context(daily_csv, repo_root, config.title)
    return {'schema_version': 1, 'performance_template_version': TEMPLATE_VERSION,
            'requested_report_contract_version': REQUESTED_REPORT_CONTRACT_VERSION, 'mode': mode,
            'title': config.title, 'strategy_summary': summary, 'periods': periods, 'series_meta': meta,
            'portfolios': sorted(portfolios), 'cost_options': costs, 'report_complete': complete,
            'limitations': limits, 'diagnostics': diagnostics,
            'calculation_notes': [f"CURRENT {TEMPLATE_VERSION} · 무위험 연이율 {config.risk_free_rate:.2%}",
                                  "Sharpe: 완결 월 수익률의 평균 초과수익 / 표본 표준편차 × √12; 월 무위험수익=(1+연이율)^(1/12)-1",
                                  "변동성: 완결 월 표본 표준편차 × √12; 표본 2개 이상",
                                  "CAGR: 사용자 기간은 실제 기준일~종료일 경과일/365.2425, 최소 365일; 정식 4기간은 기존 CURRENT 기준",
                                  "MDD·회복기간: 축약 전 전체 NAV; 회복기간은 달력일, 미회복 구간은 종료일까지 포함",
                                  "선택 기간의 수익은 시작 직전 NAV 기준; 최장기간의 최초 행은 검증된 초기자산",
                                  "벤치마크: 한국 지수 Close는 가격지수·배당 미반영" if benchmark else "벤치마크 미지정"]}


def write_requested_report(daily: pd.DataFrame, config: BacktestConfig, periods: list[dict], out: Path,
                           *, benchmark: str | None, daily_csv: Path, repo_root: Path) -> dict:
    cfg = replace(config, initial_capital=10000.0)
    result = run_requested_periods(daily, cfg, periods)
    public, metric_rows, stats_rows = {}, [], []
    for key, row in result['periods'].items():
        public[key] = {k: v for k, v in row.items() if k not in ('metrics_frame', 'daily_nav_frame')}
        if not row['ready']:
            continue
        m = row['metrics_frame'].reset_index()
        m.insert(0, 'period', key)
        m.insert(1, 'period_label', row['label'])
        m['actual_start'], m['actual_end'] = row['actual_start'], row['actual_end']
        metric_rows.append(m)
        if benchmark:
            for col in daily.columns:
                if col != benchmark:
                    stats = calculate_benchmark_statistics(row['daily_nav_frame'], col, benchmark, cfg, requested_period=True)
                    stats_rows.append({'period': key, 'strategy': col, 'benchmark': benchmark, **stats})
    payload = dashboard_payload(public, list(daily.columns), cfg, benchmark=benchmark,
                                mode='requested_period_report', complete=result['readiness']['complete'],
                                daily_csv=daily_csv, repo_root=repo_root)
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / 'daily_nav_canonical.csv', index_label='Date')
    metrics = pd.concat(metric_rows, ignore_index=True) if metric_rows else pd.DataFrame(columns=['period', 'period_label', '전략'])
    metrics.to_csv(out / 'metrics_CURRENT.csv', index=False)
    if benchmark:
        pd.DataFrame(stats_rows, columns=['period','strategy','benchmark','tracking_error','information_ratio','beta','alpha_annualized_arithmetic','downside_capture']).to_csv(out / 'benchmark_statistics_CURRENT.csv', index=False)
    manifest = {'template_version': TEMPLATE_VERSION, 'mode': 'requested_period_report',
                'requested_report_contract_version': REQUESTED_REPORT_CONTRACT_VERSION,
                'single_source_of_truth': 'scripts/quant_backtest_template_CURRENT.py',
                'source_daily_csv': str(daily_csv), 'market_calendar': cfg.market_calendar,
                'benchmark_series': benchmark, 'readiness': result['readiness'], 'periods': public,
                'dashboard_payload': payload, 'render_mode': 'three_interactive_charts_shared_period_selector',
                'dashboard_file': 'report_CURRENT.html'}
    (out / 'chat_manifest_CURRENT.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))
    write_dashboard(payload, out / 'report_CURRENT.html')
    return manifest


def build_manifest(results: dict, combined_payload: dict, args: argparse.Namespace) -> dict:
    periods = {}
    for key, result in results.items():
        p = result["chat_payload"]
        periods[key] = {
            "label": result["label"],
            "monthly_start": p["monthly_start"],
            "monthly_end": p["monthly_end"],
            "monthly_observations": p["monthly_observations"],
            "risk_frequency": p["risk_frequency"],
            "risk_observations_full": p["risk_observations"],
            "drawdown_chart_observations": p.get("drawdown_chart_observations"),
            "drawdown_chart_max_points": p.get("drawdown_chart_max_points"),
        }

    return {
        "template_version": TEMPLATE_VERSION,
        "single_source_of_truth": "scripts/quant_backtest_template_CURRENT.py",
        "strategy_code_responsibility": "daily NAV only; do not recalculate performance metrics in strategy scripts",
        "source_daily_csv": str(args.daily_csv),
        "title": args.title,
        "book_start": args.book_start,
        "book_end": args.book_end,
        "as_of_date": args.as_of_date,
        "market_calendar": args.market_calendar,
        "calendar_package_version": version("exchange_calendars") if args.market_calendar else None,
        "daily_coverage_policy": "exact named-exchange sessions; failure stops report" if args.market_calendar else "legacy weekday heuristic; monthly_fallback explicitly labeled",
        "risk_free_rate_annual": args.risk_free_rate,
        "benchmark_series": args.benchmark_series,
        "benchmark_statistics_file": "benchmark_statistics_CURRENT.csv" if args.benchmark_series else None,
        "benchmark_return_basis": "input NAV basis; DSL index benchmarks are price-only, without dividends",
        "metric_definitions": {
            "Sortino": "annual arithmetic monthly excess mean / annualized RMS of min(monthly excess, 0); MAR=monthly risk-free rate; zero downside => NaN",
            "Calmar": "CAGR / abs(MDD); zero drawdown => NaN; see MDD_source",
            "monthly_win_rate": "fraction of complete statistical months with return > 0; zero months are not wins",
            "benchmark_statistics": "monthly TE, IR, covariance beta, arithmetic annual alpha, mean-return downside capture; partial inception month excluded",
        },
        "periods": periods,
        "render_mode": "version_1_9_inline_charts",
        "render_order": [
            {"period": p, "chart": c} for p, c in PERIOD_CHART_ORDER
        ],
        "chart_payload": combined_payload,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-csv", type=Path, required=True)
    ap.add_argument("--date-col", default="Date")
    ap.add_argument("--series", default=None, help="comma-separated NAV column names; default: NAV or NAV_*")
    ap.add_argument("--title", required=True)
    ap.add_argument("--book-start", required=True)
    ap.add_argument("--book-end", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--initial-capital", type=float, default=10_000_000.0)
    ap.add_argument("--as-of-date", default=None)
    ap.add_argument("--market-calendar", default=None, help="e.g. XKRX or XNYS; exact daily session coverage required")
    ap.add_argument("--risk-free-rate", type=float, default=0.0, help="annual decimal risk-free rate")
    ap.add_argument("--benchmark-series", default=None, help="explicit NAV column used as benchmark; no inference")
    ap.add_argument("--report-periods", type=Path, help="explicit requested-period report specification JSON; default preserves formal four periods")
    args = ap.parse_args()

    as_of = pd.Timestamp(args.as_of_date) if args.as_of_date else pd.Timestamp.today().normalize()
    args.as_of_date = as_of.strftime("%Y-%m-%d")

    daily_raw = load_daily_nav(args.daily_csv, args.date_col, args.series, preserve_origin=bool(args.report_periods))
    if args.report_periods:
        cfg = BacktestConfig(title=args.title, as_of_date=args.as_of_date, market_calendar=args.market_calendar,
                             risk_free_rate=args.risk_free_rate)
        if args.benchmark_series and args.benchmark_series not in daily_raw.columns:
            raise ValueError('explicit benchmark column missing')
        manifest = write_requested_report(daily_raw, cfg, validate_report_periods(json.loads(args.report_periods.read_text())),
                                          args.output_dir, benchmark=args.benchmark_series, daily_csv=args.daily_csv,
                                          repo_root=Path(__file__).resolve().parents[1])
        print(json.dumps({'mode': manifest['mode'], 'ready': manifest['readiness']['ready'],
                          'complete': manifest['readiness']['complete'], 'dashboard': str(args.output_dir / 'report_CURRENT.html')}))
        return
    daily, monthly = derive_complete_monthly(daily_raw, as_of)
    if args.market_calendar:
        # Full supplied history and formal ending month, before creating outputs.
        assert_daily_session_coverage(daily_raw, daily_raw.index[0], daily_raw.index[-1], args.market_calendar)
        assert_daily_session_coverage(daily, daily.index[0], monthly.index[-1], args.market_calendar)
    if args.benchmark_series and args.benchmark_series not in daily.columns:
        raise ValueError(f"benchmark NAV column is missing: {args.benchmark_series}")

    cfg = BacktestConfig(
        title=args.title,
        initial_capital=args.initial_capital,
        book_start=args.book_start,
        book_end=args.book_end,
        as_of_date=args.as_of_date,
        standard_end_year=as_of.year,
        market_calendar=args.market_calendar,
        risk_free_rate=args.risk_free_rate,
    )

    results = run_four_periods(monthly, cfg, daily)
    chart_payloads = [
        results[k]["chat_payload"]
        for k in ("from_2001", "from_2021", "longest")
    ]
    combined = combine_period_payloads(*chart_payloads)
    metrics = flatten_metrics(results)

    benchmark_rows = []
    if args.benchmark_series:
        for key, result in results.items():
            for col in monthly.columns:
                if col == args.benchmark_series:
                    continue
                stats = calculate_benchmark_statistics(result["monthly_nav"], col, args.benchmark_series, cfg)
                benchmark_rows.append({"period": key, "strategy": col, "benchmark": args.benchmark_series, **stats})

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    daily.to_csv(out / "daily_nav_canonical.csv", index_label="Date")
    monthly.to_csv(out / "monthly_nav_canonical.csv", index_label="Date")
    metrics.to_csv(out / "metrics_CURRENT.csv", index=False)

    if args.benchmark_series:
        pd.DataFrame(benchmark_rows, columns=["period", "strategy", "benchmark", "tracking_error", "information_ratio", "beta", "alpha_annualized_arithmetic", "downside_capture"]).to_csv(out / "benchmark_statistics_CURRENT.csv", index=False)
    else:
        (out / "benchmark_statistics_CURRENT.csv").unlink(missing_ok=True)

    manifest = build_manifest(results, combined, args)
    dashboard_periods = {}
    for key, row in results.items():
        nav = row['daily_nav'] if row['daily_nav'] is not None else row['monthly_nav']
        dashboard_periods[key] = dashboard_period_data(nav, row['metrics'], row['label'],
                                                       baseline_date=nav.attrs.get('baseline_date'), calendar=cfg.market_calendar)
    dashboard = dashboard_payload(dashboard_periods, list(daily.columns), cfg, benchmark=args.benchmark_series,
                                  mode='canonical_report', complete=True, daily_csv=args.daily_csv,
                                  repo_root=Path(__file__).resolve().parents[1])
    manifest['dashboard_payload'] = dashboard
    manifest['dashboard_file'] = 'report_CURRENT.html'
    write_dashboard(dashboard, out / 'report_CURRENT.html')
    (out / "chat_manifest_CURRENT.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"TEMPLATE={TEMPLATE_VERSION}")
    print(f"DAILY={daily.index.min().date()}..{daily.index.max().date()} rows={len(daily)}")
    print(f"MONTHLY={monthly.index.min().date()}..{monthly.index.max().date()} rows={len(monthly)}")
    print("OUTPUTS:")
    print(out / "metrics_CURRENT.csv")
    print(out / "chat_manifest_CURRENT.json")


if __name__ == "__main__":
    main()
