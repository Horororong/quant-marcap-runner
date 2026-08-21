from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 표준 백테스트 템플릿 v1
# - 일별 NAV
# - t일 종가까지의 정보로 목표비중 산출
# - 기본 체결은 t+1 거래일에 반영(look-ahead 방지)
# - 거래비용 차감 전/후 NAV
# - LOG2 누적자산 그래프
# - 일별 Drawdown 그래프
# - CAGR / Vol / MDD / Sharpe / Sortino / Calmar
# - 월간 승률 / 월간 손익비 / 연도별 수익률 / 회전율
# ============================================================

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BacktestConfig:
    strategy_name: str = "strategy_name"
    price_csv: Path = ROOT / "data" / "derived" / "daily" / "adj_close_daily.csv"
    output_dir: Path = ROOT / "results" / "standard_backtest_v1"

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    initial_capital: float = 10_000.0
    one_way_cost_bps: float = 5.0

    # Sharpe / Sortino
    annualization: int = 252
    risk_free_annual: float = 0.0

    # 선택적 벤치마크. price_csv 안의 컬럼명이어야 함.
    benchmark_ticker: Optional[str] = None


# ============================================================
# 1. 데이터 로더
# ============================================================

def load_price_panel(config: BacktestConfig) -> pd.DataFrame:
    if not config.price_csv.exists():
        raise FileNotFoundError(f"가격 파일이 없습니다: {config.price_csv}")

    df = pd.read_csv(config.price_csv)

    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()

    if config.start_date:
        df = df.loc[pd.Timestamp(config.start_date):]
    if config.end_date:
        df = df.loc[:pd.Timestamp(config.end_date)]

    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(how="all")

    if df.empty:
        raise RuntimeError("백테스트 구간에 유효한 가격 데이터가 없습니다.")

    if not df.index.is_monotonic_increasing:
        raise RuntimeError("가격 데이터 날짜 정렬에 문제가 있습니다.")

    if df.index.has_duplicates:
        raise RuntimeError("가격 데이터에 중복 날짜가 있습니다.")

    return df


# ============================================================
# 2. 전략 규칙
#    이 함수만 전략별로 교체하는 것이 핵심.
#
#    반환값:
#      index = 가격 데이터 날짜
#      columns = 자산 티커
#      values = 목표 비중 (0~1)
#
#    중요:
#      t일 목표비중은 t일 종가까지 이용 가능한 정보만 사용해야 한다.
#      실제 포트폴리오에는 아래 run_backtest()에서 자동으로 1일 shift되어
#      t+1 거래일부터 반영된다.
# ============================================================

def build_target_weights(prices: pd.DataFrame) -> pd.DataFrame:
    """
    예시 기준전략: 모든 자산 동일가중, 매년 첫 거래일 리밸런싱.

    새 전략을 만들 때는 이 함수만 바꿔도 된다.
    신호 계산에서 미래 데이터를 사용하지 말 것.
    """

    valid_assets = [c for c in prices.columns if prices[c].notna().any()]
    if not valid_assets:
        raise RuntimeError("투자 가능한 자산이 없습니다.")

    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)

    # 각 연도의 첫 거래일에만 목표비중 생성
    rebalance_dates = prices.groupby(prices.index.year).head(1).index

    for dt in rebalance_dates:
        available = [c for c in valid_assets if pd.notna(prices.loc[dt, c])]
        if not available:
            continue

        w = 1.0 / len(available)
        weights.loc[dt, :] = 0.0
        weights.loc[dt, available] = w

    # 신호가 없는 날은 직전 목표비중 유지
    weights = weights.ffill().fillna(0.0)

    # 합계 검증
    sums = weights.sum(axis=1)
    invalid = (sums > 1.000001) | (sums < -1e-12)
    if invalid.any():
        bad_dates = list(weights.index[invalid][:5])
        raise RuntimeError(f"목표비중 합계 오류. 예시 날짜: {bad_dates}")

    return weights


# ============================================================
# 3. 핵심 백테스트 엔진
# ============================================================

