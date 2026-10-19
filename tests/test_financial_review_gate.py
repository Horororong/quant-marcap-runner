import copy,hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from financial_review_gate import normalize,verify
from financial_source_grid import Grid
class IndependentGate(unittest.TestCase):
    def fixture(self):
        g=Grid();g.feed('<p>OFS2009FY 원</p><table><tr><td>매출액</td><td>1,000</td></tr></table>')
        c=dict(id='synthetic',receipt='synthetic',metric='revenue',scope='OFS',member='main.xml',table=0,row=0,column=1,literal='1,000',account_literal='매출액',member_sha256='member',archive_sha256='archive',semantic_verdict='PASS',header_proofs=[dict(table=0,literal='OFS2009FY 원')],period_start='2009-01-01',period_end='2009-12-31',basis='annual',report_period='FY',unit='원')
        row=dict(metric='revenue',scope='OFS',source_member='main.xml',amount_krw='1000',table_index=0,row_index=0,value_col=1,period_start='2009-01-01',period_end='2009-12-31',measurement_basis='annual',period='FY',unit='원',source_member_sha256='member',document_sha256='archive',backtest_eligible=False)
        c['statement']='IS';row['statement']='IS';row['unit_multiplier']='1'
        c['semantic_rationale']='Synthetic primary IS current FY2009 OFS KRW monetary cell; no comparative or EPS selection.'
        return c,[row],{'main.xml':(g,'member','archive')}
    def test_raw_literals_and_semantic_control_required_not_parser_replay(self):
        c,r,s=self.fixture();d,p=verify(c,r,s);self.assertEqual(d['verdict'],'PASS');self.assertFalse(p['backtest_eligible']);self.assertEqual(p['correction_chain_verdict'],'UNVERIFIED')
        c['semantic_verdict']='UNVERIFIED';self.assertIsNone(verify(c,r,s)[1])
    def test_wrong_amount_or_prior_period_refused(self):
        for key,value in [('amount_krw','1000000'),('period_end','2008-12-31'),('unit_multiplier','1000'),('statement','CF')]:
            c,r,s=self.fixture();r[0][key]=value;d,p=verify(c,r,s);self.assertEqual(d['verdict'],'FAIL');self.assertIsNone(p)
    def test_conflicting_source_hold_and_missing_candidate_stay_unverified(self):
        c,r,s=self.fixture();c['hold_reason']='CFS_OFS_SOURCE_CONFLICT';d,p=verify(c,r,s);self.assertEqual(d['verdict'],'UNVERIFIED');self.assertIsNone(p)
        c.pop('hold_reason');d,p=verify(c,[],s);self.assertEqual(d['verdict'],'UNVERIFIED');self.assertIsNone(p)
    def test_literal_location_hash_unit_and_investment_flag_tampering_refused(self):
        for key,value in [('literal','1000'),('member_sha256','wrong'),('unit','USD')]:
            c,r,s=self.fixture();c[key]=value;d,p=verify(c,r,s);self.assertEqual(d['verdict'],'FAIL');self.assertIsNone(p)
        c,r,s=self.fixture();r[0]['backtest_eligible']=True;self.assertEqual(verify(c,r,s)[0]['verdict'],'FAIL')
    def test_sign_and_multiplier_independent_decimal_and_no_guessing(self):
        self.assertEqual(normalize('(1,234)','천원'),-1234000);self.assertEqual(normalize('500','원',True),-500)
        self.assertEqual(normalize('536,277,091&cr;=============','원'),536277091)
        for raw in ['-','1,23','123 456','100=','100&cr;EPS2','100&cr;===50','']:
            with self.assertRaises(ValueError):normalize(raw,'원')
    def test_different_current_amount_in_corresponding_source_is_held(self):
        c,r,s=self.fixture();g=Grid();g.feed('<table><tr><td>매출액</td><td>2,000</td></tr></table>');s['auditor.xml']=(g,'other','archive')
        c['corroborating_sources']=[dict(member='auditor.xml',table=0,row=0,column=1,literal='2,000',account_literal='매출액',member_sha256='other',unit='원',scope='OFS',period_start='2009-01-01',period_end='2009-12-31')]
        d,p=verify(c,r,s);self.assertEqual(d['verdict'],'UNVERIFIED');self.assertEqual(d['reason'],'INDEPENDENT_CROSS_MEMBER_CONFLICT');self.assertIsNone(p)
if __name__=='__main__':unittest.main()
