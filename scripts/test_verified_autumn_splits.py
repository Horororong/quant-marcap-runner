"""Actual KRX share-count oracles; software regressions, not investment results."""
from pathlib import Path
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from corporate_action_registry import load_corporate_actions
from corporate_action_reconciliation import reconcile_registered_events
from krx_history_audit import audit_source_history
from strategy_dsl_runner import run_strategy

ROOT = Path(__file__).resolve().parents[1]
EVENTS = {'278470': ('2024-10-31', 5., '2024-10-17', 266500., 50100., -6.),
          '003920': ('2024-11-20', 10., '2024-11-07', 687000., 67700., -1.46),
          '003925': ('2024-11-20', 10., '2024-11-07', 399500., 38100., -4.63)}


def main():
    panel = pd.read_parquet(ROOT/'data/krx_equities/yearly/marcap-2024.parquet')
    panel = panel[panel.Market.isin(['KOSPI','KOSDAQ'])]
    events = load_corporate_actions(ROOT,start='2024-01-01',end='2024-12-31')
    _, _, candidates = audit_source_history(panel,'2024-01-01','2024-12-31',['KOSPI','KOSDAQ'],ROOT)
    checks, reviewed = reconcile_registered_events(panel,events,candidates)
    assert checks.status.eq('reference_consistent').all() and len(checks)==6
    for code,(date,ratio,prior,previous,close,reference_pct) in EVENTS.items():
        observed = checks.set_index('Code').loc[code]
        assert observed.event_date==pd.Timestamp(date) and observed.last_trade_date==pd.Timestamp(prior)
        assert observed.share_ratio==ratio and observed.last_trade_close==previous and observed.event_close==close
        value_return=ratio*close/previous-1
        assert np.isclose(observed.effective_return,value_return,atol=1e-14)
        assert value_return<0 and np.isclose(observed.exchange_return,reference_pct/100,atol=1e-14)
        match=reviewed[reviewed.Code.eq(code)&pd.to_datetime(reviewed.Date).eq(date)]
        assert len(match)==1 and match.registry_match_status.eq('registered_split_reference_consistent').all()
    # Signal cross-section is independent of future event dates/codes/outcomes.
    signal=panel[panel.Date.eq('2024-09-30')&panel.Market.eq('KOSPI')&panel.Volume.gt(0)&panel.Close.between(100000,900000)]
    codes=signal.sort_values(['Close','Code'],ascending=[False,True]).Code.tolist()
    assert len(codes)==95 and set(EVENTS)<=set(codes[:30])
    spec=json.loads((ROOT/'config/strategies/kr_equity_autumn_splits_research.json').read_text())
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for mode in ('top_n','deciles'):
            spec['portfolio']={'selection':mode,'weighting':'equal'}
            if mode=='top_n':spec['portfolio']['number_of_positions']=30
            path=td/f'{mode}.json';path.write_text(json.dumps(spec));out=td/mode
            result=run_strategy(path,ROOT,out,postprocess=False)
            groups={'top_n':codes[:30]} if mode=='top_n' else {f'D{i+1:02d}':list(g) for i,g in enumerate(np.array_split(codes,10))}
            daily=pd.read_csv(out/'daily_nav.csv',parse_dates=['Date']).set_index('Date')
            applied=pd.read_csv(out/'corporate_actions_applied.csv',dtype={'predecessor_code':str})
            assert set(applied.predecessor_code)==set(EVENTS)
            for row in applied.itertuples():
                date,ratio,_,prior,close,_=EVENTS[row.predecessor_code]
                assert pd.Timestamp(row.Date)==pd.Timestamp(date) and row.share_ratio==ratio
                assert np.isclose(row.event_return,ratio*close/prior-1,atol=1e-14) and row.event_return<0
            buy=pd.Timestamp('2024-10-02')  # Oct 1 is an actual XKRX holiday.
            for label,holdings in groups.items():
                price=panel[panel.Code.isin(holdings)].pivot(index='Date',columns='Code',values='Close').reindex(daily.index)[holdings]
                values=price.loc[buy:]/price.loc[buy]
                for code,(date,ratio,*_) in EVENTS.items():
                    if code in holdings:values.loc[date:,code]*=ratio
                assert np.isfinite(values).all().all()
                oracle=pd.Series(1.,index=daily.index);oracle.loc[buy:]=values.mean(axis=1)
                net=oracle.copy();net.loc[buy:]*=1-9.5/10000
                prefix='NAV_' if mode=='top_n' else f'NAV_{label}_'
                assert np.allclose(daily[prefix+'Gross'],oracle,atol=1e-12,rtol=0),label
                assert np.allclose(daily[prefix+'Net_fixed'],net,atol=1e-12,rtol=0),label
                assert daily.loc[:'2024-09-30',prefix+'Gross'].eq(1.).all()
            event_dates=['2024-10-31','2024-11-20']
            if mode=='top_n':
                for ex in result['engine_result']['execution_scenarios'].values():
                    assert ex['trades'].loc[event_dates,['buy_turnover','sell_turnover','cost_fraction']].eq(0).all().all()
            else:
                trades=pd.read_csv(out/'execution_trades.csv')
                assert trades[trades.Date.isin(event_dates)][['buy_turnover','sell_turnover','cost_fraction']].eq(0).all().all()
            module='strategy_dsl_runner' if mode=='top_n' else 'strategy_dsl_deciles'
            # Every security's own record is required; no common/preferred inheritance.
            # A legal-effectiveness date is not a resume date and cannot bypass the guard.
            mutations=[('remove_'+code,code,'remove') for code in EVENTS]+[('wrong_apr_ratio','278470','ratio'),('legal_date','003920','date')]
            for label,code,kind in mutations:
                def damaged(*args,_code=code,_kind=kind,**kwargs):
                    loaded=load_corporate_actions(*args,**kwargs)
                    if _kind=='remove':return loaded[~loaded.predecessor_code.eq(_code)]
                    loaded=loaded.copy()
                    if _kind=='ratio':loaded.loc[loaded.predecessor_code.eq(_code),'share_ratio']=10.
                    else:loaded.loc[loaded.predecessor_code.eq(_code),'event_date']=pd.Timestamp('2024-11-12')
                    return loaded
                blocked=td/f'{mode}_{label}'
                with patch(f'{module}.load_corporate_actions',side_effect=damaged):
                    try:run_strategy(path,ROOT,blocked,postprocess=False)
                    except RuntimeError as exc:
                        assert 'held-return reference check' in str(exc) and code in str(exc),exc
                    else:raise AssertionError('invalid or missing split was accepted: '+label)
                assert not blocked.exists()
    print('VERIFIED AUTUMN SPLITS AND BOTH PUBLIC KRX MODES: PASS')


if __name__=='__main__':main()
