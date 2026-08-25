from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path('results/anchor_sail_moat')
nav = pd.read_csv(OUT / 'daily_nav.csv', index_col=0, parse_dates=True)
nav.index = pd.to_datetime(nav.index)
rows=[]
for year,g in nav.groupby(nav.index.year):
    for col in nav.columns:
        s=g[col].dropna()
        if len(s)==0: continue
        prev=nav.loc[nav.index < s.index[0], col].dropna()
        start_val=float(prev.iloc[-1]) if len(prev) else float(s.iloc[0])
        end_val=float(s.iloc[-1])
        annual_return=end_val/start_val-1.0
        path=pd.concat([pd.Series([start_val],index=[s.index[0]-pd.Timedelta(microseconds=1)]),s])
        annual_mdd=float((path/path.cummax()-1.0).min())
        rows.append({'Year':int(year),'Strategy':col,'Annual_Return':annual_return,'Annual_MDD':annual_mdd,'Year_End_NAV':end_val})
yearly=pd.DataFrame(rows)
yearly.to_csv(OUT/'yearly_return_mdd.csv',index=False,encoding='utf-8-sig')
yearly[yearly['Strategy']=='닻과 돛(해자기업)'][['Year','Annual_Return','Annual_MDD','Year_End_NAV']].to_csv(OUT/'yearly_main.csv',index=False,encoding='utf-8-sig')
wide=yearly.pivot(index='Year',columns='Strategy',values=['Annual_Return','Annual_MDD','Year_End_NAV'])
wide.to_csv(OUT/'yearly_return_mdd_wide.csv',encoding='utf-8-sig')

def cagr_between(series,start_date,end_date):
    s=series.loc[(series.index>=pd.Timestamp(start_date))&(series.index<=pd.Timestamp(end_date))].dropna()
    if len(s)<2:return np.nan
    years=(s.index[-1]-s.index[0]).days/365.25
    return (float(s.iloc[-1])/float(s.iloc[0]))**(1/years)-1 if years>0 else np.nan
periods=[('1990-2024','1990-01-02','2024-12-31'),('2005-2024','2005-01-03','2024-12-31'),('2020-2024','2020-01-01','2024-12-31'),('2023-2024','2023-01-01','2024-12-31'),('2025 only','2025-01-01','2025-12-31'),('2026 YTD','2026-01-01',nav.index.max().date().isoformat()),('1990-full',nav.index.min().date().isoformat(),nav.index.max().date().isoformat())]
prows=[]
for label,a,b in periods:
    for col in nav.columns:prows.append({'Period':label,'Strategy':col,'CAGR_or_PeriodReturn':cagr_between(nav[col],a,b)})
pd.DataFrame(prows).to_csv(OUT/'period_cagr_diagnostics.csv',index=False,encoding='utf-8-sig')
cut=nav.loc[nav.index<=pd.Timestamp('2024-12-31')]
rows2=[]
for col in nav.columns:
    full=nav[col].dropna();pre=cut[col].dropna();yf=(full.index[-1]-full.index[0]).days/365.25;yp=(pre.index[-1]-pre.index[0]).days/365.25
    full_cagr=(full.iloc[-1]/full.iloc[0])**(1/yf)-1;pre_cagr=(pre.iloc[-1]/pre.iloc[0])**(1/yp)-1
    rows2.append({'Strategy':col,'CAGR_full':full_cagr,'CAGR_through_2024':pre_cagr,'CAGR_lift_from_2025plus_pp':(full_cagr-pre_cagr)*100})
pd.DataFrame(rows2).to_csv(OUT/'cagr_2025_lift.csv',index=False,encoding='utf-8-sig')
print(yearly[yearly['Strategy']=='닻과 돛(해자기업)'].to_string(index=False))
