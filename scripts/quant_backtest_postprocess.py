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
)


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


def load_daily_nav(path: Path, date_col: str, series_arg: str | None) -> pd.DataFrame:
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
    x = x.div(base, axis=1)
    x.index = pd.to_datetime(x.index).normalize()
    return x


def last_complete_month_end(as_of: pd.Timestamp) -> pd.Timestamp:
    as_of = pd.Timestamp(as_of).normalize()
    this_month_end = as_of.to_period("M").to_timestamp("M").normalize()
    if this_month_end <= as_of:
        return this_month_end
    return (as_of.to_period("M") - 1).to_timestamp("M").normalize()


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
    args = ap.parse_args()

    as_of = pd.Timestamp(args.as_of_date) if args.as_of_date else pd.Timestamp.today().normalize()
    args.as_of_date = as_of.strftime("%Y-%m-%d")

    daily_raw = load_daily_nav(args.daily_csv, args.date_col, args.series)
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
