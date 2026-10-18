"""Independent split quantity economics versus rounded official price basis."""
import unittest,json
from pathlib import Path
import pandas as pd
from corporate_action_reference import validate_reference
from strategy_dsl_runner import load_project_engine
ROOT=Path(__file__).resolve().parents[1]
class Reference(unittest.TestCase):
 def fixture(self):
  engine=load_project_engine(ROOT);dates=pd.to_datetime(['2024-01-02','2024-01-03','2024-01-04','2024-01-05']);px=pd.DataFrame({'000001':[100.,110.,60.,61.]},index=dates);weights=pd.DataFrame({'000001':[1.]},index=[dates[0]])
  ref=px.pct_change(fill_method=None);ref.iloc[0]=0.;ref.iloc[2]=60/56-1
  c=dict(version=1,scope='synthetic',event_date='2024-01-04',security='000001',reference_price=56.,publication_date='2024-01-03',source='explicit synthetic fixture, not official data',evidence_path='synthetic',sha256='0'*64,location='synthetic rounded basis')
  events=pd.DataFrame([dict(event_date=dates[2],event_type='stock_split',predecessor_code='000001',successor_code='000001',share_ratio=2.,cash_per_share=0.,source='synthetic',market_reference_contract=json.dumps(c))]);return engine,dates,px,weights,ref,c,events
 def runbook(self,engine,px,weights,ref,events):return engine.simulate_target_weight_portfolio(close_prices=px,target_weights=weights,cost_assumptions=engine.TradingCostAssumptions(commission_bps=10.),execution_assumptions=engine.ExecutionAssumptions(execution_lag_sessions=1),initial_capital=10000.,reference_returns=ref,corporate_action_events=events)
 def test_independent_share_cash_and_price_comparisons(self):
  e,d,p,w,r,c,ca=self.fixture();out=self.runbook(e,p,w,r,ca);nav=out['daily_nav'];q=10000/110
  self.assertAlmostEqual(nav.at[d[2],'Gross']*10000,q*2*60,places=8)
  self.assertAlmostEqual(nav.at[d[3],'Gross']*10000,q*2*61,places=8)
  self.assertAlmostEqual(nav.at[d[2],'Net']*10000,q*.999*2*60,places=8)
  self.assertAlmostEqual(out['trades'].at[d[2],'cost_fraction'],0.)
  self.assertLess(out['daily_detail'].at[d[2],'max_held_return_difference_bps'],1e-8)
  self.assertGreater(abs((120/110-1)-(60/56-1))*10000,1.)
 def test_missing_exact_reference_fails_existing_one_bp(self):
  e,d,p,w,r,c,ca=self.fixture()
  with self.assertRaisesRegex(RuntimeError,'held-return reference'):self.runbook(e,p,w,r,ca.drop(columns='market_reference_contract'))
 def test_wrong_price_fails_without_changing_nav_or_tolerance(self):
  e,d,p,w,r,c,ca=self.fixture();c['reference_price']=55;ca['market_reference_contract']=json.dumps(c)
  with self.assertRaisesRegex(RuntimeError,'held-return reference'):self.runbook(e,p,w,r,ca)
 def test_ordinary_date_is_not_waived(self):
  e,d,p,w,r,c,ca=self.fixture();r.iloc[3]=.10
  with self.assertRaisesRegex(RuntimeError,'held-return reference'):self.runbook(e,p,w,r,ca)
 def test_future_identity_and_nonfinite_references_rejected(self):
  _,_,_,_,_,c,_=self.fixture()
  for patch in [dict(publication_date='2024-01-04'),dict(event_date='2024-01-05'),dict(security='000002'),dict(reference_price=float('nan')),dict(reference_price=True)]:
   with self.assertRaises(ValueError):validate_reference(dict(c,**patch),'2024-01-04','000001')
if __name__=='__main__':unittest.main(verbosity=2)
