"""Recent refresh storage boundaries; software fixtures and real stored DART rows."""
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import update_dart_financials as recent


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.frame = pd.DataFrame([
            {'stock_code': '005930', 'rcept_no': '20240315000001', 'filing_date': '20240315',
             'thstrm_amount': '1,234', 'account_nm': '자본총계', 'optional': 'NA'},
            {'stock_code': '000001', 'rcept_no': '20240814000002', 'filing_date': '20240814',
             'thstrm_amount': '', 'account_nm': '매출액', 'optional': ''},
        ])

    def test_deterministic_gzip_and_exact_values(self):
        a, b = self.base/'a.csv.gz', self.base/'different-name.csv.gz'
        self.assertTrue(recent.atomic_write_if_changed(self.frame, a))
        with patch('time.time', return_value=2_000_000_000):
            self.assertTrue(recent.atomic_write_if_changed(self.frame.iloc[::-1, ::-1], b))
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(a.read_bytes()[4:8], b'\0\0\0\0')
        self.assertFalse(a.read_bytes()[3] & 8, 'FNAME must be absent')
        decoded = list(csv.DictReader(io.StringIO(gzip.decompress(a.read_bytes()).decode('utf-8-sig'))))
        self.assertEqual(sorted(decoded, key=lambda r: r['stock_code']),
                         sorted(self.frame.to_dict('records'), key=lambda r: r['stock_code']))
        before = a.stat().st_mtime_ns
        self.assertFalse(recent.atomic_write_if_changed(self.frame.iloc[::-1], a))
        self.assertEqual(a.stat().st_mtime_ns, before)

    def test_preserve_equivalent_legacy_bytes(self):
        path = self.base/'old.csv.gz'
        with gzip.open(path, 'wb') as f:
            f.write(self.frame.to_csv(index=False).encode('utf-8-sig'))
        old = path.read_bytes()
        self.assertFalse(recent.atomic_write_if_changed(self.frame.iloc[::-1, ::-1], path))
        self.assertEqual(path.read_bytes(), old)
        changed = self.frame.copy()
        changed.loc[0, 'thstrm_amount'] = '1,235'
        self.assertTrue(recent.atomic_write_if_changed(changed, path))
        changed.loc[0, 'filing_date'] = '20240316'
        self.assertTrue(recent.atomic_write_if_changed(changed, path))
        changed['new_source_field'] = 'original'
        self.assertTrue(recent.atomic_write_if_changed(changed, path))

    def test_duplicates_are_preserved(self):
        p = self.base/'duplicates.csv.gz'
        repeated = pd.concat([self.frame, self.frame.iloc[:1]], ignore_index=True)
        recent.atomic_write_if_changed(repeated, p)
        self.assertEqual(len(pd.read_csv(p)), 3)
        self.assertTrue(recent.atomic_write_if_changed(self.frame, p))

    def test_timestamp_only_is_ignored_but_rotation_and_errors_are_not(self):
        p = self.base/'state.csv'
        first = pd.DataFrame([{'next_offset': 300, 'errors': 0, 'updated_at_utc': '2026-10-01'}])
        recent.atomic_write_if_changed(first, p, ignore_columns=('updated_at_utc',))
        old = p.read_bytes()
        first.loc[0, 'updated_at_utc'] = '2026-10-02'
        self.assertFalse(recent.atomic_write_if_changed(first, p, ignore_columns=('updated_at_utc',)))
        self.assertEqual(p.read_bytes(), old)
        first.loc[0, 'next_offset'] = 600
        self.assertTrue(recent.atomic_write_if_changed(first, p, ignore_columns=('updated_at_utc',)))
        first.loc[0, 'errors'] = 1
        self.assertTrue(recent.atomic_write_if_changed(first, p, ignore_columns=('updated_at_utc',)))

    def test_atomic_failure_and_corruption(self):
        p = self.base/'source.csv.gz'
        recent.atomic_write_if_changed(self.frame, p)
        old = p.read_bytes()
        changed = self.frame.copy(); changed.loc[0, 'thstrm_amount'] = '42'
        with patch.object(recent.os, 'replace', side_effect=OSError('publication failure')):
            with self.assertRaises(OSError): recent.atomic_write_if_changed(changed, p)
        self.assertEqual(p.read_bytes(), old)
        self.assertFalse(list(self.base.glob('.pending-*')))
        p.write_bytes(b'broken gzip')
        with self.assertRaises(gzip.BadGzipFile): recent.atomic_write_if_changed(self.frame, p)
        self.assertEqual(p.read_bytes(), b'broken gzip')

    def test_cycles_cover_every_company_and_stop_filename_drift(self):
        for total in (0, 1, 300, 301, 3933):
            start = 0; visited = []; tags = []
            while True:
                positions, following = recent.rotation_positions(total, start, 300)
                visited.extend(positions); tags.append((start, positions[-1] if positions else start))
                start = following
                if start == 0: break
            self.assertEqual(visited, list(range(total)))
            if total == 3933:
                self.assertEqual(len(tags), 14)
                self.assertEqual(tags[-1], (3900, 3932))
                self.assertEqual(recent.rotation_positions(total, 3838, 300), (list(range(3838,3933)), 0))
                self.assertEqual(recent.rotation_positions(total, 0, 300), (list(range(300)), 300))

    def test_main_rerun_no_git_commit_but_fresh_artifact(self):
        financial = self.base/'data/financials'; status = self.base/'data/status'
        financial.mkdir(parents=True); status.mkdir(parents=True)
        report = self.base/'run.json'
        master = pd.DataFrame([{'corp_code': '00000001', 'corp_name': '시험',
                                'stock_code': '000001', 'modify_date': '20260101'}])
        raw = [{'corp_code': '00000001', 'rcept_no': '20240315000001', 'fs_div': 'CFS',
                'sj_div': 'BS', 'account_id': 'Equity', 'account_nm': '자본총계',
                'thstrm_nm': '제1기', 'thstrm_amount': '100'}]
        class Clock:
            day = 1
            @classmethod
            def now(cls, tz=None): return datetime(2026,10,cls.day,tzinfo=tz)
        settings = dict(ROOT=financial, BATCH_DIR=financial/'recent_batches',
                        STATUS_DIR=status, STATE_FILE=status/'dart_rotation_state.csv', API_KEY='fixture')
        with patch.multiple(recent, **settings), patch.object(recent, 'get_corp_codes', return_value=master), \
             patch.object(recent, 'fetch_full_fs', return_value=raw), patch.object(recent, 'datetime', Clock), \
             patch.dict(os.environ, {'DART_REFRESH_REPORT':str(report), 'DART_MAX_COMPANIES':'300'}):
            recent.main()
            env = os.environ.copy(); env.update(GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_SYSTEM='/dev/null')
            def git(*args): return subprocess.check_output(['git',*args],cwd=self.base,env=env,text=True).strip()
            git('init','-q');git('config','user.name','fixture');git('config','user.email','fixture@example.test')
            git('add','data');git('commit','-qm','baseline')
            Clock.day = 2
            recent.main()
            git('add','data')
            self.assertEqual(git('diff','--cached','--name-only'), '')
            heartbeat = json.loads(report.read_text())
            self.assertEqual(heartbeat['changed_paths'], [])
            self.assertTrue(heartbeat['checked_at_utc'].startswith('2026-10-02'))
            self.assertEqual(pd.read_csv(status/'dart_rotation_state.csv').iloc[0]['next_offset'], 0)
            # The API still runs; a real correction must update both source and Git.
            raw[0]['thstrm_amount'] = '101'
            recent.main();git('add','data')
            self.assertIn('recent_batches/', git('diff','--cached','--name-only'))
            self.assertNotIn('fixture', report.read_text())

    def test_missing_key_repeated_run(self):
        status = self.base/'status';status.mkdir()
        with patch.multiple(recent, API_KEY='', STATUS_DIR=status), patch.dict(os.environ, {'DART_REFRESH_REPORT':''}):
            recent.main(); old = (status/'dart_status.csv').read_bytes()
            recent.main(); self.assertEqual((status/'dart_status.csv').read_bytes(), old)

    def test_real_dart_output_determinism_and_legacy_no_rewrite(self):
        files = sorted((ROOT/'data/financials/recent_batches').glob('*.csv.gz'))
        self.assertTrue(files, 'real recent DART fixture required')
        source = next(p for p in files if p.stat().st_size > 4_000_000)
        original = source.read_bytes(); checksum = hashlib.sha256(original).hexdigest()
        frame = pd.read_csv(source, dtype=str, keep_default_na=False, low_memory=False)
        a, b, old = self.base/'real-a.csv.gz', self.base/'real-b.csv.gz', self.base/'legacy.csv.gz'
        old.write_bytes(original)
        self.assertFalse(recent.atomic_write_if_changed(frame, old))
        self.assertEqual(old.read_bytes(), original)
        recent.atomic_write_if_changed(frame, a)
        recent.atomic_write_if_changed(frame.sample(frac=1,random_state=19).iloc[:,::-1], b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(gzip.decompress(a.read_bytes()), recent.canonical_csv(gzip.decompress(original)))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), checksum)
        print(f'REAL DART: {source.name}, {len(frame):,} rows; identical bytes, exact CSV values, source preserved')


if __name__ == '__main__':
    unittest.main(verbosity=2)
