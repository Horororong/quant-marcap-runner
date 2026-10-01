"""Independent Git fixtures verify reuse, real history growth and scope boundaries."""
from datetime import datetime, timezone, timedelta
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from git_storage_snapshot import snapshot, growth


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'; self.root.mkdir()
        self.git('init', '-q'); self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@example.test')
        self.path = self.root/'data/financials/recent_batches/배치 file.csv.gz'
        self.path.parent.mkdir(parents=True)
        self.first = gzip.compress(b'amount\n100\n', mtime=0); self.path.write_bytes(self.first)
        self.git('add', '.'); self.git('commit', '-qm', 'first')
        self.now = datetime(2026,10,1,tzinfo=timezone.utc)

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,text=True).strip()

    def test_reuse_vs_changed_blob_and_no_mutation(self):
        baseline = snapshot(self.root, now=self.now)
        self.assertEqual(baseline['head_bytes'], len(self.first))
        self.assertEqual(baseline['history_unique_blobs'], 1)
        self.assertEqual(baseline['history_by_category']['dart_recent']['bytes'],len(self.first))
        self.assertIn('배치 file', baseline['largest_head_files'][0]['path'])
        self.git('commit','--allow-empty','-qm','same content')
        repeated = snapshot(self.root, now=self.now + timedelta(days=1))
        self.assertEqual(growth(self.root,repeated,baseline)['history_logical_blob_bytes_delta'],0)
        second = gzip.compress(b'amount\n101\n',mtime=0);self.path.write_bytes(second)
        self.git('add','.');self.git('commit','-qm','actual amount change')
        current = snapshot(self.root, now=self.now + timedelta(days=7))
        difference = growth(self.root,current,baseline)
        self.assertEqual(current['head_bytes'], len(second))
        self.assertEqual(current['history_logical_blob_bytes'], len(self.first) + len(second))
        self.assertEqual(difference['history_logical_blob_bytes_delta'],len(second))
        self.assertEqual(difference['history_unique_blobs_delta'],1)
        self.assertEqual(difference['elapsed_days'],7)
        self.assertEqual(self.git('status','--porcelain'),'')
        self.assertEqual(self.path.read_bytes(),second)

    def test_other_branch_does_not_inflate_main_history(self):
        base=self.git('rev-parse','HEAD');self.git('switch','-qc','other')
        p=self.root/'extra.bin';p.write_bytes(b'other branch'*100)
        self.git('add','.');self.git('commit','-qm','other data')
        current=snapshot(self.root,ref=base,now=self.now)
        self.assertEqual(current['history_unique_blobs'],1)
        self.assertEqual(current['history_logical_blob_bytes'],len(self.first))

    def test_reject_shallow_history_and_foreign_baseline(self):
        clone=self.root.parent/'shallow'
        subprocess.run(['git','clone','-q','--depth','1',self.root.as_uri(),str(clone)],check=True)
        with self.assertRaisesRegex(ValueError,'Full history'):snapshot(clone)
        original=snapshot(self.root,now=self.now)
        self.git('switch','--orphan','foreign')
        (self.root/'other.txt').write_text('different root');self.git('add','other.txt')
        self.git('commit','-qm','foreign')
        with self.assertRaisesRegex(ValueError,'ancestor'):
            growth(self.root,snapshot(self.root,now=self.now),original)

    def test_reject_backwards_observation(self):
        original=snapshot(self.root,now=self.now)
        with self.assertRaisesRegex(ValueError,'predates'):
            growth(self.root,snapshot(self.root,now=self.now-timedelta(days=1)),original)


if __name__ == '__main__': unittest.main(verbosity=2)
