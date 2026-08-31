from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from bs4 import BeautifulSoup

API_KEY = os.getenv('DART_API_KEY', '').strip()
MAX_SEARCH_CORPS = max(1, int(os.getenv('DART_LEGACY_SEARCH_CORPS', '400')))
MAX_DOCUMENTS = max(1, int(os.getenv('DART_LEGACY_DOCUMENTS', '2000')))
WORKERS = max(1, min(8, int(os.getenv('DART_LEGACY_WORKERS', '6'))))
BASE = 'https://opendart.fss.or.kr/api'
START_DATE = '20010101'
END_DATE = '20151231'

ROOT = Path('data/financials/legacy')
CAND_DIR = ROOT / 'candidate_rows'
STATUS_DIR = Path('data/status')
LIFE_FILE = Path('results/security_life_table.csv')
MAP_FILE = Path('data/financials/dart_historical_code_map.csv')
CATALOG_FILE = ROOT / 'dart_legacy_report_catalog.csv.gz'
SEARCH_STATE_FILE = STATUS_DIR / 'dart_legacy_search_state.csv'
PARSE_STATE_FILE = STATUS_DIR / 'dart_legacy_parse_state.csv'
STATUS_FILE = STATUS_DIR / 'dart_legacy_status.csv'
for p in (ROOT, CAND_DIR, STATUS_DIR):
    p.mkdir(parents=True, exist_ok=True)

TARGET_PATTERNS = {
    'revenue': [r'^매출액$', r'^매출$', r'^영업수익$', r'^수익\(매출액\)$', r'^영업수익합계$'],
    'net_income': [r'당기순이익', r'분기순이익', r'반기순이익', r'당기순손익', r'분기순손익', r'반기순손익'],
    'equity': [r'^자본총계$', r'^자본합계$', r'^자기자본$'],
    'operating_cashflow': [r'영업활동.*현금흐름', r'영업활동으로인한현금흐름', r'영업활동에의한현금흐름'],
}
EXCLUDE_LABEL_PARTS = ['주당', '비율', '증가율', '감소율', '주석']


