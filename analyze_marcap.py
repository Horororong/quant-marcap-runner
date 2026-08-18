from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path
import pandas as pd
import numpy as np

START = pd.Timestamp('1998-10-20')
END = pd.Timestamp('2025-09-05')
YEARS = range(1998, 2026)
HORIZONS = [1, 5, 21, 63, 126, 252]
DATA_DIR = Path('marcap_data')
OUT_DIR = Path('results')
DATA_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

BASE = 'https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet'


def download_year(year: int) -> Path:
    p = DATA_DIR / f'marcap-{year}.parquet'
    if not p.exists() or p.stat().st_size < 1000:
        url = BASE.format(year=year)
        print(f'Downloading {year}: {url}', flush=True)
        urllib.request.urlretrieve(url, p)
    return p


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    # Be robust to Date as either column or index.
    if 'Date' not in df.columns:
        df = df.reset_index()
    if 'Date' not in df.columns:
        # Some parquet writers may preserve unnamed index.
        first = df.columns[0]
        df = df.rename(columns={first: 'Date'})
    needed = ['Date','Code','Name','Close','Volume','Amount','Marcap','Stocks','Market']
    keep = [c for c in needed if c in df.columns]
    df = df[keep].copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    for c in ['Close','Volume','Amount','Marcap','Stocks']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def load_all() -> pd.DataFrame:
    parts = []
    for y in YEARS:
        p = download_year(y)
        d = standardize(pd.read_parquet(p))
        d = d[(d['Date'] >= START) & (d['Date'] <= END)]
        if len(d):
            parts.append(d)
            print(y, len(d), d['Date'].min(), d['Date'].max(), flush=True)
    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values(['Date','Code']).drop_duplicates(['Date','Code'], keep='last')
    return df


def build_calendar(df: pd.DataFrame) -> pd.DataFrame:
    dates = pd.Index(sorted(df['Date'].dropna().unique()))
    cal = pd.DataFrame({'Date': dates})
    for h in HORIZONS:
        arr = np.full(len(dates), np.datetime64('NaT'), dtype='datetime64[ns]')
        if len(dates) > h:
            arr[:-h] = dates[h:]
        cal[f'target_{h}'] = arr
    return cal


