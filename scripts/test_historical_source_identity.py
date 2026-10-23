import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from historical_source_identity import assess_identity, source_binding


class IdentityBoundaries(unittest.TestCase):
    def fixture(self):
        raw = ('<COMPANY-NAME AREGCIK="00000001">옛회사</COMPANY-NAME>'
               '<P>당사의 약식 명칭은 새회사다. 변경일 2010년3월26일.</P>').encode()
        identity = dict(corp_code='00000001', rcept_no='20100331000001', stock_code='000001',
                        original_issuer='옛회사', source_member_sha256=hashlib.sha256(raw).hexdigest(), source_archive_sha256='a'*64)
        market = [dict(ISU_CD='000001', ISU_NM='새회사')]
        evidence = dict(date='2010-04-30', source='SYNTHETIC_TEST_ONLY', sha256='b'*64)
        alias = dict(verdict='PASS', binding=source_binding(identity), official_alias='새회사', alias_literal='새회사',
                     source_quote='당사의 약식 명칭은 새회사다.', scope='CURRENT_ISSUER_SELF_IDENTIFICATION',
                     **{'from': '2010-03-26', 'through': '2010-04-30'}, evidence=['SYNTHETIC_TEST_ONLY'])
        return identity, raw, market, evidence, [alias]

    def test_literal_legal_form_only(self):
        i, b, m, e, a = self.fixture(); m[0]['ISU_NM'] = '옛회사(주)'
        out = assess_identity(i, b, m, e, '2010-04-30')
        self.assertEqual(out['verdict'], 'PASS'); self.assertFalse(out['whole_PIT_eligible'])

    def test_current_mapping_or_similar_name_is_not_an_alias(self):
        i, b, m, e, a = self.fixture()
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-30')['verdict'], 'UNVERIFIED')

    def test_reviewed_alias_does_not_certify_intervening_dates(self):
        i, b, m, e, a = self.fixture(); out = assess_identity(i, b, m, e, '2010-04-30', a)
        self.assertEqual(out['verdict'], 'PASS')
        self.assertEqual(out['historical_security_mapping']['from'], '2010-04-30')
        self.assertEqual(out['historical_security_mapping']['through'], '2010-04-30')
        self.assertFalse(out['publication_certified'])

    def test_source_quote_cannot_be_invented(self):
        i, b, m, e, a = self.fixture(); a[0]['source_quote'] = '공식 약칭은 새회사입니다.'
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-30', a)['verdict'], 'UNVERIFIED')

    def test_alias_cannot_be_reused_for_another_issuer(self):
        i, b, m, e, a = self.fixture(); a[0]['binding']['corp_code'] = '00000002'
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-30', a)['verdict'], 'UNVERIFIED')

    def test_bad_hash_or_wrong_official_day_is_refused(self):
        i, b, m, e, a = self.fixture()
        self.assertEqual(assess_identity(i, b+b'X', m, e, '2010-04-30', a)['verdict'], 'UNVERIFIED')
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-01', a)['verdict'], 'UNVERIFIED')

    def test_alias_not_available_before_source_reviewed_change(self):
        i, b, m, e, a = self.fixture(); e['date'] = '2010-03-25'
        self.assertEqual(assess_identity(i, b, m, e, '2010-03-25', a)['verdict'], 'UNVERIFIED')

    def test_duplicate_official_code_or_name_is_refused(self):
        i, b, m, e, a = self.fixture(); m.append(copy.deepcopy(m[0]))
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-30', a)['verdict'], 'UNVERIFIED')
        m[1]['ISU_CD'] = '000002'
        self.assertEqual(assess_identity(i, b, m, e, '2010-04-30', a)['verdict'], 'UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
