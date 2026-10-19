"""No source identity/date hardcodes; reproduce an isolated title scope leak."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.legacy_native_financials import parse_native,select_verified
def header(prefix=''):
    return prefix+'현금흐름표 제7기 2009.01.01부터 2009.12.31까지 제6기 2008.01.01부터 2008.12.31까지 (단위:원)'
def money(n):return '<TABLE><TR><TH>과목</TH><TH>제7기</TH><TH>제6기</TH></TR><TR><TD>영업활동으로인한현금흐름</TD><TD>'+str(n)+'</TD><TD>10</TD></TR></TABLE>'
class Boundary(unittest.TestCase):
    def base(self):return '<COVER>사업보고서 사업연도2009.01.01부터2009.12.31까지</COVER><P>4.재무제표</P><P>'+header()+'</P>'+money(100)
    def test_isolated_cfs_title_cannot_inherit_old_ofs_contract(self):
        text=self.base()+'<TABLE><TR><TD>연 결 현 금 흐 름 표</TD></TR></TABLE><TABLE><TR><TD>제7기 2009.01.01부터2009.12.31까지 (단위:원)</TD></TR></TABLE>'+money(200)
        rows=select_verified(parse_native(text)['candidates']);self.assertEqual([(r['scope'],r['amount_krw'])for r in rows],[('OFS','100')])
    def test_unproved_same_scope_title_also_resets_instead_of_carrying(self):
        rows=select_verified(parse_native(self.base()+'<TABLE><TR><TD>재무상태표(대차대조표)</TD></TR></TABLE>'+money(200))['candidates'])
        self.assertEqual([r['amount_krw']for r in rows],['100'])
    def test_fresh_proved_cfs_prefix_still_has_own_scope(self):
        rows=select_verified(parse_native(self.base()+'<P>'+header('연결')+'</P>'+money(200))['candidates'])
        self.assertEqual({(r['scope'],r['amount_krw'])for r in rows},{('OFS','100'),('CFS','200')})
if __name__=='__main__':unittest.main()
