from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from quant_backtest_template_v2_12 import (
    BacktestConfig,
    combine_period_payloads,
    run_four_periods,
    save_chat_payload,
)

AS_OF = pd.Timestamp("2026-09-18")
LATEST_COMPLETE_MONTH = pd.Timestamp("2026-08-31")
INITIAL_CAPITAL = 10_000.0
WEIGHTS = {
    "SPY": 0.30,
    "IEF": 0.15,
    "TLT": 0.40,
    "GLD": 0.075,
    "DBC": 0.075,
}
BASE_COST_BPS = 5.0
COST_SCENARIOS_BPS = (0.0, 5.0, 15.0)
BOOK_START = "1970-01-01"
BOOK_END = "2021-12-31"

OUT = Path("results/allseasons_template_v212")
OUT.mkdir(parents=True, exist_ok=True)

POFO = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets"
PROXY_URLS = {
    "SPY": f"{POFO}/simdata/SP500.csv",
    "IEF": f"{POFO}/simdata/IEF.csv",
    "TLT": f"{POFO}/simdata/TLT.csv",
    "GLD": f"{POFO}/simdata/XAUUSD.csv",
    # Broad commodity total-return reconstruction: BCOM ER + T-bill collateral,
    # with real ICOM grafted from 2009. Used only before DBC inception.
    "DBC": f"{POFO}/simdata/IE00BDFL4P12.csv",
}
ACTUAL_FILES = {
    k: f"data/etf_us/{k}.csv" for k in WEIGHTS
}
PPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PPIACO"


def load_proxy(url: str, name: str) -> pd.Series:
    df = pd.read_csv(url, comment="#")
    if not {"date", "close"}.issubset(df.columns):
        raise RuntimeError(f"{name}: proxy columns missing: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    s = (
        df.dropna(subset=["date", "close"])
        .drop_duplicates("date")
        .set_index("date")["close"]
        .sort_index()
        .rename(name)
    )
    if s.empty or (s <= 0).any():
        raise RuntimeError(f"{name}: invalid proxy series")
    return s


def load_actual(path: str, name: str) -> pd.Series:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    df[col] = pd.to_numeric(df[col], errors="coerce")
    s = (
        df.dropna(subset=["Date", col])
        .drop_duplicates("Date")
        .set_index("Date")[col]
        .sort_index()
        .rename(name)
    )
    if s.empty or (s <= 0).any():
        raise RuntimeError(f"{name}: invalid actual ETF series")
    return s


def stitch_proxy_to_actual(proxy: pd.Series, actual: pd.Series, end: pd.Timestamp) -> pd.Series:
    idx = pd.bdate_range(proxy.index.min(), end)
    p = proxy.reindex(idx).ffill()
    a = actual.reindex(idx).ffill()
    first = actual.index[actual.index <= end].min()
    if pd.isna(first):
        return p.loc[:end]
    if first not in p.index or pd.isna(p.loc[first]) or pd.isna(a.loc[first]):
        raise RuntimeError(f"splice failure at {first}")
    scale = float(p.loc[first]) / float(a.loc[first])
    out = p.copy()
    out.loc[first:] = a.loc[first:] * scale
    return out.loc[:end]


def month_end_levels(daily: pd.DataFrame) -> pd.DataFrame:
    m = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    m.index = m.index.to_period("M").to_timestamp("M")
    return m


def load_ppi_monthly() -> pd.Series:
    df = pd.read_csv(PPI_URL)
    date_col = df.columns[0]
    val_col = "PPIACO" if "PPIACO" in df.columns else df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    s = (
        df.dropna(subset=[date_col, val_col])
        .drop_duplicates(date_col)
        .set_index(date_col)[val_col]
        .sort_index()
    )
    s.index = s.index.to_period("M").to_timestamp("M")
    return s.rename("DBC")


