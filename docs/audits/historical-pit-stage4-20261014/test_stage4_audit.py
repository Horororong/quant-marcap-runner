"""Audit-method regressions. Synthetic layouts do not attest real publication."""
import importlib.util, unittest
from pathlib import Path
import xml.etree.ElementTree as ET
spec=importlib.util.spec_from_file_location('stage4_audit',Path(__file__).with_name('run_stage4.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class AuditMethodTests(unittest.TestCase):
    def inspect(self,body):
        root=ET.fromstring('<DOCUMENT><COMPANY-NAME AREGCIK="12345678">옛이름</COMPANY-NAME>'+body+'</DOCUMENT>')
        return m.inspect({'sample_id':'synthetic','rcept_no':'synthetic'}, {'sha256':'synthetic'}, [('synthetic.xml',root,'synthetic','utf-8')])
    def test_amendment_table_date_not_original_cover(self):
        f=self.inspect('<TITLE>정 정 신 고 (보고)</TITLE><TABLE><TR><TD>2007년 08월 23일</TD></TR></TABLE><P>1. 정정대상 공시서류 : 반기</P><COVER><P-SMALL>2007년 08월 14일</P-SMALL></COVER>')
        self.assertEqual(f['declared_correction_date'],'2007-08-23')
        self.assertFalse(f['source_date_is_publication_attestation'])
    def test_missing_correction_date_stays_missing(self):
        f=self.inspect('<TITLE>정정신고 (보고)</TITLE><P>1. 정정대상 공시서류 : 반기</P><COVER><P>2007년 8월 14일</P></COVER>')
        self.assertEqual(f['declared_correction_date'],'')
    def test_bad_month_label_not_guessed(self):
        self.assertEqual(m.strict_date('2007년 05년 15일'),'')
        self.assertEqual(m.strict_date('2007년 2월 30일'),'')
    def test_explicit_dates_only(self):
        self.assertEqual(m.strict_date('2007. 5. 15'),'2007-05-15')
        self.assertEqual(m.strict_date('접수번호 20070814000001'),'')
    def test_names_not_historically_aliased(self):
        self.assertEqual(m.normalize_legal_name('(주) 동 원'),'동원')
        self.assertNotEqual(m.normalize_legal_name('HLB글로벌'),m.normalize_legal_name('동원'))
if __name__=='__main__':unittest.main(verbosity=2)
