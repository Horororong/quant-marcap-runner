from pathlib import Path
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "results" / "k_allweather_v3"
OUT = ROOT / "results" / "k_allweather_seasonal_us30y"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL_KRW = 10_000_000.0
PROFILES = ["성장형", "중립형", "안정형"]
ASSETS = ["미국주식", "한국주식", "중국주식", "인도주식", "금", "미국30년국채", "한국30년국채", "현금성자산"]
RISK_MONTHS = {11, 12, 1, 2, 3, 4}
DEFENSIVE_ASSET = "미국30년국채"
COST_SCENARIOS = {"0bp": 0.0, "10bp/매매금액": 0.0010}


def setup_korean_font():
    candidates = [f for f in font_manager.fontManager.ttflist if "NanumGothic" in f.name]
    if candidates:
        rcParams["font.family"] = "NanumGothic"
    rcParams["axes.unicode_minus"] = False


def load_inputs():
    asset_ret = pd.read_csv(SRC / "asset_returns_monthly.csv", index_col=0, parse_dates=True, encoding="utf-8-sig")
    weights = pd.read_csv(SRC / "weights.csv", index_col=0, encoding="utf-8-sig")
    baseline_nav = pd.read_csv(SRC / "nav_monthly_primary_annual_rebalance.csv", index_col=0, parse_dates=True, encoding="utf-8-sig")
    asset_ret = asset_ret[ASSETS].sort_index()
    weights = weights[ASSETS].astype(float)
    baseline_nav = baseline_nav[PROFILES].reindex(asset_ret.index)
    if asset_ret.isna().any().any():
        raise RuntimeError(f"asset_returns_monthly.csv contains missing values: {asset_ret.isna().sum().to_dict()}")
    if baseline_nav.isna().any().any():
        raise RuntimeError("Baseline NAV is not aligned with seasonal test dates")
    for p in PROFILES:
        if abs(weights.loc[p].sum() - 1.0) > 1e-9:
            raise RuntimeError(f"Weights do not sum to 1 for {p}: {weights.loc[p].sum()}")
    return asset_ret, weights, baseline_nav


def target_for_month(profile_weights: pd.Series, month: int) -> pd.Series:
    if month in RISK_MONTHS:
        return profile_weights.copy()
    w = pd.Series(0.0, index=ASSETS)
    w[DEFENSIVE_ASSET] = 1.0
    return w


def backtest(asset_ret: pd.DataFrame, profile_weights: pd.Series, cost_rate: float):
    dates = asset_ret.index
    nav = pd.Series(index=dates, dtype=float)
    pret = pd.Series(index=dates, dtype=float)
    turnover = pd.Series(0.0, index=dates, dtype=float)
    cost_paid = pd.Series(0.0, index=dates, dtype=float)

    sleeves = INITIAL_KRW * target_for_month(profile_weights, dates[0].month)

    for i, dt in enumerate(dates):
        if i > 0 and dt.month in (5, 11):
            nav_before = float(sleeves.sum())
            target = target_for_month(profile_weights, dt.month)
            target_values = nav_before * target
            traded = float((target_values - sleeves).abs().sum())
            cost = traded * cost_rate
            sleeves = (nav_before - cost) * target
            turnover.loc[dt] = traded / nav_before if nav_before > 0 else 0.0
            cost_paid.loc[dt] = cost

        nav_before_return = float(sleeves.sum())
        sleeves *= (1.0 + asset_ret.loc[dt])
        nav_after_return = float(sleeves.sum())
        pret.loc[dt] = nav_after_return / nav_before_return - 1.0 if nav_before_return > 0 else np.nan
        nav.loc[dt] = nav_after_return

    return nav, pret, turnover, cost_paid


def recovery_months(nav: pd.Series) -> int:
    dd = nav / nav.cummax() - 1.0
    longest = cur = 0
    for x in dd:
        if x < -1e-12:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return int(longest)