def build_levels() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    proxies = {k: load_proxy(u, f"{k}_proxy") for k, u in PROXY_URLS.items()}
    actual = {k: load_actual(ACTUAL_FILES[k], k) for k in WEIGHTS}

    hybrids = {
        k: stitch_proxy_to_actual(proxies[k], actual[k], LATEST_COMPLETE_MONTH).rename(k)
        for k in WEIGHTS
    }

    # Reliable daily history is limited by the broad-commodity TR reconstruction (1991-01).
    daily_start = max(s.index.min() for s in hybrids.values())
    didx = pd.bdate_range(daily_start, LATEST_COMPLETE_MONTH)
    daily_levels = pd.concat(
        [hybrids[k].reindex(didx).ffill().rename(k) for k in WEIGHTS], axis=1
    ).dropna()

    # Exploratory pre-1991 commodity extension for the book's 1970 start:
    # PPIACO is a spot/producer-price proxy, NOT an investable futures total-return index.
    # Keep it explicit so the book-period and longest-period results are labeled exploratory.
    reliable_monthly = month_end_levels(daily_levels)
    ppi = load_ppi_monthly()

    dbc_rel = reliable_monthly["DBC"].copy()
    splice_month = dbc_rel.index.min()
    ppi_anchor = ppi.loc[ppi.index <= splice_month].iloc[-1]
    dbc_scaled = dbc_rel * (float(ppi_anchor) / float(dbc_rel.iloc[0]))
    dbc_extended = pd.concat(
        [ppi.loc[ppi.index < splice_month], dbc_scaled]
    ).sort_index().rename("DBC")

    # Other four assets have credible reconstructed histories back to the late 1960s.
    other_daily = {}
    for k in ("SPY", "IEF", "TLT", "GLD"):
        s = hybrids[k]
        idx = pd.bdate_range(s.index.min(), LATEST_COMPLETE_MONTH)
        other_daily[k] = s.reindex(idx).ffill().rename(k)
    other_monthly = {
        k: month_end_levels(v.to_frame())[k] for k, v in other_daily.items()
    }

    monthly_levels = pd.concat(
        [
            other_monthly["SPY"],
            other_monthly["IEF"],
            other_monthly["TLT"],
            other_monthly["GLD"],
            dbc_extended,
        ],
        axis=1,
    ).dropna().loc[:LATEST_COMPLETE_MONTH]

    meta = {
        "daily_reliable_start": daily_levels.index.min().date().isoformat(),
        "monthly_extended_start": monthly_levels.index.min().date().isoformat(),
        "commodity_reliable_start": splice_month.date().isoformat(),
        "actual_etf_starts": {k: actual[k].index.min().date().isoformat() for k in WEIGHTS},
    }
    return monthly_levels, daily_levels, meta


def simulate(levels: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.DataFrame]:
    cols = list(WEIGHTS)
    target = np.array([WEIGHTS[c] for c in cols], dtype=float)
    ret = levels[cols].pct_change().fillna(0.0)
    values = target.copy()
    nav_rows = []
    trade_rows = []
    prev_year = levels.index[0].year

    for i, (dt, row) in enumerate(ret.iterrows()):
        if i > 0 and dt.year != prev_year:
            pre = float(values.sum())
            target_values = target * pre
            gross_notional = float(np.abs(target_values - values).sum())
            cost = gross_notional * cost_bps / 10_000.0
            post = pre - cost
            values = target * post
            trade_rows.append({
                "Date": dt,
                "GrossTurnover": gross_notional / pre if pre > 0 else np.nan,
                "CostNAV": cost,
            })
            prev_year = dt.year

        if i > 0:
            values *= 1.0 + row.to_numpy(dtype=float)
        nav_rows.append((dt, float(values.sum())))

    nav = pd.Series(dict(nav_rows), dtype=float).sort_index()
    nav /= float(nav.iloc[0])
    return nav, pd.DataFrame(trade_rows)


def benchmark_from_levels(levels: pd.DataFrame) -> pd.Series:
    s = levels["SPY"].astype(float)
    return (s / float(s.iloc[0])).rename("S&P500 100%")


def monthly_nav_from_daily(nav: pd.DataFrame) -> pd.DataFrame:
    out = nav.groupby(nav.index.to_period("M")).tail(1).copy()
    out.index = out.index.to_period("M").to_timestamp("M")
    return out


def splice_extended_monthly_to_daily(monthly_series: pd.Series, daily_series: pd.Series) -> pd.Series:
    """Keep exploratory pre-daily history, then use exact daily-derived month-end returns.

    The splice month is anchored to the extended monthly level so all later monthly
    returns are mathematically identical to the reliable daily NAV path.
    """
    dm = monthly_nav_from_daily(daily_series.to_frame("x"))["x"]
    anchor = dm.index[0]
    if anchor not in monthly_series.index:
        raise RuntimeError(f"monthly/daily NAV splice anchor missing: {anchor}")
    scaled = dm * (float(monthly_series.loc[anchor]) / float(dm.loc[anchor]))
    out = monthly_series.copy()
    out.loc[scaled.index] = scaled
    return out.sort_index()


