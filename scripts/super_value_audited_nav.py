"""Audited single-quarter super-value research. Produces NAV and audits only.

CURRENT v2-16 is imported unchanged. This is an exploratory price-return
replication, not a completed 2000-to-present or total-return backtest.
"""
from __future__ import annotations
import json, sys, re, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import exchange_calendars as xc
import backtest_super_value_v216 as old

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/super_value_audited'
OUT.mkdir(parents=True, exist_ok=True)
C = old.CURRENT
AUDIT = []
# Existing-holder share factors, not changes in total company shares outstanding.
# Rights are deliberately allowed to expire without exercise or sale in this
# conservative PRICE scenario. It is not a total-return reconstruction.
ACTIONS = {
    ('2017-10-30','001620'): (1., 'rights_forfeited', 'https://kind.krx.co.kr/external/2017/10/26/000652/20171026001598/10601.htm'),
    ('2017-10-31','123040'): (1., 'rights_forfeited', 'https://www.ms-global.com/board/mboard.asp?Action=view&strBoardID=stock&intSeq=409'),
    ('2017-12-27','001530'): (1.025, 'stock_dividend_receivable', 'https://www.edaily.co.kr/News/Read?mediaCodeNo=257&newsId=03942566616160816'),
    ('2017-12-27','018670'): (1.01, 'stock_dividend_receivable', 'https://kind.krx.co.kr/external/2018/03/09/000793/20180305000750/91471.htm'),
    ('2018-05-04','001940'): (5., 'split', 'https://www.kiscoholdings.co.kr/holdings/index.php?idx=623&mode=fdn&num=1&pCode=gongo&pg=5'),
    ('2018-12-27','071970'): (.125, 'capital_reduction_8_to_1', 'https://kind.krx.co.kr/external/2021/03/31/002590/20210331005912/11011.htm'),
}

def holder_return(row, dt, code):
    raw=float(row['raw_close_return'])
    if not np.isfinite(raw):raise RuntimeError(f'{dt.date()}: held return missing for {code}')
    action=ACTIONS.get((str(dt.date()),code))
    if bool(row['baseprice_gap']) and action is None:
        raise RuntimeError(f'{dt.date()}: unverified corporate action for {code}')
    return (1+raw)*(action[0] if action else 1.)-1

def exact_metric(row):
    aid = str(row.get('account_id', '')).lower()
    nm = re.sub(r'\s+', '', str(row.get('account_nm', '')))
    sj = str(row.get('sj_div', '')).upper()
    specs = {
        'equity': ({'BS'}, {'ifrs_equity','ifrs-full_equity'}, {'자본총계','총자본','자본합계'}),
        'revenue': ({'IS','CIS'}, {'ifrs_revenue','ifrs-full_revenue'}, {'매출액','매출','영업수익','수익(매출액)','영업수익합계'}),
        'net_income': ({'IS','CIS'}, {'ifrs_profitloss','ifrs-full_profitloss'}, {'당기순이익','당기순이익(손실)','분기순이익','분기순이익(손실)','반기순이익','반기순이익(손실)','연결당기순이익','당기순손익','분기순손익','반기순손익'}),
        'ocf': ({'CF'}, {'ifrs_cashflowsfromusedinoperatingactivities','ifrs-full_cashflowsfromusedinoperatingactivities'}, {'영업활동현금흐름','영업활동으로인한현금흐름','영업활동으로부터의현금흐름','영업활동에의한현금흐름'})
    }
    for key,(statements,ids,names) in specs.items():
        if sj not in statements: continue
        if aid in ids: return key, 0 if sj != 'CIS' else 1
        # Do not use a different standard IFRS account just because its Korean label matches.
        if nm in names and not aid.startswith(('ifrs_', 'ifrs-full_')):
            return key, 2 if sj != 'CIS' else 3
    return None,99

