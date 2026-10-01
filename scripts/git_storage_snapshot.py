"""Read-only Git storage measurements; no cleanup, financial parsing or API calls."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

CONTRACT = 1


def git(repo, *args, input=None):
    return subprocess.check_output(['git', '-c', 'core.quotePath=false', *args],
                                   cwd=repo, input=input)


def category(path):
    for prefix, name in (
        ('data/financials/recent_batches/', 'dart_recent'),
        ('data/financials/full_history/', 'dart_full_history'),
        ('data/financials/dart_raw/', 'dart_raw'),
        ('data/financials/', 'dart_other'),
        ('data/krx_equities/yearly/', 'krx_yearly'),
        ('data/krx_equities/derived/', 'krx_derived'),
        ('results/', 'results'), ('data/', 'other_data'),
    ):
        if path.startswith(prefix): return name
    return 'code_and_docs'


def aggregate(items):
    groups = defaultdict(lambda: {'objects': 0, 'bytes': 0})
    for item in items:
        group = groups[category(item['path'])]
        group['objects'] += 1
        group['bytes'] += item['bytes']
    return dict(sorted(groups.items()))


def snapshot(repo, ref='HEAD', *, now=None):
    repo = Path(repo)
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('Full history required: use fetch-depth: 0; shallow totals are incomplete')
    head = git(repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    tracked = []
    for entry in git(repo, 'ls-tree', '-r', '-l', '-z', head).split(b'\0'):
        if not entry: continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, oid, size = metadata.split()
        if kind == b'blob':
            tracked.append({'path': path.decode('utf-8', 'surrogateescape'),
                            'bytes': int(size), 'oid': oid.decode()})
    objects = {}
    for line in git(repo, 'rev-list', '--objects', head).decode('utf-8', 'surrogateescape').splitlines():
        oid, _, path = line.partition(' ')
        objects[oid] = path
    information = git(repo, 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)',
                      input=('\n'.join(objects) + '\n').encode()).decode()
    blobs = []
    for line in information.splitlines():
        oid, kind, size = line.split()
        if kind == 'blob':
            blobs.append({'path': objects[oid], 'bytes': int(size)})
    counts = {}
    for line in git(repo, 'count-objects', '-v').decode().splitlines():
        name, value = line.split(': ', 1)
        counts[name] = int(value)
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None: raise ValueError('Measurement timestamp must include timezone')
    return {
        'contract_version': CONTRACT, 'observed_at_utc': observed.astimezone(timezone.utc).isoformat(),
        'head': head, 'git_version': git(repo, '--version').decode().strip(),
        'history_scope': 'unique blobs reachable from the sampled commit only',
        'head_files': len(tracked), 'head_bytes': sum(x['bytes'] for x in tracked),
        'head_by_category': aggregate(tracked),
        'history_unique_blobs': len(blobs),
        'history_logical_blob_bytes': sum(x['bytes'] for x in blobs),
        'history_by_category': aggregate(blobs),
        'largest_head_files': sorted(tracked, key=lambda x: (-x['bytes'], x['path']))[:10],
        'clone_object_store': {
            'pack_bytes': counts['size-pack'] * 1024, 'loose_bytes': counts['size'] * 1024,
            'packed_objects': counts['in-pack'], 'loose_objects': counts['count'],
            'scope': 'this clone including other fetched refs; not GitHub server storage or billing',
            'comparison_limit': 'pack compression/layout differs between clones; use logical history/category deltas for growth',
        },
    }


def growth(repo, current, baseline):
    if baseline['contract_version'] != current['contract_version']:
        raise ValueError('Incompatible measurement contract')
    # Resolve to a commit first; never let baseline content become command options.
    old = git(repo, 'rev-parse', '--verify', '--end-of-options', baseline['head'] + '^{commit}').decode().strip()
    if subprocess.run(['git', 'merge-base', '--is-ancestor', old, current['head']],
                      cwd=repo, capture_output=True).returncode:
        raise ValueError('Baseline must be an ancestor of the measured commit')
    elapsed = (datetime.fromisoformat(current['observed_at_utc']) -
               datetime.fromisoformat(baseline['observed_at_utc'])).total_seconds()
    if elapsed < 0: raise ValueError('Current observation predates baseline')
    groups = {}
    for name in sorted(set(current['history_by_category']) | set(baseline['history_by_category'])):
        a = current['history_by_category'].get(name, {'objects': 0, 'bytes': 0})
        b = baseline['history_by_category'].get(name, {'objects': 0, 'bytes': 0})
        groups[name] = {key: a[key] - b[key] for key in ('objects', 'bytes')}
    return {'baseline_head': old, 'elapsed_days': round(elapsed / 86400, 3),
            'head_bytes_delta': current['head_bytes'] - baseline['head_bytes'],
            'history_unique_blobs_delta': current['history_unique_blobs'] - baseline['history_unique_blobs'],
            'history_logical_blob_bytes_delta': current['history_logical_blob_bytes'] - baseline['history_logical_blob_bytes'],
            'history_category_delta': groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = snapshot(args.repo_root, args.ref)
    if args.baseline:
        report['growth_since_baseline'] = growth(args.repo_root, report, json.loads(args.baseline.read_text()))
    text = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
    if args.output:
        if args.output.exists(): raise FileExistsError('Measurement output already exists')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream: stream.write(text)
    print(text, end='')


if __name__ == '__main__': main()