def compute_horizon_stats(df: pd.DataFrame, cal: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = df[['Date','Code','Close']].copy()
    base = base[(base['Close'].notna()) & (base['Close'] > 0)]

    # Last available close/date per security. Used as a proxy exit when the security disappears before target date.
    last = (base.sort_values(['Code','Date'])
                .groupby('Code', as_index=False)
                .tail(1)[['Code','Date','Close']]
                .rename(columns={'Date':'last_date','Close':'last_close'}))

    rows = []
    annual_rows = []
    date_map = cal.set_index('Date')

    for h in HORIZONS:
        print(f'Computing horizon {h}', flush=True)
        x = base.copy()
        x['target_date'] = x['Date'].map(date_map[f'target_{h}'])
        x = x[x['target_date'].notna()].copy()

        fut = base.rename(columns={'Date':'target_date','Close':'target_close'})
        x = x.merge(fut[['target_date','Code','target_close']], on=['target_date','Code'], how='left')
        x = x.merge(last, on='Code', how='left')

        # Strict close-to-close sample: only if target-date close exists.
        strict = x[x['target_close'].notna()].copy()
        strict['ret'] = strict['target_close'] / strict['Close'] - 1.0
        strict_up = strict['ret'] > 0  # zero is explicitly NOT up

        # PIT proxy: if security no longer has a target-date close and its final date is before target,
        # liquidate at its last observed close. This avoids silently deleting delisted/disappeared names,
        # but is a proxy, not a true delisting-return series.
        proxy = x.copy()
        use_last = proxy['target_close'].isna() & (proxy['last_date'] < proxy['target_date'])
        proxy['exit_close'] = proxy['target_close']
        proxy.loc[use_last, 'exit_close'] = proxy.loc[use_last, 'last_close']
        proxy = proxy[proxy['exit_close'].notna()].copy()
        proxy['ret'] = proxy['exit_close'] / proxy['Close'] - 1.0
        proxy_up = proxy['ret'] > 0

        rows.append({
            'horizon_trading_days': h,
            'label': {1:'1일',5:'1주',21:'1개월',63:'3개월',126:'6개월',252:'1년'}[h],
            'strict_n': int(len(strict)),
            'strict_up_n': int(strict_up.sum()),
            'strict_nonup_n': int((~strict_up).sum()),
            'strict_up_probability': float(strict_up.mean()) if len(strict) else np.nan,
            'pit_proxy_n': int(len(proxy)),
            'pit_proxy_up_n': int(proxy_up.sum()),
            'pit_proxy_nonup_n': int((~proxy_up).sum()),
            'pit_proxy_up_probability': float(proxy_up.mean()) if len(proxy) else np.nan,
            'proxy_last_exit_n': int(use_last.sum()),
            'missing_even_after_proxy_n': int(x['target_close'].isna().sum() - use_last.sum()),
        })

        # Annual diagnostics based on entry year, PIT proxy definition.
        proxy['entry_year'] = proxy['Date'].dt.year
        for yr, g in proxy.groupby('entry_year'):
            up = g['ret'] > 0
            annual_rows.append({
                'entry_year': int(yr),
                'horizon_trading_days': h,
                'n': int(len(g)),
                'up_n': int(up.sum()),
                'up_probability': float(up.mean()),
                'mean_return': float(g['ret'].mean()),
                'median_return': float(g['ret'].median()),
            })

    return pd.DataFrame(rows), pd.DataFrame(annual_rows)


def diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    dates = df['Date'].drop_duplicates().sort_values()
    by_code = df.groupby('Code').agg(first_date=('Date','min'), last_date=('Date','max'), rows=('Date','size'), name=('Name','last') if 'Name' in df.columns else ('Code','last')).reset_index()
    last_market_date = df['Date'].max()
    ended_early = by_code['last_date'] < last_market_date

    out = [
        ('start_date', str(df['Date'].min().date())),
        ('end_date', str(df['Date'].max().date())),
        ('rows', str(len(df))),
        ('unique_trading_dates', str(df['Date'].nunique())),
        ('unique_codes', str(df['Code'].nunique())),
        ('codes_ending_before_final_date', str(int(ended_early.sum()))),
        ('duplicate_date_code_rows_after_dedup', str(int(df.duplicated(['Date','Code']).sum()))),
        ('close_zero_or_missing_rows', str(int((df['Close'].isna() | (df['Close'] <= 0)).sum()))),
        ('volume_zero_or_missing_rows', str(int((df['Volume'].isna() | (df['Volume'] <= 0)).sum())) if 'Volume' in df.columns else 'NA'),
    ]
    if 'Market' in df.columns:
        vc = df['Market'].fillna('NA').astype(str).value_counts()
        for k,v in vc.items():
            out.append((f'market_rows::{k}', str(int(v))))
    return pd.DataFrame(out, columns=['metric','value'])


def main():
    df = load_all()
    print('Loaded', len(df), 'rows', df['Code'].nunique(), 'codes', flush=True)

    diag = diagnostics(df)
    diag.to_csv(OUT_DIR/'pit_diagnostics.csv', index=False, encoding='utf-8-sig')

    cal = build_calendar(df)
    stats, annual = compute_horizon_stats(df, cal)
    stats.to_csv(OUT_DIR/'holding_period_up_probability.csv', index=False, encoding='utf-8-sig')
    annual.to_csv(OUT_DIR/'holding_period_up_probability_by_year.csv', index=False, encoding='utf-8-sig')

    # Security life table for auditing survivorship / disappearance.
    life = df.groupby('Code').agg(
        name=('Name','last') if 'Name' in df.columns else ('Code','last'),
        first_date=('Date','min'),
        last_date=('Date','max'),
        observations=('Date','size'),
        last_close=('Close','last'),
        last_market=('Market','last') if 'Market' in df.columns else ('Code','last'),
    ).reset_index()
    life['ends_before_sample_end'] = life['last_date'] < END
    life.to_csv(OUT_DIR/'security_life_table.csv', index=False, encoding='utf-8-sig')

    # Human-readable summary.
    with open(OUT_DIR/'SUMMARY.md','w',encoding='utf-8') as f:
        f.write('# KRX marcap PIT analysis\n\n')
        f.write(f'- Sample: {START.date()} to {END.date()}\n')
        f.write(f'- Rows: {len(df):,}\n')
        f.write(f'- Unique codes: {df.Code.nunique():,}\n')
        f.write(f'- Trading dates: {df.Date.nunique():,}\n\n')
        f.write('## Holding-period up probability\n\n')
        f.write(stats.to_markdown(index=False))
        f.write('\n\n')
        f.write('Definition: return > 0 is up; return == 0 is non-up. Strict requires a close on the exact target market trading date. PIT proxy uses the last observed close when a security disappears before the target date; this avoids dropping delisted/disappeared names but is not an exact delisting-return series.\n')

    print(stats.to_string(index=False), flush=True)

if __name__ == '__main__':
    main()
