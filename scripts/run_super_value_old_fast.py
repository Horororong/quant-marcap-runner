from pathlib import Path
import pandas as pd
from backtest_super_value_original import run_sample, OUT  # execution-filtered engine

nav, sel, m, fac, de = run_sample("2016_2019","2016-09-01","2019-09-30","2016-10~2019-09")
nav.to_csv(OUT/"nav_old_fast.csv", encoding="utf-8-sig")
sel.to_csv(OUT/"selections_old_fast.csv", index=False, encoding="utf-8-sig")
m.to_csv(OUT/"metrics_old_fast.csv", index=False, encoding="utf-8-sig")
pd.DataFrame([{
    "factor_rows":len(fac),"factor_codes":fac.stock_code.nunique(),
    "factor_min":fac.available_date.min(),"factor_max":fac.available_date.max(),
    "signals":sel.signal_date.nunique(),"delisting_loss_events":de
}]).to_csv(OUT/"coverage_old_fast.csv", index=False, encoding="utf-8-sig")
print(m.to_string(index=False))
