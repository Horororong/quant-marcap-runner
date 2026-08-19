from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import requests
import pandas as pd
import FinanceDataReader as fdr

API_KEY = os.getenv('DART_API_KEY', '').strip()
ROOT = Path('data/financials')
BATCH_DIR = ROOT / 'recent_batches'
STATUS_DIR = Path('data/status')
ROOT.mkdir(parents=True, exist_ok=True)
BATCH_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)

REPORT_CODES = {'Q1':'11013', 'H1':'11012', 'Q3':'11014', 'FY':'11011'}
BASE = 'https://opendart.fss.or.kr/api'
STATE_FILE = STATUS_DIR / 'dart_rotation_state.csv'


def get_corp_codes() -> pd.DataFrame:
    r = requests.get(f'{BASE}/corpCode.xml', params={'crtfc_key': API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    rows = [{child.tag: child.text for child in node} for node in root.findall('list')]
    df = pd.DataFrame(rows)
    df['stock_code'] = df['stock_code'].fillna('').astype(str).str.zfill(6)
    return df


def current_krx_codes() -> pd.DataFrame:
    krx = fdr.StockListing('KRX').copy()
    code_col = 'Code' if 'Code' in krx.columns else 'Symbol'
    name_col = 'Name' if 'Name' in krx.columns else code_col
    out = krx[[code_col, name_col]].rename(columns={code_col:'stock_code', name_col:'stock_name'})
    out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
    return out.drop_duplicates('stock_code')


def fetch_full_fs(corp_code: str, year: int, report_code: str) -> list[dict]:
    params = {'crtfc_key':API_KEY, 'corp_code':corp_code, 'bsns_year':str(year),
              'reprt_code':report_code, 'fs_div':'CFS'}
    r = requests.get(f'{BASE}/fnlttSinglAcntAll.json', params=params, timeout=30)
    r.raise_for_status()
    obj = r.json()
    status = obj.get('status')
    if status == '000':
        return obj.get('list', [])
    if status in {'013','014'}:
        return []
    raise RuntimeError(f'DART status={status} message={obj.get("message")}')


def read_next_offset(total: int) -> int:
    if total <= 0 or not STATE_FILE.exists():
        return 0
    try:
        s = pd.read_csv(STATE_FILE)
        return int(s.iloc[-1]['next_offset']) % total
    except Exception:
        return 0


def main():
    now_utc = datetime.now(timezone.utc)
    if not API_KEY:
        pd.DataFrame([{'status':'SKIPPED','reason':'DART_API_KEY missing',
                       'updated_at_utc':now_utc.isoformat()}]).to_csv(
            STATUS_DIR/'dart_status.csv', index=False, encoding='utf-8-sig')
        return

    corp = get_corp_codes()
    krx = current_krx_codes()
    master = krx.merge(corp[['corp_code','corp_name','stock_code','modify_date']],
                       on='stock_code', how='left').sort_values('stock_code')
    master.to_csv(ROOT/'corp_master.csv', index=False, encoding='utf-8-sig')

    matched = master.dropna(subset=['corp_code']).drop_duplicates('stock_code').reset_index(drop=True)
    total = len(matched)
    batch_size = max(1, int(os.getenv('DART_MAX_COMPANIES', '300')))
    start = read_next_offset(total)
    positions = [(start + i) % total for i in range(min(batch_size, total))] if total else []
    batch = matched.iloc[positions].copy() if positions else matched.iloc[0:0].copy()
    next_offset = (start + len(batch)) % total if total else 0

    now = datetime.now()
    years = list(range(max(2015, now.year - 2), now.year + 1))
    records, errors = [], []

    for _, row in batch.iterrows():
        corp_code = str(row['corp_code'])
        stock_code = str(row['stock_code']).zfill(6)
        for year in years:
            for period, report_code in REPORT_CODES.items():
                try:
                    for raw in fetch_full_fs(corp_code, year, report_code):
                        item = dict(raw)
                        item['stock_code'] = stock_code
                        item['period'] = period
                        item['requested_year'] = year
                        rcept = str(item.get('rcept_no', ''))
                        item['filing_date'] = rcept[:8] if len(rcept) >= 8 else ''
                        records.append(item)
                except Exception as e:
                    errors.append({'stock_code':stock_code,'corp_code':corp_code,
                                   'year':year,'period':period,'error':repr(e)})

    batch_tag = f'{start:05d}_{(start + max(len(batch)-1,0)):05d}'
    if records:
        df = pd.DataFrame(records)
        keys = [c for c in ['rcept_no','corp_code','fs_div','sj_div','account_id','account_nm','thstrm_nm'] if c in df.columns]
        if keys:
            df = df.drop_duplicates(keys, keep='last')
        df.to_csv(BATCH_DIR/f'dart_recent_{batch_tag}.csv.gz', index=False,
                  encoding='utf-8-sig', compression='gzip')

    pd.DataFrame(errors).to_csv(ROOT/f'dart_errors_{batch_tag}.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([{
        'total_matched_companies':total,
        'batch_size':len(batch),
        'batch_start_offset':start,
        'next_offset':next_offset,
        'cycle_completed':bool(total and next_offset <= start),
        'updated_at_utc':now_utc.isoformat(),
    }]).to_csv(STATE_FILE, index=False, encoding='utf-8-sig')

    pd.DataFrame([{
        'status':'OK',
        'total_matched_companies':total,
        'companies_attempted':len(batch),
        'batch_start_offset':start,
        'next_offset':next_offset,
        'records':len(records),
        'errors':len(errors),
        'years':','.join(map(str, years)),
        'updated_at_utc':now_utc.isoformat(),
    }]).to_csv(STATUS_DIR/'dart_status.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
