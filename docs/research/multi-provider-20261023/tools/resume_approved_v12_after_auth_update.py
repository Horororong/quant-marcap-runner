"""Resume the exact approved v12 into its existing draft after user credential update.

Requires explicit --credential-updated. Does not create releases, overwrite
assets, publish research code, run CI, or change any original backup bytes.
The dedicated secret is passed only to gh's process environment, never logged.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

P = Path('/workspace/quant-multi-provider-20261023')
B = Path('/workspace/quant-backups/quant-recovery-union-v12-20261023')
REPO = 'Horororong/quant-marcap-runner'
RELEASE_ID = 421514386
SHA = '464aa445c1c1d92a891bad9072973f34cc27bf2e92cbb13b8947f38c4a3a820e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-updated', action='store_true', required=True)
    parser.parse_args()
    token = os.environ.get('GH_BACKUP_TOKEN')
    if not token:
        raise SystemExit('GH_BACKUP_TOKEN missing; stop without network request')
    environment = dict(os.environ, GH_TOKEN=token)
    environment.pop('GH_DEBUG', None)
    paths = [B / n for n in ['quant-recovery-union-v12-20261023.zip', 'TRANSFER_MANIFEST.json', 'VERIFICATION.json', 'SHA256SUMS.txt']]
    assert paths[0].stat().st_size == 538254 and hashlib.sha256(paths[0].read_bytes()).hexdigest() == SHA
    manifest = json.loads(paths[1].read_text())
    assert len(manifest['files']) == 41
    known = [v.encode() for k, v in os.environ.items() if re.search('TOKEN|PASSWORD|SECRET|API_KEY|ACCESS_KEY', k, re.I) and len(v) >= 12]
    for path in paths:
        raw = path.read_bytes()
        assert not any(v in raw for v in known), 'SECRET_CONTENT: stop without upload'
    with zipfile.ZipFile(paths[0]) as z:
        assert z.testzip() is None and len(z.namelist()) == 42
        for f in manifest['files']:
            data = z.read(f['path'])
            assert len(data) == f['bytes'] and hashlib.sha256(data).hexdigest() == f['sha256']

    def gh(arguments, operation):
        result = subprocess.run(['gh', *arguments], env=environment, capture_output=True)
        if result.returncode:
            # Persist only status classification, never headers or credentials.
            error = result.stderr.decode(errors='replace')
            status = next((code for code in [401, 403, 404, 422, 429] if str(code) in error), None)
            (P / 'V12_AUTH_UPDATE_STOP.json').write_text(json.dumps(dict(
                operation=operation, status=status, authentication='GH_BACKUP_TOKEN supplied to gh process only',
                response_reason='Bad credentials' if 'Bad credentials' in error else 'See status; raw authentication diagnostics withheld',
                retry=False, success=False), indent=2) + '\n')
            raise SystemExit(f'{operation} failed (HTTP {status}); no automatic retry')
        return result.stdout

    api = 'repos/' + REPO
    repo = json.loads(gh(['api', api], 'repository authentication'))
    assert repo['full_name'] == REPO and not repo['private'] and repo['permissions']['push']
    release = json.loads(gh(['api', f'{api}/releases/{RELEASE_ID}'], 'existing approved draft lookup'))
    assert release['draft'] and release['tag_name'] == 'backup-quant-recovery-union-v12-20261023-7691fd2'
    assets = json.loads(gh(['api', f'{api}/releases/{RELEASE_ID}/assets?per_page=100'], 'asset observation'))
    by_name = {a['name']: a for a in assets}
    assert len(by_name) == len(assets) and not (set(by_name) - {p.name for p in paths})
    missing = []
    for path in paths:
        if path.name in by_name:
            asset = by_name[path.name]
            assert asset['state'] == 'uploaded' and asset['size'] == path.stat().st_size
            remote = gh(['api', asset['url'], '-H', 'Accept: application/octet-stream'], 'existing asset verification')
            assert remote == path.read_bytes(), 'Existing asset differs; no overwrite'
        else:
            missing.append(path)
    if missing:
        gh(['release', 'upload', release['tag_name'], *map(str, missing), '--repo', REPO], 'approved asset upload')
    assets = json.loads(gh(['api', f'{api}/releases/{RELEASE_ID}/assets?per_page=100'], 'uploaded asset observation'))
    by_name = {a['name']: a for a in assets}
    assert len(assets) == 4 and set(by_name) == {p.name for p in paths}
    with tempfile.TemporaryDirectory(prefix='quant-v12-auth-readback-', dir='/tmp') as temp:
        for path in paths:
            remote = gh(['api', by_name[path.name]['url'], '-H', 'Accept: application/octet-stream'], 'remote download verification')
            dest = Path(temp) / path.name
            dest.write_bytes(remote)
            assert remote == path.read_bytes()
            if path == paths[0]:
                assert hashlib.sha256(remote).hexdigest() == SHA
                with zipfile.ZipFile(dest) as z:
                    assert z.testzip() is None and len(z.namelist()) == 42
                    for f in manifest['files']:
                        assert hashlib.sha256(z.read(f['path'])).hexdigest() == f['sha256']
    body = dict(body='VERIFIED: authenticated remote download, SHA256/CRC/all41payload hashes PASS. RESEARCH_ONLY. '
                f'Exact approved ZIP538254bytes SHA256 {SHA};41payload+1manifest=42ZIPentries,3sidecars=4releaseassets. '
                'Existing backups preserved. Financial HOLD and PIT gates unchanged. '
                'Whole remote-only project restoration remains unperformed.')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', dir=P) as f:
        json.dump(body, f); f.flush()
        gh(['api', f'{api}/releases/{RELEASE_ID}', '--method', 'PATCH', '--input', f.name], 'verified draft description')
    receipt = dict(status='PASS_REMOTE_DOWNLOAD_SHA256_CRC_ALL41_PAYLOADS', release_id=RELEASE_ID,
                   release_url=release['html_url'], draft=True, repository_public=True, archive_bytes=538254,
                   sha256=SHA, payload_files=41, ZIP_entries=42, sidecars=3, assets=4,
                   authentication='GH_BACKUP_TOKEN after user replacement', old_backups_changed=False)
    (P / 'V12_DELIVERY_COMPLETED.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