def run_backtest(prices: pd.DataFrame, target_weights: pd.DataFrame, config: BacktestConfig):
    prices = prices.copy()
    target_weights = target_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)

    asset_returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # t일 종가까지 계산한 목표비중 -> t+1 거래일부터 반영
    held_weights = target_weights.shift(1).fillna(0.0)

    gross_return = (held_weights * asset_returns).sum(axis=1)

    # 목표비중 변화 기준 회전율. 첫 진입도 거래로 계산.
    turnover = target_weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = target_weights.iloc[0].abs().sum()

    one_way_cost = config.one_way_cost_bps / 10_000.0

    # 비중 변경은 다음 거래일부터 적용되므로 비용도 실제 반영일에 맞춰 1일 shift
    cost_return = turnover.shift(1).fillna(0.0) * one_way_cost
    net_return = gross_return - cost_return

    gross_nav = config.initial_capital * (1.0 + gross_return).cumprod()
    net_nav = config.initial_capital * (1.0 + net_return).cumprod()

    out = pd.DataFrame({
        "gross_return": gross_return,
        "net_return": net_return,
        "turnover": turnover,
        "cost_return": cost_return,
        "gross_nav": gross_nav,
        "net_nav": net_nav,
    })

    # 선택적 벤치마크
    if config.benchmark_ticker:
        if config.benchmark_ticker not in prices.columns:
            raise KeyError(f"benchmark_ticker가 가격 패널에 없습니다: {config.benchmark_ticker}")

        bench_ret = prices[config.benchmark_ticker].pct_change(fill_method=None).fillna(0.0)
        bench_nav = config.initial_capital * (1.0 + bench_ret).cumprod()
        out["benchmark_return"] = bench_ret
        out["benchmark_nav"] = bench_nav

    return out, held_weights


# ============================================================
# 4. 성과지표
# ============================================================

