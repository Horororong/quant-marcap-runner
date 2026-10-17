"""Real CT2019 prices + common Gross/Net engine; deliberately short functional test."""
from pathlib import Path
import json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from strategy_dsl import StrategySpec
from strategy_dsl_runner import load_project_engine,execute_daily_nav
from stock_dividend_research import load_strategy_actions
from verify_research_nav import verify

def main(out):
 out.mkdir(parents=True,exist_ok=False);art=out/'artifacts';art.mkdir()
 raw=json.loads((ROOT/'config/strategies/research_size_deciles_2019_2020_v1.json').read_text())
 raw['period']=dict(start='2019-12-23',end='2020-04-29',book_start='2019-12-23',book_end='2020-04-29',as_of_date='2020-04-29');raw['initial_capital']=10000
 raw['portfolio']=dict(selection='top_n',number_of_positions=1,weighting='equal')
 spec=StrategySpec.from_dict(raw);engine=load_project_engine(ROOT)
 rows=[]
 for year in [2019,2020]:
  x=pd.read_parquet(ROOT/f'data/krx_equities/yearly/marcap-{year}.parquet',columns=['Date','Code','Close','Volume','ChangesRatio'])
  rows.append(x[x.Code.astype(str).str.zfill(6).eq('068270')])
 x=pd.concat(rows).set_index('Date').sort_index().loc[raw['period']['start']:raw['period']['end']]
 prices=x[['Close']].rename(columns={'Close':'068270'});refs=x[['ChangesRatio']].rename(columns={'ChangesRatio':'068270'})/100
 targets=pd.DataFrame({'068270':[1.,0.,.7,1.]},index=pd.to_datetime(['2019-12-23','2019-12-30','2020-01-03','2020-04-27']))
 events=load_strategy_actions(ROOT,spec,start=prices.index.min(),end=prices.index.max(),asset_codes={'068270'})
 from strategy_dsl_runner import engine_inputs
 cfg,cost,assumptions=engine_inputs(spec,engine)
 result=execute_daily_nav(engine=engine,close_prices=prices,target_weights=targets,cost_scenarios=cost,execution_assumptions=assumptions,initial_capital=10000,
  tradable_mask=x[['Volume']].rename(columns={'Volume':'068270'}).gt(0),corporate_action_events=events,reference_returns=refs)
 result['daily_nav'].rename(columns=lambda c:'NAV_'+c).to_csv(art/'daily_nav.csv',index_label='Date');targets.to_csv(art/'target_weights.csv',index_label='Date')
 (out/'strategy_normalized.json').write_text(json.dumps(spec.to_dict(),ensure_ascii=False,indent=2)+'\n')
 for name,v in result['execution_scenarios'].items():
  (art/f'books_{name}.json').write_text(json.dumps(v['stock_dividend_books'],default=str,ensure_ascii=False,indent=2))
 verify(out,out/'independent')
 print('real-price modeled functional lifecycle PASS; not original strategy performance or account/PIT certification')
if __name__=='__main__':main(Path(sys.argv[1]))
