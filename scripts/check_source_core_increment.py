"""Compare fresh original-source reproduction with the preserved field controls.

No source HTTP. Source values/bindings, identities and readiness decisions are
strict; only the readiness evidence fingerprint depends on the temporary path.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def check_protected_owners(root, pins):
    actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in pins}
    changed = {name for name in pins if actual[name] != pins[name]}
    if not changed:
        return 'EXACT_HISTORICAL_OWNERS'
    parser = 'scripts/legacy_native_financials.py'
    config_path = 'config/financial_limited_resume_v1.json'
    assert changed == {parser, config_path}, changed
    # Preserve the old pins. Only the explicit, independently reviewed parser
    # migration may account for these two differences; no generic hash refresh.
    fixture = root / 'tests/fixtures/financial_limited_resume_approved_v9_3.json'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == pins[config_path]
    old = json.loads(fixture.read_text())
    assert old['parser_version'] == 'legacy-v9.3-note-reference-token-guard'
    assert old['source_code_sha256'][parser] == pins[parser]
    from check_native_source_review_evidence import check as check_migration
    migration = check_migration(root)
    assert migration['source_module_sha256'] == actual[parser]
    return 'EXPLICIT_SOURCE_REVIEW_MIGRATION_OLD_PINS_PRESERVED'


def check(root, audit):
    evidence = root / 'docs/research/source-core-batch3-20261023/evidence'
    exact = ['new20-review/NEW20_CORE_SOURCE_REVIEW.json',
             'provider-new80/2009-FY-CANDIDATE_ACCOUNT_ROWS.csv',
             'provider-new80/2009-FY-CANDIDATE_SNAPSHOTS.csv',
             'identity-final/IDENTITY_AT_SIGNALS.json',
             'identity-final/REVIEWED_SELF_NAME_ALIASES.json']
    for relative in exact:
        assert (audit / relative).read_bytes() == (evidence / relative).read_bytes(), relative
    # Fingerprint embeds the run's absolute review JSON path. Compare all actual
    # readiness fields, financial bindings and blockers instead of masking them.
    def readiness(path):
        return [{k: v for k, v in row.items() if k != 'evidence_fingerprint'}
                for row in json.loads(path.read_text())]
    relative = 'identity-final/FIELD_READINESS_AT_SIGNALS.json'
    assert readiness(audit / relative) == readiness(evidence / relative)
    source = json.loads((audit / 'new20-review/SUMMARY.json').read_text())
    preview = json.loads((audit / 'provider-new80/SUMMARY.json').read_text())
    identity = json.loads((audit / 'identity-final/SUMMARY.json').read_text())
    assert source['new_source_meaning_PASS'] == 80 and source['new_source_meaning_FAIL'] == 0
    assert preview['canonical_preview_exact'] == preview['canonical_preview_checked'] == 80
    assert preview['source_ready_rows'] == 0 and not preview['whole_population_ready']
    assert identity['PASS'] == 33 and identity['UNVERIFIED'] == 7
    assert identity['new_complete_PIT_records'] == identity['new_live_engine_ready_records'] == 0
    pins = json.loads((evidence / 'UNCHANGED_PROTECTED_OWNERS.json').read_text())['files']
    protected_owner_mode = check_protected_owners(root, pins)
    return dict(status='PASS_SOURCE80_PROVIDER80_IDENTITY40_STRICT_FIELDS', classification='RESEARCH_ONLY',
                new_source_fields=80, source_identity_snapshots=33, unresolved_identity_snapshots=7,
                new_PIT_ready=0, financial_publication='HOLD', protected_owners_checked=5,
                protected_owner_mode=protected_owner_mode,
                fingerprint_path_variation_only=True, source_HTTP=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--audit-root', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    raw = json.dumps(check(a.root, a.audit_root), indent=2) + '\n'
    if a.output:
        with a.output.open('x') as f:
            f.write(raw)
    print(raw, end='')