def load_snapshots(year, period):
    cache = OUT / f'cache_{year}_{period}.pkl'
    if cache.exists(): return pd.read_pickle(cache)
    chunks=[]
    cols={'_stock_code','_filing_date','_fs_div_requested','rcept_no','sj_div','account_id','account_nm','thstrm_amount','thstrm_add_amount','currency','_period_end','_collected_at_utc'}
    files=sorted((ROOT/'data/financials/full_history').glob(f'dart_full_{year}_{period}_*.csv.gz'))
    for p in files:
        x=pd.read_csv(p,dtype=str,usecols=lambda z:z in cols)
        # Keep only the statement types needed; custom account names need exact matching below.
        x=x[x.sj_div.isin(['BS','IS','CIS','CF'])].copy()
        aids=x.account_id.fillna('').str.lower()
        names=x.account_nm.fillna('').str.replace(r'\s+','',regex=True)
        match=aids.str.contains('equity|revenue|profitloss|cashflowsfromusedinoperatingactivities',regex=True) | names.str.contains('자본총계|자본합계|총자본|매출|영업수익|순이익|순손익|영업활동',regex=True)
        x=x[match].copy()
        x[['metric','priority']]=pd.DataFrame([exact_metric(r) for r in x.to_dict('records')],index=x.index)
        x=x[x.metric.notna()].copy()
        chunks.append(x)
    x=pd.concat(chunks,ignore_index=True)
    x=x.rename(columns={'_stock_code':'Code','_filing_date':'filing_date','_fs_div_requested':'fs_div'})
    x.Code=x.Code.str.zfill(6)
    x['filing_date']=pd.to_datetime(x.rcept_no.str[:8],format='%Y%m%d',errors='coerce')
    x['current']=x.thstrm_amount.map(old.to_num)
    x['cumulative']=x.thstrm_add_amount.map(old.to_num) if 'thstrm_add_amount' in x else np.nan
    x=x.drop_duplicates(['Code','rcept_no','fs_div','sj_div','account_id','account_nm','current','cumulative'])
    rows=[]
    for (code,fs,rcept,fd),g in x.groupby(['Code','fs_div','rcept_no','filing_date'],dropna=False):
        rec={'Code':code,'fs_div':fs,'rcept_no':rcept,'filing_date':fd}
        currency_ok=set(g.currency.dropna().unique())=={'KRW'}
        for metric in ['equity','revenue','net_income','ocf']:
            z=g[(g.metric==metric)&g[['current','cumulative']].notna().any(axis=1)]
            rec[metric+'_current']=np.nan;rec[metric+'_cum']=np.nan
            if z.empty: continue
            z=z[z.priority==z.priority.min()]
            ambiguous=len(z[['current','cumulative']].drop_duplicates())>1
            best=z.iloc[0]
            AUDIT.append({'year':year,'period':period,'Code':code,'fs_div':fs,'rcept_no':rcept,'filing_date':fd,'metric':metric,'account_id':best.account_id,'account_nm':best.account_nm,'currency':best.currency,'ambiguous':ambiguous,'accepted':currency_ok and not ambiguous})
            if currency_ok and not ambiguous:
                rec[metric+'_current']=best.current;rec[metric+'_cum']=best.cumulative
        rows.append(rec)
    out=pd.DataFrame(rows);out.to_pickle(cache)
    print('normalized',year,period,len(out),'reports',flush=True)
    return out

def prepare():
    # Frozen raw data snapshot supports seven fully queried rebalance signals.
    signals=pd.to_datetime(['2016-10-31','2017-04-28','2017-10-31','2018-04-30','2018-10-31','2019-04-30','2019-10-31'])
    mapping=old.load_map();state=old.load_state();coverage=[]
    for signal in signals:
        ok,rows=old.signal_completeness(mapping,state,signal)
        coverage.extend(rows)
        if not ok:raise RuntimeError(f'Incomplete collection at {signal}')
    pd.DataFrame(coverage).to_csv(OUT/'collection_coverage.csv',index=False)
    required=sorted(set(p for s in signals for p in old.required_periods(s)))
    cache={p:load_snapshots(*p) for p in required}
    if AUDIT:pd.DataFrame(AUDIT).to_csv(OUT/'account_audit.csv',index=False)
    panel=C.load_krx_equity_panel(start='2016-09-01',end='2020-04-29',repo_root=ROOT,
        columns=['Date','Code','Name','Market','Close','Open','High','Low','Volume','Amount','Marcap','Stocks','ChangesRatio'])
    panel['Change']=pd.to_numeric(panel.ChangesRatio,errors='coerce')/100
    panel=panel.sort_values(['Date','Code'])
    # Detect corporate-action discontinuities without assuming that KRX base-price return
    # by itself accounts for rights, spin-off entitlements or cash dividends.
    by=panel.groupby('Code',sort=False)
    panel['raw_close_return']=by.Close.pct_change(fill_method=None)
    panel['share_change']=by.Stocks.pct_change(fill_method=None)
    panel['baseprice_gap']=(panel.raw_close_return-panel.Change).abs()>0.0001
    selections={n:{} for n in (20,30,50)};audits=[];all_sel=[];factors_all=[]
    for s in signals:
        factors=old.build_factor_table(s,cache)
        assert (pd.to_datetime(factors.available_date).dropna()<=s).all()
        factors_all.append(factors.assign(signal_date=s))
        for n in selections:
            sel,a=old.build_selection(panel,s,factors,n)
            selections[n][s]=sel;audits.append(dict(a,top_n=n));all_sel.append(sel.assign(top_n=n))
    pd.concat(all_sel).to_csv(OUT/'selections.csv',index=False)
    pd.concat(factors_all).to_csv(OUT/'factor_panel.csv',index=False)
    pd.DataFrame(audits).to_csv(OUT/'universe_audit.csv',index=False)
    return panel,selections

