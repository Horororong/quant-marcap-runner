from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "k_allweather_robustness"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL = 10_000_000.0
NAV_FILE = ROOT / "results" / "k_allweather_threeway" / "nav_monthly.csv"

PERIODS = {
    "2000-2012": (pd.Timestamp("2000-01-31"), pd.Timestamp("2012-12-31")),
    "2013-2026.08": (pd.Timestamp("2013-01-31"), pd.Timestamp("2026-08-31")),
    "2021-2026.08": (pd.Timestamp("2021-01-31"), pd.Timestamp("2026-08-31")),
}


def full_monthly_returns(nav: pd.Series) -> pd.Series:
    r = nav.pct_change(fill_method=None)
    r.iloc[0] = nav.iloc[0] / INITIAL - 1.0
    return r


def period_metrics_from_returns(r: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    if n == 0:
        return {}
    wealth = (1.0 + r).cumprod()
    cumulative = float(wealth.iloc[-1] - 1.0)
    cagr = float(wealth.iloc[-1] ** (12.0 / n) - 1.0)
    vol = float(r.std(ddof=1) * np.sqrt(12)) if n > 1 else np.nan
    dd = wealth / wealth.cummax() - 1.0
    mdd = float(dd.min())
    sharpe0 = float(r.mean() / r.std(ddof=1) * np.sqrt(12)) if n > 1 and r.std(ddof=1) > 0 else np.nan
    downside = r[r < 0].std(ddof=1)
    sortino0 = float(r.mean() / downside * np.sqrt(12)) if pd.notna(downside) and downside > 0 else np.nan
    calmar = float(cagr / abs(mdd)) if mdd < 0 else np.nan
    return {
        "개월수": n,
        "누적수익률": cumulative,
        "CAGR": cagr,
        "연환산변동성": vol,
        "MDD": mdd,
        "Sharpe_rf0": sharpe0,
        "Sortino_rf0": sortino0,
        "Calmar": calmar,
    }


def rolling_mdd(r: pd.Series, window: int = 120) -> pd.Series:
    vals = r.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    for i in range(window - 1, len(vals)):
        w = vals[i-window+1:i+1]
        wealth = np.cumprod(1.0 + w)
        wealth = np.concatenate(([1.0], wealth))
        peaks = np.maximum.accumulate(wealth)
        dd = wealth / peaks - 1.0
        out[i] = dd.min()
    return pd.Series(out, index=r.index)


def main():
    nav = pd.read_csv(NAV_FILE, index_col=0, parse_dates=True, encoding="utf-8-sig")
    nav = nav.sort_index()
    if nav.empty:
        raise RuntimeError("nav file is empty")

    returns = pd.DataFrame({c: full_monthly_returns(nav[c]) for c in nav.columns}, index=nav.index)

    # Period metrics using monthly returns actually realized within each period.
    period_rows = []
    for pname, (start, end) in PERIODS.items():
        for c in nav.columns:
            rr = returns[c].loc[(returns.index >= start) & (returns.index <= end)]
            m = period_metrics_from_returns(rr)
            period_rows.append({"기간": pname, "전략": c, **m})
    period_df = pd.DataFrame(period_rows)
    period_df.to_csv(OUT / "period_metrics.csv", index=False, encoding="utf-8-sig")

    # 10-year rolling CAGR and MDD (120 monthly return observations).
    rolling = pd.DataFrame(index=returns.index)
    for c in nav.columns:
        rr = returns[c]
        roll_growth = (1.0 + rr).rolling(120).apply(np.prod, raw=True)
        rolling[(c, "CAGR10Y")] = roll_growth ** (1.0 / 10.0) - 1.0
        rolling[(c, "MDD10Y")] = rolling_mdd(rr, 120)
    rolling.columns = pd.MultiIndex.from_tuples(rolling.columns)
    rolling = rolling.dropna(how="all")
    rolling.to_csv(OUT / "rolling10y_monthly.csv", encoding="utf-8-sig")

    # Summary of rolling distributions and worst/best windows.
    rows = []
    for c in nav.columns:
        cg = rolling[(c, "CAGR10Y")].dropna()
        md = rolling[(c, "MDD10Y")].dropna()
        worst_cg_dt = cg.idxmin(); best_cg_dt = cg.idxmax(); worst_mdd_dt = md.idxmin()
        rows.append({
            "전략": c,
            "롤링10년_창수": len(cg),
            "CAGR10Y_평균": float(cg.mean()),
            "CAGR10Y_중앙값": float(cg.median()),
            "CAGR10Y_최저": float(cg.min()),
            "CAGR10Y_최저_종료월": worst_cg_dt.strftime("%Y-%m"),
            "CAGR10Y_최고": float(cg.max()),
            "CAGR10Y_최고_종료월": best_cg_dt.strftime("%Y-%m"),
            "MDD10Y_평균": float(md.mean()),
            "MDD10Y_최악": float(md.min()),
            "MDD10Y_최악_종료월": worst_mdd_dt.strftime("%Y-%m"),
        })
    roll_summary = pd.DataFrame(rows)

    # Cross-sectional win rates among the three strategies by rolling window.
    cgmat = pd.concat({c: rolling[(c, "CAGR10Y")] for c in nav.columns}, axis=1).dropna()
    mdmat = pd.concat({c: rolling[(c, "MDD10Y")] for c in nav.columns}, axis=1).dropna()
    for i, row in roll_summary.iterrows():
        c = row["전략"]
        roll_summary.loc[i, "CAGR10Y_1위비율"] = float((cgmat.idxmax(axis=1) == c).mean())
        roll_summary.loc[i, "MDD10Y_1위비율"] = float((mdmat.idxmax(axis=1) == c).mean())  # less negative is better
    roll_summary.to_csv(OUT / "rolling10y_summary.csv", index=False, encoding="utf-8-sig")

    # Pairwise seasonal edge versus static/current over rolling 10y windows.
    pair_rows = []
    seasonal = "강환국 계절형 원본"
    for other in ["강환국 정적 원본", "최신 K-올웨더 성장형"]:
        common = pd.concat([
            cgmat[seasonal].rename("seasonal_cagr"), cgmat[other].rename("other_cagr"),
            mdmat[seasonal].rename("seasonal_mdd"), mdmat[other].rename("other_mdd")
        ], axis=1).dropna()
        pair_rows.append({
            "비교": f"{seasonal} vs {other}",
            "계절형_CAGR우위_비율": float((common["seasonal_cagr"] > common["other_cagr"]).mean()),
            "계절형_MDD우위_비율": float((common["seasonal_mdd"] > common["other_mdd"]).mean()),
            "계절형_CAGR_평균차": float((common["seasonal_cagr"] - common["other_cagr"]).mean()),
            "계절형_MDD_평균차": float((common["seasonal_mdd"] - common["other_mdd"]).mean()),
        })
    pd.DataFrame(pair_rows).to_csv(OUT / "rolling10y_pairwise.csv", index=False, encoding="utf-8-sig")

    # Compact payload for inline interactive rolling chart.
    valid_idx = cgmat.index.intersection(mdmat.index)
    payload = {
        "dates": [d.strftime("%Y-%m") for d in valid_idx],
        "cagr": {c: [round(float(rolling.loc[d, (c, "CAGR10Y")]) * 100, 3) for d in valid_idx] for c in nav.columns},
        "mdd": {c: [round(float(rolling.loc[d, (c, "MDD10Y")]) * 100, 3) for d in valid_idx] for c in nav.columns},
    }
    with open(OUT / "interactive_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print("=== PERIOD METRICS ===")
    print(period_df.to_string(index=False))
    print("\n=== ROLLING 10Y SUMMARY ===")
    print(roll_summary.to_string(index=False))


if __name__ == "__main__":
    main()
