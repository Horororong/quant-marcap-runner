"""Source restoration and actual public-mode regressions, not investment results."""
from pathlib import Path
import io
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from krx_market_normalization import normalize_markets
from repair_krx_market_segments import prepare_repair, repair, sha256
from strategy_dsl_runner import load_project_engine, run_strategy
from update_krx_equities_daily import _standardize, _write_year

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'docs/audits/kosdaq-global-repair'
PIN = 'a'*40


def fails(call, message=''):
    try:
        call()
    except (ValueError, AssertionError, RuntimeError, OSError) as exc:
        assert message in str(exc), exc
    else:
        raise AssertionError('Invalid market/source data was accepted')


def parquet_bytes(panel):
    stream = io.BytesIO()
    panel.to_parquet(stream, index=False)
    return stream.getvalue()


def normalization_tests():
    raw = pd.DataFrame({'Date': pd.to_datetime(['2024-06-13','2024-06-14','2024-10-28','2024-06-14','2024-06-14']),
        'Code': ['287410','287410','287410','001465','000001'],
        'Market': ['KOSDAQ','KOSDAQ GLOBAL','KOSDAQ','KOSPI','KONEX'],
        'MarketId': ['KSQ','KSQ','KSQ','STK','KNX'],
        'Close': [12800,12800,12900,17100,100], 'Volume': [10,11,0,20,30],
        'ChangesRatio': [.08,0,0,-14.03,0], 'Stocks': [10]*5})
    original = raw.copy(deep=True)
    normalized = _standardize(parquet_bytes(raw))
    assert len(normalized)==4 and set(normalized.Code)=={'287410','001465'}
    assert normalized[normalized.Code.eq('287410')].Market.eq('KOSDAQ').all()
    assert normalized[normalized.Code.eq('287410')].sort_values('Date').SourceMarket.tolist()==['KOSDAQ','KOSDAQ GLOBAL','KOSDAQ']
    assert normalized[normalized.Code.eq('001465')].Close.iloc[0]==17100  # preferred shares retained
    pd.testing.assert_frame_equal(raw, original)
    again = normalize_markets(normalized)
    pd.testing.assert_frame_equal(normalized, again)
    lower = raw.assign(Market=[' kosdaq ','kosdaq global','KOSDAQ','KOSPI','KONEX'])
    assert normalize_markets(lower).SourceMarket.iloc[1]=='kosdaq global'
    for label in ['KOSDAQ NEW SEGMENT','KOSDAQ GLOBAL UNKNOWN','',None]:
        fails(lambda: _standardize(parquet_bytes(raw.assign(Market=label))), 'Unknown KRX market')
    fails(lambda: normalize_markets(raw.assign(MarketId='STK')), 'MarketId disagrees')
    fails(lambda: normalize_markets(normalized.assign(SourceMarket='KOSPI')), 'SourceMarket provenance')
    # Invalid upstream classification must be rejected before overwriting a stored year.
    with tempfile.TemporaryDirectory() as td:
        target=Path(td)/'marcap-2024.parquet'; target.write_bytes(b'original')
        with patch('update_krx_equities_daily.RAW_DIR',Path(td)), patch('update_krx_equities_daily._download_year',return_value=parquet_bytes(raw.assign(Market='KOSDAQ NEW SEGMENT'))):
            fails(lambda: _write_year(2024, overwrite=True),'Unknown KRX market')
        assert target.read_bytes()==b'original'


def fixture(root, source_dir, year=2024):
    dates=pd.to_datetime([f'{year}-06-13',f'{year}-06-14',f'{year}-06-17'])
    raw=pd.DataFrame({'Date':dates,'Code':'000001','Market':['KOSDAQ','KOSDAQ GLOBAL','KOSDAQ'],
        'MarketId':'KSQ','Close':[100.,101.,102.],'Volume':100.,'ChangesRatio':[0.,1.,.99],'Stocks':1000.})
    source=source_dir/f'marcap-{year}.parquet'; raw.to_parquet(source,index=False)
    legacy=_standardize(parquet_bytes(raw[raw.Market.eq('KOSDAQ')])).drop(columns='SourceMarket')
    path=root/f'data/krx_equities/yearly/marcap-{year}.parquet';path.parent.mkdir(parents=True,exist_ok=True)
    legacy.to_parquet(path,index=False)
    record={'year':year,'url':f'https://raw.githubusercontent.com/FinanceData/marcap/{PIN}/data/marcap-{year}.parquet',
        'upstream_sha256':sha256(source),'stored_sha256':sha256(path)}
    return path,source,record


