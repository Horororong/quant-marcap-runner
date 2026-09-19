from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "kr_us_relative_momentum_v214"
RAW = ROOT / "data" / "proxy_long" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

AS_OF = pd.Timestamp("2026-09-19")
LATEST_COMPLETE = (AS_OF.to_period("M") - 1).to_timestamp("M")
INITIAL = 10_000.0
RF = 0.0
SWITCH_COST = 0.0025  # 25bp per full country switch, base case
INITIAL_ENTRY_COST = SWITCH_COST / 2.0

BOOK_START = pd.Timestamp("1982-01-31")
BOOK_END = pd.Timestamp("2021-12-31")


def read_fred(series_id: str, save_name: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    path = RAW / save_name
    path.write_bytes(r.content)
    df = pd.read_csv(path)
    date_col = df.columns[0]
    value_col = df.columns[1]
    s = pd.Series(pd.to_numeric(df[value_col], errors="coerce").values,
                  index=pd.to_datetime(df[date_col]), name=series_id).dropna()
    s.index = s.index.to_period("M").to_timestamp("M")
    return s[~s.index.duplicated(keep="last")].sort_index()


def read_exact_indices():
    kr = pd.read_csv(ROOT / "data" / "indices" / "KOSPI.csv", parse_dates=["Date"])
    us = pd.read_csv(ROOT / "data" / "indices" / "SP500.csv", parse_dates=["Date"])
    kr = kr.set_index("Date").sort_index()
    us = us.set_index("Date").sort_index()
    kr = kr.loc[:LATEST_COMPLETE]
    us = us.loc[:LATEST_COMPLETE]
    return kr, us


def month_end(s: pd.Series) -> pd.Series:
    x = s.dropna().sort_index().resample("ME").last()
    x.index = x.index.to_period("M").to_timestamp("M")
    return x


def splice_proxy_to_exact(proxy: pd.Series, exact_monthly: pd.Series):
    proxy = proxy.loc[:LATEST_COMPLETE].copy()
    exact = exact_monthly.loc[:LATEST_COMPLETE].copy()
    overlap = proxy.index.intersection(exact.index)
    if len(overlap) == 0:
        raise RuntimeError("No overlap between proxy and exact series")
    splice = overlap[0]
    scale = float(exact.loc[splice] / proxy.loc[splice])
    px = proxy * scale
    combined = px.loc[:splice].copy()
    combined = pd.concat([combined, exact.loc[exact.index > splice]])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined, splice, scale


def overlap_diag(proxy: pd.Series, exact: pd.Series, asset: str):
    ov = proxy.index.intersection(exact.index)
    p = proxy.loc[ov].pct_change()
    e = exact.loc[ov].pct_change()
    d = pd.concat([p.rename("proxy"), e.rename("exact")], axis=1).dropna()
    return {
        "asset": asset,
        "overlap_start": d.index.min().date().isoformat(),
        "overlap_end": d.index.max().date().isoformat(),
        "months": len(d),
        "return_corr": d["proxy"].corr(d["exact"]),
        "mean_abs_return_diff": (d["proxy"] - d["exact"]).abs().mean(),
        "max_abs_return_diff": (d["proxy"] - d["exact"]).abs().max(),
    }


def book_proxy_backtest(kr_level: pd.Series, us_level: pd.Series, switch_cost=SWITCH_COST):
    px = pd.concat([kr_level.rename("KOSPI"), us_level.rename("SP500")], axis=1).dropna()
    px = px.loc[:BOOK_END]
    rets = px.pct_change()
    mom = px / px.shift(12) - 1.0
    winner = pd.Series(np.where(mom["KOSPI"] > mom["SP500"], "KOSPI", "SP500"),
                       index=px.index, name="Winner")
    valid = mom.notna().all(axis=1)
    winner = winner.where(valid)

    # Book-convention diagnostic: month-end t signal is applied to close-to-close
    # return t->t+1. This is NOT treated as execution-safe; it is only used to
    # compare with the book's published 1982-2021 figures.
    pos = winner.shift(1)
    gross = pd.Series(index=px.index, dtype=float)
    for c in ["KOSPI", "SP500"]:
        gross.loc[pos == c] = rets.loc[pos == c, c]
    gross.name = "Strategy_Gross"

    change = pos.notna() & pos.shift(1).notna() & (pos != pos.shift(1))
    entry = pos.notna() & pos.shift(1).isna()
    net_factor = pd.Series(1.0, index=px.index)
    net_factor.loc[change] = 1.0 - switch_cost
    net_factor.loc[entry] = 1.0 - switch_cost / 2.0
    net = (1.0 + gross) * net_factor - 1.0
    net.name = "Strategy_Net"

    df = pd.concat([gross, net, rets["KOSPI"], rets["SP500"], pos.rename("Position"),
                    mom["KOSPI"].rename("Mom12_KR"), mom["SP500"].rename("Mom12_US")], axis=1)
    df = df.loc[(df.index >= BOOK_START) & (df.index <= BOOK_END)]
    return df


def first_common_trade_day(kr: pd.DataFrame, us: pd.DataFrame, month: pd.Period):
    k = kr.loc[kr.index.to_period("M") == month]
    u = us.loc[us.index.to_period("M") == month]
    common = k.index.intersection(u.index)
    common = common[(k.loc[common, "Open"].notna()) & (u.loc[common, "Open"].notna())]
    if len(common) == 0:
        return None
    return common[0]


def build_daily_execution(kr: pd.DataFrame, us: pd.DataFrame, switch_cost=SWITCH_COST):
    kr_close_m = month_end(kr["Close"])
    us_close_m = month_end(us["Close"])
    mpx = pd.concat([kr_close_m.rename("KOSPI"), us_close_m.rename("SP500")], axis=1).dropna()
    mom = mpx / mpx.shift(12) - 1.0
    winner = pd.Series(np.where(mom["KOSPI"] > mom["SP500"], "KOSPI", "SP500"),
                       index=mpx.index, name="Winner")
    winner = winner.where(mom.notna().all(axis=1))

    events = []
    for sig_date, asset in winner.dropna().items():
        next_month = sig_date.to_period("M") + 1
        d = first_common_trade_day(kr, us, next_month)
        if d is not None and d <= LATEST_COMPLETE:
            events.append((pd.Timestamp(d), str(asset), pd.Timestamp(sig_date)))
    if not events:
        raise RuntimeError("No execution events")
    events = sorted(events, key=lambda x: x[0])

    start = events[0][0]
    end = min(LATEST_COMPLETE, kr.index.max(), us.index.max())
    cal = kr.index.union(us.index)
    cal = cal[(cal >= start) & (cal <= end)].sort_values()

    k_close = kr["Close"].reindex(cal).ffill()
    u_close = us["Close"].reindex(cal).ffill()

    event_map = {d: (a, s) for d, a, s in events}
    gross_nav = pd.Series(index=cal, dtype=float)
    net_nav = pd.Series(index=cal, dtype=float)
    pos_series = pd.Series(index=cal, dtype=object)

    asset = None
    sh_g = None
    sh_n = None
    last_nav_g = 1.0
    last_nav_n = 1.0
    switch_rows = []

    for d in cal:
        if d in event_map:
            new_asset, signal_date = event_map[d]
            # Both markets trade on event dates by construction.
            if asset is None:
                op_new = float(kr.loc[d, "Open"] if new_asset == "KOSPI" else us.loc[d, "Open"])
                sh_g = 1.0 / op_new
                sh_n = (1.0 - INITIAL_ENTRY_COST) / op_new
                asset = new_asset
                switch_rows.append({"Date": d, "From": "", "To": asset, "SignalDate": signal_date,
                                    "CostRate": INITIAL_ENTRY_COST})
            elif new_asset != asset:
                op_old = float(kr.loc[d, "Open"] if asset == "KOSPI" else us.loc[d, "Open"])
                op_new = float(kr.loc[d, "Open"] if new_asset == "KOSPI" else us.loc[d, "Open"])
                cash_g = float(sh_g) * op_old
                cash_n = float(sh_n) * op_old * (1.0 - switch_cost)
                sh_g = cash_g / op_new
                sh_n = cash_n / op_new
                switch_rows.append({"Date": d, "From": asset, "To": new_asset, "SignalDate": signal_date,
                                    "CostRate": switch_cost})
                asset = new_asset

        if asset is None:
            continue
        close = float(k_close.loc[d] if asset == "KOSPI" else u_close.loc[d])
        last_nav_g = float(sh_g) * close
        last_nav_n = float(sh_n) * close
        gross_nav.loc[d] = last_nav_g
        net_nav.loc[d] = last_nav_n
        pos_series.loc[d] = asset

    out = pd.DataFrame({"Strategy_Gross": gross_nav, "Strategy_Net": net_nav,
                        "Position": pos_series}).dropna(subset=["Strategy_Gross", "Strategy_Net"])

    # Benchmarks normalized to the strategy's first daily NAV observation.
    idx = out.index
    kc = k_close.reindex(idx).ffill()
    uc = u_close.reindex(idx).ffill()
    out["KOSPI"] = kc / float(kc.iloc[0])
    out["SP500"] = uc / float(uc.iloc[0])

    switches = pd.DataFrame(switch_rows)
    return out, switches, mpx, mom, winner


def slice_rebase_daily(daily: pd.DataFrame, start, end):
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    pos = daily.index.searchsorted(start)
    if pos >= len(daily.index):
        raise RuntimeError(f"Empty period start {start}")
    first = daily.index[pos]
    base = daily.iloc[pos - 1] if pos > 0 else None
    x = daily.loc[first:end, ["Strategy_Gross", "Strategy_Net", "KOSPI", "SP500"]].copy()
    if x.empty:
        raise RuntimeError(f"Empty slice {start}~{end}")
    for c in x.columns:
        denom = float(base[c]) if base is not None else float(x[c].iloc[0])
        x[c] = x[c] / denom
    baseline_date = base.name if base is not None else x.index[0] - pd.offsets.BDay(1)
    return x, pd.Timestamp(baseline_date)


def drawdown_and_recovery(nav: pd.Series, baseline_date):
    s = nav.dropna()
    aug = pd.concat([pd.Series([1.0], index=[baseline_date]), s])
    running = aug.cummax()
    dd = aug / running - 1.0
    mdd = float(dd.min())
    mdd_date = pd.Timestamp(dd.idxmin())

    peak_val = float(aug.iloc[0])
    peak_date = aug.index[0]
    underwater_start = None
    longest = 0
    lp = None
    lr = None
    for dt, val in aug.iloc[1:].items():
        val = float(val)
        if val >= peak_val:
            if underwater_start is not None:
                days = (dt - underwater_start).days
                if days > longest:
                    longest = days
                    lp = underwater_start
                    lr = dt
                underwater_start = None
            peak_val = val
            peak_date = dt
        else:
            if underwater_start is None:
                underwater_start = peak_date
    if underwater_start is not None:
        days = (aug.index[-1] - underwater_start).days
        if days > longest:
            longest = days
            lp = underwater_start
            lr = pd.NaT
    return dd, mdd, mdd_date, longest, lp, lr


def metrics_daily(daily: pd.DataFrame, start, end, period, method, switches: pd.DataFrame):
    x, baseline_date = slice_rebase_daily(daily, start, end)
    monthly = x.resample("ME").last()
    rows = []
    for c in ["Strategy_Gross", "Strategy_Net", "KOSPI", "SP500"]:
        vals = monthly[c].dropna()
        ext = pd.concat([pd.Series([1.0], index=[vals.index[0] - pd.offsets.MonthEnd(1)]), vals])
        r = ext.pct_change().dropna()
        years = len(r) / 12.0
        final = float(vals.iloc[-1])
        cagr = final ** (1.0 / years) - 1.0
        vol = float(r.std(ddof=1) * math.sqrt(12))
        sharpe = float(r.mean() / r.std(ddof=1) * math.sqrt(12)) if r.std(ddof=1) > 0 else np.nan
        dd, mdd, mdd_date, rec_days, rec_peak, rec_date = drawdown_and_recovery(x[c], baseline_date)
        rows.append({
            "period": period, "series": c, "method": method,
            "start": vals.index[0].date().isoformat(), "end": vals.index[-1].date().isoformat(),
            "final_multiple": final, "final_asset_usd": final * INITIAL,
            "cumulative_return": final - 1.0, "cagr": cagr,
            "annualized_volatility": vol, "sharpe_rf0": sharpe,
            "mdd": mdd, "mdd_date": mdd_date.date().isoformat(),
            "MDD_source": "daily",
            "max_recovery_days": int(rec_days),
            "max_recovery_months": float(rec_days / 30.4375),
            "max_recovery_peak": "" if rec_peak is None else pd.Timestamp(rec_peak).date().isoformat(),
            "max_recovery_date": "" if pd.isna(rec_date) else pd.Timestamp(rec_date).date().isoformat(),
        })
    sw = switches[(switches["Date"] >= pd.Timestamp(start)) & (switches["Date"] <= pd.Timestamp(end))]
    years = max((x.index[-1] - baseline_date).days / 365.2425, 1e-9)
    turnover = {
        "period": period,
        "switch_count": int((sw["From"] != "").sum()),
        "switches_per_year": float((sw["From"] != "").sum() / years),
        "annualized_two_way_notional_turnover": float(2.0 * (sw["From"] != "").sum() / years),
    }
    return pd.DataFrame(rows), turnover, x, monthly


def metrics_monthly_book(book: pd.DataFrame):
    x = book.dropna(subset=["Strategy_Gross"]).copy()
    # Data limitation: with Korea proxy beginning 1981-01, first 12m signal is
    # known at 1982-01 month-end, so first strategy return is 1982-02.
    start = x.index.min()
    end = x.index.max()
    rows = []
    series_map = {
        "Strategy_Gross": x["Strategy_Gross"],
        "Strategy_Net": x["Strategy_Net"],
        "KOSPI": x["KOSPI"],
        "SP500": x["SP500"],
    }
    for c, r0 in series_map.items():
        r = r0.loc[start:end].fillna(0.0)
        nav = (1.0 + r).cumprod()
        years = len(r) / 12.0
        final = float(nav.iloc[-1])
        cagr = final ** (1.0 / years) - 1.0
        vol = float(r.std(ddof=1) * math.sqrt(12))
        sharpe = float(r.mean() / r.std(ddof=1) * math.sqrt(12)) if r.std(ddof=1) > 0 else np.nan
        aug = pd.concat([pd.Series([1.0], index=[nav.index[0] - pd.offsets.MonthEnd(1)]), nav])
        dd = aug / aug.cummax() - 1.0
        mdd = float(dd.min())
        mdd_date = pd.Timestamp(dd.idxmin())

        peak = float(aug.iloc[0]); peak_date = aug.index[0]
        uw = None; longest = 0; lp = None; lr = None
        for dt, v in aug.iloc[1:].items():
            v = float(v)
            if v >= peak:
                if uw is not None:
                    days = (dt - uw).days
                    if days > longest:
                        longest = days; lp = uw; lr = dt
                    uw = None
                peak = v; peak_date = dt
            elif uw is None:
                uw = peak_date
        if uw is not None:
            days = (aug.index[-1] - uw).days
            if days > longest:
                longest = days; lp = uw; lr = pd.NaT

        rows.append({
            "period": "book_validation", "series": c,
            "method": "monthly_proxy_book_convention",
            "start": nav.index[0].date().isoformat(), "end": nav.index[-1].date().isoformat(),
            "final_multiple": final, "final_asset_usd": final * INITIAL,
            "cumulative_return": final - 1.0, "cagr": cagr,
            "annualized_volatility": vol, "sharpe_rf0": sharpe,
            "mdd": mdd, "mdd_date": mdd_date.date().isoformat(),
            "MDD_source": "monthly_fallback",
            "max_recovery_days": int(longest),
            "max_recovery_months": float(longest / 30.4375),
            "max_recovery_peak": "" if lp is None else pd.Timestamp(lp).date().isoformat(),
            "max_recovery_date": "" if pd.isna(lr) else pd.Timestamp(lr).date().isoformat(),
        })
    return pd.DataFrame(rows)


def cost_sensitivity(daily_base: pd.DataFrame, kr: pd.DataFrame, us: pd.DataFrame, periods):
    rows = []
    for bps in [10, 25, 50]:
        d, sw, *_ = build_daily_execution(kr, us, switch_cost=bps / 10000.0)
        for p, st, en in periods:
            x, _ = slice_rebase_daily(d, st, en)
            m = x["Strategy_Net"].resample("ME").last()
            ext = pd.concat([pd.Series([1.0], index=[m.index[0]-pd.offsets.MonthEnd(1)]), m])
            r = ext.pct_change().dropna()
            final = float(m.iloc[-1])
            years = len(r)/12.0
            nav_daily = x["Strategy_Net"]
            aug = pd.concat([pd.Series([1.0], index=[x.index[0]-pd.offsets.BDay(1)]), nav_daily])
            dd = aug/aug.cummax()-1.0
            rows.append({
                "period": p, "switch_cost_bps": bps, "final_multiple": final,
                "cagr": final**(1/years)-1, "mdd_daily": float(dd.min()),
                "switch_count": int(((sw["Date"]>=pd.Timestamp(st))&(sw["Date"]<=pd.Timestamp(en))&(sw["From"]!="")).sum())
            })
    return pd.DataFrame(rows)


def compact_chart_files(period, x):
    # Wealth uses template's monthly NAV convention.
    m = x[["Strategy_Gross","Strategy_Net","KOSPI","SP500"]].resample("ME").last()
    m.to_csv(OUT / f"chart_wealth_{period}.csv", index_label="Date")

    # Drawdown uses reliable daily NAV. To keep the chat payload compact, preserve
    # each calendar month's daily minimum drawdown plus endpoints.
    dds = {}
    for c in ["Strategy_Gross","Strategy_Net","KOSPI","SP500"]:
        s = x[c]
        dds[c] = s/s.cummax()-1.0
    dd = pd.DataFrame(dds)
    monthly_min = dd.resample("ME").min()
    monthly_min.to_csv(OUT / f"chart_drawdown_dailymin_{period}.csv", index_label="Date")


def main():
    kr_proxy = read_fred("SPASTT01KRM661N", "OECD_KR_SHARE_PRICE_MONTHLY.csv")
    us_proxy = read_fred("SPASTT01USM661N", "OECD_US_SHARE_PRICE_MONTHLY.csv")
    kr, us = read_exact_indices()

    kr_m = month_end(kr["Close"])
    us_m = month_end(us["Close"])
    kr_long, kr_splice, kr_scale = splice_proxy_to_exact(kr_proxy, kr_m)
    us_long, us_splice, us_scale = splice_proxy_to_exact(us_proxy, us_m)

    diags = [
        overlap_diag(kr_proxy, kr_m, "Korea_OECD_vs_KOSPI"),
        overlap_diag(us_proxy, us_m, "US_OECD_vs_SP500"),
    ]
    pd.DataFrame(diags).to_csv(OUT / "proxy_overlap_diagnostics.csv", index=False)

    book = book_proxy_backtest(kr_long, us_long, SWITCH_COST)
    book.to_csv(OUT / "book_proxy_monthly_returns_and_signal.csv", index_label="Date")
    book_summary = metrics_monthly_book(book)

    daily, switches, mpx, mom, winner = build_daily_execution(kr, us, SWITCH_COST)
    daily.to_csv(OUT / "daily_nav_exact_execution.csv", index_label="Date")
    switches.to_csv(OUT / "switch_log.csv", index=False)

    latest_day = daily.index.max()
    periods = [
        ("from_2001", pd.Timestamp("2001-01-01"), latest_day),
        ("from_2021", pd.Timestamp("2021-01-01"), latest_day),
        ("longest", daily.index.min(), latest_day),
    ]

    summaries = [book_summary]
    turnover_rows = []
    for p, st, en in periods:
        sm, to, x, monthly = metrics_daily(daily, st, en, p, "exact_daily_next_common_open", switches)
        summaries.append(sm)
        turnover_rows.append(to)
        compact_chart_files(p, x)

    summary = pd.concat(summaries, ignore_index=True)
    summary.to_csv(OUT / "summary_template_v2_14.csv", index=False)
    pd.DataFrame(turnover_rows).to_csv(OUT / "turnover.csv", index=False)

    sens = cost_sensitivity(daily, kr, us, periods)
    sens.to_csv(OUT / "cost_sensitivity.csv", index=False)

    b = book_summary.set_index("series").loc["Strategy_Gross"]
    book_compare = pd.DataFrame([
        {"metric":"Final multiple", "book":445.0, "reproduced_proxy":float(b["final_multiple"])},
        {"metric":"CAGR", "book":0.162, "reproduced_proxy":float(b["cagr"])},
        {"metric":"MDD", "book":-0.527, "reproduced_proxy":float(b["mdd"])},
    ])
    book_compare["difference"] = book_compare["reproduced_proxy"] - book_compare["book"]
    book_compare.to_csv(OUT / "book_comparison.csv", index=False)

    meta = pd.DataFrame([{
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE.date().isoformat(),
        "initial_capital_usd": INITIAL,
        "base_switch_cost_bps": SWITCH_COST*10000,
        "risk_free_rate": RF,
        "kr_exact_start": kr.index.min().date().isoformat(),
        "us_exact_start": us.index.min().date().isoformat(),
        "daily_strategy_start": daily.index.min().date().isoformat(),
        "book_requested_start": BOOK_START.date().isoformat(),
        "book_actual_first_return": book.dropna(subset=["Strategy_Gross"]).index.min().date().isoformat(),
        "book_end": BOOK_END.date().isoformat(),
        "kr_proxy_start": kr_proxy.index.min().date().isoformat(),
        "us_proxy_start": us_proxy.index.min().date().isoformat(),
        "kr_splice_month": kr_splice.date().isoformat(),
        "us_splice_month": us_splice.date().isoformat(),
        "currency_treatment": "local-currency index levels; no USDKRW conversion",
        "book_validation_status": "EXPLORATORY_PROXY_NOT_EXACT_EXECUTION",
    }])
    meta.to_csv(OUT / "metadata.csv", index=False)

    readme = f"""# Korea-US Relative Momentum v2-14

Rule from book: compare trailing 12-month return of Korea and US equity indices monthly; hold the stronger index.

## Main execution-safe test
- Exact repository indices: data/indices/KOSPI.csv and data/indices/SP500.csv.
- Signal: last available close of each market at each calendar month-end.
- MOM12 = P_t / P_(t-12) - 1.
- Execution: first trading day of the next month on which both markets are open; trade at each market's Open.
- Hold 100% of the selected index until the next signal changes the selected country.
- Base cost: 25bp per full country switch; initial entry 12.5bp.
- Monthly CAGR/volatility/Sharpe; daily MDD/recovery.
- Completed data only through {LATEST_COMPLETE.date()}.

## Book validation layer
- The repository's exact KOSPI history starts {kr.index.min().date()}, later than the book's 1982 start.
- Exploratory long proxy: OECD/FRED broad share-price series for Korea and US, spliced to exact repository indices at first overlap.
- Korea proxy begins {kr_proxy.index.min().date()}, so a 12-month signal is first available at 1982-01 month-end and the first strategy return is 1982-02.
- This layer uses the conventional month-end close-to-close timing only to compare with the book. It is NOT the execution-safe result.
- MDD/recovery therefore use monthly fallback.

## Currency
Index levels are compared and compounded in each index's local-currency terms, matching the book-style index rule. No USD/KRW conversion is imposed. A Korean investor's actually investable ETF implementation can differ materially because of FX, taxes, tracking error and product costs.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    print(summary.to_string(index=False))
    print(book_compare.to_string(index=False))
    print(pd.DataFrame(diags).to_string(index=False))
    print(sens.to_string(index=False))


if __name__ == "__main__":
    main()
