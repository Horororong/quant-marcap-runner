import hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from legacy_document_quality import inspect_member,literal_label_view

class LiteralLabels(unittest.TestCase):
    def test_only_view_changes_original_bytes_hash_and_numbers_preserved(self):
        raw='<DOCUMENT><P>M&A <당기> (1,234) <주석 19></P></DOCUMENT>'.encode()
        d=inspect_member(raw,'filing.xml')
        self.assertEqual(d['issues'],[])
        self.assertEqual(d['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual([x['literal']for x in d['literal_label_view']],['<당기>','<주석 19>'])
        for x in d['literal_label_view']:
            self.assertTrue(raw.decode()[x['offset']:].startswith(x['literal']))
        self.assertIn('(1,234)',literal_label_view(raw.decode())[0])
    def test_broken_real_markup_and_incomplete_document_still_rejected(self):
        for text in ['<DOCUMENT><P><당기>10</DOCUMENT>',
                     '<DOCUMENT><TABLE><TR><TD>1</TR></TABLE></DOCUMENT>',
                     '<DOCUMENT><P><당기>10</P>',
                     '<DOCUMENT><금액 UNIT="원">1</DOCUMENT>']:
            self.assertIn('SOURCE_XML_INCOMPLETE_OR_INVALID',inspect_member(text.encode(),'a.xml')['issues'])
    def test_real_paired_elements_comments_cdata_attributes_are_not_rewritten(self):
        for text in ['<DOCUMENT><당기>1</당기></DOCUMENT>',
                     '<DOCUMENT><!-- <당기> --><P>1</P></DOCUMENT>',
                     '<DOCUMENT><![CDATA[<당기>]]></DOCUMENT>']:
            view,changes=literal_label_view(text);self.assertEqual(view,text);self.assertEqual(changes,[])
        # Invalid angle brackets inside an attribute are not made valid.
        d=inspect_member('<DOCUMENT><P TITLE="<당기>">1</P></DOCUMENT>'.encode(),'a.xml')
        self.assertTrue(d['issues'])
    def test_ascii_tags_and_number_or_formula_boundaries_not_guessed(self):
        for token in ['<EPS>','<2009>','<당기=1>','<당기/전기>']:
            # Slash label is text grammar; ASCII/numeric/attribute shapes are not.
            if token=='<당기/전기>':continue
            self.assertEqual(literal_label_view(token)[1],[])
    def test_literal_labels_with_spaces_latin_acronyms_and_years(self):
        for label in ['< 검토를 받지 아니한 재무제표>','<LED 조명기기 제조 사업부문>','<2009년도 재고조사>','<채권ㆍ채무>']:
            self.assertEqual(inspect_member(('<DOCUMENT><P>'+label+'</P></DOCUMENT>').encode(),'a.xml')['issues'],[])
        self.assertTrue(inspect_member(b'<DOCUMENT><P><LED foo>1</P></DOCUMENT>','a.xml')['issues'])
if __name__=='__main__':unittest.main()
