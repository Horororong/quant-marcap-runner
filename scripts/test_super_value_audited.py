import unittest
import pandas as pd
import numpy as np
import super_value_audited_nav as s

class ResearchRegression(unittest.TestCase):
    def test_corporate_action_share_count(self):
        row={'raw_close_return':6160/1135-1,'baseprice_gap':True}
        self.assertAlmostEqual(s.holder_return(row,pd.Timestamp('2018-12-27'),'071970'),6160/1135/8-1)
        with self.assertRaisesRegex(RuntimeError,'unverified corporate action'):
            s.holder_return(row,pd.Timestamp('2018-12-27'),'000000')

    def test_exact_account_definitions(self):
        cases=[('ifrs_ProfitLoss','IS','net_income'),('ifrs-full_ProfitLoss','CIS','net_income'),('ifrs_ProfitLossBeforeTax','IS',None),('ifrs-full_ProfitLossAttributableToOwnersOfParent','IS',None),('ifrs_Equity','BS','equity'),('ifrs-full_EquityAndLiabilities','BS',None)]
        for aid,sj,want in cases:
            self.assertEqual(s.exact_metric({'account_id':aid,'sj_div':sj,'account_nm':''})[0],want)

    def panel(self):
        rows=[]
        for dt,r in zip(pd.to_datetime(['2019-10-31','2019-11-01','2019-11-04']),[0.,1.,.1]):
            for code in ['000010','000020']:
                rows.append(dict(Date=dt,Code=code,Name=code,Close=100.,Open=95.,High=110.,Low=90.,Volume=1000.,Change=r if code=='000010' else 0.,baseprice_gap=False,share_change=0.,raw_close_return=r))
        return pd.DataFrame(rows)

    def test_next_close_and_first_trade_cost(self):
        p=self.panel();sel={pd.Timestamp('2019-10-31'):pd.DataFrame({'Code':['000010']})}
        gross,_,_=s.simulate(p,sel,1,'gross')
        net,_,_=s.simulate(p,sel,1,'base')
        self.assertAlmostEqual(gross.iloc[0],1.)
        self.assertAlmostEqual(gross.iloc[-1],1.1)
        self.assertAlmostEqual(net.iloc[-1],1.1/(1+.00215))

    def test_missing_held_return_is_not_zero(self):
        p=self.panel();p.loc[(p.Date=='2019-11-04')&(p.Code=='000010'),'Change']=np.nan
        sel={pd.Timestamp('2019-10-31'):pd.DataFrame({'Code':['000010']})}
        with self.assertRaisesRegex(RuntimeError,'held return missing'):
            s.simulate(p,sel,1,'gross')

    def test_unavailable_buy_stays_cash(self):
        p=self.panel();p.loc[(p.Date=='2019-11-01')&(p.Code=='000010'),'Volume']=0
        sel={pd.Timestamp('2019-10-31'):pd.DataFrame({'Code':['000010']})}
        nav,tr,_=s.simulate(p,sel,1,'gross')
        self.assertAlmostEqual(nav.iloc[-1],1.)
        self.assertEqual(tr.iloc[0].blocked_buys,'000010')

    def test_suspended_holding_is_not_sold(self):
        p=self.panel()
        p.loc[(p.Date=='2019-11-04')&(p.Code=='000010'),'Volume']=0
        p.loc[(p.Date=='2019-11-04')&(p.Code=='000010'),'Change']=0
        p.loc[(p.Date=='2019-11-04')&(p.Code=='000010'),'raw_close_return']=0
        extra=p[p.Date=='2019-11-04'].copy();extra['Date']=pd.Timestamp('2019-11-05')
        extra.loc[extra.Code=='000010','Volume']=1000
        extra.loc[extra.Code=='000010','Change']=.2
        extra.loc[extra.Code=='000010','raw_close_return']=.2
        p=pd.concat([p,extra])
        sel={pd.Timestamp('2019-10-31'):pd.DataFrame({'Code':['000010']}),pd.Timestamp('2019-11-01'):pd.DataFrame({'Code':['000020']})}
        nav,tr,_=s.simulate(p,sel,1,'gross')
        self.assertAlmostEqual(nav.iloc[-1],1.2)
        self.assertEqual(tr.iloc[1].locked_holdings,'000010')
        self.assertAlmostEqual(tr.iloc[1].sell_turnover,0)
        self.assertTrue(tr.iloc[-1].retry_after_suspension)

if __name__=='__main__':unittest.main()
