"""Offline distribution failure boundaries; tiny committed fixtures, no network."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import build_sandbox_kit as builder
import sandbox_bootstrap as bootstrap
import sandbox_runtime as runtime


class KitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.wheels = self.base / 'wheels/cp312'
        self.wheels.mkdir(parents=True)
        wheel = self.wheels / 'pip-25.0.1-py3-none-any.whl'
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('pip-25.0.1.dist-info/METADATA', 'Name: pip\nVersion: 25.0.1\n')
        files = {
            'scripts/sandbox_runtime.py': '# fixture\n', 'scripts/sandbox_bootstrap.py': '# fixture\n',
            'scripts/strategy_dsl_run.py': '# fixture\n', 'scripts/strategy_dsl_aliases.py': '# fixture\n',
            'scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py': '# fixture\n',
            'SANDBOX_START_HERE.md': 'instructions', 'docs/STRATEGY_DSL.md': 'dsl',
            'docs/STRATEGY_DSL_RUN.md': 'run', 'docs/CANONICAL_PERFORMANCE.md': 'current',
            'config/strategy_dsl_schema_v1.json': '{}',
            'config/strategy_dsl_capabilities_v1.json': '{"dsl_machine_contract_version":"21"}',
            'config/kr_corporate_actions.csv': 'code,event\n', 'config/kr_corporate_action_gaps.json': '{}',
            'config/strategies/fixture.json': '{}', 'data/source.csv': 'Code,Date\n000001,2020-01-01\n',
            'config/sandbox/requirements-cp312-linux-x86_64.lock':
                f'pip==25.0.1 --hash=sha256:{bootstrap.hash_file(wheel)}\n',
            '.env': 'must-not-be-packaged', 'results/private.json': 'must-not-be-packaged',
        }
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        for args in [('init', '-q'), ('add', '.'), ('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)
        self.source_selector = builder.selected_sources
        self.selection = patch.object(builder, 'selected_sources', return_value=({'data/source.csv'}, {'examples': []}))
        self.selection.start()
        self.addCleanup(self.selection.stop)
        self.key = patch.object(bootstrap, 'runtime_key', return_value='cp312-linux-x86_64')
        self.key.start()
        self.addCleanup(self.key.stop)
        self.output = self.base / 'kit'
        self.build(self.output)

    def build(self, output):
        return builder.build_kit(self.root, output, self.base / 'wheels', targets=('cp312',),
                                 strategies=['config/strategies/fixture.json'], part_bytes=96)

    def assemble(self):
        destination = self.base / 'installed'
        manifest, _ = bootstrap.assemble_bundle(self.output, destination)
        return destination, manifest

    def test_repeated_build_is_byte_identical_without_secrets(self):
        other = self.base / 'other'
        self.build(other)
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir()}, {p.name: p.read_bytes() for p in other.iterdir()})
        manifest = bootstrap.load_manifest(self.output / 'kit_manifest.json')
        self.assertNotIn('.env', [p['path'] for p in manifest['files']])
        self.assertNotIn('results/private.json', [p['path'] for p in manifest['files']])
        self.assertEqual((self.root / 'data/source.csv').read_text(), 'Code,Date\n000001,2020-01-01\n')

    def test_roundtrip_inventory_and_metadata(self):
        root, manifest = self.assemble()
        bootstrap.verify_inventory(root, manifest, ('code', 'data', 'wheel'))
        data = next(p for p in manifest['files'] if p['kind'] == 'data')
        self.assertEqual(data['rows'], 1)
        self.assertEqual(data['columns'], ['Code', 'Date'])

    def test_corrupt_part_blocks_before_destination(self):
        next(self.output.glob('data.part*')).write_bytes(b'changed')
        with self.assertRaises(bootstrap.KitIntegrityError):
            self.assemble()
        self.assertFalse((self.base / 'installed').exists())

    def test_missing_part_blocks_before_destination(self):
        next(self.output.glob('wheel.part*')).unlink()
        with self.assertRaises(bootstrap.KitIntegrityError):
            self.assemble()
        self.assertFalse((self.base / 'installed').exists())

    def test_no_overwrite_build_or_install(self):
        with self.assertRaises(FileExistsError):
            self.build(self.output)
        self.assemble()
        with self.assertRaises(FileExistsError):
            self.assemble()

    def test_dirty_tree_blocks_build(self):
        (self.root / 'data/source.csv').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'clean committed'):
            self.build(self.base / 'dirty')

    def test_changed_data_and_added_shard_rejected(self):
        root, manifest = self.assemble()
        source = root / 'data/source.csv'
        saved = source.read_bytes()
        source.write_bytes(b'changed')
        with self.assertRaises(bootstrap.KitIntegrityError):
            bootstrap.verify_inventory(root, manifest)
        source.write_bytes(saved)
        (root / 'data/extra.csv').write_text('extra')
        with self.assertRaisesRegex(bootstrap.KitIntegrityError, 'unexpected kit source'):
            bootstrap.verify_inventory(root, manifest)

    def test_symlink_rejected_and_new_dsl_allowed(self):
        root, manifest = self.assemble()
        (root / 'config/strategies/new.json').write_text('{}')
        bootstrap.verify_inventory(root, manifest)
        (root / 'scripts/injected.py').symlink_to(root / 'data/source.csv')
        with self.assertRaisesRegex(bootstrap.KitIntegrityError, 'symlink'):
            bootstrap.verify_inventory(root, manifest)

    def test_paths_rejected(self):
        for name in ('../x', '/x', 'a/../x', 'a//b', './x', 'a\\b', ''):
            with self.subTest(name=name), self.assertRaises(bootstrap.KitIntegrityError):
                bootstrap.safe_relative(name)

    def test_malformed_manifest_and_identity(self):
        path = self.output / 'kit_manifest.json'
        original = json.loads(path.read_text())
        for mutate in (lambda m: m.update(kit_id='0'*64), lambda m: m.update(source_revision='main'),
                       lambda m: m.update(files=[]), lambda m: m['files'].append(m['files'][0]),
                       lambda m: m['files'][0].update(path='../escape'),
                       lambda m: m['runtime_targets']['cp312-linux-x86_64'].update(wheel_paths=['data/source.csv'])):
            value = copy.deepcopy(original)
            mutate(value)
            if value['kit_id'] != '0'*64:
                value['kit_id'] = bootstrap.manifest_id(value)
            path.write_text(json.dumps(value))
            with self.assertRaises(bootstrap.KitIntegrityError):
                bootstrap.load_manifest(path)
        path.write_text('{"kit_id":1,"kit_id":2}')
        with self.assertRaises(bootstrap.KitIntegrityError):
            bootstrap.load_manifest(path)

    def test_wrong_platform_and_package_rejected(self):
        with patch('platform.machine', return_value='arm64'), self.assertRaises(bootstrap.KitEnvironmentError):
            self.key.stop()
            try:
                bootstrap.runtime_key()
            finally:
                self.key.start()
        with patch.object(bootstrap.metadata, 'version', return_value='different'), self.assertRaises(bootstrap.KitEnvironmentError):
            bootstrap.check_environment({'packages': {'pandas': '3.0.6'}})

    def test_invalid_dsl_never_hashes_or_loads_data(self):
        from strategy_dsl_run import run_checked_strategy
        bad = self.base / 'bad.json'
        bad.write_text('{"strategy_id":"bad", "surprise":true}')
        manifest = bootstrap.load_manifest(self.output / 'kit_manifest.json')
        out = self.base / 'bad-run'
        with patch.object(runtime, 'verify_kit', return_value=(manifest, {})), \
             patch.object(runtime, 'verify_inventory', side_effect=AssertionError('data must not be touched')):
            result = runtime.run_in_kit(self.output, bad, out, postprocess=False)
        self.assertEqual(result['status'], 'capability_gap')
        self.assertFalse(result['nav_ready'])
        self.assertFalse((out / 'preflight.json').exists())
        execution = json.loads((out / 'sandbox_execution_manifest.json').read_text())
        self.assertFalse(execution['data_integrity_verified'])
        exported = runtime.export_run(out, self.base / 'failed.zip')
        self.assertEqual(exported['status'], 'capability_gap')
        self.assertFalse(exported['report_ready'])
        with self.assertRaises(FileExistsError):
            runtime.export_run(out, self.base / 'failed.zip')
        (out / 'strategy_input.json').write_text('changed')
        with self.assertRaises(bootstrap.KitIntegrityError):
            runtime.export_run(out, self.base / 'changed.zip')

    def test_actual_trading_signal_selects_partial_month_dart_and_warmup(self):
        history = self.root / 'data/financials/full_history'
        history.mkdir(parents=True)
        for period in ('Q3', 'FY'):
            (history / f'dart_full_2019_{period}_CFS_00000.csv.gz').write_bytes(b'fixture')
        spec = SimpleNamespace(period=SimpleNamespace(start='2020-04-01', end='2020-04-29'),
                               factors=[SimpleNamespace(source='dart')], benchmark=None,
                               rebalance=SimpleNamespace(dart_period_policy='legacy_april_october'),
                               universe=SimpleNamespace(filters=[]))
        audit = {'status': 'ok', 'signal_dates': ['2020-04-29']}
        with patch('strategy_dsl.load_strategy_spec', return_value=spec), \
             patch('strategy_dsl_preflight.preflight_strategy', return_value=audit):
            files, coverage = self.source_selector(self.root, ['config/strategies/fixture.json'])
            self.assertEqual(coverage['dart_periods'], [[2019, 'FY'], [2019, 'Q3']])
            self.assertIn('data/financials/full_history/dart_full_2019_FY_CFS_00000.csv.gz', files)
            spec.factors = [SimpleNamespace(source='technical')]
            _, coverage = self.source_selector(self.root, ['config/strategies/fixture.json'])
            self.assertEqual(coverage['krx_years'], [2018, 2019, 2020])
            spec.benchmark = SimpleNamespace(symbol='KOSDAQ')
            files, _ = self.source_selector(self.root, ['config/strategies/fixture.json'])
            self.assertIn('data/indices/KOSDAQ.csv', files)
            self.assertNotIn('data/indices/KOSPI.csv', files)

    def test_lock_mismatch_and_duplicate_rejected(self):
        wheel = next(self.wheels.glob('*.whl'))
        wheel.write_bytes(b'not a wheel')
        with self.assertRaises(zipfile.BadZipFile):
            builder.locked_wheels(self.wheels, builder.read_lock(self.root / 'config/sandbox/requirements-cp312-linux-x86_64.lock'))
        lock = self.base / 'bad.lock'
        lock.write_text('pandas>=2\n')
        with self.assertRaises(ValueError):
            builder.read_lock(lock)


if __name__ == '__main__':
    unittest.main()
