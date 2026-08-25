from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yfinance as yf

START = pd.Timestamp('1990-01-01')
INITIAL = 10_000.0
BASE_COST_BPS = 5.0
TBILL_DAYS = 91.0
OUT = Path('results/anchor_sail_moat')
OUT.mkdir(parents=True, exist_ok=True)

MOAT_TICKERS = {
    'ASML': 'ASML',   # EUV lithography / semiconductor equipment bottleneck
    'TSM': 'TSM',     # leading-edge foundry / process know-how
    'NVDA': 'NVDA',   # accelerated-computing platform / CUDA ecosystem
    'GOOGL': 'GOOGL', # search-distribution-data-cloud/AI platform
}


def load_price_csv(path, preferred=('Adj Close', 'Close')):
    df = pd.read_csv(path)
    if 'Date' not in df.columns:
        raise RuntimeError(f'Date column missing: {path}')
    df['Date'] = pd.to_datetime(df['Date'])
    for col in preferred:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors='coerce')
            return pd.Series(s.values, index=df['Date'], name=Path(path).stem).sort_index().dropna()
    raise RuntimeError(f'No usable price column in {path}')


def load_sp500_long():
    candidates = [Path('data/indices/SP500_LONG.csv'), Path('data/proxy_long/raw/SP500_PRICE.csv')]
    for p in candidates:
        if p.exists():
            try:
                s = load_price_csv(p, preferred=('Adj Close', 'Close', 'Value'))
                s = s[s.index >= START]
                if len(s) > 5000:
                    return s
            except Exception:
                pass
    # external fallback only if repository long series cannot be used
    return download_yf('^GSPC', START)


def load_nasdaq_repo_plus_fallback(end):
    p = Path('data/indices/NASDAQ_COMPOSITE.csv')
    repo = load_price_csv(p) if p.exists() else pd.Series(dtype=float)
    repo = repo[(repo.index >= START) & (repo.index <= end)]
    if len(repo) and repo.index.min() <= START + pd.Timedelta(days=10):
        return repo
    # Repository currently begins in 1995; fetch only the missing early segment, then splice.
    missing_end = (repo.index.min() - pd.Timedelta(days=1)) if len(repo) else end
    ext = download_yf('^IXIC', START, missing_end + pd.Timedelta(days=1))
    out = pd.concat([ext[ext.index < repo.index.min()] if len(repo) else ext, repo]).sort_index()
    return out[~out.index.duplicated(keep='last')]


def load_gold():
    p = Path('data/proxy_long/raw/GOLD_LBMA_PM_USD.csv')
    df = pd.read_csv(p)
    df['Date'] = pd.to_datetime(df['Date'])
    col = 'Close' if 'Close' in df.columns else 'Value'
    s = pd.to_numeric(df[col], errors='coerce')
    return pd.Series(s.values, index=df['Date'], name='Gold').sort_index().dropna()


def load_tbill_yield():
    p = Path('data/proxy_long/raw/US_3M_TBILL.csv')
    df = pd.read_csv(p)
    df['Date'] = pd.to_datetime(df['Date'])
    col = 'Value' if 'Value' in df.columns else 'Close'
    s = pd.to_numeric(df[col], errors='coerce')
    return pd.Series(s.values, index=df['Date'], name='DTB3').sort_index()


def download_yf(ticker, start, end=None):
    kwargs = dict(start=start.strftime('%Y-%m-%d'), progress=False, auto_adjust=False, actions=False, threads=False)
    if end is not None:
        kwargs['end'] = pd.Timestamp(end).strftime('%Y-%m-%d')
    df = yf.download(ticker, **kwargs)
    if df is None or len(df) == 0:
        raise RuntimeError(f'yfinance returned no data for {ticker}')
    if isinstance(df.columns, pd.MultiIndex):
        if ('Adj Close', ticker) in df.columns:
            s = df[('Adj Close', ticker)]
        elif ('Close', ticker) in df.columns:
            s = df[('Close', ticker)]
        else:
            s = df.xs('Close', axis=1, level=0).iloc[:, 0]
    else:
        col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        s = df[col]
    s = pd.to_numeric(s, errors='coerce').dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.sort_index()


