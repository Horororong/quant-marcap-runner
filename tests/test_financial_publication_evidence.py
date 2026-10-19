import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from financial_publication_evidence import viewer_evidence
class Publication(unittest.TestCase):
 def test_attachment_date_not_parent_and_script_parameter_not_chain(self):
  raw=b'''<select id="family"><option value="rcpNo=parent">2010.03.31 Report</option></select><select id="att"><option value="rcpNo=parent&amp;dcmNo=late">2010.04.30 Added</option></select><script>alertInvestNotice("parent","doc","OTHER","0")</script>'''
  r=viewer_evidence(raw);self.assertEqual([x['date']for x in r['options']],['2010-03-31','2010-04-30']);self.assertEqual(r['options'][1]['document_id'],'late');self.assertEqual(r['chain_certification'],'UNVERIFIED')
 def test_no_date_does_not_inherit_or_guess(self):
  r=viewer_evidence(b'<select id="att"><option value="rcpNo=p&amp;dcmNo=d">Added report</option></select>');self.assertIsNone(r['options'][0]['date'])
if __name__=='__main__':unittest.main()
