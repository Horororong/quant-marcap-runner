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
MAX_TASKS = max(1, int(os.getenv('DART_BACKFILL_TASKS', '3000')))
WORKERS = max(1, min(8, int(os.getenv('DART_BACKFILL_WORKERS', '6'))))
BASE = 'https://opendart.fss.or.kr/api'

# OpenDART report codes.
# Q1/H1/Q3/FY are all retained so later research can compare:
# - latest reported quarter only
# - cumulative YTD
# - TTM
# - annual-only
REPORT_CODES = {
    'Q1': '11013',
    'H1': '11012',
    'Q3': '11014',
    'FY': '11011',
}
PERIOD_END_MMDD = {
    'Q1': '03-31',
    'H1': '06-30',
    'Q3': '09-30',
    'FY': '12-31',
}

ROOT = Path('data/financials')
STATUS_DIR = Path('data/status')
LIFE_FILE = Path('results/security_life_table.csv')
MAP_FILE = ROOT / 'dart_historical_code_map.csv'
CANDIDATE_FILE = ROOT / 'dart_value_factor_candidates.csv.gz'
TASK_FILE = STATUS_DIR / 'dart_value_backfill_state.csv'
STATUS_FILE = STATUS_DIR / 'dart_value_backfill_status.csv'
ROOT.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)


class RateLimitExceeded(RuntimeError):
    pass