def tbill_effective_annual(discount_yield_pct):
    d = float(discount_yield_pct) / 100.0
    denom = 360.0 - d * TBILL_DAYS
    return (365.0 * d) / denom if denom > 0 else 0.0


def price_return_on_master(price, master):
    p = price.reindex(master).ffill()
    r = p.pct_change().fillna(0.0)
    return r


def tbill_return_on_master(yield_series, master):
    y = yield_series.reindex(pd.date_range(yield_series.index.min(), master.max(), freq='D')).ffill()
    out = pd.Series(0.0, index=master)
    for prev, date in zip(master[:-1], master[1:]):
        rate = y.loc[prev]
        if pd.isna(rate):
            rate = 0.0
        ann = tbill_effective_annual(rate)
        days = (date - prev).days
        out.loc[date] = (1.0 + ann) ** (days / 365.25) - 1.0
    return out


def first_rebalance_year_after_listing(company_price, master):
    first = company_price.index.min()
    year = first.year + 1
    eligible = master[master.year >= year]
    if len(eligible) == 0:
        raise RuntimeError('No eligible rebalance date after listing')
    return eligible[0]


def stitched_moat_return(nasdaq_ret, company_price, master):
    comp = company_price.reindex(master).ffill()
    comp_ret = comp.pct_change()
    switch = first_rebalance_year_after_listing(company_price, master)
    r = nasdaq_ret.copy()
    mask = master >= switch
    r.loc[mask] = comp_ret.loc[mask].fillna(0.0)
    return r, switch


def simulate(asset_returns, weights, cost_bps=0.0):
    idx = asset_returns.index
    cols = list(weights)
    w = pd.Series(weights, dtype=float)
    if not math.isclose(float(w.sum()), 1.0, abs_tol=1e-9):
        raise RuntimeError('Weights must sum to 1')
    values = INITIAL * w.copy()
    nav_records = [(idx[0], INITIAL)]
    trade_rows = []
    prev_year = idx[0].year

    for date in idx[1:]:
        values = values * (1.0 + asset_returns.loc[date, cols])
        nav_pre = float(values.sum())
        if date.year != prev_year:
            target = nav_pre * w
            # one-way turnover: half of total absolute reallocation
            turnover_notional = 0.5 * float((target - values).abs().sum())
            cost = turnover_notional * cost_bps / 10000.0
            nav_post = nav_pre - cost
            values = nav_post * w
            trade_rows.append({
                'Date': date,
                'NAV_pre_cost': nav_pre,
                'OneWay_Turnover': turnover_notional / nav_pre if nav_pre else np.nan,
                'Cost_USD': cost,
                'Cost_bps': cost_bps,
            })
            nav = nav_post
            prev_year = date.year
        else:
            nav = nav_pre
        nav_records.append((date, nav))

    return pd.Series(dict(nav_records), name='NAV').sort_index(), pd.DataFrame(trade_rows)


