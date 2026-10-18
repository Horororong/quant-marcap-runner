"""Actual Kakao split, independent quantity/cash checks, no strategy performance."""
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from strategy_dsl_runner import load_project_engine
from corporate_action_registry import load_corporate_actions

def main(out):
 out.mkdir(parents=True,exist_ok=False);engine=load_project_engine(ROOT)
 panel=engine.load_krx_equity_panel(start='2021-04-08',end='2021-04-16',markets=['KOSPI'],columns=['Date','Code','Close','Volume','ChangesRatio'],repo_root=ROOT);x=panel[panel.Code.eq('035720')].set_index('Date').sort_index();prices=x[['Close']].rename(columns={'Close':'035720'});refs=x[['ChangesRatio']].rename(columns={'ChangesRatio':'035720'})/100;targets=pd.DataFrame({'035720':[1.]},index=[prices.index[0]])
 costs=engine.TradingCostAssumptions(commission_bps=1.5,sell_tax_bps=15.,spread_bps=3.,slippage_bps=5.)
 events=load_corporate_actions(ROOT,start=prices.index[0],end=prices.index[-1],asset_codes={'035720'})
 result=engine.simulate_target_weight_portfolio(close_prices=prices,target_weights=targets,cost_assumptions=costs,execution_assumptions=engine.ExecutionAssumptions(execution_lag_sessions=1),initial_capital=10000.,tradable_mask=x[['Volume']].rename(columns={'Volume':'035720'}).gt(0),corporate_action_events=events,reference_returns=refs)
 q=10000/float(x.loc['2021-04-09','Close']);rows=[]
 for d in prices.index:
  expected=10000. if d<=pd.Timestamp('2021-04-09') else q*(5 if d>=pd.Timestamp('2021-04-15') else 1)*float(prices.at[d,'035720'])
  for book in ['Gross','Net']:
   value=expected*(1-.00095) if book=='Net' and d>=pd.Timestamp('2021-04-09') else expected
   actual=result['daily_nav'].at[d,book]*10000.;assert abs(value-actual)<1e-5,(d,book,value,actual)
   rows.append(dict(Date=str(d.date()),book=book,independent_value=value,engine_value=actual,absolute_error=abs(value-actual)))
 economic=5*120500/558000-1;market=120500/112000-1
 assert abs(market-.0759)*10000<1 and abs(economic-.0759)*10000>1
 result['daily_nav'].to_csv(out/'daily_nav.csv',index_label='Date');pd.DataFrame(rows).to_csv(out/'independent_ledger.csv',index=False);result['daily_detail'].to_csv(out/'daily_detail.csv',index_label='Date');result['corporate_actions'].to_csv(out/'corporate_actions.csv',index=False)
 summary=dict(status='PASS_ACTUAL_PRICE_SPLIT_COMPONENT',sessions=len(prices),ledger_rows=len(rows),economic_split_return=economic,official_basis_price_return=market,source_ChangesRatio=.0759,price_difference_bps=abs(market-.0759)*10000,max_ledger_error=max(r['absolute_error'] for r in rows),investment_approved=False,scope='functional actual-price accounting, not a shortened original-strategy run or legal/PIT account certification')
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main(Path(sys.argv[1]))
