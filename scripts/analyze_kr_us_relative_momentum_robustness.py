from pathlib import Path
import pandas as pd

import backtest_kr_us_relative_momentum_v214 as core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "kr_us_relative_momentum_v214"

def main():
    kr = pd.read_csv(ROOT / "data" / "indices" / "KOSPI200.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    us = pd.read_csv(ROOT / "data" / "indices" / "SP500.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    kr = kr.loc[:core.LATEST_COMPLETE]
    us = us.loc[:core.LATEST_COMPLETE]

    daily, switches, *_ = core.build_daily_execution(kr, us, core.SWITCH_COST)
    latest = daily.index.max()
    periods = [
        ("from_2001", pd.Timestamp("2001-01-01"), latest),
        ("from_2021", pd.Timestamp("2021-01-01"), latest),
        ("longest", daily.index.min(), latest),
    ]
    rows = []
    for p, st, en in periods:
        sm, to, *_ = core.metrics_daily(daily, st, en, p, "KOSPI200_exact_daily_next_common_open", switches)
        sm = sm[sm["series"].isin(["Strategy_Gross","Strategy_Net","KOSPI","SP500"])].copy()
        sm["kr_index"] = "KOSPI200"
        rows.append(sm)
    pd.concat(rows, ignore_index=True).to_csv(OUT / "robustness_kospi200.csv", index=False)
    print(pd.concat(rows, ignore_index=True).to_string(index=False))

if __name__ == "__main__":
    main()