def annualized_return(nav: pd.Series) -> float:
    nav = nav.dropna()
    if len(nav) < 2:
        return np.nan

    days = (nav.index[-1] - nav.index[0]).days
    if days <= 0 or nav.iloc[0] <= 0 or nav.iloc[-1] <= 0:
        return np.nan

    years = days / 365.2425
    return (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0


def max_drawdown(nav: pd.Series):
    running_max = nav.cummax()
    dd = nav / running_max - 1.0

    trough = dd.idxmin()
    mdd = float(dd.loc[trough])
    peak = nav.loc[:trough].idxmax()

    after = nav.loc[trough:]
    peak_value = float(nav.loc[peak])
    recovered = after[after >= peak_value]
    recovery = recovered.index[0] if len(recovered) else pd.NaT

    if pd.isna(recovery):
        recovery_days = np.nan
    else:
        recovery_days = (recovery - peak).days

    return mdd, peak, trough, recovery, recovery_days, dd


def sharpe_ratio(returns: pd.Series, config: BacktestConfig) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return np.nan

    rf_daily = (1.0 + config.risk_free_annual) ** (1.0 / config.annualization) - 1.0
    excess = r - rf_daily
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan

    return float(excess.mean() / sd * np.sqrt(config.annualization))


def sortino_ratio(returns: pd.Series, config: BacktestConfig) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return np.nan

    rf_daily = (1.0 + config.risk_free_annual) ** (1.0 / config.annualization) - 1.0
    excess = r - rf_daily
    downside = excess[excess < 0]

    if len(downside) == 0:
        return np.nan

    downside_sd = downside.std(ddof=1)
    if downside_sd == 0 or np.isnan(downside_sd):
        return np.nan

    return float(excess.mean() / downside_sd * np.sqrt(config.annualization))


def monthly_statistics(returns: pd.Series):
    monthly = (1.0 + returns).resample("ME").prod() - 1.0
    monthly = monthly.dropna()

    if len(monthly) == 0:
        return np.nan, np.nan, monthly

    win_rate = float((monthly > 0).mean())

    pos = monthly[monthly > 0]
    neg = monthly[monthly < 0]

    if len(pos) == 0 or len(neg) == 0:
        pnl_ratio = np.nan
    else:
        pnl_ratio = float(pos.mean() / abs(neg.mean()))

    return win_rate, pnl_ratio, monthly


def calculate_metrics(bt: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    nav = bt["net_nav"]
    ret = bt["net_return"]

    cagr = annualized_return(nav)
    mdd, peak, trough, recovery, recovery_days, _ = max_drawdown(nav)

    ann_vol = float(ret.std(ddof=1) * np.sqrt(config.annualization))
    sharpe = sharpe_ratio(ret, config)
    sortino = sortino_ratio(ret, config)
    calmar = np.nan if mdd == 0 else float(cagr / abs(mdd))

    win_rate, pnl_ratio, monthly = monthly_statistics(ret)

    annual = (1.0 + ret).resample("YE").prod() - 1.0
    worst_year = int(annual.idxmin().year) if len(annual.dropna()) else np.nan
    worst_year_return = float(annual.min()) if len(annual.dropna()) else np.nan

    result = {
        "strategy_name": config.strategy_name,
        "start": nav.index.min().date(),
        "end": nav.index.max().date(),
        "initial_capital": config.initial_capital,
        "final_asset_gross": float(bt["gross_nav"].iloc[-1]),
        "final_asset_net": float(nav.iloc[-1]),
        "cumulative_return_net": float(nav.iloc[-1] / config.initial_capital - 1.0),
        "cagr_net": cagr,
        "annualized_volatility": ann_vol,
        "mdd_daily": mdd,
        "mdd_peak_date": peak.date(),
        "mdd_trough_date": trough.date(),
        "mdd_recovery_date": recovery.date() if not pd.isna(recovery) else "not_recovered",
        "max_recovery_days": recovery_days,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "monthly_win_rate": win_rate,
        "monthly_profit_loss_ratio": pnl_ratio,
        "worst_year": worst_year,
        "worst_year_return": worst_year_return,
        "average_annual_turnover": float(bt["turnover"].resample("YE").sum().mean()),
        "total_cost_drag": float(bt["gross_nav"].iloc[-1] - bt["net_nav"].iloc[-1]),
        "one_way_cost_bps": config.one_way_cost_bps,
        "risk_free_annual": config.risk_free_annual,
        "annualization": config.annualization,
        "execution_rule": "signal at t close -> weight effective from t+1 trading day",
    }

    return pd.DataFrame([result])


# ============================================================
# 5. 표준 출력
# ============================================================

def save_outputs(bt: pd.DataFrame, held_weights: pd.DataFrame, metrics: pd.DataFrame, config: BacktestConfig):
    outdir = config.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    bt.to_csv(outdir / "daily_nav.csv", encoding="utf-8-sig")
    held_weights.to_csv(outdir / "held_weights_daily.csv", encoding="utf-8-sig")
    metrics.to_csv(outdir / "summary.csv", index=False, encoding="utf-8-sig")

    annual = (1.0 + bt["net_return"]).resample("YE").prod() - 1.0
    annual_df = pd.DataFrame({
        "year": annual.index.year,
        "return": annual.values,
    })
    annual_df.to_csv(outdir / "annual_returns.csv", index=False, encoding="utf-8-sig")

    monthly = (1.0 + bt["net_return"]).resample("ME").prod() - 1.0
    monthly_df = pd.DataFrame({
        "Date": monthly.index,
        "return": monthly.values,
    })
    monthly_df.to_csv(outdir / "monthly_returns.csv", index=False, encoding="utf-8-sig")

    # 채팅 표시 및 경량 시각화용 월별 데이터
    nav = bt["net_nav"]
    wealth = nav / config.initial_capital
    dd = nav / nav.cummax() - 1.0

    chart = pd.DataFrame({
        "WealthMultiple": wealth.resample("ME").last(),
        "Drawdown": dd.resample("ME").min(),
    }).dropna()
    chart.to_csv(outdir / "chart_monthly.csv", encoding="utf-8-sig")

    # --------------------------------------------------------
    # LOG2 누적자산 그래프
    # --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nav.index, wealth, linewidth=1.8)
    ax.set_yscale("log", base=2)

    max_multiple = float(wealth.max())
    max_pow = max(0, int(np.ceil(np.log2(max_multiple))))
    ticks = [2 ** i for i in range(0, max_pow + 1)]

    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{int(x)}x" for x in ticks])
    ax.set_title(f"{config.strategy_name} - Cumulative Wealth (LOG2)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Wealth Multiple")
    ax.grid(True, which="both", linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(outdir / "cumulative_wealth_log2.png", dpi=180)
    plt.close()

    # --------------------------------------------------------
    # 일별 Drawdown 그래프
    # --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dd.index, dd * 100.0, linewidth=1.6)
    ax.set_title(f"{config.strategy_name} - Daily Drawdown")
    ax.set_xlabel("Year")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(outdir / "drawdown_daily.png", dpi=180)
    plt.close()


# ============================================================
# 6. 실행
# ============================================================

def main():
    config = BacktestConfig(
        strategy_name="STANDARD_TEMPLATE_V1",
        price_csv=ROOT / "data" / "derived" / "daily" / "adj_close_daily.csv",
        output_dir=ROOT / "results" / "standard_backtest_v1",
        start_date=None,
        end_date=None,
        initial_capital=10_000.0,
        one_way_cost_bps=5.0,
        risk_free_annual=0.0,
        benchmark_ticker=None,
    )

    prices = load_price_panel(config)
    target_weights = build_target_weights(prices)
    bt, held_weights = run_backtest(prices, target_weights, config)
    metrics = calculate_metrics(bt, config)
    save_outputs(bt, held_weights, metrics, config)

    print("표준 백테스트 v1 완료")
    print(metrics.T)
    print(f"결과 폴더: {config.output_dir}")


if __name__ == "__main__":
    main()
