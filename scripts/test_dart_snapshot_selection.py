"""Hand-computed stable account-selection cases, not a financial source audit."""
import unittest
import pandas as pd
from dart_value_factor_adapter import report_snapshots


class SnapshotSelection(unittest.TestCase):
    def test_missing_priority_ties_numeric_and_scope(self):
        rows=[]
        def row(account,amount,*,name="당기순이익",statement="IS",cum="-",fs="CFS",receipt="20200401000001"):
            rows.append(dict(stock_code="000001",fs_div_requested=fs,rcept_no=receipt,filing_date=pd.Timestamp("2020-04-01"),sj_div=statement,account_id=account,account_nm=name,thstrm_amount=amount,thstrm_add_amount=cum))
        row("ifrs-full_ProfitLoss","-")
        row("z","300")
        row("a","(125)")  # usable > missing, then lexical a > z
        row("a","999")    # exact tie keeps first source row
        row("ifrs-full_ProfitLoss","777",statement="CIS")  # concept beats alias
        row("ifrs-full_ProfitLossBeforeTax","99999",name="법인세전이익")
        row("ifrs-full_Equity","1,234",name="자본총계",statement="BS")
        row("ifrs-full_ProfitLoss","4",fs="OFS")
        frame=pd.DataFrame(rows)
        r=report_snapshots(frame).set_index("fs_div")
        self.assertEqual(r.loc["CFS","net_income_current"],777)
        self.assertEqual(r.loc["OFS","net_income_current"],4)
        self.assertEqual(r.loc["CFS","equity_current"],1234)
        r=report_snapshots(frame[frame.sj_div.ne("CIS")]).set_index("fs_div")
        self.assertEqual(r.loc["CFS","net_income_current"],-125)

    def test_unusable_new_report_is_preserved_only_under_explicit_policy(self):
        raw=pd.DataFrame([dict(stock_code="000001",fs_div_requested="CFS",rcept_no="20200401000001",filing_date=pd.NaT,
            sj_div="",account_id="",account_nm="",thstrm_amount="",thstrm_add_amount="")])
        self.assertTrue(report_snapshots(raw).empty)
        r=report_snapshots(raw,keep_empty_reports=True)
        self.assertEqual(len(r),1)
        self.assertTrue(r.net_income_current.isna().all())
        self.assertEqual(r.rcept_no.iloc[0],"20200401000001")


if __name__=="__main__": unittest.main(verbosity=2)
