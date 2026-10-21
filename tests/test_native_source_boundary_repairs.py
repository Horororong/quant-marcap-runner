"""Source-derived boundaries; no receipts, APIs, clocks or permissive fallbacks."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.legacy_native_financials import decimal_amount, parse_native, select_verified


def statement(citation='연결재무제표에 대한 주석 참조', zone='다. 연결재무제표',
              unit='원', end='2009.12.31', amount='3,507,674,422'):
    return f'''<DOCUMENT><COVER><P>사업보고서</P>
    사업연도2009.01.01부터2009.12.31까지</COVER><P>{zone}</P>
    <P>"{citation}"</P><P>연결손익계산서</P>
    <TABLE><TR><TD>제22기2009.01.01부터{end}까지</TD></TR>
    <TR><TD>제21기2008.01.01부터2008.12.31까지</TD></TR>
    <TR><TD>단위:{unit}</TD></TR></TABLE>
    <TABLE><TR><TH>과목</TH><TH COLSPAN="2">제22(당)기</TH>
    <TH COLSPAN="2">제21(전)기</TH></TR>
    <TR><TD>매출액</TD><TD></TD><TD>{amount}</TD><TD></TD><TD>9,999</TD></TR>
    </TABLE></DOCUMENT>'''


class NoteReferenceBoundary(unittest.TestCase):
    def selected(self, **kwargs):
        return select_verified(parse_native(statement(**kwargs))['candidates'])

    def test_citation_inside_primary_section_preserves_current_source_contract(self):
        for citation in ['연결재무제표에 대한 주석 참조', '재무제표에 대한 주석 참조']:
            with self.subTest(citation=citation):
                rows = self.selected(citation=citation)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row['scope'], 'CFS')
                self.assertEqual(row['statement'], 'IS')
                self.assertEqual(row['amount_krw'], '3507674422')
                self.assertEqual(row['value_col'], 2)
                self.assertEqual(row['period_start'], '2009-01-01')
                self.assertEqual(row['period_end'], '2009-12-31')
                self.assertFalse(row['backtest_eligible'])
                self.assertEqual(row['availability_status'], 'UNVERIFIED')

    def test_citation_never_opens_an_unproved_or_excluded_section(self):
        for zone in ['', '주석', '다. 연결재무제표 주석', '부문별재무현황',
                     '다. 연결재무제표 사업부문별재무', '다. 연결재무제표 합병전후']:
            with self.subTest(zone=zone):
                self.assertEqual(self.selected(zone=zone), [])

    def test_real_note_entry_after_citation_still_closes(self):
        for citation in ['연결재무제표에 대한 주석 참조 주석',
                         '주석 연결재무제표에 대한 주석 참조',
                         '연결재무제표에 대한 주석 참조 부문별재무현황']:
            with self.subTest(citation=citation):
                self.assertEqual(self.selected(citation=citation), [])

    def test_current_period_and_unit_must_remain_proved(self):
        for kwargs in [{'unit': ''}, {'end': '2008.12.31'}, {'amount': ''},
                       {'amount': '-'}, {'amount': '3,507,674,422 9,999'}]:
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.selected(**kwargs), [])

    def test_contradictory_current_amounts_are_not_selected(self):
        text = statement().replace('<TD></TD><TD>3,507,674,422</TD>',
                                   '<TD>123</TD><TD>3,507,674,422</TD>')
        self.assertEqual(select_verified(parse_native(text)['candidates']), [])


class NativeBreakDecoration(unittest.TestCase):
    def test_one_scalar_then_native_linebreak_and_terminal_rule(self):
        for token, expected in [('4,877,276,061&cr;=============', '4877276061'),
                                ('0&cr;__', '0'), ('(1,234)&cr;===', '-1234')]:
            with self.subTest(token=token):
                self.assertEqual(decimal_amount(token), Decimal(expected))

    def test_native_entity_does_not_join_or_guess_numeric_boundaries(self):
        for token in ['1&cr;2', '1&cr;2&cr;===', '1 2&cr;===',
                      '12,34&cr;===', '1&cr;=2', '&cr;1===',
                      '1&cr;=', '1&cr;===2', '1&cr;=== (주2)',
                      '1%&cr;===', '-&cr;===', '&cr;===',
                      '1&cr;===&cr;2', '1&unknown;===']:
            with self.subTest(token=token):
                self.assertIsNone(decimal_amount(token))

    def test_parsed_cell_keeps_original_token_and_records_normalization(self):
        text = statement(citation='').replace('3,507,674,422',
                                             '4,877,276,061&cr;=============')
        rows = select_verified(parse_native(text)['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['amount_krw'], '4877276061')
        self.assertEqual(rows[0]['raw_amount'], '4,877,276,061&cr;=============')
        self.assertEqual(rows[0]['numeric_normalization'], 'native_linebreak_terminal_underline')
        self.assertFalse(rows[0]['backtest_eligible'])


class ApprovalBoundary(unittest.TestCase):
    def test_old_approved_collection_contract_rejects_new_parser(self):
        import json
        from datetime import datetime, timezone
        from scripts.financial_limited_resume import check_gate, initial
        config = json.loads((Path(__file__).resolve().parents[1] /
                             'config/financial_limited_resume_v1.json').read_text())
        state = initial()
        before = json.dumps(state, sort_keys=True)
        self.assertEqual(config['parser_version'], 'legacy-v9.2-statement-boundary-guard')
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED_PARSER_OR_DIAGNOSTIC_VERSION'):
            check_gate(config, state, datetime(2026, 10, 21, tzinfo=timezone.utc), 'schedule')
        self.assertEqual(json.dumps(state, sort_keys=True), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
