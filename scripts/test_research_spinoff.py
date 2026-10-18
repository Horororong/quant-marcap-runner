"""Synthetic two-leg quantity conservation and fail-closed source boundaries."""
import json,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_dsl_runner import load_project_engine
from research_spinoff import validate,normalize
ROOT=Path(__file__).resolve().parents[1]


def fixture():
 d=pd.bdate_range('2024-01-02',periods=9);p=pd.DataFrame({'000001':[100]*5+[80,81,82,83],'000002':[np.nan]*5+[25,26,27,28],'000003':[50]*9},index=d,dtype=float)
 v=pd.DataFrame(100.,index=d,columns=p.columns);v.loc[d[2:5],'000001']=0;v.loc[d[:5],'000002']=np.nan;m=p.notna()&v.gt(0);r=p.pct_change(fill_method=None);r.loc[d[5],['000001','000002']]=0.
 c=dict(version=1,scope='synthetic',parent='000001',child='000002',last_trade_date=str(d[1].date()),record_date=str(d[2].date()),legal_date=str(d[3].date()),listing_date=str(d[5].date()),parent_ratio=.9,child_ratio=.4,parent_reference=80.,child_reference=25.,quantity_basis='continuous_pro_rata',halt_valuation='observed_frozen_cum_right_basket',settlement='virtual_on_simultaneous_listing_close',evidence=[])
 ev=pd.DataFrame([dict(event_date=d[5],event_type='stock_spinoff',predecessor_code='000001',successor_code='000001',share_ratio=.9,cash_per_share=0.,child_code='000002',source='synthetic:not-primary',spin_off_contract=json.dumps(c))])
 w=pd.DataFrame([[.6,0,.4],[0,0,1]],index=d[[0,2]],columns=p.columns)
 return d,p,v,m,r,ev,w


class SpinOff(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.e=load_project_engine(ROOT)
 def execute(self,**patch):
  d,p,v,m,r,ev,w=fixture();kw=dict(close_prices=p,target_weights=w,initial_capital=10000.,tradable_mask=m,source_volumes=v,reference_returns=r,corporate_action_events=ev,cost_assumptions=self.e.TradingCostAssumptions(commission_bps=10.,sell_tax_bps=20.),execution_assumptions=self.e.ExecutionAssumptions(nontradable_policy='defer_full_rebalance_events_v1'));kw.update(patch);return self.e.simulate_target_weight_portfolio(**kw)
 def test_pending_order_sells_both_issued_legs_without_cash_advance(self):
  d,p,v,m,r,ev,w=fixture();out=self.execute()
  # Gross60 old parent shares +80 third-security shares. After listing:
  # 54parent*80 +24child*25 +80third*50 =8920. Both legs sold once.
  self.assertAlmostEqual(out['daily_nav'].loc[d[4],'Gross']*10000,10000.)
  self.assertAlmostEqual(out['daily_nav'].loc[d[5],'Gross']*10000,8920.)
  # Net initial common10bp: all quantities are .999 of Gross. Sell book4920,
  # buy third4920 on that Net book; tax20bp plus10bp both ways.
  expected=.999*(8920-4920*.004)
  self.assertAlmostEqual(out['daily_nav'].loc[d[5],'Net']*10000,expected)
  self.assertEqual(out['execution_schedule'].iloc[1].execution_date,d[5])
  self.assertEqual(out['trades'].loc[d[3],'cost_fraction'],0.)
  self.assertEqual(out['weights'].loc[d[5],'000001'],0.)
  self.assertEqual(out['weights'].loc[d[5],'000002'],0.)
 def test_hold_both_legs_marked_independently_not_same_asset_split(self):
  d,p,v,m,r,ev,w=fixture();out=self.execute(target_weights=w.iloc[:1])
  for i in range(5,9):self.assertAlmostEqual(out['daily_nav'].iloc[i].Gross*10000,54*p.iloc[i,0]+24*p.iloc[i,1]+4000)
  self.assertEqual(out['trades'].loc[d[5],'cost_fraction'],0.)
 def test_new_parent_buyer_after_listing_gets_no_historical_child(self):
  d,p,v,m,r,ev,w=fixture();w=pd.DataFrame([[1,0,0]],index=d[6:7],columns=p.columns);out=self.execute(target_weights=w)
  self.assertTrue(out['weights']['000002'].eq(0).all());self.assertEqual(len(out['corporate_actions']),0)
 def test_non_simultaneous_or_missing_observations_do_not_receive_exception(self):
  d,p,v,m,r,ev,w=fixture()
  for name in ['missing','tradable','wrong_reference','child_early']:
   pp=p.copy();mm=m.copy();rr=r.copy()
   if name=='missing':pp.loc[d[3],'000001']=np.nan
   if name=='tradable':mm.loc[d[3],'000001']=True
   if name=='wrong_reference':rr.loc[d[5],'000002']=.01
   if name=='child_early':mm.loc[d[3],'000002']=True
   with self.assertRaises((ValueError,RuntimeError)):self.execute(close_prices=pp,tradable_mask=mm,reference_returns=rr)
 def test_original_execution_and_missing_contract_remain_blocked(self):
  with self.assertRaisesRegex(ValueError,'split/no-action'):self.execute(execution_assumptions=self.e.ExecutionAssumptions(nontradable_policy='defer_full_rebalance'))
  d,p,v,m,r,ev,w=fixture();ev['spin_off_contract']='{}'
  with self.assertRaisesRegex(ValueError,'contract'):self.execute(corporate_action_events=ev)
 def test_general_one_bp_guard_survives_registered_spinoff(self):
  d,p,v,m,r,ev,w=fixture();r.loc[d[4],'000003']=.01
  with self.assertRaisesRegex(RuntimeError,'held-return reference'):self.execute(reference_returns=r)

if __name__=='__main__':unittest.main(verbosity=2)
