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


# Trust anchors are bytes from the explicitly approved immutable cc817 commit.
# Updating both a proof and its mutable hash is insufficient; a new reviewed
# migration must explicitly change this executable contract.
REVIEWED_94_FILES = {'docs/research/source-core-batch3-20261023/evidence/UNCHANGED_PROTECTED_OWNERS.json': 'b0725ab4fec5fdf3b0f69c3b87a920671e6189d7b1dc16ab8bc60021d78a1d85',
 'docs/research/source-core-batch3-20261023/evidence/FROZEN_NEW_REVIEW_SCOPE.json': '0b02281fb0ff5bfe1dca3d002ef86c5dfab4976cedf54c2e4b46f83a57b0267a',
 'docs/research/source-core-batch3-20261023/evidence/new20-review/NEW20_CORE_SOURCE_REVIEW.json': '12d129003bfeb0f9aa9bf321f19cbb059cd344fd6b5d32d31dfcf03ce46bfd32',
 'docs/research/source-core-batch3-20261023/evidence/provider-new80/2009-FY-CANDIDATE_ACCOUNT_ROWS.csv': 'e3abe5a64111f18a4a77bb818a24d6b86ac638543fe46596070a99175b10cd5d',
 'docs/research/source-core-batch3-20261023/evidence/provider-new80/2009-FY-CANDIDATE_SNAPSHOTS.csv': '9843a44ba09a70fb1d0568add659fa10a8928ab46c7e79e91a2b9326716d1391',
 'docs/research/source-core-batch3-20261023/evidence/identity-final/IDENTITY_AT_SIGNALS.json': 'b189eb8b5c62ec77cccb29d694a06cb5b38a2341cde809c8d4d65785ca949a05',
 'docs/research/source-core-batch3-20261023/evidence/identity-final/REVIEWED_SELF_NAME_ALIASES.json': 'c2bec547d27a821028d0706567945d727de35d134b6b58eba37d72e7c9ac6e83',
 'docs/research/source-core-batch3-20261023/evidence/identity-final/FIELD_READINESS_AT_SIGNALS.json': '93fa80b01e45978e247f50db5afb27369d33493b57f581605f74518ded4199a8',
 'data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39248507369/manifest.json': '0700992fc90e9e0cc0d7c6014586b1d8335f49d80f12a9bd624231215ff6659d',
 'docs/research/source-review-batch2-20261021/DELTA_MANIFEST.json': '9c1e363cb8e926ce1d34e70ff88a965eaa5a9d0977994c62d620c73998ae4a36',
 'docs/research/native-source-boundary-repair-20261021/EVIDENCE_MANIFEST.json': 'dca8cd7ee6aa44344d567b51a2d756b276be7487e56c210037980af4022f2dfc',
 'tests/fixtures/financial_limited_resume_approved_v9_2.json': '054ea855ecb0d83720463de4deb5696b38ce19fb7fd06a1cfc190e83ac825884',
 'tests/fixtures/financial_limited_resume_approved_v9_3.json': '7a537780bfe2403a9e0f49d934d58ecec44c98e69324f34891fb799d8172354a',
 'scripts/legacy_native_financials.py': 'd167cc1dfbad2b67f62ebbbe3664d1834c1913663d94bddf35c2075e1ebb8edf',
 'config/financial_limited_resume_v1.json': 'e24a26fa52f61aeea79056f75a6d60ab15d8fa41c468598c816883c4c9a00ffc',
 'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json': '346a0f9626d5e9c4e699661d80e7230cc1b5ba9f351fb0158d84ae04582f1e3b',
 'docs/research/sbm-reference-pit-20261023/evidence/REPLAY.json': 'ad652d29de810e2a62c53c81fb04b09a58d3bc995a5c44c3ba385d7b692d902e',
 'docs/research/sbm-reference-pit-20261023/evidence/SBM_SOURCE_REVIEW.json': '46517f043a0d665f9c9a9efbe9554a548f4ab3da7ead87c89f721a4004a4ae4a',
 'docs/research/sbm-reference-pit-20261023/evidence/NEW21_REPLAY.json': 'c2ac1928e66fa347aadf1edde0a4ea191ef120fecb740b81177d4155fa214a12'}
HISTORICAL_OWNER_FILE = 'docs/research/source-core-batch3-20261023/evidence/UNCHANGED_PROTECTED_OWNERS.json'

def check_reviewed_migration_bytes(root):
    for name, expected in REVIEWED_94_FILES.items():
        path = root / name
        assert path.is_file(), "MISSING_REVIEWED_MIGRATION_FILE: " + name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, "UNAPPROVED_MIGRATION_BYTES: " + name


def check_protected_owners(root, pins):
    owner_path = root / HISTORICAL_OWNER_FILE
    assert hashlib.sha256(owner_path.read_bytes()).hexdigest() == REVIEWED_94_FILES[HISTORICAL_OWNER_FILE]
    assert pins == json.loads(owner_path.read_text())["files"], "UNBOUND_HISTORICAL_OWNER_PINS"
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
    check_reviewed_migration_bytes(root)
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