def metrics(nav: pd.Series, ret: pd.Series, rf: pd.Series, turnover: pd.Series, total_cost: float, rebalance_count: int):
    years = len(ret) / 12.0
    final = float(nav.iloc[-1])
    cagr = (final / INITIAL_KRW) ** (1.0 / years) - 1.0
    vol = float(ret.std(ddof=1) * math.sqrt(12.0))
    dd = nav / nav.cummax() - 1.0
    mdd = float(dd.min())
    excess = ret - rf.reindex(ret.index).fillna(0.0)
    sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(12.0)) if excess.std(ddof=1) > 0 else np.nan
    downside = ret[ret < 0].std(ddof=1)
    sortino = float((ret.mean() - rf.mean()) / downside * math.sqrt(12.0)) if downside and downside > 0 else np.nan
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    annual = (1.0 + ret).groupby(ret.index.year).prod() - 1.0
    rebals = turnover[turnover > 0]
    return {
        "시작": nav.index[0].date().isoformat(),
        "종료": nav.index[-1].date().isoformat(),
        "초기자산_원": INITIAL_KRW,
        "최종자산_원": final,
        "누적수익률": final / INITIAL_KRW - 1.0,
        "CAGR": cagr,
        "연환산변동성": vol,
        "MDD": mdd,
        "최대손실회복기간_개월": recovery_months(nav),
        "Sharpe_현금초과": sharpe,
        "Sortino": sortino,
        "Calmar": calmar,
        "월간승률": float((ret > 0).mean()),
        "최악연도": int(annual.idxmin()),
        "최악연도수익률": float(annual.min()),
        "최고연도": int(annual.idxmax()),
        "최고연도수익률": float(annual.max()),
        "평균리밸런싱회전율": float(rebals.mean()) if len(rebals) else 0.0,
        "연간리밸런싱횟수": rebalance_count,
        "누적거래비용_원": float(total_cost),
    }


def baseline_metrics(baseline_nav: pd.Series, rf: pd.Series):
    ret = baseline_nav.pct_change()
    ret.iloc[0] = baseline_nav.iloc[0] / INITIAL_KRW - 1.0
    dummy_turnover = pd.Series(0.0, index=baseline_nav.index)
    return metrics(baseline_nav, ret, rf, dummy_turnover, 0.0, 1), ret


