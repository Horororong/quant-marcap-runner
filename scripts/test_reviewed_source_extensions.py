import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_reviewed_financial_batch import run


class ReviewExtensionBoundaries(unittest.TestCase):
    def fixture(self, root):
        catalog = root / 'data/financials/legacy_2000_2014/legacy_filings.csv.gz'
        catalog.parent.mkdir(parents=True)
        pd.DataFrame([dict(rcept_no='20100331000001', corp_code='00000001', stock_code='000001', rcept_dt='2010-03-31')]).to_csv(catalog, index=False)
        return dict(receipt='20100331000001', metric='equity', semantic_verdict='PASS',
                    source_member='20100331000001.xml', source_member_sha256='a'*64,
                    source_archive_sha256='b'*64, period_start='', period_end='2009-12-31',
                    measurement_basis='instant', scope='OFS', statement='BS',
                    reference_unit='원', reference_unit_multiplier='1', candidate_amount_krw='100',
                    table=1, row=2, current_physical_column=1, period_current_comparative='PASS',
                    scope_heading='PASS', unit_sign='PASS', account_definition='PASS')

    def test_new_increment_stages_without_loading_old_defaults_or_granting_PIT(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); row = self.fixture(root); source = root / 'review.json'
            source.write_text(json.dumps(dict(rows=[row])))
            with contextlib.redirect_stdout(io.StringIO()):
                run(root, root / 'out', [source], extension_only=True)
            result = json.loads((root / 'out/SUMMARY.json').read_text())
            self.assertEqual(result['candidate_rows'], 1)
            self.assertEqual(result['canonical_preview_exact'], 1)
            self.assertEqual(result['source_ready_rows'], 0)

    def test_asserted_PASS_without_period_proof_cannot_enter_preview(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); row = self.fixture(root); row.pop('period_current_comparative')
            source = root / 'review.json'; source.write_text(json.dumps(dict(rows=[row])))
            with contextlib.redirect_stdout(io.StringIO()):
                run(root, root / 'out', [source], extension_only=True)
            result = json.loads((root / 'out/SUMMARY.json').read_text())
            self.assertEqual(result['candidate_rows'], 0)
            self.assertEqual(result['held_rows'], 1)

    def test_extension_only_cannot_silently_fall_back_to_earlier_ledgers(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'SOURCE_REVIEW_LEDGER_REQUIRED'):
                run(root, root / 'out', extension_only=True)


if __name__ == '__main__':
    unittest.main()