def flatten(results: dict) -> pd.DataFrame:
    rows = []
    for key, r in results.items():
        x = r["metrics"].copy().reset_index()
        x.insert(0, "Period", key)
        x.insert(1, "PeriodLabel", r["label"])
        x.insert(2, "Start", pd.Timestamp(r["start"]).strftime("%Y-%m-%d"))
        x.insert(3, "End", pd.Timestamp(r["end"]).strftime("%Y-%m-%d"))
        rows.append(x)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    monthly_levels, daily_levels, data_meta = build_levels()

    # Build extended monthly NAV (1968+) and reliable daily NAV (1991+).
    mg, mt0 = simulate(monthly_levels, 0.0)
    mn, mt5 = simulate(monthly_levels, BASE_COST_BPS)
    mb = benchmark_from_levels(monthly_levels)
    dg, dt0 = simulate(daily_levels, 0.0)
    dn, dt5 = simulate(daily_levels, BASE_COST_BPS)
    db = benchmark_from_levels(daily_levels)
    daily_nav = pd.concat(
        [
            dg.rename("사계절 비용전"),
            dn.rename("사계절 비용후(5bp)"),
            db,
        ],
        axis=1,
    ).dropna()

    # Preserve the exploratory pre-1991 monthly history, but from the first reliable
    # daily month onward use exact daily-derived month-end returns. This removes
    # frequency-engine drift from all fixed periods starting in 2001 or later.
    mg = splice_extended_monthly_to_daily(mg, dg)
    mn = splice_extended_monthly_to_daily(mn, dn)
    mb = splice_extended_monthly_to_daily(mb, db)
    monthly_nav = pd.concat(
        [
            mg.rename("사계절 비용전"),
            mn.rename("사계절 비용후(5bp)"),
            mb.rename("S&P500 100%"),
        ],
        axis=1,
    ).dropna()

    # Critical cross-frequency check from reliable daily-history start onward.
    dmonth = monthly_nav_from_daily(daily_nav)
    common = monthly_nav.index.intersection(dmonth.index)
    common = common[common >= pd.Timestamp("1991-02-28")]
    max_ret_diff = {}
    for c in monthly_nav.columns:
        a = monthly_nav.loc[common, c].pct_change().dropna()
        b = dmonth.loc[common, c].pct_change().dropna()
        ix = a.index.intersection(b.index)
        max_ret_diff[c] = float((a.loc[ix] - b.loc[ix]).abs().max())

    config = BacktestConfig(
        title="거인의 포트폴리오 4번 - 사계절 포트폴리오",
        initial_capital=INITIAL_CAPITAL,
        periods_per_year=12,
        risk_free_rate=0.0,
        book_start=BOOK_START,
        book_end=BOOK_END,
        standard_end_year=2026,
        as_of_date=str(AS_OF.date()),
    )

    results = run_four_periods(monthly_nav, config, daily_nav)
    summary = flatten(results)
    summary.to_csv(OUT / "summary_four_periods_template.csv", index=False, encoding="utf-8-sig")

    combined = combine_period_payloads(
        *[results[k]["chat_payload"] for k in ["book_validation", "from_2001", "from_2021", "longest"]]
    )
    save_chat_payload(combined, str(OUT / "chat_payload_four_periods.json"))

    monthly_nav.to_csv(OUT / "monthly_nav_full.csv", encoding="utf-8-sig")
    daily_nav.to_csv(OUT / "daily_nav_reliable_1991plus.csv.gz", compression="gzip")

    # Explicit inline fallback dataset required by v2-12: 2001~current cumulative wealth.
    p2001 = results["from_2001"]["monthly_nav"]
    rows = []
    for dt, row in p2001.iterrows():
        rows.append({
            "month": dt.strftime("%Y-%m"),
            "all_seasons": round(float(row["사계절 비용후(5bp)"]), 6),
            "sp500": round(float(row["S&P500 100%"]), 6),
        })
    (OUT / "inline_2001_cumulative.json").write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8"
    )

    # Cost sensitivity through the same v2-12 engine.
    sens = []
    for bps in COST_SCENARIOS_BPS:
        mx, mtr = simulate(monthly_levels, bps)
        dx, dtr = simulate(daily_levels, bps)
        mx = splice_extended_monthly_to_daily(mx, dx)
        m = pd.DataFrame({f"사계절_{bps:g}bp": mx})
        d = pd.DataFrame({f"사계절_{bps:g}bp": dx})
        rr = run_four_periods(m, config, d)
        for key, result in rr.items():
            q = result["metrics"].iloc[0]
            start = pd.Timestamp(result["start"])
            end = pd.Timestamp(result["end"])
            tr = mtr[(mtr["Date"] >= start) & (mtr["Date"] <= end)] if len(mtr) else mtr
            sens.append({
                "Period": key,
                "Cost_bps": bps,
                "CAGR": q["CAGR"],
                "MDD": q["MDD"],
                "MDD_source": q["MDD_source"],
                "Sharpe": q["Sharpe"],
                "Annualized_Std": q["연환산_표준편차"],
                "Max_Recovery_Months": q["최대회복기간_개월"],
                "Final_Asset_USD": q["최종자산"],
                "Avg_Annual_Gross_Turnover": float(tr["GrossTurnover"].mean()) if len(tr) else 0.0,
            })
    pd.DataFrame(sens).to_csv(OUT / "cost_sensitivity_template.csv", index=False, encoding="utf-8-sig")

    book = results["book_validation"]["metrics"].loc["사계절 비용전"]
    pd.DataFrame([
        {"Metric": "Final_Asset_USD", "Book": 1_140_000.0, "Template_Backtest": float(book["최종자산"])},
        {"Metric": "CAGR", "Book": 0.096, "Template_Backtest": float(book["CAGR"])},
        {"Metric": "MDD", "Book": -0.131, "Template_Backtest": float(book["MDD"])},
        {"Metric": "Sharpe", "Book": 0.63, "Template_Backtest": float(book["Sharpe"])},
    ]).to_csv(OUT / "book_verification_template.csv", index=False, encoding="utf-8-sig")

    # Actual-ETF-only overlap robustness: from DBC inception, hybrid returns must equal actual returns.
    actual = {k: load_actual(ACTUAL_FILES[k], k) for k in WEIGHTS}
    overlap_start = max(s.index.min() for s in actual.values())
    idx = pd.bdate_range(overlap_start, LATEST_COMPLETE_MONTH)
    actual_levels = pd.concat([actual[k].reindex(idx).ffill() for k in WEIGHTS], axis=1).dropna()
    hybrid_same = daily_levels.reindex(actual_levels.index).ffill().dropna()
    anav, _ = simulate(actual_levels, 0.0)
    hnav, _ = simulate(hybrid_same, 0.0)
    chk = pd.concat([anav.rename("actual"), hnav.rename("hybrid")], axis=1).dropna()
    rchk = chk.pct_change().dropna()
    overlap_check = {
        "start": chk.index[0].date().isoformat(),
        "end": chk.index[-1].date().isoformat(),
        "max_abs_daily_return_diff": float((rchk["actual"] - rchk["hybrid"]).abs().max()),
        "final_multiple_actual": float(chk["actual"].iloc[-1] / chk["actual"].iloc[0]),
        "final_multiple_hybrid": float(chk["hybrid"].iloc[-1] / chk["hybrid"].iloc[0]),
    }
    (OUT / "actual_etf_overlap_check.json").write_text(
        json.dumps(overlap_check, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    template_path = Path("scripts/quant_backtest_template_v2_12.py")
    meta = {
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE_MONTH.date().isoformat(),
        "strategy": "SPY 30% / IEF 15% / TLT 40% / GLD 7.5% / DBC 7.5%, annual rebalance",
        "book_period": "1970-01 through 2021-12",
        "initial_capital_usd": INITIAL_CAPITAL,
        "risk_free_rate_for_template_sharpe": 0.0,
        "base_cost_bps_on_gross_rebalance_notional": BASE_COST_BPS,
        "initial_deployment_cost_included": False,
        "taxes_included": False,
        "reliable_daily_history_start": data_meta["daily_reliable_start"],
        "exploratory_monthly_history_start": data_meta["monthly_extended_start"],
        "commodity_reliable_proxy_start": data_meta["commodity_reliable_start"],
        "pre_1991_commodity_extension": "FRED PPIACO monthly producer-price index; exploratory/non-investable proxy only",
        "commodity_1991_to_DBC_inception": "pofo IE00BDFL4P12: Bloomberg Commodity TR reconstruction (BCOM ER + T-bill collateral)",
        "actual_etf_sources": ACTUAL_FILES,
        "proxy_sources": PROXY_URLS,
        "cross_frequency_max_abs_monthly_return_diff_1991plus": max_ret_diff,
        "template_path": str(template_path),
        "template_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(),
        "limitations": [
            "Book-period 1970-1990 DBC sleeve cannot be directly reconstructed from an investable broad-commodity total-return series with the available data.",
            "Therefore book_validation and longest are exploratory and use PPIACO only for the pre-1991 commodity sleeve.",
            "Because reliable daily commodity history starts in 1991, book_validation and longest MDD/recovery must be monthly_fallback under v2-12.",
            "2001-current and 2021-current have full daily coverage and therefore use daily MDD/recovery.",
            "DBC's pre-inception proxy is Bloomberg Commodity TR, not DBC's exact DBIQ Optimum Yield index; proxy basis risk remains.",
        ],
    }
    (OUT / "run_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(summary.to_string(index=False))
    print("\nBook comparison")
    print((OUT / "book_verification_template.csv").read_text(encoding="utf-8-sig"))
    print("\nCross-frequency max return diff:", max_ret_diff)
    print("\nActual ETF overlap:", overlap_check)
    print("\nTemplate SHA256:", meta["template_sha256"])


if __name__ == "__main__":
    main()
