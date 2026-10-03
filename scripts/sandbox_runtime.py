from __future__ import annotations

"""Verify a frozen offline kit, use the checked runner, export verified results."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import zipfile

# -I deliberately ignores ambient PYTHONPATH and third-party user packages.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox_bootstrap import (canonical_bytes, check_environment, hash_file, load_manifest,
                               runtime_key, verify_inventory, verify_file, safe_relative,
                               KitEnvironmentError, KitIntegrityError)
ROOT = Path(__file__).resolve().parents[1]


def verify_kit(root, *, data=True):
    manifest = load_manifest(root / 'kit_manifest.json')
    key = runtime_key()
    if key not in manifest['runtime_targets']:
        raise KitEnvironmentError(f'kit has no runtime target: {key}')
    packages = check_environment(manifest['runtime_targets'][key])
    verify_inventory(root, manifest, ('code', 'data') if data else ('code',))
    from execution_contract import DSL_MACHINE_CONTRACT_VERSION, EXECUTION_ENGINE_VERSION, PERFORMANCE_TEMPLATE_VERSION, REQUESTED_REPORT_CONTRACT_VERSION
    from factor_registry import FACTOR_REGISTRY_VERSION
    for name, actual in [('dsl_machine_contract_version', DSL_MACHINE_CONTRACT_VERSION),
                         ('execution_engine_version', EXECUTION_ENGINE_VERSION),
                         ('performance_template_version', PERFORMANCE_TEMPLATE_VERSION),
                         ('requested_report_contract_version', REQUESTED_REPORT_CONTRACT_VERSION),
                         ('factor_registry_version', FACTOR_REGISTRY_VERSION)]:
        if manifest['versions'][name] != actual:
            raise KitIntegrityError(f'contract mismatch: {name}')
    return manifest, packages


def published_files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*') if p.is_file()
            and not any(part.startswith('_') or part == '.venv' for part in p.relative_to(root).parts)
            and p.name not in {'sandbox_execution_manifest.json', 'run_status.json'}}


def run_in_kit(root, strategy, output=None, *, postprocess=True, report_periods=None):
    root, strategy = Path(root).resolve(), Path(strategy).resolve()
    manifest, packages = verify_kit(root, data=False)
    from strategy_dsl import load_strategy_spec
    from strategy_dsl_run import run_checked_strategy
    with tempfile.TemporaryDirectory(prefix='quant-sandbox-input-') as temporary:
        frozen = Path(temporary) / 'strategy.json'
        frozen.write_bytes(strategy.read_bytes())
        data_verified = False
        try:
            load_strategy_spec(frozen)
        except (ValueError, KeyError, TypeError):
            pass  # Shared checked runner persists the exact input capability_gap.
        else:
            verify_inventory(root, manifest)
            data_verified = True
        result = run_checked_strategy(frozen, root, output, postprocess=postprocess, report_periods=report_periods)
    out = Path(result['output_dir'])
    result['input_path'] = str(strategy)
    result['kit_id'] = manifest['kit_id']
    result['sandbox_manifest'] = 'sandbox_execution_manifest.json'
    shutil.copyfile(root / 'kit_manifest.json', out / 'kit_manifest.json')
    # Include the final status in the protected export inventory, avoiding a
    # circular checksum between status and execution manifest.
    (out / 'run_status.json').write_bytes(canonical_bytes(result) + b'\n')
    outputs = [{'path': name, 'bytes': path.stat().st_size, 'sha256': hash_file(path)}
               for name, path in sorted({**published_files(out), 'run_status.json': out / 'run_status.json'}.items())]
    execution = {'kit_id': manifest['kit_id'], 'source_revision': manifest['source_revision'],
                 'versions': manifest['versions'], 'python': platform.python_version(),
                 'platform': platform.platform(), 'packages': packages,
                 'strategy_fingerprint': result['strategy_fingerprint'], 'status': result['status'],
                 'nav_ready': result['nav_ready'], 'report_ready': result['report_ready'],
                 'data_integrity_verified': data_verified, 'files': outputs}
    (out / 'sandbox_execution_manifest.json').write_bytes(canonical_bytes(execution) + b'\n')
    return result


def export_run(run_dir, output):
    run_dir, output = Path(run_dir).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'export output must be new: {output}')
    if output.is_relative_to(run_dir):
        raise ValueError('export ZIP must be outside the result directory')
    execution = json.loads((run_dir / 'sandbox_execution_manifest.json').read_text())
    status = json.loads((run_dir / 'run_status.json').read_text())
    kit = load_manifest(run_dir / 'kit_manifest.json')
    if status['status'] == 'running' or execution['kit_id'] != kit['kit_id'] or status['kit_id'] != kit['kit_id']:
        raise KitIntegrityError('unfinished run or kit identity mismatch')
    if any(execution[key] != status[key] for key in ('status', 'nav_ready', 'report_ready', 'strategy_fingerprint')):
        raise KitIntegrityError('run status no longer matches the recorded execution')
    files = {}
    for entry in execution['files']:
        verify_file(run_dir, entry)
        if entry['path'] in files:
            raise KitIntegrityError('duplicate result inventory')
        files[entry['path']] = run_dir / entry['path']
    expected = set(published_files(run_dir)) | {'run_status.json'}
    if files.keys() != expected:
        raise KitIntegrityError('result inventory changed after execution')
    files['sandbox_execution_manifest.json'] = run_dir / 'sandbox_execution_manifest.json'
    # Standard library only. Do not import the networked builder into the kit.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            safe_relative(name)
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open('rb') as src, archive.open(info, 'w', force_zip64=True) as dst:
                shutil.copyfileobj(src, dst)
    return {'status': status['status'], 'nav_ready': status['nav_ready'], 'report_ready': status['report_ready'],
            'path': str(output), 'sha256': hash_file(output), 'bytes': output.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    run = sub.add_parser('run')
    run.add_argument('strategy', type=Path)
    run.add_argument('--output-dir', type=Path)
    run.add_argument('--execution-only', action='store_true')
    run.add_argument('--report-periods', type=Path)
    export = sub.add_parser('export')
    export.add_argument('run_dir', type=Path)
    export.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            if args.command == 'verify':
                manifest, packages = verify_kit(ROOT)
                result = {'status': 'ok', 'kit_id': manifest['kit_id'], 'source_revision': manifest['source_revision'],
                          'runtime': runtime_key(), 'packages': packages, 'coverage': manifest['coverage']}
            elif args.command == 'run':
                result = run_in_kit(ROOT, args.strategy, args.output_dir, postprocess=not args.execution_only, report_periods=args.report_periods)
            else:
                result = export_run(args.run_dir, args.output)
        if log.getvalue():
            print(log.getvalue(), file=sys.stderr, end='')
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'failed', 'phase': 'kit', 'error': {'type': type(exc).__name__, 'message': str(exc)}}))
        raise SystemExit(4)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == 'run':
        from strategy_dsl_run import exit_code_for_run
        raise SystemExit(exit_code_for_run(result))


if __name__ == '__main__':
    main()