def main():
    setup_korean_font()
    asset_ret, weights, baseline_nav = load_inputs()
    rf = asset_ret["현금성자산"]
    seasonal_navs = {}
    seasonal_rets = {}
    rows = []

    for p in PROFILES:
        m, _ = baseline_metrics(baseline_nav[p], rf)
        m.update({"전략": "기존 K-올웨더", "유형": p, "리밸런싱": "연1회(1월)", "거래비용": "0bp"})
        rows.append(m)

    for cost_label, cost_rate in COST_SCENARIOS.items():
        for p in PROFILES:
            nav, ret, turnover, costs = backtest(asset_ret, weights.loc[p], cost_rate)
            m = metrics(nav, ret, rf, turnover, costs.sum(), 2)
            m.update({
                "전략": "계절형 K-올웨더 → 미국30년국채",
                "유형": p,
                "리밸런싱": "연2회(11월초 K-올웨더 / 5월초 미국30년국채100%)",
                "거래비용": cost_label,
            })
            rows.append(m)
            if cost_label == "0bp":
                seasonal_navs[p] = nav
                seasonal_rets[p] = ret

    summary = pd.DataFrame(rows)
    col_order = [
        "전략","유형","리밸런싱","거래비용","시작","종료","초기자산_원","최종자산_원","누적수익률","CAGR",
        "연환산변동성","MDD","최대손실회복기간_개월","Sharpe_현금초과","Sortino","Calmar","월간승률",
        "최악연도","최악연도수익률","최고연도","최고연도수익률","평균리밸런싱회전율","연간리밸런싱횟수","누적거래비용_원"
    ]
    summary[col_order].to_csv(OUT / "summary_compare.csv", index=False, encoding="utf-8-sig")

    seasonal_nav_df = pd.DataFrame(seasonal_navs)
    seasonal_ret_df = pd.DataFrame(seasonal_rets)
    seasonal_nav_df.to_csv(OUT / "seasonal_nav_0bp.csv", encoding="utf-8-sig")
    seasonal_ret_df.to_csv(OUT / "seasonal_returns_0bp.csv", encoding="utf-8-sig")
    annual = pd.DataFrame({p: (1.0 + seasonal_rets[p]).groupby(seasonal_rets[p].index.year).prod() - 1.0 for p in PROFILES})
    annual.to_csv(OUT / "annual_returns_seasonal_0bp.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(13, 7))
    for p in PROFILES:
        ax.plot(seasonal_nav_df.index, seasonal_nav_df[p] / 1e6, label=f"계절형 {p}")
        ax.plot(baseline_nav.index, baseline_nav[p] / 1e6, linestyle="--", alpha=0.65, label=f"기존 {p}")
    ax.set_title("K-올웨더: 기존 vs 11월~4월 보유 / 5월~10월 미국30년국채")
    ax.set_ylabel("자산 (백만원)")
    ax.set_xlabel("연도")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "01_누적자산_비교.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 7))
    for p in PROFILES:
        ax.plot(seasonal_nav_df.index, np.log2(seasonal_nav_df[p] / INITIAL_KRW), label=f"계절형 {p}")
        ax.plot(baseline_nav.index, np.log2(baseline_nav[p] / INITIAL_KRW), linestyle="--", alpha=0.65, label=f"기존 {p}")
    ax.set_title("K-올웨더 기존 vs 계절형 - 로그2 누적자산")
    ax.set_ylabel("log2(자산 / 초기자산)")
    ax.set_xlabel("연도")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "02_로그2누적자산_비교.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 7))
    for p in PROFILES:
        sdd = seasonal_nav_df[p] / seasonal_nav_df[p].cummax() - 1.0
        bdd = baseline_nav[p] / baseline_nav[p].cummax() - 1.0
        ax.plot(sdd.index, sdd * 100, label=f"계절형 {p}")
        ax.plot(bdd.index, bdd * 100, linestyle="--", alpha=0.65, label=f"기존 {p}")
    ax.set_title("K-올웨더 기존 vs 계절형 - 낙폭")
    ax.set_ylabel("낙폭 (%)")
    ax.set_xlabel("연도")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "03_낙폭_비교.png", dpi=180)
    plt.close(fig)

    readme = f"""K-올웨더 계절형 미국30년국채 회피전략\n\n기간: {asset_ret.index[0].date()} ~ {asset_ret.index[-1].date()}\n초기자산: 10,000,000원\n\n규칙\n- 11월 초: 성장형/중립형/안정형의 원래 K-올웨더 목표비중으로 리밸런싱\n- 11월~4월: 해당 K-올웨더 포트폴리오 보유(중간 월에는 리밸런싱하지 않고 비중 드리프트 허용)\n- 5월 초: 전 자산 매도 후 미국30년국채 100%로 전환\n- 5월~10월: 미국30년국채 100% 보유\n- 연 2회 리밸런싱\n- 월별 수익률 자료이므로 '월 초' 체결은 해당 월 전체 수익률에 새 비중이 적용되는 방식으로 근사\n- 거래비용: 0bp 및 매매금액당 10bp 민감도 비교\n\n주의\n- 장기 구간은 기존 K-올웨더 v3의 프록시/ETF 스플라이스 월수익률을 그대로 사용함.\n- 2000년 이전 실제 ETF 미존재 문제와 한국 30년채 프록시 한계는 기존 v3와 동일함.\n"""
    (OUT / "README.txt").write_text(readme, encoding="utf-8")
    print(summary[col_order].to_string(index=False))


if __name__ == "__main__":
    main()
