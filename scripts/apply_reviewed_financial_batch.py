"""Reuse preserved field reviews; stage typed rows without granting PIT admission.

No parser replay, HTTP, status-ledger mutation or source-data certification.
The catalog supplies identifier/date HINTS only. Each value keeps the review's
exact archive/member hash, coordinates, period, scope, unit and amount.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from financial_record_readiness import assess, binding
from legacy_reviewed_provider_bridge import CONCEPTS, UNITS
from reviewed_financial_batch_bridge import compile_reviewed_batch, normalise_reviewed

SOURCES = [
    ('old871', 'docs/research/source-review-batch2-20261021/all-871-candidate-decisions.json'),
    ('held9', 'docs/research/native-source-boundary-repair-20261021/new-9-independent-source-controls.json'),
    ('trial34', 'docs/research/legacy-provider-link-20261023/evidence/NEW34_SOURCE_REVIEW.json'),
]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    catalog_path = root / 'data/financials/legacy_2000_2014/legacy_filings.csv.gz'
    catalog = pd.read_csv(catalog_path, dtype=str).fillna('')
    records, inputs, excluded, counts = [], [], [], Counter()
    for group, relative in SOURCES:
        raw = (root / relative).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        rows = payload if group == 'old871' else payload['records' if group == 'held9' else 'rows']
        inputs.append(dict(path=relative, bytes=len(raw), sha256=sha, rows=len(rows)))
        for index, d in enumerate(rows):
            passed = (d.get('semantic_verdict') == 'PASS' if group == 'old871' else
                      d.get('source_row_semantics') == 'PASS' if group == 'held9' else
                      d.get('semantic') == 'PASS_NAMED_SOURCE_FIELD')
            counts['source_semantic_PASS' if passed else 'source_semantic_UNVERIFIED'] += 1
            if not passed or d['metric'] not in CONCEPTS:
                counts['not_core_or_unverified'] += 1
                continue
            receipt = d['receipt']
            cat = catalog[catalog.rcept_no.eq(receipt)]
            identities = cat[['corp_code', 'stock_code', 'rcept_dt']].drop_duplicates()
            if len(identities) != 1:
                excluded.append(dict(receipt=receipt, metric=d['metric'], reason='CATALOG_IDENTITY_NOT_UNIQUE'))
                continue
            hint = identities.iloc[0]
            if d.get('corp_code', hint.corp_code) != hint.corp_code or d.get('stock_code_hint', hint.stock_code) != hint.stock_code:
                excluded.append(dict(receipt=receipt, metric=d['metric'], reason='CATALOG_REVIEW_HINT_DISAGREEMENT'))
                continue
            unit = d.get('reference_unit', d.get('unit'))
            if unit not in UNITS:
                excluded.append(dict(receipt=receipt, metric=d['metric'], reason='SOURCE_UNIT_UNKNOWN'))
                continue
            # held9's independent table controls explicitly prove the full
            # Jan1..Dec31 current interval. Preserve that evidence separately;
            # never borrow the old parser's month-first period hints.
            basis = d.get('measurement_basis')
            if group == 'held9':
                basis = 'instant' if d['metric'] == 'equity' else 'cumulative' if d['metric'] == 'ocf' else 'duration'
            row = dict(
                rcept_no=receipt, document_sha256=d.get('source_archive_sha256', d.get('document_sha256')),
                source_member=d['source_member'], source_member_sha256=d['source_member_sha256'],
                corp_code=hint.corp_code, stock_code=hint.stock_code, metric=d['metric'], scope=d['scope'],
                statement=d['statement'], period_start=d['period_start'], period_end=d['period_end'],
                measurement_basis=basis, unit=unit,
                unit_multiplier=str(d.get('reference_unit_multiplier', d.get('unit_multiplier', UNITS[unit]))),
                amount_krw=str(d.get('candidate_amount_krw', d.get('independent_amount_krw', d.get('amount_krw')))),
                structural_status='PASS',
            )
            flags = [d.get(k) == 'PASS' for k in ['period_current_comparative', 'scope_heading', 'unit_sign', 'account_definition']]
            if group != 'old871':
                flags = [passed] * 4  # explicit, named-source independent control; no PIT inference
            proof = dict(verdict='PASS', binding=binding(row),
                         evidence=[dict(path=relative, sha256=sha, record=index,
                                        table=d['table'], row=d['row'], column=d.get('current_physical_column', d.get('column')))],
                         **dict(zip(['current_period_proved', 'scope_proved', 'unit_sign_proved', 'account_definition_proved'], flags)))
            filing_date = pd.Timestamp(hint.rcept_dt).date().isoformat()
            records.append(dict(row=row, review=proof, filing_index_date=filing_date,
                                identifier_status='CATALOG_HINT_NOT_HISTORICAL_ATTESTATION'))
    result = compile_reviewed_batch(records, '2010-04-30', {'verdict': 'UNVERIFIED', 'evidence': []})
    dump(output / 'INPUTS.json', inputs)
    dump(output / 'BOUND_SOURCE_REVIEW_RECORDS.json', records)
    dump(output / 'AUDIT.json', result['audit'])
    dump(output / 'HELD.json', excluded + result['held'])
    dump(output / 'CONFLICTS.json', result['conflicts'])
    # Expose all independent blockers, not just select_asof's first rejection.
    readiness = []
    for record in records:
        try:
            prepared = normalise_reviewed(record['row'], record['review'], record['filing_index_date'])
        except (ValueError, KeyError, TypeError):
            continue  # held reasons already saved above
        attestation = dict(binding=binding(prepared['row']), financial_accuracy=dict(
            verdict='PASS', evidence=record['review']['evidence']))
        readiness.append(assess(prepared['row'], '2010-04-30', attestation, {'verdict': 'UNVERIFIED', 'evidence': []}))
    dump(output / 'PER_ROW_READINESS.json', readiness)
    decisions, roundtrips, period_counts = [], [], []
    all_receipts, all_corps = set(), set()
    for (year, period), part in result['partitions'].items():
        stem = f'{year}-{period}'
        frame, snapshots = part['candidate_rows'], part['candidate_snapshots']
        frame.to_csv(output / f'{stem}-CANDIDATE_ACCOUNT_ROWS.csv', index=False)
        snapshots.to_csv(output / f'{stem}-CANDIDATE_SNAPSHOTS.csv', index=False)
        part['ready']['raw'].to_csv(output / f'{stem}-STRICT_READY_ROWS.csv', index=False)
        decisions.extend(part['ready']['decisions'])
        # Query the actual canonical snapshot owner, then compare with the exact
        # reviewed decimal. A successful preview never grants engine admission.
        for rec in frame.to_dict('records'):
            metric = next(m for m in CONCEPTS if CONCEPTS[m][1] == rec['account_nm'])
            snap = snapshots[snapshots.Code.eq(rec['stock_code']) & snapshots.fs_div.eq(rec['fs_div_requested']) & snapshots.rcept_no.eq(rec['rcept_no'])]
            slot = 'current' if rec['thstrm_amount'] else 'cum'
            expected = rec['thstrm_amount'] or rec['thstrm_add_amount']
            actual = snap.iloc[0][f'{metric}_{slot}'] if len(snap) == 1 else None
            exact = actual is not None and pd.notna(actual) and Decimal(str(actual)) == Decimal(expected)
            roundtrips.append(dict(receipt=rec['rcept_no'], stock_hint=rec['stock_code'], metric=metric,
                                   period=stem, scope=rec['fs_div_requested'], column=slot, expected=expected,
                                   actual=str(actual), exact=bool(exact), engine_eligible=False))
        all_receipts.update(frame.rcept_no)
        all_corps.update(a['corp'] for a in result['audit'] if tuple(a['period']) == (year, period))
        period_counts.append(dict(year=year, period=period, candidate_rows=len(frame), stock_hints=frame.stock_code.nunique(),
                                  snapshot_rows=len(snapshots), strict_ready_rows=part['ready']['source_ready_rows']))
    dump(output / 'STRICT_ADMISSION_DECISIONS.json', decisions)
    dump(output / 'CANONICAL_PREVIEW_ROUNDTRIPS.json', roundtrips)
    summary = {k: v for k, v in result.items() if k not in {'partitions', 'audit', 'held', 'conflicts'}}
    summary.update(source_counts=dict(counts), submitted_core_rows=len(records), held_rows=len(excluded) + len(result['held']),
                   same_receipt_field_conflicts=len(result['conflicts']), period_counts=period_counts,
                   receipt_count=len(all_receipts), company_hints=len(all_corps),
                   IS_taxonomy_normalizations=sum(a['normalization_changed_binding'] for a in result['audit']),
                   canonical_preview_exact=sum(r['exact'] for r in roundtrips), canonical_preview_checked=len(roundtrips),
                   strict_blockers=dict(Counter(d['reason'] for d in decisions)),
                   independent_readiness_blockers=dict(Counter(dim for r in readiness for dim in r['blockers'])),
                   NEW_PIT_stocks=0, NEW_meaning_reviews=0, NEW_live_engine_stocks=0,
                   existing_semantic_decisions_reused=True, missing_values_filled=False,
                   catalog=dict(path=str(catalog_path.relative_to(root)), sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest()),
                   note='Candidate snapshots are an explicit quarantine preview; no completion ledger/provider registry/gate edited.')
    dump(output / 'SUMMARY.json', summary)
    if not all(r['exact'] for r in roundtrips):
        raise ValueError('CANONICAL_PREVIEW_AMOUNT_MISMATCH: see preserved evidence')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    run(a.root, a.output)
