"""Verify the preserved source-audit population and reviewed parser binding.

This checks source-row evidence and its regression provenance. It does not
rerun the source parser, collect documents, certify PIT or publish values.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    return json.loads(path.read_text())


def candidate_key(row):
    return (row['receipt'], row['scope'], row['metric'], row['period_end'],
            row['measurement_basis'])


def check(root):
    batch = root / 'docs/research/source-review-batch2-20261021'
    repair = root / 'docs/research/native-source-boundary-repair-20261021'
    for manifest_name, directory in [('DELTA_MANIFEST.json', batch),
                                      ('EVIDENCE_MANIFEST.json', repair)]:
        for pin in load(directory / manifest_name)['files']:
            raw = (directory / pin['path']).read_bytes()
            assert len(raw) == pin['bytes'], pin['path']
            assert hashlib.sha256(raw).hexdigest() == pin['sha256'], pin['path']
    original = load(batch / 'all-871-candidate-decisions.json')
    previous = load(root / 'docs/research/operating-source-review-20261021/candidate-review-348.json')
    assert original[:348] == previous
    assert len(original) == 871
    assert sum(x['semantic_verdict'] == 'PASS' for x in original) == 848
    assert sum(x['semantic_verdict'] == 'UNVERIFIED' for x in original) == 23
    assert all(x['PIT'] == 'UNVERIFIED' for x in original)
    keys = {candidate_key(x) for x in original}
    assert len(keys) == 871
    replay = load(repair / 'original-57-replay.json')
    assert replay['source_documents'] == 57 and replay['old_candidates'] == 871
    assert replay['new_candidates'] == 880
    assert replay['existing_changes'] == replay['existing_losses'] == []
    assert replay['baseline_replay_vs_stored_mismatch'] == []
    assert len(replay['source_gap_documents_unchanged']) == 9
    assert replay['source_HTTP'] == replay['financial_publication'] == 0
    controls = load(repair / 'new-9-independent-source-controls.json')['records']
    assert len(controls) == len(replay['additions']) == 9
    for row in replay['additions']:
        key = candidate_key(row)
        assert key not in keys, key
        keys.add(key)
        reference = next(x for x in controls if
                         (x['receipt'], x['scope'], x['metric']) == key[:3])
        assert reference['source_row_semantics'] == 'PASS'
        assert reference['PIT'] == 'UNVERIFIED'
        assert row['amount_krw'] == reference['independent_amount_krw']
        assert row['source_member_sha256'] == reference['source_member_sha256']
        assert row['availability_status'] == 'UNVERIFIED'
        assert row['backtest_eligible'] is False
    assert len(keys) == 880
    uv = load(batch / 'unverified-23-cause-ledger.json')
    assert len(uv) == 23
    assert sum(x['previous_reviewed_12'] for x in uv) == 12
    prior_uv = {candidate_key(x) for x in previous if x['semantic_verdict'] == 'UNVERIFIED'}
    current_uv = {candidate_key(x) for x in original if x['semantic_verdict'] == 'UNVERIFIED'}
    assert prior_uv <= current_uv and len(current_uv - prior_uv) == 11
    # Every added unresolved decision was previously outside the reviewed348.
    prior_keys = {candidate_key(x) for x in previous}
    assert not (current_uv - prior_uv) & prior_keys
    config = load(root / 'config/financial_limited_resume_v1.json')
    old = load(root / 'tests/fixtures/financial_limited_resume_approved_v9_2.json')
    for key in old:
        if key not in {'parser_version', 'source_code_sha256'}:
            assert config[key] == old[key], key
    from scripts.legacy_native_financials import PARSER_VERSION
    source = 'scripts/legacy_native_financials.py'
    preserved = load(repair / 'MIGRATION_AND_TEST_STATUS.json')
    if PARSER_VERSION == replay['after_version']:
        assert config['parser_version'] == PARSER_VERSION
        assert config['source_code_sha256'][source] == preserved['research_source_sha256']
    else:
        # Historical9.3 evidence remains pinned to9.3. A later reviewed parser
        # must prove an explicit migration; never relabel the old replay/hash.
        assert PARSER_VERSION == config['parser_version'] == 'legacy-v9.4-explicit-audit-note-reference'
        v93 = load(root / 'tests/fixtures/financial_limited_resume_approved_v9_3.json')
        assert v93['parser_version'] == replay['after_version']
        assert v93['source_code_sha256'][source] == preserved['research_source_sha256']
        directory = root / 'docs/research/sbm-reference-pit-20261023/evidence'
        migration = load(directory / 'MIGRATION.json')
        regression = load(directory / 'REPLAY.json')
        controls = load(directory / 'SBM_SOURCE_REVIEW.json')
        assert migration['before_version'] == replay['after_version']
        assert migration['after_version'] == PARSER_VERSION
        assert migration['before_source_sha256'] == preserved['research_source_sha256']
        assert migration['after_source_sha256'] == config['source_code_sha256'][source]
        for file, field in [('REPLAY.json', 'replay_sha256'), ('SBM_SOURCE_REVIEW.json', 'source_review_sha256')]:
            assert hashlib.sha256((directory / file).read_bytes()).hexdigest() == migration[field]
        assert regression['before_version'] == replay['after_version']
        assert regression['after_version'] == PARSER_VERSION
        assert regression['existing_changes'] == regression['existing_losses'] == []
        assert len(regression['documents']) == 159
        assert sum(d['before'] for d in regression['documents']) == 2277
        assert len(regression['additions']) == len(controls['rows']) == 15
        assert {d['receipt'] for d in regression['additions']} == {'20100331001822'}
        references = {candidate_key(r): r for r in controls['rows']}
        for row in regression['additions']:
            reference = references[candidate_key(row)]
            assert reference['semantic_verdict'] == 'PASS'
            assert row['amount_krw'] == reference['independent_amount_krw']
            assert row['source_member_sha256'] == reference['source_member_sha256']
            assert (row['table_index'], row['row_index'], row['value_col']) == (reference['table'], reference['row'], reference['current_physical_column'])
            assert not reference['engine_eligible'] and reference['PIT'].startswith('UNVERIFIED')
        for name in v93:
            if name not in {'parser_version', 'source_code_sha256'}:
                assert config[name] == v93[name], name
        additional_path = directory / 'NEW21_REPLAY.json'
        assert hashlib.sha256(additional_path.read_bytes()).hexdigest() == migration['additional_replay_sha256']
        additional = load(additional_path)
        assert additional['before_version'] == replay['after_version']
        assert additional['after_version'] == PARSER_VERSION
        assert additional['existing_changes'] == additional['existing_losses'] == additional['additions'] == []
        assert additional['groups'] == {'new21': {'documents': 21, 'before': 273, 'after': 273}}
        assert additional['source_HTTP'] == 0
    assert set(config['source_code_sha256']) == set(old['source_code_sha256'])
    for name, expected in config['source_code_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
        if name != source:
            assert expected == old['source_code_sha256'][name], name
    return dict(status='PASS_SOURCE_ROW_EVIDENCE_AND_REAPPROVAL',
                original_candidates=871, original_PASS=848, original_UNVERIFIED=23,
                new_candidates=9, new_semantic_PASS=9, new_PIT_UNVERIFIED=9,
                unique_proposed_candidates=880, proposed_PASS=857,
                proposed_UNVERIFIED=23, previous_UNVERIFIED=12,
                newly_reviewed_UNVERIFIED=11, reclassified_prior_decisions=0,
                source_gap_documents=9, all_880_PIT='UNVERIFIED',
                operating_candidate_store_replaced=False,
                financial_publication='HOLD', research_only=True,
                whole_filing_completeness='UNVERIFIED',
                source_module_sha256=config['source_code_sha256'][source])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(ROOT)
    raw = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(raw)
    print(raw, end='')
