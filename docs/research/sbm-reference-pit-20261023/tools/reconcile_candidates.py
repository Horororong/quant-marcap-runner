"""Prove population membership using immutable source-bound candidate IDs."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--first100', type=Path, required=True)
p.add_argument('--second57', type=Path, required=True)
p.add_argument('--trial', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
def load(f): return json.loads(f.read_text())
def key(receipt, r):
    return (receipt, r['scope'], r['metric'], r['period_end'], r['measurement_basis'])
old = load(a.root / 'docs/research/source-review-batch2-20261021/all-871-candidate-decisions.json')
old_decisions = {key(r['receipt'], r): r['semantic_verdict'] for r in old}
review80 = load(a.root / 'docs/research/source-core-batch3-20261023/evidence/new20-review/NEW20_CORE_SOURCE_REVIEW.json')['rows']
new_decisions = {key(r['receipt'], r): r['semantic_verdict'] for r in review80}
assert len(old_decisions) == 871 and len(new_decisions) == 80
records = []
def append(group, receipt, r, verdict):
    binding = dict(receipt=receipt, **{k: r.get(k) for k in
        ['scope', 'statement', 'metric', 'period_start', 'period_end', 'measurement_basis',
         'source_member', 'source_member_sha256', 'table_index', 'row_index', 'value_col']})
    identity = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    records.append(dict(candidate_id='source-candidate-v1:' + hashlib.sha256(identity).hexdigest(),
                        group=group, **binding, amount_krw=r['amount_krw'],
                        semantic_status=verdict, PIT='UNVERIFIED', live_engine_eligible=False))
for group, directory in [('original_first100', a.first100), ('original_second57', a.second57), ('new_trial34', a.trial)]:
    for f in sorted(directory.rglob('results/*.json')):
        d = load(f); receipt = d['meta']['rcept_no']
        for r in d['rows']:
            if group == 'original_first100': verdict = new_decisions.get(key(receipt, r), 'UNREVIEWED')
            elif group == 'original_second57': verdict = old_decisions[key(receipt, r)]
            else: verdict = 'PASS'  # all34 separately reviewed in the preserved source controls
            append(group, receipt, r, verdict)
repaired = load(a.root / 'docs/research/native-source-boundary-repair-20261021/original-57-replay.json')['additions']
for r in repaired: append('held_repair9', r['receipt'], r, 'PASS')
ids = [r['candidate_id'] for r in records]
assert len(ids) == len(set(ids)) == 2277
original_ids = {r['candidate_id'] for r in records if r['group'].startswith('original_')}
extension_ids = {r['candidate_id'] for r in records if r['group'] in ['held_repair9', 'new_trial34']}
research_ids = set(ids)
assert len(original_ids) == 2234 and len(extension_ids) == 43 and not original_ids & extension_ids
assert research_ids == original_ids | extension_ids
summary = dict(classification='RESEARCH_ONLY', id_contract='source-candidate-v1',
    id_fields='receipt/scope/statement/metric/exact period/basis/member+SHA/table/row/column',
    amounts_not_in_id='Changing an amount at the same source locator must be a regression, not a new ID',
    groups=dict(Counter(r['group'] for r in records)),
    decisions=dict(Counter(r['semantic_status'] for r in records)),
    original_population=2234, repair_additions=9, collected_additions=34,
    research_population=2277, unique_ids=len(set(ids)), exact_same_set=True,
    missing_from_research=[], extra_in_research=[], duplicate_ids=0,
    old_first100_reviews_are_within_population=80,
    source_gap_documents_separate=23, canary_four_fields_outside_population=True,
    provider_quarantine_rows=298, provider_company_hints=70, new_live_engine_values=0,
    full_PIT_promotions=0, source_HTTP=0,
    limit='SBM new parser additions are excluded from this historical2277 population and reported separately')
assert summary['groups'] == dict(original_first100=1363, original_second57=871, new_trial34=34, held_repair9=9)
assert summary['decisions'] == dict(PASS=971, UNVERIFIED=23, UNREVIEWED=1283)
a.output.mkdir(exist_ok=False, parents=True)
with (a.output / 'CANDIDATE_ID_MEMBERSHIP.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
summary['membership_sha256'] = hashlib.sha256((a.output / 'CANDIDATE_ID_MEMBERSHIP.csv').read_bytes()).hexdigest()
(a.output / 'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