def repair_tests():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);sources=root/'source';sources.mkdir();path,source,record=fixture(root,sources)
        original=path.read_bytes();original_panel=pd.read_parquet(path)
        manifest=root/'manifest.json';manifest.write_text(json.dumps({'upstream_commit':PIN,'years':[record]}))
        report=root/'audit/repair.json'
        dry=repair(manifest,sources,root,report)
        assert dry['status']=='dry_run' and dry['total_added_rows']==1 and path.read_bytes()==original
        applied=repair(manifest,sources,root,report,apply=True)
        assert applied['status']=='applied' and applied['total_added_rows']==1
        restored=pd.read_parquet(path)
        assert restored.Date.tolist()==pd.to_datetime(['2024-06-13','2024-06-14','2024-06-17']).tolist()
        assert restored.Close.tolist()==[100.,101.,102.] and restored.Market.eq('KOSDAQ').all()
        retained=restored[restored.Date.ne('2024-06-14')][original_panel.columns].reset_index(drop=True)
        pd.testing.assert_frame_equal(retained,original_panel,check_dtype=False)
        proof=root/'audit'/applied['years'][0]['added_observations_file']
        assert sha256(proof)==applied['years'][0]['added_observations_sha256']
        assert pd.read_csv(proof).Close.tolist()==[101.]
        repaired_bytes=path.read_bytes()
        replay=repair(manifest,sources,root,root/'replay/result.json',apply=True)
        assert replay['total_added_rows']==0 and path.read_bytes()==repaired_bytes
        # Wrong source identity, price corrections, additional ordinary-market gaps and duplicates cannot be inferred.
        path.write_bytes(original)
        fails(lambda: prepare_repair(path,source,{**record,'upstream_sha256':'0'*64}),'SHA256 mismatch')
        changed=original_panel.copy();changed.loc[0,'Close']=99.;changed.to_parquet(path,index=False)
        fails(lambda: prepare_repair(path,source,record),'Close')
        path.write_bytes(original)
        original_panel.to_parquet(path,index=False,compression='gzip')
        fails(lambda: prepare_repair(path,source,record),'Stored file moved')
        path.write_bytes(original)
        raw=pd.read_parquet(source);raw.loc[1,'Market']='KOSDAQ';raw.to_parquet(source,index=False)
        fails(lambda: prepare_repair(path,source,{**record,'upstream_sha256':sha256(source)}),'non-segment')
        pd.concat([raw,raw.iloc[:1]]).to_parquet(source,index=False)
        fails(lambda: prepare_repair(path,source,{**record,'upstream_sha256':sha256(source)}),'Duplicate')
    # Every source is staged and verified before any year can be changed; failed replacement rolls back.
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);sources=root/'source';sources.mkdir()
        a,_,ra=fixture(root,sources,2024);b,_,rb=fixture(root,sources,2025)
        originals=[a.read_bytes(),b.read_bytes()];manifest=root/'manifest.json';out=root/'audit/report.json'
        def write(records):manifest.write_text(json.dumps({'upstream_commit':PIN,'years':records}))
        write([ra,{**rb,'upstream_sha256':'0'*64}])
        fails(lambda: repair(manifest,sources,root,out,apply=True),'SHA256 mismatch')
        assert [a.read_bytes(),b.read_bytes()]==originals and not out.exists()
        write([ra,rb]);import os
        replace=os.replace;count=0
        def interrupted(src,dst):
            nonlocal count
            count+=1
            if count==2:raise OSError('independent write failure')
            return replace(src,dst)
        with patch('repair_krx_market_segments.os.replace',side_effect=interrupted):
            fails(lambda: repair(manifest,sources,root,out,apply=True),'independent write failure')
        assert [a.read_bytes(),b.read_bytes()]==originals and not out.exists()
        assert not list(root.rglob('*.repair.tmp'))


def restored_source_tests():
    report=json.loads((AUDIT/'repair_report.json').read_text())
    assert report['status']=='applied' and report['total_added_rows']==46753
    assert [r['added_rows'] for r in report['years']]==[1479,12332,11718,12160,9064]
    for r in report['years']:
        evidence=AUDIT/r['added_observations_file']
        assert sha256(evidence)==r['added_observations_sha256']
        expected=pd.read_csv(evidence,dtype={'Code':str},parse_dates=['Date'],float_precision='round_trip')
        panel=pd.read_parquet(ROOT/f"data/krx_equities/yearly/marcap-{r['year']}.parquet")
        assert not panel.duplicated(['Date','Code']).any()
        window=panel[panel.Date.between(r['stored_start'],r['stored_end'])]
        assert len(window)==r['after_rows']
        assert len(expected)==r['added_rows'] and expected.Code.nunique()==r['added_codes']
        assert window.SourceMarket.eq('KOSDAQ GLOBAL').sum()==len(expected)
        observed=window.set_index(['Date','Code']).loc[expected.set_index(['Date','Code']).index].reset_index()[expected.columns]
        pd.testing.assert_frame_equal(observed,expected,check_dtype=False,check_index_type=False,check_exact=True)
        assert observed.Market.eq('KOSDAQ').all()
    # Both historical membership transitions retain the same security and actual values.
    panel=pd.read_parquet(ROOT/'data/krx_equities/yearly/marcap-2024.parquet')
    jeisys=panel[panel.Code.eq('287410')].set_index('Date')
    assert len(jeisys)==207 and jeisys.SourceMarket.eq('KOSDAQ GLOBAL').sum()==89
    assert jeisys.loc[['2024-06-13','2024-06-14','2024-10-25','2024-10-28'],'SourceMarket'].tolist()==['KOSDAQ','KOSDAQ GLOBAL','KOSDAQ GLOBAL','KOSDAQ']
    assert jeisys.loc[['2024-06-13','2024-06-14','2024-10-25','2024-10-28'],'Close'].tolist()==[12800,12800,12900,12900]
    assert jeisys.Market.eq('KOSDAQ').all()


