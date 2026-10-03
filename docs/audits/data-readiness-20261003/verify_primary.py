"""Read manually located original cells; never import the collection parser.

An audit tool, not a financial provider or investment performance calculator.
"""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import zipfile


def cell_lines(cell):
    cell = re.sub(r'<(?:BR|/P)[^>]*>', '\n', cell, flags=re.I)
    return [line for part in cell.splitlines()
            if (line := re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', part))).strip())]


def inspect(expectations, primary_dir, repo, state_path, viewer_zip):
    state = {x['rcept_no']: x for x in csv.DictReader(state_path.open(encoding='utf-8-sig'))}
    out = []
    with zipfile.ZipFile(viewer_zip) as archive:
        for expected in expectations['records']:
            x = dict(expected)
            raw = (primary_dir / x['source_file']).read_bytes()
            source = raw.decode('utf-8', errors='strict')
            report = json.loads((repo / x['source_report_path']).read_text())
            assert report['download_status'] == 'HTTP_RESPONSE_CAPTURED' and report['http_status'] == 200
            assert hashlib.sha256(raw).hexdigest() == report['body_sha256'], x['source_file']
            rows = list(re.finditer(r'<TR\b[^>]*>.*?</TR>', source, re.S | re.I))
            row = rows[x['row_index']]
            cells = re.findall(r'<T[DH]\b[^>]*>(.*?)</T[DH]>', row.group(), re.S | re.I)
            label = re.sub(r'\s+', '', ' '.join(cell_lines(cells[0])))
            assert re.sub(r'\s+', '', x['label_contains']) in label, (x['metric'], label)
            value = cell_lines(cells[x['cell_index']])[x['line_index']]
            assert value == x['raw_value'], (x['rcept_no'], x['metric'], value, x['raw_value'])
            viewer_name = next(n for n in archive.namelist() if n.endswith(x['rcept_no'] + '-viewer.html'))
            viewer_bytes = archive.read(viewer_name)
            assert hashlib.sha256(viewer_bytes).hexdigest() == report['viewer_sha256']
            viewer = viewer_bytes.decode('utf-8', errors='strict')
            title = html.unescape(re.search(r'<title>(.*?)</title>', viewer, re.S | re.I).group(1))
            assert x['filing_date'].replace('-', '.') in title
            current = state[x['rcept_no']]
            assert current['parser_version'] == 'legacy-v5-single-amount'
            assert current['source_version'] == 'opendart-document-v1'
            # Do not certify amounts or the intended period from HTTP success.
            x.update(source_body_sha256=report['body_sha256'], source_viewer_sha256=report['viewer_sha256'],
                     source_character_start=row.start(), source_character_end=row.end(),
                     source_row_sha256=hashlib.sha256(row.group().encode()).hexdigest(),
                     source_cell_excerpt=value, filing_date_evidence=title,
                     filing_date_match=True, correction_status='정정 관계/전체 이력 미확인',
                     strategy_usable_date='', pit_status='legacy provider 미허용; 정정·결산기 매핑 검증 미완료',
                     stored_value='', stored_unit='', stored_parser=current['parser_version'],
                     stored_receipt_status=current['status'], declared_current_metric_rows=current['metric_rows'],
                     numeric_match='계산 불가', difference_reason='', audit_status='')
            if x['scope'] == 'CFS':
                x['audit_status'] = 'PRIOR_ANNUAL_SOURCE_VERIFIED_EXCLUDED_FROM_CURRENT'
                x['difference_reason'] = '전기 연결 연간 원문. 현재 분기 normalized 값과 비교하거나 대체하지 않음'
            elif current['status'] == 'NO_METRICS' and current['metric_rows'] == '0':
                x['audit_status'] = 'STORED_CURRENT_METRIC_MISSING'
                x['difference_reason'] = '최신 main receipt state NO_METRICS/metric_rows=0; 원문 본문에는 해당 당기 숫자가 있음'
            else:
                raise AssertionError('Receipt status changed; inspect exact normalized source before comparing')
            if x['unit'] == '미기재':
                x['source_amount_status'] = 'UNIT_UNVERIFIED'
                x['difference_reason'] += '; 원문 단위 미기재: 환산 금액 미인증'
            elif x['expected_amount_krw'] is None:
                x['source_amount_status'] = 'SIGN_CONTEXT_UNVERIFIED'
                x['difference_reason'] += '; BS 총계 괄호의 표시 관행/부호 추가 확인 필요'
            else:
                x['source_amount_status'] = 'MANUAL_SOURCE_AMOUNT_RECORDED'
            out.append(x)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--primary-dir', type=Path, required=True)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--viewer-zip', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    a = p.parse_args()
    expected = json.loads(Path(__file__).with_name('primary_expectations.json').read_text())
    records = inspect(expected, a.primary_dir, a.repo, a.state, a.viewer_zip)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    with (a.output_dir / 'financial_audit.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    summary = {'audit_contract': 'manual-primary-audit/1', 'primary_cells_inspected': len(records),
               'companies': len({x['corp_code'] for x in records}),
               'current_ofs_items': sum(x['scope'] == 'OFS' for x in records),
               'prior_annual_cfs_items': sum(x['scope'] == 'CFS' for x in records),
               'current_stored_missing': sum(x['audit_status'] == 'STORED_CURRENT_METRIC_MISSING' for x in records),
               'independently_matched_stored_amounts': 0, 'whole_dataset_certified': False,
               'pit_certified': False, 'source_amounts_unverified': sum(x['source_amount_status'] != 'MANUAL_SOURCE_AMOUNT_RECORDED' for x in records),
               'source_parser_imported': False, 'status': 'QUALITY_GAPS_FOUND'}
    (a.output_dir / 'financial_audit_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
