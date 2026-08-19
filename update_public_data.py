from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import traceback
import pandas as pd
import FinanceDataReader as fdr

ROOT = Path('data')
DIRS = {
    'indices': ROOT / 'indices',
    'fx': ROOT / 'fx',
    'macro': ROOT / 'macro',
    'status': ROOT / 'status',
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

START_MARKET = '1995-01-01'
START_MACRO = '1995-01-01'

INDEX_SERIES = {
    'KOSPI': 'KS11',
    'KOSDAQ': 'KQ11',
    'KOSPI200': 'KS200',
    'KOSDAQ150': 'KQ150',
    'DOW': 'DJI',
    'NASDAQ_COMPOSITE': 'IXIC',
    'SP500': 'US500',
    'VIX': 'VIX',
}

FX_SERIES = {
    'USDKRW': 'USD/KRW',
}

FRED_SERIES = {
    'US10Y': 'DGS10',
    'US2Y': 'DGS2',
    'US10Y2Y_SPREAD': 'T10Y2Y',
    'FED_FUNDS_EFFECTIVE': 'DFF',
    'US_CPI': 'CPIAUCSL',
    'US_UNEMPLOYMENT': 'UNRATE',
    'US_INDUSTRIAL_PRODUCTION': 'INDPRO',
}


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()
    x = df.copy()
    if isinstance(x.index, pd.DatetimeIndex):
        x = x.reset_index()
    if 'Date' not in x.columns:
        first = x.columns[0]
        x = x.rename(columns={first: 'Date'})
    x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
    x = x.dropna(subset=['Date']).sort_values('Date')
    x = x.drop_duplicates(subset=['Date'], keep='last')
    return x


def save_series(category: str, name: str, df: pd.DataFrame) -> dict:
    p = DIRS[category] / f'{name}.csv'
    x = normalize(df)
    if len(x) == 0:
        raise RuntimeError(f'empty dataframe: {category}/{name}')
    x.to_csv(p, index=False, encoding='utf-8-sig')
    return {
        'category': category,
        'name': name,
        'rows': len(x),
        'start_date': str(x['Date'].min().date()),
        'end_date': str(x['Date'].max().date()),
        'status': 'OK',
        'error': '',
    }


def main():
    status = []

    for name, symbol in INDEX_SERIES.items():
        try:
            print(f'INDEX {name} <- {symbol}', flush=True)
            status.append(save_series('indices', name, fdr.DataReader(symbol, START_MARKET)))
        except Exception as e:
            status.append({'category':'indices','name':name,'rows':0,'start_date':'','end_date':'','status':'ERROR','error':repr(e)})
            traceback.print_exc()

    for name, symbol in FX_SERIES.items():
        try:
            print(f'FX {name} <- {symbol}', flush=True)
            status.append(save_series('fx', name, fdr.DataReader(symbol, START_MARKET)))
        except Exception as e:
            status.append({'category':'fx','name':name,'rows':0,'start_date':'','end_date':'','status':'ERROR','error':repr(e)})
            traceback.print_exc()

    for name, fred_id in FRED_SERIES.items():
        try:
            print(f'FRED {name} <- {fred_id}', flush=True)
            status.append(save_series('macro', name, fdr.DataReader(f'FRED:{fred_id}', START_MACRO)))
        except Exception as e:
            status.append({'category':'macro','name':name,'rows':0,'start_date':'','end_date':'','status':'ERROR','error':repr(e)})
            traceback.print_exc()

    st = pd.DataFrame(status)
    st['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    st.to_csv(DIRS['status'] / 'public_data_status.csv', index=False, encoding='utf-8-sig')

    failed = st[st['status'] != 'OK']
    print(st.to_string(index=False), flush=True)
    if len(failed):
        print(f'WARNING: {len(failed)} series failed; successful series were still saved.', flush=True)


if __name__ == '__main__':
    main()
