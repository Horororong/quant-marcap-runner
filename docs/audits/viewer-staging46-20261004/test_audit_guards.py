"""Failure boundaries for the independent primary-cell audit, using fixed sources."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("independent_remaining_audit", HERE / "verify_remaining_cells.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditGuards(unittest.TestCase):
    def evidence_copy(self, destination):
        for name in ("SAMPLE_PLAN.json", "EXPECTED_PRIMARY_CELLS.json", "PRIMARY_CELL_EVIDENCE.json"):
            (destination / name).write_bytes((HERE / name).read_bytes())

    def change(self, destination, name, function):
        value = json.loads((destination / name).read_text())
        function(value)
        (destination / name).write_text(json.dumps(value, ensure_ascii=False) + "\n")

    def test_complete_primary_population_and_measurement_limits(self):
        summary, rows, provenance = module.audit()
        self.assertEqual(summary["numeric_matches"], 46)
        self.assertEqual(summary["source_contract_matches"], 46)
        self.assertEqual({r["sample_id"] for r in rows if r["semantic_qualification"]},
                         {"R008", "R026", "R034", "R037", "R042", "R044"})
        self.assertEqual(next(r for r in rows if r["sample_id"] == "R018")["source_amount_krw"], "-112165454689")
        self.assertTrue(provenance["inputs_unchanged"])
        self.assertTrue(all(r["actual_filing_date"] is None and r["strategy_usable_date"] is None and not r["pit_ready"] for r in rows))

    def test_changed_manual_token_disagrees_with_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(source_token="7,499,733,959"))
            with self.assertRaisesRegex(ValueError, "manual account/token"):
                module.audit(evidence_dir=copied)

    def test_wrong_previous_numeric_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(source_current_columns=[2]))
            with self.assertRaisesRegex(ValueError, "current numeric columns"):
                module.audit(evidence_dir=copied)

    def test_wrong_period_end_is_rejected_by_original_header(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(source_period_end="2000-03-31"))
            with self.assertRaisesRegex(ValueError, "quarter/annual source span"):
                module.audit(evidence_dir=copied)

    def test_consolidated_heading_cannot_supply_separate_values(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "PRIMARY_CELL_EVIDENCE.json", lambda v: v["sources"]["20000809000052"]["capture"].update(heading="4.연결재무제표"))
            with self.assertRaisesRegex(ValueError, "OFS heading"):
                module.audit(evidence_dir=copied)

    def test_unknown_unit_is_never_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(source_unit=""))
            with self.assertRaisesRegex(ValueError, "manual source unit"):
                module.audit(evidence_dir=copied)

    def test_quarter_span_cannot_be_relabelled_as_annual(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(source_period_kind="FY"))
            with self.assertRaisesRegex(ValueError, "quarter/annual"):
                module.audit(evidence_dir=copied)

    def test_changed_literal_span_cannot_pass_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "PRIMARY_CELL_EVIDENCE.json", lambda v: v["sources"]["20000809000052"]["cells"]["1/1/1"].update(start_character=1))
            with self.assertRaisesRegex(ValueError, "literal span"):
                module.audit(evidence_dir=copied)

    def test_changed_selection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v["records"][0].update(metric="bonds_payable"))
            with self.assertRaisesRegex(ValueError, "sample identity"):
                module.audit(evidence_dir=copied)

    def test_changed_staging_amount_is_compared_to_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)
            self.evidence_copy(copied)
            staging = json.loads((module.ROOT / "docs/audits/viewer-line-alignment-20261004/replay/source_replay.json").read_text())
            row = next(r for c in staging for r in c["rows"] if r["rcept_no"] == "20000809000052" and r["metric"] == "cash_and_equivalents")
            row["amount_krw"] += 1
            path = copied / "changed-staging.json"
            path.write_text(json.dumps(staging, ensure_ascii=False) + "\n")
            self.change(copied, "SAMPLE_PLAN.json", lambda v: v.update(staging_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            self.change(copied, "EXPECTED_PRIMARY_CELLS.json", lambda v: v.update(sample_plan_sha256=hashlib.sha256((copied / "SAMPLE_PLAN.json").read_bytes()).hexdigest()))
            summary, rows, _ = module.audit(evidence_dir=copied, staging_path=path)
            self.assertEqual(summary["results"]["MISMATCH"], 1)
            self.assertEqual(next(r for r in rows if r["sample_id"] == "R001")["result"], "MISMATCH")

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            marker = destination / "checkpoint"
            marker.write_text("keep")
            result = subprocess.run([sys.executable, str(HERE / "verify_remaining_cells.py"), "--output-dir", directory],
                                    text=True,capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("preserve existing audit", result.stderr)
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
