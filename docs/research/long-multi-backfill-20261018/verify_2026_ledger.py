"""Test oracle: raw official closes + separate units/cash, no engine loader.

Deliberately limited to the predeclared2026largest-cap fixture (one purchase,
no held corporate-action exposure). Not an alternative strategy executor.
"""
import base64,gzip,hashlib,json
from pathlib import Path
import pandas as pd
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def verify(run,output):
    spec=json.loads((run/'strategy_normalized.json').read_bytes())
    selected=pd.read_csv(run/'artifacts/selections.csv',dtype={'Code':str})
    assert selected.Code.tolist()==['005930'] and len(selected)==1
    source=pd.read_parquet(ROOT/'data/krx_equities/yearly/marcap-2026.parquet',columns=['Date','Code','Close'])
    source=source[source.Code.eq('005930')][['Date','Close']]
    additions=[]
    for p in sorted((HOME/'sources').glob('stk_bydd_trd_*.json.gz.b64')):
        raw=gzip.decompress(base64.b64decode(p.read_bytes()))
        for row in json.loads(raw)['OutBlock_1']:
            if row['ISU_CD']=='005930':additions.append(dict(Date=pd.Timestamp(row['BAS_DD']),Close=float(row['TDD_CLSPRC'])))
    assert len(additions)==5
    source=pd.concat([source,pd.DataFrame(additions)],ignore_index=True)
    source.Date=pd.to_datetime(source.Date);assert not source.Date.duplicated().any()
    prices=source.set_index('Date').Close
    observed=pd.read_csv(run/'artifacts/daily_nav.csv',parse_dates=['Date']).set_index('Date')
    dates=observed.index;assert len(dates)==192 and str(dates[-1].date())=='2026-10-16'
    targets=pd.read_csv(run/'artifacts/target_weights.csv',index_col=0,parse_dates=True)
    assert targets['005930'].sum()==1 and (targets.fillna(0).sum(axis=1)<=1).all()
    signal=next(t for t in targets.index if targets.at[t,'005930']>0)
    assert signal==pd.Timestamp('2026-04-30');execution=dates[dates.get_loc(signal)+spec['execution']['lag_sessions']]
    assert execution==pd.Timestamp('2026-05-04')
    records=[]
    for label,cost in [('Gross',{}),('Net_zero',{}),('Net_fixed_cost',spec['cost_scenarios']['fixed_cost'])]:
        units=0.;cash=float(spec['initial_capital'])
        for day in dates:
            p=float(prices.at[day]);fee=0.
            if day==execution:
                assert units==0
                fee=cash*sum(cost.get(k,0) for k in ['commission_bps','spread_bps','slippage_bps','market_impact_bps'])/10000
                units=(cash-fee)/p;cash=0.
            expected=cash+units*p;actual=float(observed.at[day,'NAV_'+label])*spec['initial_capital']
            error=abs(expected-actual);assert error<=1e-5,(day,label,error)
            records.append(dict(Date=str(day.date()),book=label,shares=units,cash=cash,rights=0,fee=fee,expected_nav=expected,engine_nav=actual,absolute_error=error))
    output.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(records).to_csv(output/'independent_ledger.csv',index=False)
    summary=dict(status='PASS_MODEL_ACCOUNTING',rows=len(records),sessions=len(dates),max_absolute_error=max(r['absolute_error'] for r in records),currency_tolerance=1e-5,official_extension_days=5,zero_advanced_sale_cash=True,source='Original parquet plus direct raw official STK JSON fields, NOT production append loader',investment_approved=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