class RateLimitExceeded(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    s = str(value or '').strip().lower()
    s = s.replace('주식회사', '').replace('(주)', '').replace('㈜', '')
    return re.sub(r'[^0-9a-z가-힣]', '', s)


def load_corp_master() -> pd.DataFrame:
    r = requests.get(f'{BASE}/corpCode.xml', params={'crtfc_key': API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    root = ET.fromstring(xml)
    rows = [{child.tag: child.text for child in node} for node in root.findall('list')]
    df = pd.DataFrame(rows)
    df['corp_code'] = df['corp_code'].fillna('').astype(str).str.strip()
    df['corp_name'] = df['corp_name'].fillna('').astype(str).str.strip()
    raw = df['stock_code'].fillna('').astype(str).str.strip()
    df['stock_code'] = raw.where(raw.str.fullmatch(r'\d{6}'), '')
    df['norm_name'] = df['corp_name'].map(normalize_name)
    return df.drop_duplicates('corp_code', keep='last')


def build_mapping(corp: pd.DataFrame) -> pd.DataFrame:
    if MAP_FILE.exists():
        m = pd.read_csv(MAP_FILE, dtype={'stock_code': str, 'corp_code': str})
        m['stock_code'] = m['stock_code'].astype(str).str.zfill(6)
        m['first_date'] = pd.to_datetime(m['first_date'], errors='coerce')
        m['last_date'] = pd.to_datetime(m['last_date'], errors='coerce')
        return m
    if not LIFE_FILE.exists():
        raise FileNotFoundError(LIFE_FILE)
    life = pd.read_csv(LIFE_FILE, dtype={'Code': str})
    life['Code'] = life['Code'].astype(str).str.zfill(6)
    life['first_date'] = pd.to_datetime(life['first_date'], errors='coerce')
    life['last_date'] = pd.to_datetime(life['last_date'], errors='coerce')
    life['norm_name'] = life['name'].map(normalize_name)
    by_code = corp[corp['stock_code'] != ''].drop_duplicates('stock_code').set_index('stock_code')
    counts = corp[corp['norm_name'] != ''].groupby('norm_name')['corp_code'].nunique()
    unique_names = set(counts[counts == 1].index)
    by_name = corp[corp['norm_name'].isin(unique_names)].drop_duplicates('norm_name').set_index('norm_name')
    rows = []
    for _, r in life.iterrows():
        corp_code = ''
        method = 'unmatched'
        if r['Code'] in by_code.index:
            corp_code = str(by_code.loc[r['Code'], 'corp_code'])
            method = 'stock_code'
        elif r['norm_name'] in by_name.index:
            corp_code = str(by_name.loc[r['norm_name'], 'corp_code'])
            method = 'normalized_name_unique'
        rows.append({'stock_code': r['Code'], 'marcap_name': r['name'], 'corp_code': corp_code,
                     'mapping_method': method, 'first_date': r['first_date'], 'last_date': r['last_date']})
    return pd.DataFrame(rows)


def relevant_mapping(mapping: pd.DataFrame) -> pd.DataFrame:
    start = pd.Timestamp('2001-01-01')
    end = pd.Timestamp('2015-12-31')
    m = mapping.copy()
    m['first_date'] = pd.to_datetime(m['first_date'], errors='coerce')
    m['last_date'] = pd.to_datetime(m['last_date'], errors='coerce')
    mask = (m['first_date'] <= end) & (m['last_date'] >= start) & m['corp_code'].astype(str).str.fullmatch(r'\d{8}')
    return m[mask].drop_duplicates('corp_code').sort_values(['first_date', 'stock_code']).reset_index(drop=True)


def dart_json(path: str, params: dict) -> dict:
    for attempt in range(4):
        r = requests.get(f'{BASE}/{path}', params={'crtfc_key': API_KEY, **params}, timeout=45)
        r.raise_for_status()
        obj = r.json()
        status = str(obj.get('status', ''))
        if status == '000':
            return obj
        if status == '013':
            return {'status': '013', 'list': [], 'total_page': 0}
        if status == '020':
            raise RateLimitExceeded(obj.get('message', 'request limit exceeded'))
        if attempt == 3:
            raise RuntimeError(f'DART {path} status={status}: {obj.get("message")}')
        time.sleep(1 + attempt)
    return {}


def search_corp_reports(corp_code: str, stock_code: str) -> list[dict]:
    page = 1
    out: list[dict] = []
    while True:
        obj = dart_json('list.json', {
            'corp_code': corp_code,
            'bgn_de': START_DATE,
            'end_de': END_DATE,
            'last_reprt_at': 'Y',
            'pblntf_ty': 'A',
            'page_no': str(page),
            'page_count': '100',
            'sort': 'date',
            'sort_mth': 'asc',
        })
        for item in obj.get('list', []) or []:
            nm = str(item.get('report_nm', '') or '')
            if not any(k in nm for k in ('사업보고서', '반기보고서', '분기보고서')):
                continue
            rcept_dt = str(item.get('rcept_dt', '') or '')
            if not (START_DATE <= rcept_dt <= END_DATE):
                continue
            report_type = 'FY' if '사업보고서' in nm else ('H1' if '반기보고서' in nm else 'Q')
            period_match = re.search(r'\((\d{4})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?\)', nm)
            period_end = ''
            if period_match:
                yy, mm, dd = period_match.group(1), period_match.group(2), period_match.group(3) or '01'
                period_end = f'{int(yy):04d}-{int(mm):02d}-{int(dd):02d}'
            out.append({
                'stock_code': stock_code,
                'corp_code': corp_code,
                'corp_name': item.get('corp_name', ''),
                'rcept_no': item.get('rcept_no', ''),
                'rcept_dt': rcept_dt,
                'report_nm': nm,
                'report_type': report_type,
                'period_end_hint': period_end,
                'rm': item.get('rm', ''),
            })
        total_page = int(obj.get('total_page') or 0)
        if page >= total_page or total_page == 0:
            break
        page += 1
    return out


def read_search_done() -> set[str]:
    if not SEARCH_STATE_FILE.exists():
        return set()
    df = pd.read_csv(SEARCH_STATE_FILE, dtype=str)
    return set(df.loc[df['status'].isin(['OK', 'NO_REPORTS']), 'corp_code'].astype(str))


def save_search_state(rows: list[dict]) -> None:
    new = pd.DataFrame(rows)
    old = pd.read_csv(SEARCH_STATE_FILE, dtype=str) if SEARCH_STATE_FILE.exists() else pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True)
    if len(out):
        out = out.sort_values('updated_at_utc').drop_duplicates('corp_code', keep='last')
    out.to_csv(SEARCH_STATE_FILE, index=False, encoding='utf-8-sig')


def save_catalog(rows: list[dict]) -> pd.DataFrame:
    new = pd.DataFrame(rows)
    old = pd.read_csv(CATALOG_FILE, dtype=str, compression='gzip') if CATALOG_FILE.exists() else pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True)
    if len(out):
        out['stock_code'] = out['stock_code'].astype(str).str.zfill(6)
        out = out.drop_duplicates('rcept_no', keep='last').sort_values(['rcept_dt', 'stock_code', 'rcept_no'])
    out.to_csv(CATALOG_FILE, index=False, encoding='utf-8-sig', compression='gzip')
    return out


def download_document(rcept_no: str) -> list[tuple[str, str]]:
    for attempt in range(4):
        r = requests.get(f'{BASE}/document.xml', params={'crtfc_key': API_KEY, 'rcept_no': rcept_no}, timeout=90)
        r.raise_for_status()
        content = r.content
        if content[:2] != b'PK':
            txt = content.decode('utf-8', errors='ignore')
            if '<status>020</status>' in txt:
                raise RateLimitExceeded('document request limit exceeded')
            if attempt == 3:
                raise RuntimeError(f'Not a zip for {rcept_no}: {txt[:300]}')
            time.sleep(1 + attempt)
            continue
        docs = []
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in z.namelist():
                if not name.lower().endswith(('.xml', '.html', '.htm', '.txt')):
                    continue
                raw = z.read(name)
                text = ''
                for enc in ('utf-8', 'cp949', 'euc-kr'):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        pass
                if not text:
                    text = raw.decode('utf-8', errors='ignore')
                docs.append((name, text))
        return docs
    return []


def clean_cell(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s or '').replace('\xa0', ' ')).strip()