def metrics(nav, rf_nav, trades=None):
    r = nav.pct_change().dropna()
    rf = rf_nav.pct_change().reindex(r.index).fillna(0.0)
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0
    vol = r.std(ddof=1) * np.sqrt(252)
    excess = r - rf
    sharpe = excess.mean() / excess.std(ddof=1) * np.sqrt(252) if excess.std(ddof=1) > 0 else np.nan
    downside = r[r < 0].std(ddof=1) * np.sqrt(252)
    sortino = (r.mean() * 252) / downside if downside > 0 else np.nan
    peak = nav.cummax()
    dd = nav / peak - 1.0
    mdd = float(dd.min())
    trough = dd.idxmin()
    peak_date = nav.loc[:trough].idxmax()
    peak_value = float(nav.loc[peak_date])
    rec = nav.loc[trough:][nav.loc[trough:] >= peak_value]
    recovery = rec.index[0] if len(rec) else pd.NaT
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    monthly = nav.resample('ME').last().pct_change().dropna()
    annual = nav.resample('YE').last().pct_change()
    if len(annual):
        first_year_end = nav.loc[str(nav.index[0].year)].iloc[-1]
        annual.iloc[0] = first_year_end / nav.iloc[0] - 1.0
    annual_valid = annual.dropna()
    avg_turn = float(trades['OneWay_Turnover'].mean()) if trades is not None and len(trades) else 0.0
    total_cost = float(trades['Cost_USD'].sum()) if trades is not None and len(trades) else 0.0
    return {
        'Start': nav.index[0].date().isoformat(),
        'End': nav.index[-1].date().isoformat(),
        'Years': years,
        'Final_NAV': float(nav.iloc[-1]),
        'Cumulative_Return': float(nav.iloc[-1] / nav.iloc[0] - 1.0),
        'CAGR': float(cagr),
        'Ann_Vol': float(vol),
        'MDD': mdd,
        'MDD_Peak': peak_date.date().isoformat(),
        'MDD_Trough': trough.date().isoformat(),
        'MDD_Recovery': recovery.date().isoformat() if pd.notna(recovery) else 'UNRECOVERED',
        'Sharpe_excess_DTB3': float(sharpe),
        'Sortino_MAR0': float(sortino),
        'Calmar': float(calmar),
        'Monthly_Win_Rate': float((monthly > 0).mean()),
        'Worst_Year': int(annual_valid.idxmin().year) if len(annual_valid) else np.nan,
        'Worst_Year_Return': float(annual_valid.min()) if len(annual_valid) else np.nan,
        'Avg_Annual_OneWay_Turnover': avg_turn,
        'Total_Trading_Cost_USD': total_cost,
    }, annual, dd


def configure_korean_font():
    candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
    ]
    for p in candidates:
        if Path(p).exists():
            font_manager.fontManager.addfont(p)
            plt.rcParams['font.family'] = font_manager.FontProperties(fname=p).get_name()
            break
    plt.rcParams['axes.unicode_minus'] = False


