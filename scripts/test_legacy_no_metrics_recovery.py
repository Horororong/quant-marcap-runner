import json
from pathlib import Path
import tempfile
import unittest
try:
    from scripts.recover_legacy_no_metrics import run, publication_evidence, ROOT
except ModuleNotFoundError:
    from recover_legacy_no_metrics import run, publication_evidence, ROOT


class RecoveryTests(unittest.TestCase):
    def test_real_five_receipt_checkpoint_resume_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "recovery"
            source = ROOT / "tests/fixtures/legacy_dart/recovery_primary"
            a = run(source, out, 2)
            self.assertEqual((a["processed_receipts"], a["remaining_receipts"]), (2, 3))
            b = run(source, out, 3, True)
            self.assertEqual((b["processed_receipts"], b["staging_rows_recovered"]), (5, 78))
            before = {p.name: p.read_bytes() for p in out.glob("*.json")}
            c = run(source, out, 3, True)
            self.assertEqual(c["processed_this_batch"], 0)
            self.assertEqual(c["production_valid_rows_recovered"], 0)
            self.assertEqual(c["verified_pit_items"], 0)
            self.assertTrue(all((out / p).read_bytes() == body for p, body in before.items()))
            with self.assertRaises(FileExistsError):
                run(source, out, 2)

    def test_changed_native_archive_cannot_recover_or_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sources"; source.mkdir()
            (source / "20000809000052-corrupt.zip").write_bytes(b"corrupt")
            out = Path(temp) / "output"
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                run(source, out, 1)
            self.assertFalse((out / "20000809000052.json").exists())

    def test_missing_viewer_date_is_not_inferred_from_receipt(self):
        r = publication_evidence(b'<select id="family"><option value="rcpNo=20010103000052">report</option></select>', "20010103000052")
        self.assertIsNone(r["displayed_publication_date"])
        self.assertIsNone(r["strategy_usable_date"])
        self.assertFalse(r["pit_ready"])

    def test_visible_date_does_not_certify_original_or_correction_chain(self):
        r = publication_evidence(b'<select id="family"><option value="rcpNo=20010103000052">2001.01.03 report</option></select>', "20010103000052")
        self.assertEqual(r["displayed_publication_date"], "2001-01-03")
        self.assertFalse(r["correction_chain_complete"])
        self.assertIsNone(r["publication_time"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