def simulate(panel, selections, n, scenario, lag=1):
    dates=pd.DatetimeIndex(sorted(panel.Date.unique()))
    events={dates[dates.searchsorted(s,side='right')+lag-1]:(s,sel) for s,sel in selections.items()}
    first=min(events);dates=dates[(dates>=first)&(dates<=pd.Timestamp('2020-04-29'))]
    held={};cash=1.;nav=1.;out=[];trades=[];issues=[]
    desired=None;pending=set();active_signal=None;cash_desired=0.
    cost=old.COSTS[scenario]
    lookup={dt:g.set_index('Code') for dt,g in panel.groupby('Date')}
    for dt in dates:
        day=lookup[dt];values={}
        for code,w in held.items():
            if code not in day.index or not np.isfinite(day.loc[code,'Change']):
                raise RuntimeError(f'{dt.date()}: held return missing for {code}; no invented delisting recovery')
            r=holder_return(day.loc[code],dt,code)
            if r < -1:raise RuntimeError('return below -100%')
            values[code]=w*(1+r)
            if day.loc[code,'baseprice_gap']:
                factor,policy,source=ACTIONS[(str(dt.date()),code)]
                issues.append({'Date':dt,'Code':code,'Name':day.loc[code,'Name'],'weight':w,'raw_close_return':day.loc[code,'raw_close_return'],'KRX_return':day.loc[code,'Change'],'holder_return':r,'share_factor':factor,'share_change':day.loc[code,'share_change'],'issue':policy,'source':source})
        total=cash+sum(values.values());nav*=total
        held={k:v/total for k,v in values.items()};cash/=total
        def tradable(code):
            if code not in day.index:return False
            z=day.loc[code]
            return bool(z.Volume>0 and z.Close>0 and not ((z.High==z.Low) and abs(z.Change)>=0.295))
        retry=bool(pending and any(tradable(code) for code in pending))
        if dt in events or retry:
            blocked=[]
            if dt in events:
                signal,sel=events[dt];active_signal=signal;desired={}
            else:
                signal=active_signal;sel=None
            for code in ([] if sel is None else sel.Code):
                if tradable(code):desired[code]=1/n
                elif code in held:
                    # Existing stock cannot be sold or resized during suspension.
                    desired[code]=1/n
                else:blocked.append(code)
            if sel is not None:cash_desired=1-sum(desired.values())
            locked={code:w for code,w in held.items() if not tradable(code)}
            pending=set(locked)
            locked_weight=sum(locked.values())
            free_desired={code:w for code,w in desired.items() if code not in locked and tradable(code)}
            denominator=cash_desired+sum(free_desired.values())
            if denominator<=1e-14:
                free_proportions={};cash_proportion=1.
            else:
                free_proportions={code:w/denominator for code,w in free_desired.items()};cash_proportion=cash_desired/denominator
            # Solve self-financing costs while preserving the monetary value of frozen holdings.
            tax=0 if not cost.apply_sell_tax else (30. if dt<pd.Timestamp('2019-05-30') else 25.)
            assumptions=C.TradingCostAssumptions(commission_bps=cost.commission_bps,spread_bps=cost.spread_bps,slippage_bps=cost.slippage_bps,market_impact_bps=cost.market_impact_bps,sell_tax_bps=tax)
            fee=0.
            for _ in range(60):
                available=1-fee-locked_weight
                if available < -1e-12:raise RuntimeError('Insufficient liquid funds for costs')
                target_values=dict(locked)
                target_values.update({k:v*max(0,available) for k,v in free_proportions.items()})
                keys=set(held)|set(target_values)
                buy=sum(max(0,target_values.get(k,0)-held.get(k,0)) for k in keys)
                sell=sum(max(0,held.get(k,0)-target_values.get(k,0)) for k in keys)
                new_fee=float(C.calculate_trading_cost_fraction(pd.Series([buy]),pd.Series([sell]),assumptions).iloc[0])
                if abs(new_fee-fee)<1e-14:break
                fee=new_fee
            else:raise RuntimeError('Self-financing cost solver did not converge')
            nav*=1-fee;held={k:v/(1-fee) for k,v in target_values.items() if v>1e-14}
            cash=max(0,1-fee-locked_weight)*cash_proportion/(1-fee)
            trades.append({'signal_date':signal,'execution_date':dt,'top_n':n,'scenario':scenario,'lag_sessions':lag,'buy_turnover':buy,'sell_turnover':sell,'cost_fraction':fee,'blocked_buys':'|'.join(blocked),'locked_holdings':'|'.join(locked),'retry_after_suspension':retry,'cash_weight':cash})
        assert abs(sum(held.values())+cash-1)<1e-9
        out.append((dt,nav))
    return pd.Series(dict(out)),pd.DataFrame(trades),pd.DataFrame(issues)