def classify_label(label: str) -> str:
    norm = re.sub(r'[\s·ㆍⅠⅡⅢIVX\d\.\-\(\)\[\]]+', '', label)
    if any(x in norm for x in EXCLUDE_LABEL_PARTS):
        return ''
    for metric, patterns in TARGET_PATTERNS.items():
        if any(re.search(p, norm) for p in patterns):
            return metric
    return ''


def parse_number(text: str):
    s = clean_cell(text)
    if not s or s in {'-', '—', '–'}:
        return None
    neg = False
    if s.startswith('(') and s.endswith(')'):
        neg = True
    if s.startswith('△') or s.startswith('▲'):
        neg = True
    s2 = re.sub(r'[^0-9.\-]', '', s.replace(',', ''))
    if not s2 or s2 in {'-', '.', '-.'}:
        return None
    try:
        v = float(s2)
        return -abs(v) if neg else v
    except ValueError:
        return None


def unit_hint(text: str) -> str:
    m = re.search(r'단위\s*[:：]?\s*([^\s<>,\)\]]+)', text)
    return m.group(1)[:30] if m else ''


def extract_candidates(meta: dict, docs: list[tuple[str, str]]) -> list[dict]:
    rows_out: list[dict] = []
    for filename, text in docs:
        soup = BeautifulSoup(text, 'lxml')
        for table_idx, table in enumerate(soup.find_all('table')):
            table_text = clean_cell(table.get_text(' ', strip=True))
            if not any(k in table_text for k in ('매출', '영업수익', '순이익', '순손익', '자본총계', '자기자본', '현금흐름')):
                continue
            tr_list = table.find_all('tr')
            header_rows = []
            for tr in tr_list[:6]:
                header_rows.append([clean_cell(c.get_text(' ', strip=True)) for c in tr.find_all(['th', 'td'])])
            table_unit = unit_hint(table_text[:1500])
            if not table_unit:
                prev_text = []
                node = table
                for _ in range(5):
                    node = node.find_previous()
                    if node is None:
                        break
                    if hasattr(node, 'get_text'):
                        prev_text.append(clean_cell(node.get_text(' ', strip=True)))
                table_unit = unit_hint(' '.join(prev_text))
            for row_idx, tr in enumerate(tr_list):
                cells = [clean_cell(c.get_text(' ', strip=True)) for c in tr.find_all(['th', 'td'])]
                if len(cells) < 2:
                    continue
                metric = ''
                label = ''
                label_idx = -1
                for i, cell in enumerate(cells[:4]):
                    m = classify_label(cell)
                    if m:
                        metric, label, label_idx = m, cell, i
                        break
                if not metric:
                    continue
                values = [parse_number(c) for c in cells]
                numeric_count = sum(v is not None for v in values)
                if numeric_count == 0:
                    continue
                rows_out.append({
                    **meta,
                    'document_name': filename,
                    'table_index': table_idx,
                    'row_index': row_idx,
                    'metric_candidate': metric,
                    'account_label': label,
                    'label_cell_index': label_idx,
                    'unit_hint': table_unit,
                    'cells_json': json.dumps(cells, ensure_ascii=False),
                    'numbers_json': json.dumps(values, ensure_ascii=False),
                    'headers_json': json.dumps(header_rows, ensure_ascii=False),
                    'collected_at_utc': datetime.now(timezone.utc).isoformat(),
                })
    return rows_out


