from __future__ import annotations

"""Build a checksummed offline kit from a clean, pinned repository commit."""
import argparse
import ast
import email
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from sandbox_bootstrap import KIT_CONTRACT_VERSION, canonical_bytes, hash_file, manifest_id, safe_relative

STARTER = ('super_value_dart_benchmark_dsl', 'kr_equity_size_deciles_research', 'kr_equity_split_research')
ROOT = Path(__file__).resolve().parents[1]
LOCK_LINE = re.compile(r'([A-Za-z0-9._-]+)==([^\s]+) --hash=sha256:([a-f0-9]{64})$')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def read_lock(path):
    pins = {}
    for line in Path(path).read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        match = LOCK_LINE.fullmatch(line)
        if not match:
            raise ValueError(f'invalid exact wheel lock: {line}')
        name, version, digest = match.groups()
        name = re.sub(r'[-_.]+', '-', name).lower()
        if name in pins:
            raise ValueError(f'duplicate locked package: {name}')
        pins[name] = (version, digest)
    if 'pip' not in pins:
        raise ValueError('offline lock must include pip')
    return pins


def locked_wheels(directory, pins):
    selected = {}
    for path in sorted(Path(directory).glob('*.whl')):
        with zipfile.ZipFile(path) as wheel:
            headers = email.message_from_bytes(wheel.read(next(n for n in wheel.namelist() if n.endswith('.dist-info/METADATA'))))
        name = re.sub(r'[-_.]+', '-', headers['Name']).lower()
        if name in pins and headers['Version'] == pins[name][0] and hash_file(path) == pins[name][1]:
            if name in selected:
                raise ValueError(f'duplicate matching wheel: {name}')
            selected[name] = path
    if selected.keys() != pins.keys():
        raise ValueError(f'missing/hash-mismatched locked wheels: {sorted(pins.keys() - selected.keys())}')
    return selected


def local_module_closure(root, seeds):
    pending, found = list(seeds), set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        found.add(name)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                local = 'scripts/' + module.split('.')[0] + '.py'
                if (root / local).is_file() and local not in found:
                    pending.append(local)
    return found


def selected_sources(root, strategies, extra_years=()):
    import pandas as pd
    from strategy_dsl import load_strategy_spec
    from strategy_dsl_preflight import preflight_strategy
    from dart_value_factor_adapter import required_periods, DART_HISTORY_DIR, DART_BACKFILL_STATE_FILE, DART_CODE_MAP_FILE
    from factor_registry import get_filter_definition
    years, periods, coverage = set(extra_years), set(), []
    for name in strategies:
        spec = load_strategy_spec(root / name)
        audit = preflight_strategy(root / name, root)
        if audit['status'] != 'ok':
            raise ValueError(f'kit example is not executable: {name}: {audit}')
        coverage.append({'strategy_path': name, 'preflight': audit})
        years.update(range(pd.Timestamp(spec.period.start).year, pd.Timestamp(spec.period.end).year + 1))
        signals = pd.date_range(spec.period.start, spec.period.end, freq='ME')
        sources = {factor.source for factor in spec.factors}
        sources.update(get_filter_definition(f.field).source for f in spec.universe.filters)
        for signal in signals:
            if spec.rebalance.months and signal.month not in spec.rebalance.months:
                continue
            if 'dart' in sources:
                periods.update(required_periods(signal))
            if 'technical' in sources:
                years.update(range(signal.year - 2, signal.year + 1))
    files = {f'data/krx_equities/yearly/marcap-{year}.parquet' for year in years}
    files.add('data/status/krx_equities_status.csv')
    if any(json.loads((root / name).read_text()).get('benchmark') for name in strategies):
        # The public contract currently has a single KOSPI price-index source.
        files.add('data/indices/KOSPI.csv')
    if periods:
        files.update((DART_BACKFILL_STATE_FILE, DART_CODE_MAP_FILE))
        for year, period in sorted(periods):
            shards = sorted((root / DART_HISTORY_DIR).glob(f'dart_full_{year}_{period}_*.csv.gz'))
            if not shards:
                raise FileNotFoundError(f'missing DART source period: {year} {period}')
            files.update(p.relative_to(root).as_posix() for p in shards)
    return files, {'examples': coverage, 'krx_years': sorted(years), 'dart_periods': [list(p) for p in sorted(periods)],
                   'scope': 'original whole-year panels and whole required-period shards; no present-day universe pruning',
                   'other_requests': 'runtime preflight required; catalog support does not certify included data coverage'}