class FatalDartError(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    s = str(value or '').strip().lower()
    s = s.replace('주식회사', '').replace('(주)', '').replace('㈜', '')
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def load_all_dart_corps() -> pd.DataFrame:
    r = requests.get(f'{BASE}/corpCode.xml', params={'crtfc_key': API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    root = ET.fromstring(xml)
    rows = [{child.tag: child.text for child in node} for node in root.findall('list')]
    df = pd.DataFrame(rows)
    for c in ['corp_code', 'corp_name', 'stock_code', 'modify_date']:
        if c not in df.columns:
            df[c] = ''
    df['corp_code'] = df['corp_code'].fillna('').astype(str).str.strip()
    df['corp_name'] = df['corp_name'].fillna('').astype(str).str.strip()
    raw_code = df['stock_code'].fillna('').astype(str).str.strip()
    df['stock_code'] = raw_code.where(raw_code.str.fullmatch(r'\d{6}'), '')
    df['norm_name'] = df['corp_name'].map(normalize_name)
    return df.drop_duplicates('corp_code', keep='last').reset_index(drop=True)


def build_historical_code_map(corp: pd.DataFrame) -> pd.DataFrame:
    if not LIFE_FILE.exists():
        raise FileNotFoundError(f'Missing {LIFE_FILE}')

    life = pd.read_csv(LIFE_FILE, dtype={'Code': str})
    life['Code'] = life['Code'].astype(str).str.zfill(6)
    life['first_date'] = pd.to_datetime(life['first_date'], errors='coerce')
    life['last_date'] = pd.to_datetime(life['last_date'], errors='coerce')
    life = life[life['last_date'] >= pd.Timestamp('2015-01-01')].copy()
    life['norm_name'] = life['name'].map(normalize_name)

    by_code = (
        corp[corp['stock_code'] != ''][['stock_code', 'corp_code', 'corp_name']]
        .drop_duplicates('stock_code', keep='last')
        .set_index('stock_code')
    )

    name_counts = corp[corp['norm_name'] != ''].groupby('norm_name')['corp_code'].nunique()
    unique_norm_names = set(name_counts[name_counts == 1].index)
    by_name = (
        corp[corp['norm_name'].isin(unique_norm_names)][['norm_name', 'corp_code', 'corp_name']]
        .drop_duplicates('norm_name', keep='last')
        .set_index('norm_name')
    )

    rows = []
    for _, r in life.iterrows():
        stock_code = r['Code']
        corp_code = ''
        dart_name = ''
        method = 'unmatched'

        if stock_code in by_code.index:
            d = by_code.loc[stock_code]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'stock_code'
        elif r['norm_name'] and r['norm_name'] in by_name.index:
            d = by_name.loc[r['norm_name']]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'normalized_name_unique'

        rows.append({
            'stock_code': stock_code,
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


def report_available_after(year: int, period: str) -> pd.Timestamp:
    """Conservative collection cutoff only.

    Backtests must use the actual filing_date saved from rcept_no, never this
    cutoff. The cutoff simply avoids permanently recording a not-yet-filed
    current-year report as NO_DATA.
    """
    if period == 'Q1':
        return pd.Timestamp(f'{year}-05-16')
    if period == 'H1':
        return pd.Timestamp(f'{year}-08-16')
    if period == 'Q3':
        return pd.Timestamp(f'{year}-11-16')
    if period == 'FY':
        return pd.Timestamp(f'{year + 1}-04-01')
    raise ValueError(f'Unknown period: {period}')


def build_tasks(mapping: pd.DataFrame, now_kst: datetime) -> pd.DataFrame:
    today = pd.Timestamp(now_kst.date())
    current_year = now_kst.year
    rows = []

    mapped = mapping[mapping['corp_code'].astype(str).str.fullmatch(r'\d{8}')].copy()
    for _, r in mapped.iterrows():
        first_date = pd.Timestamp(r['first_date'])
        last_date = pd.Timestamp(r['last_date'])

        # Prior-year FY can be useful immediately after listing, so include one
        # pre-listing year. Quarterly pre-listing years are unnecessary.
        start_year = max(2015, first_date.year - 1)
        end_year = min(current_year, last_date.year)

        for year in range(start_year, end_year + 1):
            periods = ['FY'] if year < first_date.year else ['Q1', 'H1', 'Q3', 'FY']

            for period in periods:
                if today < report_available_after(year, period):
                    continue

                rows.append({
                    'stock_code': r['stock_code'],
                    'corp_code': r['corp_code'],
                    'year': year,
                    'period': period,
                    'period_end': f'{year}-{PERIOD_END_MMDD[period]}',
                    'reprt_code': REPORT_CODES[period],
                })

    tasks = pd.DataFrame(rows)
    if tasks.empty:
        return tasks

    period_order = {'Q1': 1, 'H1': 2, 'Q3': 3, 'FY': 4}
    tasks['_period_order'] = tasks['period'].map(period_order)
    tasks = (
        tasks.drop_duplicates(['stock_code', 'corp_code', 'year', 'period'])
        .sort_values(['year', '_period_order', 'stock_code'])
        .drop(columns='_period_order')
        .reset_index(drop=True)
    )
    return tasks


def api_call(corp_code: str, year: int, reprt_code: str, fs_div: str) -> list[dict]:
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': reprt_code,
        'fs_div': fs_div,
    }
    for attempt in range(3):
        try:
            r = requests.get(f'{BASE}/fnlttSinglAcntAll.json', params=params, timeout=30)
            r.raise_for_status()
            obj = r.json()
            status = str(obj.get('status', ''))
            if status == '000':
                return obj.get('list', []) or []
            if status in {'013', '014'}:
                return []
            if status == '020':
                raise RateLimitExceeded(obj.get('message', 'request limit exceeded'))
            if status in {'010', '011', '012', '901'}:
                raise FatalDartError(f'DART status={status}: {obj.get("message")}')
            raise RuntimeError(f'DART status={status}: {obj.get("message")}')
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
            time.sleep(1.0 + attempt)
    return []


def classify_candidate(item: dict) -> str:
    sj = str(item.get('sj_div', '') or '').upper()
    aid = str(item.get('account_id', '') or '').lower()
    nm = re.sub(r'\s+', '', str(item.get('account_nm', '') or '').lower())

    if sj == 'BS' and (
        'equity' in aid or '자본총계' in nm or '지배기업의소유주에게귀속되는자본' in nm
    ):
        return 'equity_candidate'

    if sj in {'IS', 'CIS'} and (
        'revenue' in aid or '매출액' in nm or '영업수익' in nm or nm in {'수익', '수익(매출액)'}
    ):
        return 'revenue_candidate'

    if sj in {'IS', 'CIS'} and (
        'profitloss' in aid or '당기순이익' in nm or '반기순이익' in nm or '분기순이익' in nm
    ):
        return 'net_income_candidate'

    if sj == 'CF' and (
        'cashflowsfromusedinoperatingactivities' in aid
        or '영업활동현금흐름' in nm
        or '영업활동으로인한현금흐름' in nm
    ):
        return 'operating_cashflow_candidate'

    return ''


def process_task(task: dict) -> tuple[dict, list[dict]]:
    stock_code = str(task['stock_code']).zfill(6)
    corp_code = str(task['corp_code'])
    year = int(task['year'])
    period = str(task['period'])
    period_end = str(task.get('period_end', f'{year}-{PERIOD_END_MMDD[period]}'))
    reprt_code = str(task['reprt_code'])

    raw = api_call(corp_code, year, reprt_code, 'CFS')
    fs_div_used = 'CFS'
    if not raw:
        raw = api_call(corp_code, year, reprt_code, 'OFS')
        fs_div_used = 'OFS'

    state = {
        'stock_code': stock_code,
        'corp_code': corp_code,
        'year': year,
        'period': period,
        'period_end': period_end,
        'reprt_code': reprt_code,
        'status': 'OK' if raw else 'NO_DATA',
        'fs_div_used': fs_div_used if raw else '',
        'candidate_rows': 0,
        'error': '',
        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
    }

    rows = []
    for item in raw:
        metric = classify_candidate(item)
        if not metric:
            continue

        rcept_no = str(item.get('rcept_no', '') or '')
        rows.append({
            'stock_code': stock_code,
            'corp_code': corp_code,
            'year': year,
            'period': period,
            'period_end': period_end,
            'reprt_code': reprt_code,
            'fs_div': str(item.get('fs_div', fs_div_used) or fs_div_used),
            'sj_div': str(item.get('sj_div', '') or ''),
            'metric_candidate': metric,
            'rcept_no': rcept_no,
            # This is the field to use for point-in-time availability.
            'filing_date': rcept_no[:8] if len(rcept_no) >= 8 else '',
            'account_id': item.get('account_id', ''),
            'account_nm': item.get('account_nm', ''),
            # Keep both period and cumulative values. For example Q2 standalone
            # can later be reconstructed from H1 cumulative - Q1 cumulative.
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

    state['candidate_rows'] = len(rows)
    return state, rows


def read_done_keys() -> set[tuple[str, str, int, str]]:
    if not TASK_FILE.exists():
        return set()

    state = pd.read_csv(TASK_FILE, dtype={'stock_code': str, 'corp_code': str})
    state = state[state['status'].isin(['OK', 'NO_DATA'])].copy()
    return set(zip(
        state['stock_code'].astype(str).str.zfill(6),
        state['corp_code'].astype(str),
        state['year'].astype(int),
        state['period'].astype(str),
    ))


def save_state(new_rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(new_rows)
    if TASK_FILE.exists():
        old = pd.read_csv(TASK_FILE, dtype={'stock_code': str, 'corp_code': str})
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new

    if len(out):
        out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
        out = out.sort_values('updated_at_utc').drop_duplicates(
            ['stock_code', 'corp_code', 'year', 'period'], keep='last'
        )

    out.to_csv(TASK_FILE, index=False, encoding='utf-8-sig')
    return out


def save_candidates(new_rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(new_rows)
    if CANDIDATE_FILE.exists():
        old = pd.read_csv(
            CANDIDATE_FILE,
            dtype={'stock_code': str, 'corp_code': str},
            compression='gzip',
        )
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new

    if len(out):
        out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
        key_cols = [
            'stock_code', 'corp_code', 'year', 'period', 'fs_div', 'sj_div',
            'rcept_no', 'account_id', 'account_nm', 'metric_candidate',
        ]
        existing_keys = [c for c in key_cols if c in out.columns]
        out = out.drop_duplicates(existing_keys, keep='last')

        period_order = {'Q1': 1, 'H1': 2, 'Q3': 3, 'FY': 4}
        out['_period_order'] = out['period'].map(period_order).fillna(99)
        out = (
            out.sort_values(
                ['year', '_period_order', 'stock_code', 'metric_candidate', 'account_nm']
            )
            .drop(columns='_period_order')
        )

    out.to_csv(CANDIDATE_FILE, index=False, encoding='utf-8-sig', compression='gzip')
    return out


def main() -> None:
    if not API_KEY:
        raise FatalDartError('DART_API_KEY is missing')

    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)

    corp = load_all_dart_corps()
    mapping = build_historical_code_map(corp)
    tasks = build_tasks(mapping, now_kst)
    done = read_done_keys()

    if len(tasks):
        keys = list(zip(
            tasks['stock_code'].astype(str).str.zfill(6),
            tasks['corp_code'].astype(str),
            tasks['year'].astype(int),
            tasks['period'].astype(str),
        ))
        pending_mask = [key not in done for key in keys]
        pending = tasks.loc[pending_mask].head(MAX_TASKS).copy()
    else:
        pending = tasks

    mapped_count = int((mapping['mapping_method'] != 'unmatched').sum())
    available_counts = (
        tasks['period'].value_counts().to_dict() if len(tasks) else {}
    )
    print(
        f'DART quarterly value backfill: mapped={mapped_count}/{len(mapping)} '
        f'total_tasks={len(tasks)} run_tasks={len(pending)} '
        f'Q1={available_counts.get("Q1", 0)} '
        f'H1={available_counts.get("H1", 0)} '
        f'Q3={available_counts.get("Q3", 0)} '
        f'FY={available_counts.get("FY", 0)} '
        f'workers={WORKERS}',
        flush=True,
    )

    states: list[dict] = []
    candidates: list[dict] = []
    rate_limited = False

    if len(pending):
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            future_map = {
                executor.submit(process_task, row.to_dict()): row.to_dict()
                for _, row in pending.iterrows()
            }

            completed = 0
            for future in as_completed(future_map):
                task = future_map[future]
                try:
                    state, rows = future.result()
                    states.append(state)
                    candidates.extend(rows)
                except RateLimitExceeded as exc:
                    rate_limited = True
                    states.append({
                        **task,
                        'status': 'ERROR',
                        'fs_div_used': '',
                        'candidate_rows': 0,
                        'error': f'RATE_LIMIT: {exc}',
                        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
                    })
                except FatalDartError:
                    raise
                except Exception as exc:
                    states.append({
                        **task,
                        'status': 'ERROR',
                        'fs_div_used': '',
                        'candidate_rows': 0,
                        'error': repr(exc),
                        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
                    })

                completed += 1
                if completed % 250 == 0 or completed == len(pending):
                    print(
                        f'DART quarterly value backfill progress '
                        f'{completed}/{len(pending)}',
                        flush=True,
                    )

    if states:
        state_df = save_state(states)
    elif TASK_FILE.exists():
        state_df = pd.read_csv(TASK_FILE)
    else:
        state_df = pd.DataFrame()

    if candidates:
        candidate_df = save_candidates(candidates)
    elif CANDIDATE_FILE.exists():
        candidate_df = pd.read_csv(CANDIDATE_FILE, compression='gzip')
    else:
        candidate_df = pd.DataFrame()

    done_count = int(
        state_df['status'].isin(['OK', 'NO_DATA']).sum()
    ) if len(state_df) else 0
    error_count = int(
        (state_df['status'] == 'ERROR').sum()
    ) if len(state_df) else 0
    unmatched_count = int((mapping['mapping_method'] == 'unmatched').sum())

    completed_period_counts = {}
    if len(state_df):
        completed_state = state_df[state_df['status'].isin(['OK', 'NO_DATA'])]
        completed_period_counts = completed_state['period'].value_counts().to_dict()

    status_df = pd.DataFrame([{
        'status': 'RATE_LIMITED' if rate_limited else 'OK',
        'historical_codes': len(mapping),
        'mapped_codes': mapped_count,
        'unmatched_codes': unmatched_count,
        'total_available_tasks': len(tasks),
        'q1_available_tasks': int(available_counts.get('Q1', 0)),
        'h1_available_tasks': int(available_counts.get('H1', 0)),
        'q3_available_tasks': int(available_counts.get('Q3', 0)),
        'fy_available_tasks': int(available_counts.get('FY', 0)),
        'completed_tasks': done_count,
        'q1_completed_tasks': int(completed_period_counts.get('Q1', 0)),
        'h1_completed_tasks': int(completed_period_counts.get('H1', 0)),
        'q3_completed_tasks': int(completed_period_counts.get('Q3', 0)),
        'fy_completed_tasks': int(completed_period_counts.get('FY', 0)),
        'remaining_tasks_estimate': max(0, len(tasks) - done_count),
        'error_tasks': error_count,
        'candidate_rows_saved': len(candidate_df),
        'max_tasks_per_run': MAX_TASKS,
        'workers': WORKERS,
        'updated_at_utc': now_utc.isoformat(),
    }])
    status_df.to_csv(STATUS_FILE, index=False, encoding='utf-8-sig')
    print(status_df.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
