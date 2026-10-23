"""Open existing fixed source packs into a NEW audit directory; no HTTP/parser.

Each transfer has its own progress selection.json. Keep partNN namespaces;
flattening those five different checkpoint snapshots would overwrite evidence.
"""
import argparse
import base64
import gzip
import hashlib
import json
import shutil
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', required=True, type=Path)
p.add_argument('--workdir', required=True, type=Path)
a = p.parse_args()
a.workdir.mkdir(parents=True, exist_ok=False)
base = a.root / 'data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39248507369'
manifest = json.loads((base / 'manifest.json').read_text())
files = sorted(base.glob('sources*.json.gz.b64'))
assert len(files) == len(manifest['transfers']) == 5
for i, f in enumerate(files):
    packed = base64.b64decode(f.read_bytes())
    pin = manifest['transfers'][i]
    assert len(packed) == pin['bytes'] and hashlib.sha256(packed).hexdigest() == pin['compressed_sha256']
    for name, encoded in json.loads(gzip.decompress(packed))['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        target = a.workdir / 'first100-chunks' / f'part{i:02d}' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(base64.b64decode(encoded))
scope = Path(__file__).resolve().parents[1] / 'evidence/FROZEN_NEW_REVIEW_SCOPE.json'
shutil.copyfile(scope, a.workdir / scope.name)
print('Existing fixed source packs opened; source HTTP0. RESEARCH_ONLY.')
