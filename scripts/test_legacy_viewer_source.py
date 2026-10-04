"""Primary-source regressions plus explicit mutation/failure boundary tests."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

try:
    from scripts.legacy_viewer_source import adapt_viewer, viewer_amount
    from scripts.replay_legacy_viewer_sources import replay, write_once, FIXTURES
    from scripts.legacy_financial_fields import parse_number
    from scripts.recheck_legacy_primary_audit import materialize_sources
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from legacy_viewer_source import adapt_viewer, viewer_amount
    from replay_legacy_viewer_sources import replay, write_once, FIXTURES
    from legacy_financial_fields import parse_number
    from recheck_legacy_primary_audit import materialize_sources


def synthetic(html):
    """Mutations are synthetic boundary tests, never primary financial evidence."""
    body = html.encode()
    capture = dict(rcept_no="20010103000052", eleId="3618", heading="3. 재무제표", http_status=200,
                   url="https://dart.fss.or.kr/report/viewer.do?rcpNo=20010103000052&dcmNo=86557&eleId=3618&offset=1&length=100&dtd=dart2.dtd",
                   body_bytes=len(body), body_sha256=hashlib.sha256(body).hexdigest(), source_encoding="utf-8")
    return body, capture


def statement(current="10,000", prior="20,000", dates="제38기3분기 2000.1.1부터2000.9.30까지", unit="원",
              columns="<th>과목</th><th>제38기3분기</th><th>제37기연간</th>", row=None):
    return ("<h2>3. 재무제표</h2><h3>손익계산서</h3><table>"
            f"<tr><td>{dates}</td></tr><tr><td>제37기 1999.1.1부터1999.12.31까지</td></tr>"
            f"<tr><td>(단위: {unit})</td></tr></table><table><tr>{columns}</tr>"
            + (row or f"<tr><td>매출액</td><td>{current}</td><td>{prior}</td></tr>") + "</table>")


class ViewerGuardTests(unittest.TestCase):
    request = dict(period_end="2000-09-30", kind="Q3", scope="OFS")

    def parse(self, html, request=None):
        body, cap = synthetic(html)
        return adapt_viewer(body, cap, request or self.request)

    def test_primary_all_49_cells_and_12_bodies(self):
        summary, captures, audited = replay()
        self.assertEqual(summary["results"], {"MATCH": 17, "WITHHELD_LAYOUT_GUARD": 5,
                                            "WITHHELD_PRIOR_PERIOD": 22, "WITHHELD_UNKNOWN_UNIT": 5})
        self.assertEqual(summary["staging_rows"], 63)
        self.assertEqual(summary["unreviewed_staging_rows"], 46)
        self.assertEqual(len(captures), 12)
        self.assertEqual(len(audited), 49)
        self.assertEqual(summary["verified_pit_items"], 0)
        self.assertFalse(summary["financial_quality_complete"])

    def test_primary_previous_annual_ocf_never_becomes_current_quarter(self):
        _, captures, _ = replay()
        for capture in captures:
            self.assertFalse(any(r["metric"] == "ocf" for r in capture["rows"]), capture["file"])
            for row in capture["rows"]:
                self.assertEqual(row["period_end"], capture["request"]["period_end"])
                self.assertIsNone(row["strategy_usable_date"])
                self.assertFalse(row["filing_date_verified"])

    def test_primary_unknown_vitz_unit_cannot_inherit_later_cf_unit(self):
        _, captures, _ = replay()
        item = next(c for c in captures if c["file"].endswith("20000814000085-3439.html.gz"))
        self.assertEqual(item["rows"], [])
        self.assertEqual(sum(g["reason"] == "UNIT_UNPROVEN" for g in item["gaps"]), 2)

    def test_primary_cfs_prior_annual_is_not_current_ofs(self):
        _, captures, _ = replay()
        for item in captures:
            if item["request"]["scope"] == "CFS":
                self.assertEqual(item["rows"], [], item["file"])

    def test_primary_body_sha_detects_corruption(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        item = manifest["records"][0]
        body = gzip.decompress((FIXTURES / item["file"]).read_bytes())
        parsed = adapt_viewer(body + b" ", item["capture"], item["request"])
        self.assertEqual(parsed["gaps"][0]["reason"], "SOURCE_IDENTITY_MISMATCH")
        self.assertFalse(parsed["rows"])

    def test_current_column_is_selected_after_previous_column(self):
        html = statement(columns="<th>과목</th><th>제37기연간</th><th>제38기3분기</th>",
                         row="<tr><td>매출액</td><td>20,000</td><td>10,000</td></tr>")
        self.assertEqual(self.parse(html)["rows"][0]["amount_krw"], 10000)

    def test_missing_current_cell_never_falls_back_to_previous_value(self):
        for value in ("", "-", "—", "누락", "1 (주2)"):
            with self.subTest(value=value):
                self.assertEqual(self.parse(statement(current=value))["rows"], [])

    def test_explicit_zero_remains_a_source_observation(self):
        self.assertEqual(self.parse(statement(current="0"))["rows"][0]["amount_krw"], 0)

    def test_note_column_cannot_be_a_numeric_amount(self):
        html = statement(columns="<th>과목</th><th>주석</th><th>제38기3분기</th><th>제37기연간</th>",
                         row="<tr><td>매출액</td><td>2</td><td>10,000</td><td>20,000</td></tr>")
        self.assertEqual(self.parse(html)["rows"][0]["amount_krw"], 10000)

    def test_colspan_group_requires_one_unambiguous_amount(self):
        cols = "<th>과목</th><th colspan='2'>제38기3분기</th><th>제37기연간</th>"
        good = statement(columns=cols, row="<tr><td>매출액</td><td></td><td>10,000</td><td>20,000</td></tr>")
        bad = statement(columns=cols, row="<tr><td>매출액</td><td>99</td><td>10,000</td><td>20,000</td></tr>")
        self.assertEqual(self.parse(good)["rows"][0]["amount_krw"], 10000)
        self.assertFalse(self.parse(bad)["rows"])

    def test_current_term_or_date_mismatch_is_a_gap(self):
        for html in (statement(dates="제37기3분기 2000.1.1부터2000.9.30까지"),
                     statement(dates="제38기3분기 2000.1.1부터2000.6.30까지"),
                     statement(dates="제38기3분기")):
            self.assertFalse(self.parse(html)["rows"])

    def test_annual_flow_is_not_quarter_even_if_end_matches(self):
        html = statement(dates="제38기3분기 1999.10.1부터2000.9.30까지")
        self.assertFalse(self.parse(html)["rows"])

    def test_generic_quarter_requires_source_date_range_proof(self):
        html = statement(dates="제38기 2000.1.1부터2000.9.30까지", columns="<th>과목</th><th>제38기분기</th><th>제37기연간</th>")
        self.assertEqual(self.parse(html)["rows"][0]["period_kind"], "Q3")
        self.assertFalse(self.parse(html.replace("2000.1.1부터2000.9.30까지", "2000.9.30현재"))["rows"])

    def test_missing_blank_or_unsupported_unit_is_a_gap(self):
        for unit in ("", "달러", "주", "천주"):
            with self.subTest(unit=unit):
                self.assertFalse(self.parse(statement(unit=unit))["rows"])

    def test_explicit_unit_multiplier(self):
        for unit, mult in (("원", 1), ("천원", 1000), ("백만원", 1000000), ("억원", 100000000)):
            self.assertEqual(self.parse(statement(unit=unit))["rows"][0]["amount_krw"], 10000 * mult)

    def test_conflicting_units_and_future_table_unit_do_not_fill(self):
        html = statement().replace("(단위: 원)", "(단위: 원)</td></tr><tr><td>(단위: 천원)")
        self.assertFalse(self.parse(html)["rows"])
        html = statement(unit="") + "<table><tr><td>(단위: 원)</td></tr></table>"
        self.assertFalse(self.parse(html)["rows"])

    def test_scope_requires_matching_route_and_body_heading(self):
        body, cap = synthetic(statement())
        for scope, heading in (("CFS", "3. 재무제표"), ("OFS", "3. 연결재무제표"), ("OFS", "불명")):
            cap["heading"] = heading
            self.assertFalse(adapt_viewer(body, cap, dict(self.request, scope=scope))["rows"])

    def test_contrary_statement_scope_cannot_inherit_ofs(self):
        self.assertFalse(self.parse(statement().replace("<h3>손익계산서", "<h3>연결손익계산서"))["rows"])

    def test_unknown_statement_is_not_inferred_from_account(self):
        self.assertFalse(self.parse(statement().replace("손익계산서", "사업의내용"))["rows"])

    def test_br_empty_lines_are_preserved_without_concatenation(self):
        row = "<tr><td>매출액<br/><br/>당기순이익</td><td>10,000<br/><br/>500</td><td>20,000<br/><br/>600</td></tr>"
        rows = self.parse(statement(row=row))["rows"]
        self.assertEqual({r["metric"]: r["amount_krw"] for r in rows}, {"revenue": 10000, "net_income": 500})

    def test_br_missing_line_is_not_shifted_or_padded(self):
        row = "<tr><td>매출액<br/><br/>당기순이익</td><td>10,000<br/>500</td><td>20,000<br/><br/>600</td></tr>"
        self.assertFalse(self.parse(statement(row=row))["rows"])

    def test_multiple_numeric_tokens_are_rejected(self):
        for token in ("10,000 5,000", "751,637 22,35416,940", "1,234<br/>567", "12,34", "1.5%", "1" + "0" * 309):
            self.assertFalse(self.parse(statement(current=token))["rows"], token)

    def test_source_negative_prefix_triangles_and_loss_labels(self):
        for token in ("(-)5,000", "△5,000", "▲5,000", "Δ5,000", "(-5,000)", "(△5,000)"):
            self.assertEqual(viewer_amount(token), -5000)
        html = statement(row="<tr><td>당기순손실</td><td>5,000</td><td>20,000</td></tr>")
        self.assertEqual(self.parse(html)["rows"][0]["amount_krw"], -5000)

    def test_ambiguous_parentheses_do_not_guess_sign(self):
        self.assertTrue(math.isnan(viewer_amount("(5,000)")))
        self.assertEqual(parse_number("(5,000)"), -5000)  # Native v5 contract unchanged.

    def test_duplicate_current_alias_is_not_resolved_by_priority(self):
        row = "<tr><td>매출액</td><td>10,000</td><td>20,000</td></tr><tr><td>매출</td><td>9,000</td><td>20,000</td></tr>"
        self.assertFalse(self.parse(statement(row=row))["rows"])

    def test_current_unit_date_are_not_inherited_by_following_table(self):
        html = statement() + "<table><tr><th>과목</th><th>제38기3분기</th></tr><tr><td>당기순이익</td><td>500</td></tr></table>"
        self.assertEqual([r["metric"] for r in self.parse(html)["rows"]], ["revenue"])

    def test_first_of_month_and_missing_scope_are_invalid_requests(self):
        for request in (dict(self.request, period_end="2000-09-01"), dict(self.request, scope="")):
            with self.assertRaises(ValueError):
                self.parse(statement(), request)

    def test_nested_tables_and_budget_overflow_are_gaps(self):
        for html in (statement().replace("10,000", "<table><tr><td>10,000</td></tr></table>"),
                     statement() + "<table></table>" * 401):
            self.assertFalse(self.parse(html)["rows"])

    def test_non_dart_or_mismatched_receipt_is_rejected(self):
        body, cap = synthetic(statement())
        for replacement in (cap["url"].replace("dart.fss.or.kr", "example.com"),
                            cap["url"].replace("rcpNo=20010103000052", "rcpNo=20010103000053")):
            self.assertFalse(adapt_viewer(body, dict(cap, url=replacement), self.request)["rows"])

    def test_non_200_or_unknown_encoding_is_a_gap(self):
        body, cap = synthetic(statement())
        for changed in (dict(cap, http_status=403), dict(cap, source_encoding="unknown")):
            self.assertFalse(adapt_viewer(body, changed, self.request)["rows"])

    def test_replay_preserves_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            write_once(path, "first")
            write_once(path, "first")
            with self.assertRaises(ValueError):
                write_once(path, "second")
            self.assertEqual(path.read_text(), "first")

    def test_native_archives_and_viewer_bodies_recover_exact_14_primary_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = materialize_sources(directory)
            self.assertEqual(len(evidence), 14)
            for item in evidence:
                raw = (Path(directory) / item["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["source_sha256"])

    def test_primary_native_sha_chain_matches_preexisting_probe(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "tests/fixtures/legacy_dart/native_primary/manifest.json").read_text())
        for item in manifest["records"]:
            probe = json.loads((root / f"docs/audits/legacy/source_probes/{item['rcept_no']}.json").read_text())
            self.assertEqual(item["document_sha256"], probe["document_sha256"])
            member = next(m for m in probe["members"] if m["member_name"] == item["member_name"])
            self.assertEqual(item["member_sha256"], member["member_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
