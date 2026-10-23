"""Offline before/after structural regression; not independent source review."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import zipfile

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--first100', type=Path)
p.add_argument('--second57', type=Path)
p.add_argument('--trial', type=Path)
p.add_argument('--new-batch', type=Path, help='Compare only the newly collected21; never repeat completed159')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.root))
from scripts import legacy_native_financials as new
from scripts.legacy_document_quality import inspect_member, empty_parse_status

BASE = '33abf89aa46a388a57aab41c220ca82870cb1747'
old = types.ModuleType('reviewed_v93')
exec(compile(subprocess.check_output(['git', '-C', str(a.root), 'show',
    BASE + ':scripts/legacy_native_financials.py']), '<pinned-v93>', 'exec'), old.__dict__)
FIELDS = ['metric', 'scope', 'statement', 'term', 'period_start', 'period_end',
          'measurement_basis', 'amount_reported', 'amount_krw', 'unit',
          'unit_multiplier', 'structural_status', 'availability_status',
          'backtest_eligible', 'source_member', 'source_member_sha256',
          'table_index', 'row_index', 'value_col', 'source_character',
          'raw_amount', 'account_name', 'correction_file', 'amendment_region',
          'numeric_normalization', 'fiscal_year', 'fiscal_year_evidence']
def key(r):
    return tuple(r[k] for k in ('metric', 'scope', 'period_end', 'measurement_basis'))
def fingerprint(r):
    return {k: r.get(k) for k in FIELDS}

documents, additions, changes, losses = [], [], [], []
sbm = {}
groups = [('new21', a.new_batch)] if a.new_batch else [('first100', a.first100), ('second57', a.second57), ('trial2', a.trial)]
for group, directory in groups:
    assert directory is not None
    files = sorted(directory.rglob('results/*.json'))
    assert len(files) == {'first100': 100, 'second57': 57, 'trial2': 2, 'new21': 21}[group], (group, len(files))
    for f in files:
        d = json.loads(f.read_text()); receipt = d['meta']['rcept_no']
        archive = next((f.parent.parent / 'native').glob(receipt + '-*.zip'))
        raw = archive.read_bytes(); archive_sha = hashlib.sha256(raw).hexdigest()
        assert archive_sha == archive.stem.split('-')[1]
        before, after, diags = [], [], []
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for name in z.namelist():
                if name.endswith('/'): continue
                data = z.read(name); diag = inspect_member(data, name); diags.append(diag)
                enc = diag.get('resolved_encoding')
                if enc: text = data.decode(enc)
                else:
                    for enc in ['utf-8', 'cp949', 'euc-kr']:
                        try: text = data.decode(enc); break
                        except UnicodeDecodeError: pass
                    else: raise ValueError((receipt, name, 'ENCODING'))
                metadata = dict(source_member=name, source_member_sha256=hashlib.sha256(data).hexdigest())
                b = old.parse_native(text); n = new.parse_native(text)
                before.extend({**r, **metadata} for r in b['candidates'])
                after.extend({**r, **metadata} for r in n['candidates'])
                if receipt == '20100331001822':
                    sbm[name] = dict(member_sha256=metadata['source_member_sha256'],
                                     before=b, after=n)
        gap = empty_parse_status(diags) == 'SOURCE_GAP'
        b = {key(r): r for r in ([] if gap else old.select_verified(before))}
        n = {key(r): r for r in ([] if gap else new.select_verified(after))}
        for k in b:
            if k not in n: losses.append(dict(receipt=receipt, key=k, before=b[k]))
            elif fingerprint(b[k]) != fingerprint(n[k]):
                changes.append(dict(receipt=receipt, key=k, before=b[k], after=n[k]))
        for k in n.keys() - b.keys():
            additions.append(dict(receipt=receipt, group=group, **n[k],
                                  source_archive_sha256=archive_sha,
                                  state='NEW_STRUCTURAL_CANDIDATE_REQUIRES_SOURCE_REVIEW'))
        documents.append(dict(receipt=receipt, group=group, before=len(b), after=len(n),
                              added=len(n.keys() - b.keys()), gap=gap))
        print(group, receipt, len(b), '->', len(n), flush=True)
report = dict(classification='RESEARCH_ONLY', baseline=BASE,
              before_version=old.PARSER_VERSION, after_version=new.PARSER_VERSION,
              compared_fields=FIELDS, documents=documents, additions=additions,
              existing_changes=changes, existing_losses=losses,
              source_HTTP=0, publication='HOLD', PIT='UNVERIFIED',
              groups={g: dict(documents=sum(d['group'] == g for d in documents),
                              before=sum(d['before'] for d in documents if d['group'] == g),
                              after=sum(d['after'] for d in documents if d['group'] == g))
                      for g, _ in groups})
a.output.mkdir(exist_ok=False, parents=True)
(a.output / 'REPLAY.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(a.output / 'SBM_PARSE.json').write_text(json.dumps(sbm, ensure_ascii=False, indent=2) + '\n')
assert not changes and not losses, ('REGRESSION', len(changes), len(losses))
print(json.dumps(report['groups'], indent=2))
