"""Compare preselected primary-source cells with immutable legacy observations.

No collector, financial parser or performance module is imported. The expected
cells are human-selected in financial_expected.json, not inferred from storage.
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def read_csv(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    expected_path = Path(__file__).with_name('financial_expected.json')
    expected = json.loads(expected_path.read_text())['records']
    receipts = {row['rcept_no'] for row in expected}
    filings = {row['rcept_no']: row for row in read_csv(args.repo_root / 'data/financials/legacy_2000_2014/legacy_filings.csv.gz') if row['rcept_no'] in receipts}
    normalized = []
    for path in sorted((args.repo_root / 'data/financials/legacy_2000_2014/normalized').glob('*.csv.gz')):
        normalized.extend(row for row in read_csv(path) if row['rcept_no'] in receipts)
    state = {row['rcept_no']: row for row in read_csv(args.repo_root / 'data/status/dart_legacy_backfill_state.csv') if row['rcept_no'] in receipts}
    audited = []
    for sample in expected:
        matches = list(args.source_dir.rglob(sample['file']))
        assert len(matches) == 1, (sample['file'], matches)
        body = matches[0].read_bytes()
        assert hashlib.sha256(body).hexdigest() == sample['source_sha256']
        assert body.decode('utf-8')[sample['cell_start']:sample['cell_end']] == sample['literal_cell']
        filing = filings[sample['rcept_no']]
        stored = [row for row in normalized if all(row.get(key) == sample[key] for key in ('rcept_no', 'metric', 'scope')) and row['parser_version'] == sample['stored_parser_version']]
        # Earlier shards may retain identical observations. Preserve differing
        # values explicitly rather than resolving them by forward filling.
        stored = list({json.dumps(row, sort_keys=True): row for row in stored}.values())
        token = sample['source_token']
        amount = None
        if sample['unit'] != '확인불가' and sample['sign_policy'] != 'not_amount':
            negative = token.startswith(('(-)', '△', '-')) or (token.startswith('(') and token.endswith(')')) or sample['sign_policy'] == 'loss_label'
            token = token.replace('(-)', '').replace('△', '').strip('()-').replace(',', '').replace(' ', '')
            amount = Decimal(token) * {'원': 1, '천원': 1000, '백만원': 1000000}[sample['unit']]
            if negative:
                amount = -amount
        equal = None if amount is None or not stored else all(Decimal(row['amount_krw']) == amount for row in stored)
        if not stored:
            result = 'stored_missing'
        elif sample['sign_policy'] == 'not_amount' or sample['period_flag'] == 'asset_as_liability':
            result = 'semantic_mismatch'
        elif amount is None:
            result = 'unit_unverified'
        elif not equal:
            result = 'amount_mismatch'
        elif sample['period_flag']:
            result = 'period_mismatch'
        else:
            result = 'numeric_match_only'
        filed = filing['rcept_dt']
        filed = f'{filed[:4]}-{filed[4:6]}-{filed[6:]}' if '-' not in filed else filed
        assert filed.replace('-', '') == sample['rcept_no'][:8]
        audited.append(dict(sample_id=sample['sample_id'], corp_code=filing['corp_code'], stock_code=filing['stock_code'], indexed_name=filing['corp_name'], report_name=filing['report_nm'], rcept_no=sample['rcept_no'], source_period_start=sample['source_period_start'], source_period_end=sample['source_period_end'], source_period_kind=sample['source_period_kind'], metric=sample['metric'], scope=sample['scope'], unit=sample['unit'], source_url=sample['source_url'], source_sha256=sample['source_sha256'], artifact_id=sample['artifact_id'], source_token=sample['source_token'], source_amount_krw=None if amount is None else str(amount), stored_values=[{key: row.get(key, '') for key in ('amount_krw', 'raw_amount', 'fiscal_year', 'period', 'period_end', 'filing_date', 'parser_version')} for row in stored], actual_filing_date=filed, correction_indicator=('기재정정' in filing['report_nm'] or '첨부정정' in filing['report_nm']), attachment_addition=('첨부추가' in filing['report_nm']), correction_chain='not_reviewed', earliest_receipt_availability=filed, strategy_available_date='UNSUPPORTED_LEGACY: no verified PIT date; receipt date alone insufficient', current_state=state.get(sample['rcept_no'], {}).get('status'), current_parser=state.get(sample['rcept_no'], {}).get('parser_version'), numeric_equal=equal, result=result, full_pit_match=False, period_flag=sample['period_flag'], note=sample['note']))
    summary = dict(samples=len(audited), companies=len({row['corp_code'] for row in audited}), receipts=len(receipts), source_period_end_years=sorted({row['source_period_end'][:4] for row in audited}), scope_counts=dict(Counter(row['scope'] for row in audited)), results=dict(Counter(row['result'] for row in audited)), numeric_equal=sum(row['numeric_equal'] is True for row in audited), numeric_unequal=sum(row['numeric_equal'] is False for row in audited), stored_present=sum(bool(row['stored_values']) for row in audited), stored_missing=sum(not row['stored_values'] for row in audited), unit_unverified=sum(row['unit'] == '확인불가' for row in audited), correction_chain_verified=0, verified_pit_items=0, expected_sha256=hashlib.sha256(expected_path.read_bytes()).hexdigest(), source_verification='full archived primary body SHA and original literal cell offsets', interpretation='failure-oriented sample; not full-data certification; preserved v4 observations are not current provider inputs')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [('financial_audit.json', audited), ('financial_summary.json', summary)]:
        (args.output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    with (args.output_dir / 'financial_audit.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audited[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()} for row in audited)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
