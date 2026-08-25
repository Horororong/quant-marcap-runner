from pathlib import Path
import math
import numpy as np
import pandas as pd
import yfinance as yf

START = pd.Timestamp('1990-01-01')
INITIAL = 10_000.0
COST_BPS = 5.0
LOOKBACK = 756  # ~3 trading years
N_SELECT = 4
OUT = Path('results/moat_anti_overheat')
OUT.mkdir(parents=True, exist_ok=True)

# 2026 current-moat candidate universe. This is intentionally a hindsight-defined universe,
# so results are exploratory rather than a clean point-in-time stock-selection backtest.
CANDIDATES = ['ASML','TSM','NVDA','AVGO','GOOGL','MSFT','AAPL','AMZN','META','ORCL']


def download_adj(ticker, start, end):
    df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=(end + pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
                     progress=False, auto_adjust=False, actions=False, threads=False)
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        if ('Adj Close', ticker) in df.columns:
            s = df[('Adj Close', ticker)]
        elif ('Close', ticker) in df.columns:
            s = df[('Close', ticker)]
        else:
            s = df.xs('Close', axis=1, level=0).iloc[:,0]
    else:
        col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        s = df[col]
    s = pd.to_numeric(s, errors='coerce').dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.sort_index()


def one_way_turnover(old_w, new_w):
    keys = sorted(set(old_w) | set(new_w))
    return 0.5 * sum(abs(old_w.get(k,0.0)-new_w.get(k,0.0)) for k in keys)


def metrics(nav):
    r = nav.pct_change().dropna()
    years = (nav.index[-1]-nav.index[0]).days/365.25
    cagr = (nav.iloc[-1]/nav.iloc[0])**(1/years)-1
    peak = nav.cummax(); dd = nav/peak-1
    mdd = float(dd.min())
    vol = float(r.std(ddof=1)*np.sqrt(252))
    sharpe = float(r.mean()/r.std(ddof=1)*np.sqrt(252)) if r.std(ddof=1)>0 else np.nan
    return {'Start':nav.index[0].date().isoformat(),'End':nav.index[-1].date().isoformat(),
            'Final_NAV':float(nav.iloc[-1]),'CAGR':float(cagr),'Ann_Vol':vol,'MDD':mdd,'Sharpe_rf0':sharpe}