def plot_linear(frame):
    configure_korean_font()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in frame.columns:
        ax.plot(frame.index, frame[col], label=col, linewidth=1.5)
    ax.set_title('닻과 돛 포트폴리오 — 누적자산')
    ax.set_ylabel('포트폴리오 가치 ($)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / '01_누적자산_선형.png', dpi=180)
    plt.close(fig)


def plot_log2(frame):
    configure_korean_font()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in frame.columns:
        ax.plot(frame.index, frame[col], label=col, linewidth=1.5)
    ax.set_yscale('log', base=2)
    ymin = INITIAL
    ymax = frame.max().max()
    ticks = []
    v = ymin
    while v <= ymax * 1.15:
        ticks.append(v)
        v *= 2
    ax.set_yticks(ticks)
    ax.set_yticklabels([f'${x:,.0f}' for x in ticks])
    ax.set_title('닻과 돛 포트폴리오 — 누적자산 로그2')
    ax.set_ylabel('포트폴리오 가치 (log2)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / '02_누적자산_로그2.png', dpi=180)
    plt.close(fig)


def plot_drawdown(dd_frame):
    configure_korean_font()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in dd_frame.columns:
        ax.plot(dd_frame.index, dd_frame[col] * 100.0, label=col, linewidth=1.4)
    ax.set_title('닻과 돛 포트폴리오 — 낙폭(Drawdown)')
    ax.set_ylabel('고점 대비 하락률 (%)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / '03_낙폭.png', dpi=180)
    plt.close(fig)


def main():
    spx = load_sp500_long()
    gold = load_gold()
    tbill_yield = load_tbill_yield()
    tentative_end = min(spx.index.max(), gold.index.max())
    spx = spx[(spx.index >= START) & (spx.index <= tentative_end)]
    master = spx.index
    if len(master) < 5000:
        raise RuntimeError('Master S&P500 calendar is unexpectedly short')

    nasdaq = load_nasdaq_repo_plus_fallback(master.max()).reindex(master).ffill()
    if nasdaq.loc[nasdaq.index >= START].isna().any():
        raise RuntimeError('NASDAQ proxy has missing values after splice')

    gold_ret = price_return_on_master(gold, master)
    spx_ret = price_return_on_master(spx, master)
    nasdaq_ret = price_return_on_master(nasdaq, master)
    tbill_ret = tbill_return_on_master(tbill_yield, master)

    company_prices = {}
    moat_returns = {}
    switch_dates = {}
    for label, ticker in MOAT_TICKERS.items():
        price = download_yf(ticker, START, master.max() + pd.Timedelta(days=1))
        company_prices[label] = price
        stitched, switch = stitched_moat_return(nasdaq_ret, price, master)
        moat_returns[label] = stitched
        switch_dates[label] = switch

    asset_ret = pd.DataFrame({
        '금': gold_ret,
        '단기채': tbill_ret,
        'ASML': moat_returns['ASML'],
        'TSM': moat_returns['TSM'],
        'NVDA': moat_returns['NVDA'],
        'GOOGL': moat_returns['GOOGL'],
    }, index=master).fillna(0.0)

    weights_moat = {'금': 0.30, '단기채': 0.30, 'ASML': 0.10, 'TSM': 0.10, 'NVDA': 0.10, 'GOOGL': 0.10}
    proxy_ret = pd.DataFrame({'금': gold_ret, '단기채': tbill_ret, 'NASDAQ': nasdaq_ret}, index=master).fillna(0.0)
    weights_proxy = {'금': 0.30, '단기채': 0.30, 'NASDAQ': 0.40}

    nav_moat, tr_moat = simulate(asset_ret, weights_moat, BASE_COST_BPS)
    nav_proxy, tr_proxy = simulate(proxy_ret, weights_proxy, BASE_COST_BPS)
    nav_spx = INITIAL * (1.0 + spx_ret).cumprod()
    nav_spx.iloc[0] = INITIAL
    nav_rf = INITIAL * (1.0 + tbill_ret).cumprod()
    nav_rf.iloc[0] = INITIAL

    rows = []
    annuals = {}
    dds = {}
    series_map = {
        '닻과돛_해자기업형': (nav_moat, tr_moat),
        '닻과돛_NASDAQ프록시': (nav_proxy, tr_proxy),
        'S&P500_100': (nav_spx, None),
    }
    for name, (nav, trades) in series_map.items():
        m, annual, dd = metrics(nav, nav_rf, trades)
        m['Strategy'] = name
        rows.append(m)
        annuals[name] = annual
        dds[name] = dd

    summary = pd.DataFrame(rows).set_index('Strategy')
    summary.to_csv(OUT / 'summary.csv', encoding='utf-8-sig')
    pd.DataFrame(annuals).to_csv(OUT / 'annual_returns.csv', encoding='utf-8-sig')
    nav_frame = pd.DataFrame({
        '닻과 돛(해자기업)': nav_moat,
        '닻과 돛(NASDAQ 40%)': nav_proxy,
        'S&P500 100%': nav_spx,
    })
    nav_frame.to_csv(OUT / 'daily_nav.csv', encoding='utf-8-sig')
    pd.DataFrame(dds).to_csv(OUT / 'daily_drawdown.csv', encoding='utf-8-sig')
    asset_ret.to_csv(OUT / 'asset_returns_daily.csv', encoding='utf-8-sig')
    asset_ret.corr().to_csv(OUT / 'asset_return_correlations.csv', encoding='utf-8-sig')
    pd.DataFrame([{'Asset': k, 'Ticker': MOAT_TICKERS[k], 'First_Data': company_prices[k].index.min().date().isoformat(), 'Portfolio_Switch_Date': switch_dates[k].date().isoformat()} for k in MOAT_TICKERS]).to_csv(OUT / 'moat_asset_eligibility.csv', index=False, encoding='utf-8-sig')
    tr_moat.to_csv(OUT / 'rebalance_trades_moat.csv', index=False, encoding='utf-8-sig')

    # Cost sensitivity for the main strategy.
    sens = []
    for bps in [0, 5, 10]:
        nav, trades = simulate(asset_ret, weights_moat, bps)
        m, _, _ = metrics(nav, nav_rf, trades)
        sens.append({'Cost_bps': bps, 'Final_NAV': m['Final_NAV'], 'CAGR': m['CAGR'], 'MDD': m['MDD']})
    pd.DataFrame(sens).to_csv(OUT / 'cost_sensitivity.csv', index=False, encoding='utf-8-sig')

    # Clean modern sub-period: all four selected companies have actual market history.
    common_start = max([switch_dates[k] for k in MOAT_TICKERS])
    modern_ret = asset_ret.loc[asset_ret.index >= common_start]
    nav_modern, tr_modern = simulate(modern_ret, weights_moat, BASE_COST_BPS)
    rf_modern = nav_rf.loc[nav_rf.index >= common_start]
    rf_modern = INITIAL * rf_modern / rf_modern.iloc[0]
    modern_metrics, modern_annual, modern_dd = metrics(nav_modern, rf_modern, tr_modern)
    pd.DataFrame([modern_metrics]).to_csv(OUT / 'summary_modern_all_actual.csv', index=False, encoding='utf-8-sig')
    modern_annual.to_csv(OUT / 'annual_returns_modern_all_actual.csv', encoding='utf-8-sig')

    plot_linear(nav_frame)
    plot_log2(nav_frame)
    plot_drawdown(pd.DataFrame({
        '닻과 돛(해자기업)': dds['닻과돛_해자기업형'],
        '닻과 돛(NASDAQ 40%)': dds['닻과돛_NASDAQ프록시'],
        'S&P500 100%': dds['S&P500_100'],
    }))

    assumptions = f'''# 닻과 돛 백테스트 가정\n\n- 기간: {master[0].date()} ~ {master[-1].date()} (저장소 공통 최신일)\n- 초기자산: $10,000\n- 기본 비중: 금 30% + 미국 3개월 T-Bill 30% + 공격자산 40%\n- 해자기업 공격자산: ASML 10% + TSM 10% + NVDA 10% + GOOGL 10%\n- 리밸런싱: 매년 첫 S&P500 거래일 종가 기준, 연 1회\n- 기본 거래비용: one-way turnover 기준 5bp, 민감도 0/5/10bp\n- 세금: 제외\n- 금: 저장소 data/proxy_long/raw/GOLD_LBMA_PM_USD.csv\n- 단기채: 저장소 FRED DTB3 3개월 T-Bill 할인수익률을 투자수익률로 근사 후 달력일수로 복리 누적\n- S&P500 및 NASDAQ: 저장소 지수 데이터를 우선 사용\n- 저장소 NASDAQ 데이터의 1990~1994 결손 구간만 yfinance ^IXIC로 보완\n- ASML/TSM/NVDA/GOOGL은 저장소에 개별주 장기데이터가 없어 yfinance Adjusted Close 사용\n- 생존자편향 주의: 네 기업은 2026년 시점에 알고 있는 승자를 사후 선정한 것이므로 1990년 투자자가 미리 선택할 수 있었다는 뜻이 아님\n- 이를 완화하기 위해 각 기업의 상장 전에는 해당 10% 슬리브를 NASDAQ Composite로 운용하고, 상장 다음 해 첫 연간 리밸런싱 때 기업으로 전환\n- 별도 summary_modern_all_actual.csv는 네 기업이 모두 실제 상장된 이후만 잘라 본 보조검증\n- S&P500/NASDAQ 지수는 price index, 개별주는 Adjusted Close이므로 배당 처리 기준이 완전히 동일하지 않음. 해자전략의 절대수익률보다는 방어력·상관·낙폭 구조 비교에 더 적합\n- MDD: 일별 NAV 기준\n'''
    (OUT / 'ASSUMPTIONS.md').write_text(assumptions, encoding='utf-8')
    print(summary.to_string())
    print('\nSwitch dates:', {k: str(v.date()) for k, v in switch_dates.items()})


if __name__ == '__main__':
    main()