def read_parse_done() -> set[str]:
    if not PARSE_STATE_FILE.exists():
        return set()
    df = pd.read_csv(PARSE_STATE_FILE, dtype=str)
    return set(df.loc[df['status'].isin(['OK', 'NO_CANDIDATES']), 'rcept_no'].astype(str))


def save_parse_state(rows: list[dict]) -> None:
    new = pd.DataFrame(rows)
    old = pd.read_csv(PARSE_STATE_FILE, dtype=str) if PARSE_STATE_FILE.exists() else pd.DataFrame()
    out = pd.concat([old, new], ignore_index=True)
    if len(out):
        out = out.sort_values('updated_at_utc').drop_duplicates('rcept_no', keep='last')
    out.to_csv(PARSE_STATE_FILE, index=False, encoding='utf-8-sig')


def save_candidate_shards(rows: list[dict]) -> int:
    if not rows:
        return 0
    df = pd.DataFrame(rows)
    df['year'] = df['rcept_dt'].astype(str).str[:4]
    count = 0
    for year, g in df.groupby('year'):
        stable = g[['rcept_no', 'document_name', 'table_index', 'row_index', 'metric_candidate']].astype(str).sort_values(list(g[['rcept_no', 'document_name', 'table_index', 'row_index', 'metric_candidate']].columns))
        digest = hashlib.sha1(stable.to_csv(index=False).encode('utf-8')).hexdigest()[:12]
        path = CAND_DIR / f'dart_legacy_candidates_{year}_{digest}.csv.gz'
        if not path.exists():
            g.drop(columns='year').to_csv(path, index=False, encoding='utf-8-sig', compression='gzip')
            count += len(g)
    return count