def real_public_modes():
    panel=pd.read_parquet(ROOT/'data/krx_equities/yearly/marcap-2024.parquet')
    # Only May 31 observations determine eligibility; membership is not a survival filter.
    signal=panel[panel.Date.eq('2024-05-31')&panel.Market.eq('KOSDAQ')&panel.Volume.gt(0)&panel.Marcap.between(800000000000,1200000000000)]
    codes=signal.sort_values(['Marcap','Code'],ascending=[False,True]).Code.tolist()
    assert len(codes)==43 and signal.SourceMarket.eq('KOSDAQ GLOBAL').sum()==11
    assert codes.index('287410')==27
    spec=json.loads((ROOT/'config/strategies/kr_equity_market_segment_research.json').read_text())
    buy=pd.Timestamp('2024-06-03');transition=pd.Timestamp('2024-06-14')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for mode in ('top_n','deciles'):
            spec['portfolio']={'selection':mode,'weighting':'equal'}
            if mode=='top_n':spec['portfolio']['number_of_positions']=30
            path=td/f'{mode}.json';path.write_text(json.dumps(spec));out=td/mode
            result=run_strategy(path,ROOT,out,postprocess=False)
            groups={'top_n':codes[:30]} if mode=='top_n' else {f'D{i+1:02d}':list(g) for i,g in enumerate(np.array_split(codes,10))}
            daily=pd.read_csv(out/'daily_nav.csv',parse_dates=['Date']).set_index('Date')
            selections=pd.read_csv(out/('selections.csv' if mode=='top_n' else 'decile_membership.csv'),dtype={'Code':str})
            assert set(selections.Code)==set(codes[:30] if mode=='top_n' else codes)
            for label,holdings in groups.items():
                price=panel[panel.Code.isin(holdings)].pivot(index='Date',columns='Code',values='Close').reindex(daily.index)[holdings]
                values=price.loc[buy:]/price.loc[buy]
                assert np.isfinite(values).all().all()
                oracle=pd.Series(1.,index=daily.index);oracle.loc[buy:]=values.mean(axis=1)
                net=oracle.copy();net.loc[buy:]*=1-9.5/10000
                prefix='NAV_' if mode=='top_n' else f'NAV_{label}_'
                assert np.allclose(daily[prefix+'Gross'],oracle,atol=1e-12,rtol=0),label
                assert np.allclose(daily[prefix+'Net_fixed'],net,atol=1e-12,rtol=0),label
                assert daily.loc[:'2024-05-31',prefix+'Gross'].eq(1.).all()
            if mode=='top_n':
                for execution in result['engine_result']['execution_scenarios'].values():
                    assert pd.Timestamp(execution['execution_schedule'].iloc[0].execution_date)==buy
                    assert execution['trades'].loc[transition,['buy_turnover','sell_turnover','cost_fraction']].eq(0).all()
                    assert execution['corporate_actions'].empty and execution['return_reference_check']['enabled']
            else:
                trades=pd.read_csv(out/'execution_trades.csv')
                assert trades[trades.Date.eq(str(transition.date()))][['buy_turnover','sell_turnover','cost_fraction']].eq(0).all().all()
            # Reproduce the original classification bug: loss of a held GLOBAL row must stop before outputs.
            damaged=panel[panel.Date.between(spec['period']['start'],spec['period']['end']) & ~panel.SourceMarket.eq('KOSDAQ GLOBAL')]
            engine=load_project_engine(ROOT);module='strategy_dsl_runner' if mode=='top_n' else 'strategy_dsl_deciles'
            blocked=td/f'{mode}_original_bug'
            with patch(f'{module}.load_project_engine',return_value=engine),patch.object(engine,'load_krx_equity_panel',return_value=damaged):
                fails(lambda: run_strategy(path,ROOT,blocked,postprocess=False))
            assert not blocked.exists()
    print('KRX MARKET NORMALIZATION, EXACT RESTORATION AND BOTH PUBLIC MODES: PASS')


if __name__=='__main__':
    normalization_tests()
    repair_tests()
    restored_source_tests()
    real_public_modes()
