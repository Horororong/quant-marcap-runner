from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import traceback
import pandas as pd
import requests
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
START_KOSDAQ150 = '2015-07-13'
KRX_KOSDAQ_INDEX_URL = 'https://data-dbg.krx.co.kr/svc/apis/idx/kosdaq_dd_trd'

INDEX_SERIES = {
    'KOSPI': 'KS11',
    'KOSDAQ': 'KQ11',
    'KOSPI200': 'KS200',
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


def _num(v):
    if v is None or v == '':
        return None
    return pd.to_numeric(str(v).replace(',', ''), errors='coerce')


def _fetch_krx_kosdaq150_day(day: pd.Timestamp, auth_key: str):
    r = requests.get(
        KRX_KOSDAQ_INDEX_URL,
        headers={'AUTH_KEY': auth_key},
        params={'basDd': day.strftime('%Y%m%d')},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()
    rows = payload.get('OutBlock_1') or payload.get('output') or []
    for row in rows:
        idx_name = str(row.get('IDX_NM', '')).replace(' ', '').upper()
        if idx_name in {'코스닥150', 'KOSDAQ150'}:
            fluc_rt = _num(row.get('FLUC_RT'))
            return {
                'Date': pd.to_datetime(row.get('BAS_DD') or day.strftime('%Y%m%d')),
                'Open': _num(row.get('OPNPRC_IDX')),
                'High': _num(row.get('HGPRC_IDX')),
                'Low': _num(row.get('LWPRC_IDX')),
                'Close': _num(row.get('CLSPRC_IDX')),
                'Volume': _num(row.get('ACC_TRDVOL')),
                'Change': (fluc_rt / 100.0) if pd.notna(fluc_rt) else None,
                'Amount': _num(row.get('ACC_TRDVAL')),
                'MarCap': _num(row.get('MKTCAP')),
            }
    return None


def read_kosdaq150_official() -> pd.DataFrame:
    auth_key = os.getenv('KRX_AUTH_KEY', '').strip()
    if not auth_key:
        raise RuntimeError('KRX_AUTH_KEY is not configured')

    p = DIRS['indices'] / 'KOSDAQ150.csv'
    existing = pd.DataFrame()
    if p.exists():
        existing = normalize(pd.read_csv(p))

    today = pd.Timestamp.now(tz='Asia/Seoul').tz_localize(None).normalize()
    if len(existing):
        start = max(existing['Date'].max().normalize() - pd.Timedelta(days=7), pd.Timestamp(START_KOSDAQ150))
    else:
        start = pd.Timestamp(START_KOSDAQ150)

    days = pd.date_range(start, today, freq='B')
    fresh_rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_krx_kosdaq150_day, d, auth_key): d for d in days}
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                fresh_rows.append(row)

    fresh = pd.DataFrame(fresh_rows)
    if len(existing) and len(fresh):
        return normalize(pd.concat([existing, fresh], ignore_index=True))
    if len(existing):
        return existing
    return normalize(fresh)


def main():
    status = []

    for name, symbol in INDEX_SERIES.items():
        try:
            print(f'INDEX {name} <- {symbol}', flush=True)
            status.append(save_series('indices', name, fdr.DataReader(symbol, START_MARKET)))
        except Exception as e:
            status.append({'category':'indices','name':name,'rows':0,'start_date':'','end_date':'','status':'ERROR','error':repr(e)})
            traceback.print_exc()

    try:
        print('INDEX KOSDAQ150 <- official KRX Open API', flush=True)
        status.append(save_series('indices', 'KOSDAQ150', read_kosdaq150_official()))
    except Exception as e:
        status.append({'category':'indices','name':'KOSDAQ150','rows':0,'start_date':'','end_date':'','status':'ERROR','error':repr(e)})
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
