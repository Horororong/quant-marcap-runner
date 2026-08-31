from __future__ import annotations

import io
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import requests

API_KEY = os.getenv('DART_API_KEY', '').strip()
ROOT = Path('data/financials')
STATUS_DIR = Path('data/status')
ROOT.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = ROOT / 'dart_value_factor_candidates.csv.gz'
TASK_STATE_FILE = STATUS_DIR / 'dart_value_backfill_state.csv'
MAP_FILE = ROOT / 'dart_historical_code_map.csv'
BACKFILL_STATUS_FILE = STATUS_DIR / 'dart_value_backfill_status.csv'
LIFE_FILE = Path('results/security_life_table.csv')

BASE = 'https://opendart.fss.or.kr/api'
REPORT_CODES = {'H1': '11012', 'FY': '11011'}
MAX_TASKS = max(1, int(os.getenv('DART_BACKFILL_TASKS', '6000')))
WORKERS = max(1, min(8, int(os.getenv('DART_BACKFILL_WORKERS', '6'))))


class RateLimitExceeded(RuntimeError):
    pass


class FatalDartError(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    s = str(value or '').strip().lower()
    s = s.replace('주식회사', '').replace('(주)', '').replace('㈜', '')
    s = re.sub(r'[^0-9a-z가-힣]', '', s)
    return s


def get_full_corp_master() -> pd.DataFrame:
    r = requests.get(f'{BASE}/corpCode.xml', params={'crtfc_key': API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    rows = [{child.tag: child.text for child in node} for node in root.findall('list')]
    df = pd.DataFrame(rows)
    for col in ['corp_code', 'corp_name', 'stock_code', 'modify_date']:
        if col not in df.columns:
            df[col] = ''
    df['corp_code'] = df['corp_code'].fillna('').astype(str).str.strip()
    df['corp_name'] = df['corp_name'].fillna('').astype(str).str.strip()
    df['stock_code'] = df['stock_code'].fillna('').astype(str).str.strip()
    df['stock_code'] = df['stock_code'].where(df['stock_code'].str.fullmatch(r'\d{6}'), '')
    df['norm_name'] = df['corp_name'].map(normalize_name)
    return df.drop_duplicates('corp_code', keep='last').reset_index(drop=True)


def build_historical_map(corp: pd.DataFrame) -> pd.DataFrame:
    if not LIFE_FILE.exists():
        raise FileNotFoundError(f'Missing historical security life table: {LIFE_FILE}')

    life = pd.read_csv(LIFE_FILE, dtype={'Code': str})
    life['Code'] = life['Code'].astype(str).str.zfill(6)
    life['first_date'] = pd.to_datetime(life['first_date'], errors='coerce')
    life['last_date'] = pd.to_datetime(life['last_date'], errors='coerce')
    life = life[life['last_date'] >= pd.Timestamp('2015-01-01')].copy()
    life['norm_name'] = life['name'].map(normalize_name)

    direct = (corp[corp['stock_code'] != ''][['stock_code', 'corp_code', 'corp_name']]
              .drop_duplicates('stock_code', keep='last')
              .set_index('stock_code'))

    name_counts = corp[corp['norm_name'] != ''].groupby('norm_name')['corp_code'].nunique()
    unique_names = set(name_counts[name_counts == 1].index)
    by_name = (corp[corp['norm_name'].isin(unique_names)]
               .drop_duplicates('norm_name', keep='last')
               .set_index('norm_name'))

    rows = []
    for _, r in life.iterrows():
        code = r['Code']
        method = 'unmatched'
        corp_code = ''
        dart_name = ''

        if code in direct.index:
            d = direct.loc[code]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'stock_code'
        elif r['norm_name'] and r['norm_name'] in by_name.index:
            d = by_name.loc[r['norm_name']]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'normalized_name_unique'

        rows.append({
            'stock_code': code,
            'marcap_name': r.get('name', ''),
            'corp_code': corp_code,
            'dart_name': dart_name,
            'mapping_method': method,
            'first_date': r['first_date'],
            'last_date': r['last_date'],
        })

    out = pd.DataFrame(rows).sort_values('stock_code').reset_index(drop=True)
    out.to_csv(MAP_FILE, index=False, encoding='utf-8-sig')
    return out


def available_report_tasks(mapping: pd.DataFrame, now_kst: datetime) -> pd.DataFrame:
    rows = []
    current_year = now_kst.year
    current_date = pd.Timestamp(now_kst.date())

    mapped = mapping[mapping['corp_code'].astype(str).str.len() == 8].copy()
    for _, r in mapped.iterrows():
        first_date = pd.Timestamp(r['first_date'])
        last_date = pd.Timestamp(r['last_date'])
        start_year = max(2015, first_date.year - 1)
        end_year = min(current_year, last_date.year)

        for year in range(start_year, end_year + 1):
            # H1 is normally available by mid-August of the same year.
            if year < current_year or current_date >= pd.Timestamp(f'{year}-08-15'):
                rows.append({
                    'stock_code': r['stock_code'], 'corp_code': r['corp_code'],
                    'year': year, 'period': 'H1', 'reprt_code': REPORT_CODES['H1'],
                })
            # FY report is normally available by the end of March of the next year.
            if year < current_year and current_date >= pd.Timestamp(f'{year + 1}-04-01'):
                rows.append({
                    'stock_code': r['stock_code'], 'corp_code': r['corp_code'],
                    'year': year, 'period': 'FY', 'reprt_code': REPORT_CODES['FY'],
                })

    tasks = pd.DataFrame(rows)
    if tasks.empty:
        return tasks
    return tasks.drop_duplicates(['stock_code', 'corp_code', 'year', 'period']).sort_values(
        ['year', 'period', 'stock_code']
    ).reset_index(drop=True)


def dart_request(corp_code: str, year: int, reprt_code: str, fs_div: str) -> tuple[str, list[dict]]:
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': reprt_code,
        'fs_div': fs_div,
    }
    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(f'{BASE}/fnlttSinglAcntAll.json', params=params, timeout=30)
            r.raise_for_status()
            obj = r.json()
            status = str(obj.get('status', ''))
            if status == '000':
                return status, obj.get('list', []) or []
            if status in {'013', '014'}:
                return status, []
            if status == '020':
                raise RateLimitExceeded(obj.get('message', 'DART request limit exceeded'))
            if status in {'010', '011', '012', '901'}:
                raise FatalDartError(f'DART status={status}: {obj.get("message")}')
            raise RuntimeError(f'DART status={status}: {obj.get("message")}')
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.0 + attempt)
                continue
            raise
    if last_error:
        raise last_error
    return '013', []


def fetch_task(task: dict) -> tuple[dict, list[dict]]:
    stock_code = str(task['stock_code']).zfill(6)
    corp_code = str(task['corp_code'])
    year = int(task['year'])
    period = str(task['period'])
    reprt_code = str(task['reprt_code'])

    status, raw = dart_request(corp_code, year, reprt_code, 'CFS')
    fs_div_used = 'CFS'
    if not raw:
        status2, raw2 = dart_request(corp_code, year, reprt_code, 'OFS')
        if raw2:
            raw = raw2
            status = status2
            fs_div_used = 'OFS'

    state = {
        'stock_code': stock_code,
        'corp_code': corp_code,
        'year': year,
        'period': period,
        'reprt_code': reprt_code,
        'status': 'OK' if raw else 'NO_DATA',
        'fs_div_used': fs_div_used if raw else '',
        'candidate_rows': 0,
        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
        'error': '',
    }

    candidates = []
    if raw:
        for item in raw:
            account_id = str(item.get('account_id', '') or '')
            account_nm = str(item.get('account_nm', '') or '')
            sj_div = str(item.get('sj_div', '') or '').upper()
            aid = account_id.lower()
            anm = re.sub(r'\s+', '', account_nm.lower())

            metric = ''
            if sj_div == 'BS' and (
                'equity' in aid or '자본총계' in anm or '지배기업의소유주에게귀속되는자본' in anm
            ):
                metric = 'equity_candidate'
            elif sj_div in {'IS', 'CIS'} and (
                'revenue' in aid or '매출액' in anm or '영업수익' in anm or anm in {'수익', '수익(매출액)'}
            ):
                metric = 'revenue_candidate'
            elif sj_div in {'IS', 'CIS'} and (
                'profitloss' in aid or '당기순이익' in anm or '반기순이익' in anm or '분기순이익' in anm
            ):
                metric = 'net_income_candidate'
            elif sj_div == 'CF' and (
                'cashflowsfromusedinoperatingactivities' in aid
                or '영업활동현금흐름' in anm
                or '영업활동으로인한현금흐름' in anm
            ):
                metric = 'operating_cashflow_candidate'

            if not metric:
                continue

            rcept = str(item.get('rcept_no', '') or '')
            candidates.append({
                'stock_code': stock_code,
                'corp_code': corp_code,
                'year': year,
                'period': period,
                'reprt_code': reprt_code,
                'fs_div': str(item.get('fs_div', fs_div_used) or fs_div_used),
                'sj_div': sj_div,
                'metric_candidate': metric,
                'rcept_no': rcept,
                'filing_date': rcept[:8] if len(rcept) >= 8 else '',
                'account_id': account_id,
                'account_nm': account_nm,
                'thstrm_nm': item.get('thstrm_nm', ''),
                'thstrm_amount': item.get('thstrm_amount', ''),
                'thstrm_add_amount': item.get('thstrm_add_amount', ''),
                'frmtrm_nm': item.get('frmtrm_nm', ''),
                'frmtrm_amount': item.get('frmtrm_amount', ''),
                'frmtrm_add_amount': item.get('frmtrm_add_amount', ''),
                'bfefrmtrm_nm': item.get('bfefrmtrm_nm', ''),
                'bfefrmtrm_amount': item.get('bfefrmtrm_amount', ''),
                'currency': item.get('currency', ''),
            })

    state['candidate_rows'] = len(candidates)
    return state, candidates


def load_done_keys() -> set[tuple[str, str, int, str]]:
    if not TASK_STATE_FILE.exists():
        return set()
    try:
        s = pd.read_csv(TASK_STATE_FILE, dtype={'stock_code': str, 'corp_code': str})
    except Exception:
        return set()
    done = s[s['status'].isin(['OK', 'NO_DATA'])].copy()
    return set(zip(
        done['stock_code'].astype(str).str.zfill(6),
        done['corp_code'].astype(str),
        done['year'].astype(int),
        done['period'].astype(str),
    ))


def merge_state(new_rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(new_rows)
    if TASK_STATE_FILE.exists():
        try:
            old = pd.read_csv(TASK_STATE_FILE, dtype={'stock_code': str, 'corp_code': str})
        except Exception:
            old = pd.DataFrame()
    else:
        old = pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True) if len(old) else new
    if len(out):
        out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
        out = out.sort_values('updated_at_utc').drop_duplicates(
            ['stock_code', 'corp_code', 'year', 'period'], keep='last'
        )
    out.to_csv(TASK_STATE_FILE, index=False, encoding='utf-8-sig')
    return out


def merge_candidates(new_rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(new_rows)
    if OUT_FILE.exists():
        try:
            old = pd.read_csv(OUT_FILE, dtype={'stock_code': str, 'corp_code': str}, compression='gzip')
        except Exception:
            old = pd.DataFrame()
    else:
        old = pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True) if len(old) else new
    if len(out):
        out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
        keys = [
            'stock_code', 'corp_code', 'year', 'period', 'fs_div', 'sj_div',
            'rcept_no', 'account_id', 'account_nm', 'metric_candidate',
        ]
        out = out.drop_duplicates([k for k in keys if k in out.columns], keep='last')
        out = out.sort_values(['year', 'period', 'stock_code', 'metric_candidate', 'account_nm'])
    out.to_csv(OUT_FILE, index=False, encoding='utf-8-sig', compression='gzip')
    return out


def main() -> None:
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)

    if not API_KEY:
        raise FatalDartError('DART_API_KEY is missing')

    corp = get_full_corp_master()
    mapping = build_historical_map(corp)
    tasks = available_report_tasks(mapping, now_kst)
    done = load_done_keys()

    if len(tasks):
        task_keys = list(zip(
            tasks['stock_code'].astype(str).str.zfill(6),
            tasks['corp_code'].astype(str),
            tasks['year'].astype(int),
            tasks['period'].astype(str),
        ))
        mask = [k not in done for k in task_keys]
        pending = tasks.loc[mask].head(MAX_TASKS).copy()
    else:
        pending = tasks

    state_rows: list[dict] = []
    candidate_rows: list[dict] = []
    rate_limited = False

    print(
        f'DART value backfill: mapped={int((mapping.mapping_method != "unmatched").sum())}/'
        f'{len(mapping)} total_tasks={len(tasks)} pending_this_run={len(pending)} workers={WORKERS}',
        flush=True,
    )

    if len(pending):
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(fetch_task, row.to_dict()): row.to_dict() for _, row in pending.iterrows()}
            completed = 0
            for fut in as_completed(futures):
                task = futures[fut]
                try:
                    state, candidates = fut.result()
                    state_rows.append(state)
                    candidate_rows.extend(candidates)
                except RateLimitExceeded as e:
                    rate_limited = True
                    state_rows.append({
                        **task,
                        'status': 'ERROR', 'fs_div_used': '', 'candidate_rows': 0,
                        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
                        'error': f'RATE_LIMIT: {e}',
                    })
                except FatalDartError:
                    raise
                except Exception as e:
                    state_rows.append({
                        **task,
                        'status': 'ERROR', 'fs_div_used': '', 'candidate_rows': 0,
                        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
                        'error': repr(e),
                    })
                completed += 1
                if completed % 250 == 0 or completed == len(pending):
                    print(f'DART value backfill progress {completed}/{len(pending)}', flush=True)

    state = merge_state(state_rows) if state_rows else (
        pd.read_csv(TASK_STATE_FILE) if TASK_STATE_FILE.exists() else pd.DataFrame()
    )
    candidates = merge_candidates(candidate_rows) if candidate_rows else (
        pd.read_csv(OUT_FILE, compression='gzip') if OUT_FILE.exists() else pd.DataFrame()
    )

    done_count = int(state['status'].isin(['OK', 'NO_DATA']).sum()) if len(state) else 0
    error_count = int((state['status'] == 'ERROR').sum()) if len(state) else 0
    matched_count = int((mapping['mapping_method'] != 'unmatched').sum())
    unmatched_count = int((mapping['mapping_method'] == 'unmatched').sum())

    status = pd.DataFrame([{
        'status': 'RATE_LIMITED' if rate_limited else 'OK',
        'historical_codes': len(mapping),
        'mapped_codes': matched_count,
        'unmatched_codes': unmatched_count,
        'total_available_tasks': len(tasks),
        'processed_done_tasks': done_count,
        'remaining_tasks_estimate': max(0, len(tasks) - done_count),
        'error_tasks': error_count,
        'candidate_rows_saved': len(candidates),
        'max_tasks_per_run': MAX_TASKS,
        'workers': WORKERS,
        'updated_at_utc': now_utc.isoformat(),
    }])
    status.to_csv(BACKFILL_STATUS_FILE, index=False, encoding='utf-8-sig')
    print(status.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
