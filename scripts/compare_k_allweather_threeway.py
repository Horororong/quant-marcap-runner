from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "k_allweather_threeway"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL = 10_000_000.0

CURRENT_NAV = ROOT / "results" / "k_allweather_v3" / "nav_monthly_primary_annual_rebalance.csv"
KANG_NAV = ROOT / "results" / "kang_k_allweather_original" / "nav_monthly_gross.csv"


def load_nav():
    cur = pd.read_csv(CURRENT_NAV, index_col=0, parse_dates=True, encoding="utf-8-sig")
    kang = pd.read_csv(KANG_NAV, index_col=0, parse_dates=True, encoding="utf-8-sig")

    if "성장형" not in cur.columns:
        raise RuntimeError(f"성장형 column missing from {CURRENT_NAV}")
    for c in ["강환국 정적 K-올웨더", "강환국 계절형 K-올웨더"]:
        if c not in kang.columns:
            raise RuntimeError(f"{c} missing from {KANG_NAV}")

    nav = pd.concat([
        cur["성장형"].rename("최신 K-올웨더 성장형"),
        kang["강환국 정적 K-올웨더"].rename("강환국 정적 원본"),
        kang["강환국 계절형 K-올웨더"].rename("강환국 계절형 원본"),
    ], axis=1, join="inner").dropna()

    if nav.empty:
        raise RuntimeError("No overlapping NAV data")
    return nav


def metrics(nav: pd.Series):
    r = nav.pct_change().dropna()
    years = len(r) / 12.0
    final = float(nav.iloc[-1])
    cagr = (final / INITIAL) ** (1.0 / years) - 1.0
    vol = float(r.std(ddof=1) * np.sqrt(12))
    dd = nav / nav.cummax() - 1.0
    mdd = float(dd.min())
    sharpe0 = float((r.mean() / r.std(ddof=1)) * np.sqrt(12)) if r.std(ddof=1) > 0 else np.nan
    downside = r[r < 0].std(ddof=1)
    sortino0 = float((r.mean() / downside) * np.sqrt(12)) if pd.notna(downside) and downside > 0 else np.nan
    calmar = float(cagr / abs(mdd)) if mdd < 0 else np.nan

    # longest recovery in months, based on monthly NAV
    peak = nav.cummax()
    underwater = nav < peak
    longest = 0
    cur = 0
    for x in underwater:
        if x:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    return {
        "최종자산_원": final,
        "누적수익률": final / INITIAL - 1.0,
        "CAGR": cagr,
        "연환산변동성": vol,
        "MDD": mdd,
        "Sharpe_rf0": sharpe0,
        "Sortino_rf0": sortino0,
        "Calmar": calmar,
        "최대손실회복기간_개월": int(longest),
    }


def main():
    nav = load_nav()
    nav.to_csv(OUT / "nav_monthly.csv", encoding="utf-8-sig")

    rows = []
    for c in nav.columns:
        row = {"전략": c, "시작": nav.index.min().date().isoformat(), "종료": nav.index.max().date().isoformat(), **metrics(nav[c])}
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")

    # Compact payload for ChatGPT inline interactive chart.
    payload = {
        "dates": [d.strftime("%Y-%m") for d in nav.index],
        "series": {
            c: [round(float(v / INITIAL), 4) for v in nav[c].values]
            for c in nav.columns
        },
        "summary": {
            row["전략"]: {
                "final_million": round(row["최종자산_원"] / 1_000_000, 2),
                "cagr_pct": round(row["CAGR"] * 100, 2),
                "vol_pct": round(row["연환산변동성"] * 100, 2),
                "mdd_pct": round(row["MDD"] * 100, 2),
                "sharpe0": round(row["Sharpe_rf0"], 2),
                "calmar": round(row["Calmar"], 2),
                "recovery_months": int(row["최대손실회복기간_개월"]),
            }
            for row in rows
        },
    }
    with open(OUT / "interactive_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
