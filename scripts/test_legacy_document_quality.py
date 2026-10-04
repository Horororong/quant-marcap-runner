import unittest
import gzip
import json
from pathlib import Path
try:
    from scripts.legacy_document_quality import inspect_member, empty_parse_status
except ModuleNotFoundError:
    from legacy_document_quality import inspect_member, empty_parse_status


class QualityTests(unittest.TestCase):
    def test_truncated_source_is_not_item_absence(self):
        d = inspect_member(b'<?xml version="1.0" encoding="utf-8"?><DOCUMENT><P>value', "receipt.xml")
        self.assertEqual(empty_parse_status([d]), "SOURCE_GAP")
        self.assertIn("SOURCE_XML_INCOMPLETE_OR_INVALID", d["issues"])

    def test_replacement_characters_are_unrecoverable_source_damage(self):
        d = inspect_member('<DOCUMENT><P>\ufffd</P></DOCUMENT>'.encode(), "receipt.xml")
        self.assertEqual(d["replacement_characters"], 1)
        self.assertEqual(empty_parse_status([d]), "SOURCE_GAP")

    def test_clean_absent_item_remains_no_metrics(self):
        d = inspect_member(b'<DOCUMENT><P>no financial table</P></DOCUMENT>', "receipt.xml")
        self.assertEqual(empty_parse_status([d]), "NO_METRICS")

    def test_valid_financial_source_is_not_quarantined(self):
        d = inspect_member('<DOCUMENT><TABLE><TR><TD>매출액</TD><TD>0</TD></TR></TABLE></DOCUMENT>'.encode(), "receipt.xml")
        self.assertEqual(d["issues"], [])

    def test_invalid_declared_encoding_is_explicit_gap(self):
        d = inspect_member(b'<?xml version="1.0" encoding="unknown-encoding"?><DOCUMENT/>', "receipt.xml")
        self.assertEqual(d["issues"], ["SOURCE_ENCODING_INVALID"])

    def test_actual_absent_consolidated_scope_is_not_recovered_from_ofs(self):
        try:
            from scripts.legacy_viewer_source import adapt_viewer
        except ModuleNotFoundError:
            from legacy_viewer_source import adapt_viewer
        root = Path(__file__).resolve().parents[1] / "tests/fixtures/legacy_dart/viewer_primary"
        manifest = json.loads((root / "manifest.json").read_text())
        item = next(r for r in manifest["records"] if r["file"] == "viewer-section-20000814000085-3564.html.gz")
        body = gzip.decompress((root / item["file"]).read_bytes())
        self.assertIn("연결재무제표 작성 의무가 없으므로 해당사항이 없습니다", body.decode())
        result = adapt_viewer(body, item["capture"], item["request"])
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["pit_ready"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