def main():
    panel,sels=prepare();series={};trade_all=[];issues_all=[];failures=[]
    for n,scenario,lag in [(20,'gross',1),(20,'minimum',1),(20,'base',1),(20,'conservative',1),(30,'base',1),(50,'base',1),(20,'base',2)]:
        name=f'Top{n}_{scenario}'+('_lag2' if lag==2 else '')
        try:
            nav,tr,iss=simulate(panel,sels[n],n,scenario,lag);series[name]=nav
            trade_all.append(tr);issues_all.append(iss.assign(variant=name))
            print('NAV',name,len(nav),float(nav.iloc[-1]),'corporate events',len(iss),flush=True)
        except RuntimeError as e:
            failures.append({'variant':name,'error':str(e)});print('BLOCKED',name,str(e),flush=True)
    (OUT/'execution_failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2))
    if 'Top20_base' not in series:raise RuntimeError('Base execution failed; no valid base NAV published')
    nav=pd.DataFrame(series).sort_index();nav.index.name='Date'
    # Lagged variant is cash until its later first trade.
    nav['Top20_base_lag2']=nav['Top20_base_lag2'].fillna(1.) if 'Top20_base_lag2' in nav else np.nan
    if nav.isna().all().any():nav=nav.dropna(axis=1,how='all')
    bench=old.load_kospi_nav(nav.index[0],nav.index[-1],pd.Timestamp('2016-10-31')).reindex(nav.index)
    if bench.isna().any():raise RuntimeError('Benchmark missing session')
    nav['KOSPI']=bench
    sessions=xc.get_calendar('XKRX').sessions_in_range(nav.index[0],nav.index[-1])
    assert nav.index.equals(pd.DatetimeIndex(sessions).tz_localize(None))
    assert nav.notna().all().all()
    nav.to_csv(OUT/'daily_nav.csv')
    pd.concat(trade_all).to_csv(OUT/'trades.csv',index=False)
    pd.concat(issues_all).to_csv(OUT/'corporate_action_audit.csv',index=False)
    old.adv_audit(panel,sels[20]).to_csv(OUT/'liquidity.csv',index=False)
    meta={'template_version':C.TEMPLATE_VERSION,'template_sha256':hashlib.sha256((ROOT/'scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py').read_bytes()).hexdigest(),'source_commit':'571c7627bb7efb90b97920fca8a7a737b22bf5b4','strategy':'original super value, latest standalone quarter, rank inverse ratios','status':'EXPLORATORY_RIGHTS_FORFEITED_PRICE_SCENARIO','baseline':'2016-10-31','start':str(nav.index[0].date()),'end':str(nav.index[-1].date()),'sessions':len(nav),'initial_capital_krw':10000000,'all_held_returns_observed':True,'dividends':'cash dividends excluded; stock dividends marked as share receivables on ex-date; fractional shares allowed; delivery dates/tax not modeled', 'corporate_actions':'raw close returns with six sourced share-factor/policy events; all other >1bp KRX-vs-close gaps block execution; rights forfeited with zero credit; suspension carried at last quote; not total return','universe':'PIT KOSPI/KOSDAQ; no ex-post survivors filter; no sector/management/new-listing exclusion; all four KRW accounts required; preferred/SPAC/REIT not explicitly excluded','missing_factors':'logged in universe_audit.csv; no zero imputation','account_definition':'exact total equity, total net profit, revenue, operating cash flow; CFS first, OFS fallback; negative values retained','quarter':'April FY minus Q3 YTD; October H1 three-month earnings/revenue, OCF H1 minus Q1','pit_limit':'filing receipt date gate; overwritten/restated original filings not reconstructed; NO_DATA is not proof of historical absence','trade':'next session close, new holdings earn starting following session; unavailable new buy allocation held as cash, no replacement; fail on missing held return; frozen holdings retained until tradable, then rebalance remaining capital','calendar':'XKRX, exact session equality checked'}
    (OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
