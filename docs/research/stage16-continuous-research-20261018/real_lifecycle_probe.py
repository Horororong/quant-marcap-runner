"""Actual2020 dividend2021 approval/listing functional tests, NOT strategy returns."""
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'docs/research/stage15-research-environment-20261017')]
from strategy_dsl import StrategySpec
from strategy_dsl_runner import load_project_engine,execute_daily_nav,engine_inputs
from stock_dividend_research import load_strategy_actions
from verify_research_nav import verify

def main(out):
 out.mkdir(parents=True,exist_ok=False);summaries={}
 for code in ['068270','091990']:
  run=out/code;art=run/'artifacts';art.mkdir(parents=True)
  raw=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2025_v1.json').read_text());raw['period']=dict(start='2020-12-23',end='2021-04-28',book_start='2020-12-23',book_end='2021-04-28',as_of_date='2021-04-28');raw['initial_capital']=10000;raw['portfolio']=dict(selection='top_n',number_of_positions=1,weighting='equal');spec=StrategySpec.from_dict(raw)
  engine=load_project_engine(ROOT);panel=engine.load_krx_equity_panel(start=spec.period.start,end=spec.period.end,markets=spec.universe.markets,columns=['Date','Code','Close','Volume','ChangesRatio'],repo_root=ROOT);x=panel[panel.Code.eq(code)].set_index('Date').sort_index()
  prices=x[['Close']].rename(columns={'Close':code});refs=x[['ChangesRatio']].rename(columns={'ChangesRatio':code})/100;tw=pd.DataFrame({code:[1.,0.,.7,1.]},index=pd.to_datetime(['2020-12-23','2020-12-30','2021-01-04','2021-04-26']))
  events=load_strategy_actions(ROOT,spec,start=prices.index.min(),end=prices.index.max(),asset_codes={code});_,cost,assumptions=engine_inputs(spec,engine)
  result=execute_daily_nav(engine=engine,close_prices=prices,target_weights=tw,cost_scenarios=cost,execution_assumptions=assumptions,initial_capital=10000,tradable_mask=x[['Volume']].rename(columns={'Volume':code}).gt(0),corporate_action_events=events,reference_returns=refs)
  result['daily_nav'].rename(columns=lambda c:'NAV_'+c).to_csv(art/'daily_nav.csv',index_label='Date');tw.to_csv(art/'target_weights.csv',index_label='Date');(run/'strategy_normalized.json').write_text(json.dumps(spec.to_dict(),ensure_ascii=False,indent=2)+'\n')
  for name,v in result['execution_scenarios'].items():(art/f'books_{name}.json').write_text(json.dumps(v['stock_dividend_books'],default=str,ensure_ascii=False,indent=2))
  summaries[code]=verify(run,run/'independent')
 (out/'summary.json').write_text(json.dumps(dict(status='PASS_MODEL_REAL_PRICE_FUNCTIONAL_LIFECYCLE',cases=summaries,scope='short component test; not original strategy, account deposit or investment PIT approval',investment_approved=False),indent=2)+'\n')
if __name__=='__main__':main(Path(sys.argv[1]))