def main() -> None:
    if not API_KEY:
        raise RuntimeError('DART_API_KEY is missing')
    now = datetime.now(timezone.utc).isoformat()
    corp = load_corp_master()
    mapping = relevant_mapping(build_mapping(corp))

    search_done = read_search_done()
    to_search = mapping[~mapping['corp_code'].astype(str).isin(search_done)].head(MAX_SEARCH_CORPS)
    search_states = []
    new_catalog_rows = []
    for _, r in to_search.iterrows():
        try:
            reports = search_corp_reports(str(r['corp_code']), str(r['stock_code']).zfill(6))
            new_catalog_rows.extend(reports)
            search_states.append({'corp_code': r['corp_code'], 'stock_code': str(r['stock_code']).zfill(6),
                                  'status': 'OK' if reports else 'NO_REPORTS', 'reports_found': len(reports),
                                  'error': '', 'updated_at_utc': now})
        except RateLimitExceeded:
            break
        except Exception as exc:
            search_states.append({'corp_code': r['corp_code'], 'stock_code': str(r['stock_code']).zfill(6),
                                  'status': 'ERROR', 'reports_found': 0, 'error': repr(exc), 'updated_at_utc': now})
    if search_states:
        save_search_state(search_states)
    catalog = save_catalog(new_catalog_rows) if new_catalog_rows else (pd.read_csv(CATALOG_FILE, dtype=str, compression='gzip') if CATALOG_FILE.exists() else pd.DataFrame())

    parse_done = read_parse_done()
    if len(catalog):
        pending = catalog[~catalog['rcept_no'].astype(str).isin(parse_done)].sort_values(['rcept_dt', 'stock_code']).head(MAX_DOCUMENTS)
    else:
        pending = pd.DataFrame()

    parse_states: list[dict] = []
    candidate_rows: list[dict] = []
    if len(pending):
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(download_document, str(row['rcept_no'])): row.to_dict() for _, row in pending.iterrows()}
            for fut in as_completed(futs):
                meta = futs[fut]
                rcept_no = str(meta['rcept_no'])
                try:
                    docs = fut.result()
                    rows = extract_candidates(meta, docs)
                    candidate_rows.extend(rows)
                    parse_states.append({'rcept_no': rcept_no, 'status': 'OK' if rows else 'NO_CANDIDATES',
                                         'candidate_rows': len(rows), 'documents_in_zip': len(docs),
                                         'error': '', 'updated_at_utc': datetime.now(timezone.utc).isoformat()})
                except RateLimitExceeded as exc:
                    parse_states.append({'rcept_no': rcept_no, 'status': 'ERROR', 'candidate_rows': 0,
                                         'documents_in_zip': 0, 'error': f'RATE_LIMIT: {exc}',
                                         'updated_at_utc': datetime.now(timezone.utc).isoformat()})
                except Exception as exc:
                    parse_states.append({'rcept_no': rcept_no, 'status': 'ERROR', 'candidate_rows': 0,
                                         'documents_in_zip': 0, 'error': repr(exc),
                                         'updated_at_utc': datetime.now(timezone.utc).isoformat()})
    if parse_states:
        save_parse_state(parse_states)
    written = save_candidate_shards(candidate_rows)

    searched_state = pd.read_csv(SEARCH_STATE_FILE, dtype=str) if SEARCH_STATE_FILE.exists() else pd.DataFrame()
    parsed_state = pd.read_csv(PARSE_STATE_FILE, dtype=str) if PARSE_STATE_FILE.exists() else pd.DataFrame()
    status = pd.DataFrame([{
        'status': 'OK',
        'legacy_mapped_corps': len(mapping),
        'searched_corps_done': int(searched_state['status'].isin(['OK', 'NO_REPORTS']).sum()) if len(searched_state) else 0,
        'catalog_reports': len(catalog),
        'parsed_reports_done': int(parsed_state['status'].isin(['OK', 'NO_CANDIDATES']).sum()) if len(parsed_state) else 0,
        'parse_errors': int((parsed_state['status'] == 'ERROR').sum()) if len(parsed_state) else 0,
        'candidate_rows_written_this_run': written,
        'candidate_shards_total': len(list(CAND_DIR.glob('*.csv.gz'))),
        'max_search_corps_per_run': MAX_SEARCH_CORPS,
        'max_documents_per_run': MAX_DOCUMENTS,
        'workers': WORKERS,
        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
    }])
    status.to_csv(STATUS_FILE, index=False, encoding='utf-8-sig')
    print(status.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