def main():
    base = pd.read_csv('results/anchor_sail_moat/asset_returns_daily.csv', index_col=0, parse_dates=True)
    base.index = pd.to_datetime(base.index)
    base = base.loc[base.index >= START]
    master = base.index
    gold_ret = base['금'].astype(float)
    tbill_ret = base['단기채'].astype(float)
    end = master[-1]

    prices = pd.DataFrame(index=master)
    for t in CANDIDATES:
        s = download_adj(t, START - pd.Timedelta(days=1200), end)
        prices[t] = s.reindex(master).ffill()

    returns = prices.pct_change().fillna(0.0)
    # Rebalance on first master trading day of each calendar year.
    rebalance_dates = pd.Series(master, index=master).groupby(master.year).first().values
    rebalance_dates = pd.DatetimeIndex(rebalance_dates)

    current_weights = {'GOLD':0.30,'TBILL':0.70}  # until first rebalance decision
    values = {k: INITIAL*w for k,w in current_weights.items()}
    nav_rows=[(master[0],INITIAL)]
    selection_rows=[]
    trade_rows=[]
    rset=set(rebalance_dates)

    for i,date in enumerate(master[1:], start=1):
        # accrue today's asset returns using holdings decided previously
        new_values={}
        for k,v in values.items():
            if k=='GOLD': rr=float(gold_ret.loc[date])
            elif k=='TBILL': rr=float(tbill_ret.loc[date])
            else: rr=float(returns.loc[date,k])
            new_values[k]=v*(1+rr)
        values=new_values
        nav_pre=sum(values.values())

        if date in rset:
            prev_dates = master[master < date]
            signal_date = prev_dates[-1]
            scored=[]
            for t in CANDIDATES:
                hist = prices.loc[prices.index <= signal_date, t].dropna()
                if len(hist) < LOOKBACK:
                    continue
                px=float(hist.iloc[-1])
                med=float(hist.iloc[-LOOKBACK:].median())
                if med>0:
                    scored.append((t, px/med, px, med))
            scored.sort(key=lambda x:x[1])
            selected=[x[0] for x in scored[:N_SELECT]]
            new_w={'GOLD':0.30,'TBILL':0.30 + 0.10*(N_SELECT-len(selected))}
            for t in selected:
                new_w[t]=0.10
            # trading cost on one-way turnover of whole portfolio
            old_w={k:v/nav_pre for k,v in values.items()}
            turn=one_way_turnover(old_w,new_w)
            cost=nav_pre*turn*COST_BPS/10000.0
            nav_post=nav_pre-cost
            values={k:nav_post*w for k,w in new_w.items()}
            current_weights=new_w
            trade_rows.append({'Date':date,'Turnover':turn,'Cost_USD':cost})
            scoremap={x[0]:x[1] for x in scored}
            selection_rows.append({'Year':date.year,'SignalDate':signal_date.date().isoformat(),
                                   'Selected':','.join(selected),
                                   'EligibleCount':len(scored),
                                   'Scores_Selected':';'.join([f'{t}:{scoremap[t]:.3f}' for t in selected])})
            nav=nav_post
        else:
            nav=nav_pre
        nav_rows.append((date,nav))

    nav = pd.Series(dict(nav_rows), name='Moat_AntiOverheat_NAV').sort_index()
    nav.to_csv(OUT/'daily_nav.csv', encoding='utf-8-sig')
    pd.DataFrame(selection_rows).to_csv(OUT/'annual_selections.csv', index=False, encoding='utf-8-sig')
    trades=pd.DataFrame(trade_rows); trades.to_csv(OUT/'rebalance_trades.csv', index=False, encoding='utf-8-sig')

    # Comparators from already-generated repository results.
    cmp = pd.read_csv('results/anchor_sail_moat/daily_nav.csv', index_col=0, parse_dates=True)
    cmp.index=pd.to_datetime(cmp.index)
    frame=pd.DataFrame({'해자+과열회피':nav,
                        '기존 해자기업 고정':cmp['닻과 돛(해자기업)'].reindex(nav.index),
                        'NASDAQ 40%':cmp['닻과 돛(NASDAQ 40%)'].reindex(nav.index),
                        'S&P500 100%':cmp['S&P500 100%'].reindex(nav.index)}).dropna()
    frame.to_csv(OUT/'comparison_daily_nav.csv', encoding='utf-8-sig')

    rows=[]
    for c in frame.columns:
        m=metrics(frame[c]); m['Strategy']=c; rows.append(m)
    pd.DataFrame(rows).set_index('Strategy').to_csv(OUT/'summary.csv', encoding='utf-8-sig')

    # Year-by-year return and within-year MDD for new strategy.
    yr=[]
    for year,g in nav.groupby(nav.index.year):
        prev=nav.loc[nav.index < g.index[0]]
        startv=float(prev.iloc[-1]) if len(prev) else float(g.iloc[0])
        path=pd.concat([pd.Series([startv],index=[g.index[0]-pd.Timedelta(microseconds=1)]),g])
        ret=float(g.iloc[-1]/startv-1)
        mdd=float((path/path.cummax()-1).min())
        yr.append({'Year':int(year),'Annual_Return':ret,'Annual_MDD':mdd,'Year_End_NAV':float(g.iloc[-1])})
    pd.DataFrame(yr).to_csv(OUT/'yearly_return_mdd.csv', index=False, encoding='utf-8-sig')

    (OUT/'ASSUMPTIONS.md').write_text(f'''# Moat + anti-overheat exploratory backtest\n\n- Period: {nav.index[0].date()} ~ {nav.index[-1].date()}\n- Base: Gold 30% + 3M T-Bill 30% + moat sleeve 40%\n- Candidate universe (defined with 2026 hindsight): {', '.join(CANDIDATES)}\n- Annual signal: previous trading day only\n- Eligibility: at least ~3 trading years ({LOOKBACK} observations) of own price history\n- Overheat score: current adjusted price / median adjusted price of previous {LOOKBACK} trading days\n- Select the 4 LOWEST scores each year; equal 10% each\n- If fewer than 4 eligible names, unused 10% slots remain in T-Bills\n- Rebalance: first trading day each year\n- Trading cost: 5bp on one-way turnover\n- Taxes: excluded\n- IMPORTANT: this is NOT a historical valuation backtest because PIT P/E or P/S data are unavailable in the repository. It tests price-overheat avoidance inside a present-day moat candidate universe.\n- IMPORTANT: candidate-universe survivorship/hindsight bias remains.\n''', encoding='utf-8')
    print(pd.read_csv(OUT/'summary.csv').to_string(index=False))
    print(pd.DataFrame(selection_rows).tail(10).to_string(index=False))

if __name__=='__main__':
    main()