def fixed_zip(output, files):
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name, path in sorted(files.items()):
            safe_relative(name)
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100644 << 16)
            info.create_system = 3
            with Path(path).open('rb') as src, archive.open(info, 'w', force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)


def entry(path, name, kind=None):
    value = {'path': name, 'bytes': path.stat().st_size, 'sha256': hash_file(path)}
    if kind:
        value['kind'] = kind
    return value


def source_metadata(path):
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        table = pq.ParquetFile(path)
        result = {'rows': table.metadata.num_rows, 'schema': str(table.schema_arrow)}
        dates = table.read(columns=['Date']).column('Date')
        import pyarrow.compute as pc
        result['date_min'] = str(pc.min(dates).as_py())
        result['date_max'] = str(pc.max(dates).as_py())
        return result
    import csv, gzip
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        rows = csv.reader(stream)
        columns = next(rows)
        return {'rows': sum(1 for _ in rows), 'columns': columns}


def build_kit(root, output, wheels, targets=('cp311', 'cp312'), strategies=None, extra_years=(), part_bytes=32 * 1024**2):
    root, output, wheels = Path(root).resolve(), Path(output).resolve(), Path(wheels).resolve()
    if output.exists():
        raise FileExistsError(f'kit output must be new: {output}')
    if part_bytes < 1:
        raise ValueError('part size must be positive')
    revision = git(root, 'rev-parse', 'HEAD')
    if git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('kit requires a clean committed source tree')
    strategies = list(strategies or (f'config/strategies/{name}.json' for name in STARTER))
    for name in strategies:
        safe_relative(name)
    data, coverage = selected_sources(root, strategies, extra_years)
    code = local_module_closure(root, ('scripts/sandbox_runtime.py', 'scripts/sandbox_bootstrap.py',
                                     'scripts/strategy_dsl_run.py', 'scripts/strategy_dsl_aliases.py',
                                     'scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py'))
    code.update(('SANDBOX_START_HERE.md', 'docs/STRATEGY_DSL.md', 'docs/STRATEGY_DSL_RUN.md',
                 'docs/CANONICAL_PERFORMANCE.md', 'config/strategy_dsl_schema_v1.json',
                 'config/strategy_dsl_capabilities_v1.json', 'config/kr_corporate_actions.csv',
                 'config/kr_corporate_action_gaps.json', *strategies))
    runtime_targets, wheel_files = {}, {}
    for abi in sorted(set(targets)):
        if abi not in ('cp311', 'cp312'):
            raise ValueError(f'unsupported wheel ABI: {abi}')
        lock = f'config/sandbox/requirements-{abi}-linux-x86_64.lock'
        code.add(lock)
        pins = read_lock(root / lock)
        chosen = locked_wheels(wheels / abi, pins)
        target_paths = []
        for path in chosen.values():
            name = 'wheels/' + path.name
            if name in wheel_files and hash_file(path) != hash_file(wheel_files[name]):
                raise ValueError(f'conflicting shared wheel: {name}')
            wheel_files[name] = path
            target_paths.append(name)
        runtime_targets[f'{abi}-linux-x86_64'] = {'python_minor': f'3.{abi[3:]}', 'requirements_path': lock,
                                                 'packages': {n: v for n, (v, _) in pins.items()},
                                                 'wheel_paths': sorted(target_paths)}
    inventory = []
    with tempfile.TemporaryDirectory(prefix='quant-kit-snapshot-') as tmp:
        stage = Path(tmp)
        for name in sorted(code | data):
            path = root / name
            if path.is_symlink():
                raise ValueError(f'source symlink forbidden: {name}')
            blob = git(root, 'rev-parse', revision + ':' + name)
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            digest = hashlib.sha1(f'blob {dest.stat().st_size}\0'.encode())
            with dest.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != blob:
                raise ValueError(f'source changed during kit snapshot: {name}')
            value = entry(dest, name, 'data' if name in data else 'code')
            value['git_blob'] = blob
            if name in data:
                value.update(source_metadata(dest))
            inventory.append(value)
        for name, path in sorted(wheel_files.items()):
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            inventory.append(entry(dest, name, 'wheel'))
        # Verify copied wheels against their locks again, not just mutable input cache.
        for target in runtime_targets.values():
            locked_wheels(stage / 'wheels', read_lock(stage / target['requirements_path']))
        if git(root, 'rev-parse', 'HEAD') != revision or git(root, 'status', '--porcelain', '--untracked-files=no'):
            raise ValueError('source commit/tree changed during kit build')
        output.mkdir(parents=True, exist_ok=False)
        bootstrap_path = output / 'bootstrap_quant.py'
        shutil.copyfile(stage / 'scripts/sandbox_bootstrap.py', bootstrap_path)
        archives = []
        for kind in ('code', 'data', 'wheel'):
            packed = stage / f'{kind}.zip'
            fixed_zip(packed, {v['path']: stage / v['path'] for v in inventory if v['kind'] == kind})
            value = entry(packed, packed.name)
            value['parts'] = []
            with packed.open('rb') as source:
                number = 1
                while chunk := source.read(part_bytes):
                    name = f'{kind}.part{number:03d}'
                    part = output / name
                    part.write_bytes(chunk)
                    value['parts'].append(entry(part, name))
                    number += 1
            archives.append(value)
        caps = json.loads((stage / 'config/strategy_dsl_capabilities_v1.json').read_text())
        versions = {key: value for key, value in caps.items() if key.endswith('_version')}
        manifest = {'kit_contract_version': KIT_CONTRACT_VERSION, 'source_repository': 'Horororong/quant-marcap-runner',
                    'source_revision': revision, 'versions': versions, 'profile': {'strategies': strategies, 'mode': 'execution_only'},
                    'coverage': coverage, 'runtime_targets': runtime_targets, 'files': inventory,
                    'archives': archives, 'bootstrap': entry(bootstrap_path, bootstrap_path.name)}
        manifest['kit_id'] = manifest_id(manifest)
        (output / 'kit_manifest.json').write_bytes(canonical_bytes(manifest) + b'\n')
        shutil.copyfile(stage / 'SANDBOX_START_HERE.md', output / 'SANDBOX_START_HERE.md')
        fixed_zip(output / f"quant-sandbox-{manifest['kit_id'][:12]}.zip", {p.name: p for p in output.iterdir() if p.is_file()})
    return {'status': 'ok', 'kit_id': manifest['kit_id'], 'source_revision': revision, 'output_dir': str(output),
            'archives_bytes': sum(a['bytes'] for a in archives), 'runtime_targets': sorted(runtime_targets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--wheels-dir', type=Path, required=True)
    parser.add_argument('--runtime-target', action='append', choices=('cp311', 'cp312'))
    parser.add_argument('--strategy', action='append')
    parser.add_argument('--extra-krx-years', type=int, nargs='*', default=[])
    parser.add_argument('--part-size-mib', type=int, default=32)
    args = parser.parse_args()
    result = build_kit(args.repo_root, args.output_dir, args.wheels_dir, args.runtime_target or ('cp311', 'cp312'),
                       args.strategy, args.extra_krx_years, args.part_size_mib * 1024**2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
