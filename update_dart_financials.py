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
ROOT.mkdir(parents=True, exist_ok=True)
STATUS_DIR = Path('data/status')
STATUS_DIR.mkdir(parents=True, exist_ok=True)

REPORT_CODES = {
    'Q1': '11013',
    'H1': '11012',
    'Q3': '11014',
    'FY': '11011',
}

BASE = 'https://opendart.fss.or.kr/api'


def get_corp_codes() -> pd.DataFrame:
    r = requests.get(f'{BASE}/corpCode.xml', params={'crtfc_key': API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml_bytes = z.read(z.namelist()[0])
    root = ET.fromstring(xml_bytes)
    rows = []
    for node in root.findall('list'):
        rows.append({child.tag: child.text for child in node})
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
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': report_code,
        'fs_div': 'CFS',
    }
    r = requests.get(f'{BASE}/fnlttSinglAcntAll.json', params=params, timeout=30)
    r.raise_for_status()
    obj = r.json()
    status = obj.get('status')
    if status == '000':
        return obj.get('list', [])
    if status in {'013', '014'}:  # no data / file not found type responses
        return []
    raise RuntimeError(f'DART status={status} message={obj.get("message")} corp={corp_code} year={year} report={report_code}')


def main():
    if not API_KEY:
        print('DART_API_KEY is not configured. Skipping DART update safely.')
        pd.DataFrame([{
            'status':'SKIPPED',
            'reason':'DART_API_KEY missing',
            'updated_at_utc':datetime.now(timezone.utc).isoformat(),
        }]).to_csv(STATUS_DIR/'dart_status.csv', index=False, encoding='utf-8-sig')
        return

    corp = get_corp_codes()
    krx = current_krx_codes()
    master = krx.merge(corp[['corp_code','corp_name','stock_code','modify_date']], on='stock_code', how='left')
    master.to_csv(ROOT/'corp_master.csv', index=False, encoding='utf-8-sig')

    # Daily automation is intentionally incremental: recent fiscal years only.
    # Historical PIT backfill should be run separately to avoid excessive API calls.
    now = datetime.now()
    years = list(range(max(2015, now.year - 2), now.year + 1))

    records = []
    errors = []
    matched = master.dropna(subset=['corp_code']).copy()

    # Conservative cap for daily CI runs. Increase with DART_MAX_COMPANIES secret/env if desired.
    max_companies = int(os.getenv('DART_MAX_COMPANIES', '300'))
    matched = matched.head(max_companies)

    for _, row in matched.iterrows():
        corp_code = str(row['corp_code'])
        stock_code = str(row['stock_code']).zfill(6)
        for year in years:
            for period, report_code in REPORT_CODES.items():
                try:
                    items = fetch_full_fs(corp_code, year, report_code)
                    for item in items:
                        item = dict(item)
                        item['stock_code'] = stock_code
                        item['period'] = period
                        item['requested_year'] = year
                        rcept = str(item.get('rcept_no', ''))
                        item['filing_date'] = rcept[:8] if len(rcept) >= 8 else ''
                        records.append(item)
                except Exception as e:
                    errors.append({'stock_code':stock_code,'corp_code':corp_code,'year':year,'period':period,'error':repr(e)})

    if records:
        df = pd.DataFrame(records)
        key_cols = [c for c in ['rcept_no','corp_code','fs_div','sj_div','account_id','account_nm','thstrm_nm'] if c in df.columns]
        if key_cols:
            df = df.drop_duplicates(key_cols, keep='last')
        df.to_csv(ROOT/'dart_full_financial_statements_recent.csv', index=False, encoding='utf-8-sig')

    pd.DataFrame(errors).to_csv(ROOT/'dart_errors.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([{
        'status':'OK',
        'companies_attempted':len(matched),
        'records':len(records),
        'errors':len(errors),
        'years':','.join(map(str, years)),
        'updated_at_utc':datetime.now(timezone.utc).isoformat(),
    }]).to_csv(STATUS_DIR/'dart_status.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
