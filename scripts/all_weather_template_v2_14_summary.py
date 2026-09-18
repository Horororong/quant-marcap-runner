from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"all_weather_long"
INITIAL=10_000.0
END=pd.Timestamp("2026-08-31")
PERIODS={
    "from_2001": pd.Timestamp("2001-01-01"),
    "from_2021": pd.Timestamp("2021-01-01"),
    "longest": None,
}

def sample_std(x):
    return float(x.std(ddof=1))

def month_end_nav(daily: pd.DataFrame) -> pd.DataFrame:
    x=daily.loc[:END,["NAV_Gross","NAV_Net","NAV_SPY"]].copy()
    return x.resample("ME").last()

def slice_rebase(daily,start):
    if start is None:
        x=daily.loc[:END].copy()
        base=None
    else:
        pos=daily.index.searchsorted(start)
        while pos < len(daily.index) and daily.index[pos] < start:
            pos += 1
        if pos >= len(daily): raise RuntimeError(f"empty period {start}")
        first=daily.index[pos]
        base=daily.iloc[pos-1] if pos>0 else None
        x=daily.loc[first:END].copy()
    for c in ["NAV_Gross","NAV_Net","NAV_SPY"]:
        denom=float(base[c]) if base is not None else float(x[c].iloc[0])
        x[c]=x[c]/denom
    return x, (base.name if base is not None else None)

def exact_monthly_metrics(daily,start,is_longest=False):
    x,baseline_date=slice_rebase(daily,start)
    monthly=x[["NAV_Gross","NAV_Net","NAV_SPY"]].resample("ME").last()
    rows=[]
    for c in ["NAV_Gross","NAV_Net","NAV_SPY"]:
        vals=monthly[c].dropna()
        ext=pd.concat([pd.Series([1.0],index=[vals.index[0]-pd.offsets.MonthEnd(1)]),vals])
        rets=ext.pct_change().dropna()
        if is_longest:
            perf_base=(x.index[0]-pd.offsets.BDay(1))
            years=(vals.index[-1]-perf_base).days/365.2425
            stats=rets.iloc[1:] if perf_base.to_period("M")==vals.index[0].to_period("M") else rets
        else:
            years=len(rets)/12.0
            stats=rets
        final=float(vals.iloc[-1])
        cagr=final**(1.0/years)-1.0
        vol=float(stats.std(ddof=1)*math.sqrt(12))
        sharpe=float(stats.mean()/stats.std(ddof=1)*math.sqrt(12)) if stats.std(ddof=1)>0 else np.nan

        # Daily drawdown with explicit baseline NAV=1 before first in-period observation.
        s=x[c].dropna()
        aug=pd.concat([pd.Series([1.0],index=[baseline_date if baseline_date is not None else (s.index[0]-pd.offsets.BDay(1))]),s])
        running=aug.cummax()
        dd=aug/running-1.0
        mdd=float(dd.min()); mdd_date=dd.idxmin()

        # Maximum time under water from peak date to recovery (or sample end).
        peak_val=float(aug.iloc[0]); peak_date=aug.index[0]
        underwater_start=None; longest=0; longest_peak=None; longest_recovery=None
        for dt,val in aug.iloc[1:].items():
            val=float(val)
            if val>=peak_val:
                if underwater_start is not None:
                    days=(dt-underwater_start).days
                    if days>longest:
                        longest=days; longest_peak=underwater_start; longest_recovery=dt
                    underwater_start=None
                peak_val=val; peak_date=dt
            else:
                if underwater_start is None:
                    underwater_start=peak_date
        if underwater_start is not None:
            days=(aug.index[-1]-underwater_start).days
            if days>longest:
                longest=days; longest_peak=underwater_start; longest_recovery=pd.NaT

        rows.append({
            "series":c,
            "start":vals.index[0].date().isoformat(),
            "end":vals.index[-1].date().isoformat(),
            "final_multiple":final,
            "final_asset_usd":final*INITIAL,
            "cumulative_return":final-1.0,
            "cagr":cagr,
            "annualized_volatility_monthly":vol,
            "sharpe_monthly_rf0":sharpe,
            "mdd_daily":mdd,
            "mdd_date":mdd_date.date().isoformat(),
            "max_recovery_days":int(longest),
            "max_recovery_months":float(longest/30.4375),
            "max_recovery_peak":"" if longest_peak is None else longest_peak.date().isoformat(),
            "max_recovery_date":"" if pd.isna(longest_recovery) else longest_recovery.date().isoformat(),
            "monthly_return_count":len(rets),
            "daily_obs":len(s),
        })
    return pd.DataFrame(rows), monthly

def benchmark_stats(monthly):
    ext=pd.concat([pd.DataFrame({"NAV_Gross":[1.0],"NAV_SPY":[1.0]},index=[monthly.index[0]-pd.offsets.MonthEnd(1)]),monthly[["NAV_Gross","NAV_SPY"]]])
    r=ext.pct_change().dropna()
    g=r["NAV_Gross"]; b=r["NAV_SPY"]; active=g-b
    te=float(active.std(ddof=1)*math.sqrt(12))
    ir=float(active.mean()/active.std(ddof=1)*math.sqrt(12)) if active.std(ddof=1)>0 else np.nan
    beta=float(g.cov(b)/b.var(ddof=1)) if b.var(ddof=1)>0 else np.nan
    alpha=float((g.mean()-beta*b.mean())*12)
    return {"tracking_error":te,"information_ratio":ir,"beta":beta,"alpha_annualized_arithmetic_rf0":alpha}

def main():
    path=OUT/"daily_nav.csv"
    daily=pd.read_csv(path,parse_dates=["Date"]).set_index("Date").sort_index()
    daily=daily.loc[:END]
    # Normalize entire panel at the first daily observation so SPY starts at 1 too.
    for c in ["NAV_Gross","NAV_Net","NAV_SPY"]:
        daily[c]=daily[c]/float(daily[c].iloc[0])

    summaries=[]; bench=[]
    for name,start in PERIODS.items():
        sm,monthly=exact_monthly_metrics(daily,start,is_longest=(name=="longest"))
        sm.insert(0,"period",name)
        summaries.append(sm)
        b=benchmark_stats(monthly)
        b["period"]=name
        gross=sm.loc[sm["series"]=="NAV_Gross"].iloc[0]
        spy=sm.loc[sm["series"]=="NAV_SPY"].iloc[0]
        b["excess_cagr_vs_spy"]=float(gross["cagr"]-spy["cagr"])
        bench.append(b)

    summary=pd.concat(summaries,ignore_index=True)
    summary.to_csv(OUT/"summary_template_v2_14.csv",index=False)
    pd.DataFrame(bench).to_csv(OUT/"benchmark_template_v2_14.csv",index=False)

    # Gross calendar-year returns, compounded from exact daily NAV.
    ret=daily["NAV_Gross"].pct_change().fillna(0.0)
    annual=(1.0+ret).groupby(ret.index.year).prod()-1.0
    annual.index.name="Year"; annual.name="GrossReturn"
    annual.to_csv(OUT/"annual_returns_template.csv")

    # Cross-check key invariants.
    base=summary[(summary.period=="from_2001")&(summary.series=="NAV_Gross")].iloc[0]
    recent=summary[(summary.period=="from_2021")&(summary.series=="NAV_Gross")].iloc[0]
    assert abs(base["mdd_daily"] - (-0.2890058028958309)) < 1e-10
    assert abs(recent["mdd_daily"] - (-0.2686489305010741)) < 1e-10
    print(summary.to_string(index=False))
    print(pd.DataFrame(bench).to_string(index=False))

if __name__=="__main__":
    main()
