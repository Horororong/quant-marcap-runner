"""Offline regression tests for CI failures and bounded version claims."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

HOME = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HOME / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

V = load('preservation', 'verify_preserved60.py')
A = load('versions', 'audit_versions.py')

class RestoreExitTests(unittest.TestCase):
    def run_gap(self, exception, second=False):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'output'
            archive = Path(folder) / 'fixture.zip'
            with zipfile.ZipFile(archive, 'w'):
                pass
            failures = [archive, exception] if second else exception
            options = {'side_effect': failures}
            with mock.patch.object(sys, 'argv', ['verify', '--output', str(output)]), \
                 mock.patch.object(V, 'fetch', **options) as fetch, \
                 mock.patch.object(V, 'verify_originals', return_value=60), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = V.main()
            return code, json.loads((output / 'verification.json').read_text()), fetch.call_count

    def test_http_restore_gap_is_unverified_and_nonzero_without_retry(self):
        code, result, calls = self.run_gap(V.RestoreGap('ARTIFACT_HTTP_FAILURE', 503))
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'UNVERIFIED')
        self.assertEqual(result['original60'], 'UNVERIFIED')
        self.assertEqual(result['restore_error']['http_status'], 503)
        self.assertEqual((calls, result['requests'], result['restore_error']['retries']), (1, 1, 0))

    def test_transport_gap_is_unverified_and_nonzero(self):
        code, result, calls = self.run_gap(V.RestoreGap('ARTIFACT_TRANSPORT_FAILURE'))
        self.assertEqual((code, result['status'], calls), (2, 'UNVERIFIED', 1))
        self.assertEqual(result['investment_approved'], 0)

    def test_second_restore_gap_preserves_partial_result_and_fails(self):
        code, result, calls = self.run_gap(V.RestoreGap('ARTIFACT_HTTP_FAILURE', 410), second=True)
        self.assertEqual((code, result['status'], calls), (2, 'UNVERIFIED', 2))
        self.assertEqual(result['original60'], 'PASS')
        self.assertEqual(result['replay60'], 'UNVERIFIED')
        self.assertEqual(result['protected518'], 'UNVERIFIED')
        self.assertEqual(result['core64'], 'UNVERIFIED')

    def test_hash_failure_remains_fail_exit_one(self):
        code, result, calls = self.run_gap(AssertionError('fixture hash mismatch'))
        self.assertEqual((code, result['status'], calls), (1, 'FAIL', 1))

    def test_missing_auth_actual_cli_exit_is_nonzero_and_diagnostic_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'output'
            env = {k: v for k, v in os.environ.items() if k != 'GH_TOKEN'}
            run = subprocess.run([sys.executable, '-I', str(HOME / 'verify_preserved60.py'),
                                  '--output', str(output)], env=env, capture_output=True, text=True)
            result = json.loads((output / 'verification.json').read_text())
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertEqual(result['status'], 'UNVERIFIED')
            self.assertEqual(result['restore_error']['kind'], 'GITHUB_ACTIONS_TOKEN_MISSING')

    def test_verified_local_path_still_exits_zero_without_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'output'
            archive = Path(folder) / 'fixture.zip'
            with zipfile.ZipFile(archive, 'w'):
                pass
            argv = ['verify', '--output', str(output), '--local-originals', str(archive),
                    '--local-replays', str(archive)]
            with mock.patch.object(sys, 'argv', argv), \
                 mock.patch.object(V, 'fetch', side_effect=AssertionError('unexpected network')) as fetch, \
                 mock.patch.object(V, 'verify_originals', return_value=60), \
                 mock.patch.object(V, 'verify_replays', return_value={'fixture': True}), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = V.main()
            result = json.loads((output / 'verification.json').read_text())
            self.assertEqual((code, result['status'], result['requests']), (0, 'PASS', 0))
            fetch.assert_not_called()

class VersionScopeTests(unittest.TestCase):
    root = {'corp_code': '12345678', 'period_start': '2007-01-01',
            'period_end': '2007-06-30', 'document_name': 'half-year',
            'receipt_date': '2007-08-14', 'rcept_no': '20070814000001',
            'is_correction': False, 'official_title': 'half-year',
            'relationship_grade': 'CERTIFIED'}
    correction = {**root, 'rcept_no': '20070814000002', 'is_correction': True,
                  'initial_date': '2007-08-14', 'root_receipt': root['rcept_no']}

    def test_explicit_root_still_certified_in_same_accounting_period(self):
        self.assertEqual(A.certify_root(self.correction, [self.root]),
                         ('CERTIFIED', self.root['rcept_no']))

    def test_same_end_different_start_is_not_a_certified_root(self):
        other = {**self.root, 'period_start': '2007-04-01'}
        self.assertEqual(A.certify_root(self.correction, [other]), ('CANDIDATE', ''))

    def test_missing_period_start_blocks_root_certification(self):
        unknown = {k: v for k, v in self.correction.items() if k != 'period_start'}
        self.assertEqual(A.certify_root(unknown, [self.root]), ('CANDIDATE', ''))

    def test_root_reference_does_not_certify_immediate_predecessor_or_full_chain(self):
        edges, full_chain = A.version_scope([self.correction, self.root])
        self.assertEqual(edges[0]['grade'], 'CANDIDATE')
        self.assertEqual(full_chain, 'UNVERIFIED')

    def test_single_original_is_not_proof_of_no_corrections(self):
        self.assertEqual(A.version_scope([self.root]), ([], 'UNVERIFIED'))

    def test_actual_preserved_families_have_no_adjacency_or_completeness_proof(self):
        original = json.loads((HOME / 'stage6_version_chains.json').read_text())
        for sample in original['samples']:
            edges, full_chain = A.version_scope(sample['documents'])
            self.assertEqual(full_chain, 'UNVERIFIED', sample['sample_id'])
            self.assertTrue(all(edge['grade'] == 'CANDIDATE' for edge in edges))

if __name__ == '__main__':
    unittest.main(verbosity=2)
