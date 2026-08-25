from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

START = pd.Timestamp('2001-01-01')
INITIAL = 10_000.0
WEIGHT_SPY = 0.50
BASE_COST_BPS = 5.0
TBILL_DAYS = 91.0
OUT = Path('results/cash_sp500_5050')
OUT.mkdir(parents=True, exist_ok=True)


def load_spy():
    p = Path('data/etf_us/SPY.csv')
    df = pd.read_csv(p)
    df['Date'] = pd.to_datetime(df['Date'])
    col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    s = df.set_index('Date')[col].astype(float).sort_index()
    s = s.loc[s.index >= START].dropna()
    if len(s) < 1000:
        raise RuntimeError('SPY history is unexpectedly short')
    return s


def load_tbill(start, end):
    # Repository copy of FRED DTB3 (3-Month Treasury Bill Secondary Market Rate,
    # Discount Basis), downloaded by scripts/download_long_proxy_inputs.py.
    p = Path('data/proxy_long/raw/US_3M_TBILL.csv')
    df = pd.read_csv(p)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    s = df.set_index('Date')['Value'].sort_index()
    daily = s.reindex(pd.date_range(s.index.min(), max(end, s.index.max()), freq='D')).ffill()
    daily = daily.loc[(daily.index >= start - pd.Timedelta(days=10)) & (daily.index <= end)]
    if daily.loc[daily.index >= start].isna().any():
        raise RuntimeError('DTB3 contains unresolved missing values')
    return daily


def tbill_effective_annual(discount_yield_pct):
    # Convert 3M bank-discount yield to an approximate investment-basis annual yield:
    # BEY ~= 365*d / (360 - d*t), t=91 days, d in decimal.
    d = float(discount_yield_pct) / 100.0
    return (365.0 * d) / (360.0 - d * TBILL_DAYS)


def simulate(spy, rate_daily=None, cost_bps=0.0):
    idx = spy.index
    first = idx[0]
    price0 = float(spy.iloc[0])
    nav = INITIAL
    units = nav * WEIGHT_SPY / price0
    cash = nav * (1 - WEIGHT_SPY)
    records = [(first, nav)]
    trades = []
    prev_date = first
    prev_year = first.year

    for date in idx[1:]:
        if rate_daily is not None:
            days = (date - prev_date).days
            y = tbill_effective_annual(rate_daily.loc[prev_date])
            cash *= (1.0 + y) ** (days / 365.25)

        price = float(spy.loc[date])
        nav_pre = units * price + cash

        # Annual rebalance at the close of the first SPY trading day of each new year.
        if date.year != prev_year:
            target_spy_pre = nav_pre * WEIGHT_SPY
            current_spy = units * price
            traded = abs(target_spy_pre - current_spy)
            cost = traded * cost_bps / 10000.0
            nav = nav_pre - cost
            units = (nav * WEIGHT_SPY) / price
            cash = nav * (1 - WEIGHT_SPY)
            trades.append({
                'Date': date,
                'NAV_pre_cost': nav_pre,
                'SPY_trade_notional': traded,
                'Turnover': traded / nav_pre if nav_pre else np.nan,
                'Cost': cost,
                'Cost_bps': cost_bps,
            })
            prev_year = date.year
        else:
            nav = nav_pre

        records.append((date, nav))
        prev_date = date

    return pd.Series(dict(records), name='NAV').sort_index(), pd.DataFrame(trades)


def simulate_spy100(spy):
    nav = INITIAL * spy / spy.iloc[0]
    nav.name = 'NAV'
    return nav


def simulate_tbill100(index, rate_daily):
    nav = [INITIAL]
    value = INITIAL
    for prev, date in zip(index[:-1], index[1:]):
        days = (date - prev).days
        y = tbill_effective_annual(rate_daily.loc[prev])
        value *= (1.0 + y) ** (days / 365.25)
        nav.append(value)
    return pd.Series(nav, index=index, name='TBill_NAV')


def max_drawdown_details(nav):
    peak = nav.cummax()
    dd = nav / peak - 1.0
    trough = dd.idxmin()
    peak_date = nav.loc[:trough].idxmax()
    peak_value = float(nav.loc[peak_date])
    after = nav.loc[trough:]
    rec = after[after >= peak_value]
    recovery = rec.index[0] if len(rec) else pd.NaT
    recovery_days = (recovery - peak_date).days if pd.notna(recovery) else np.nan

    high = nav >= nav.cummax() * (1 - 1e-12)
    last_high = nav.index[0]
    longest = 0
    for d, is_high in high.items():
        if is_high:
            longest = max(longest, (d - last_high).days)
            last_high = d
    longest = max(longest, (nav.index[-1] - last_high).days)
    return dd, float(dd.min()), peak_date, trough, recovery, recovery_days, longest


def metrics(nav, rf_nav, trades=None):
    r = nav.pct_change().dropna()
    rf = rf_nav.pct_change().reindex(r.index).fillna(0.0)
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    vol = r.std(ddof=1) * np.sqrt(252)
    excess = r - rf
    sharpe = excess.mean() / excess.std(ddof=1) * np.sqrt(252) if excess.std(ddof=1) > 0 else np.nan
    downside = r[r < 0].std(ddof=1) * np.sqrt(252)
    sortino = (r.mean() * 252) / downside if downside > 0 else np.nan
    dd, mdd, peak_date, trough, recovery, recovery_days, longest = max_drawdown_details(nav)
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan

    monthly = nav.resample('ME').last().pct_change().dropna()
    annual = nav.resample('YE').last().pct_change()
    if len(annual):
        first_year_end = nav.loc[str(nav.index[0].year)].iloc[-1]
        annual.iloc[0] = first_year_end / nav.iloc[0] - 1
    annual_valid = annual.dropna()
    worst_year = int(annual_valid.idxmin().year) if len(annual_valid) else np.nan
    worst_year_ret = float(annual_valid.min()) if len(annual_valid) else np.nan
    avg_turnover = float(trades['Turnover'].mean()) if trades is not None and len(trades) else 0.0
    total_cost = float(trades['Cost'].sum()) if trades is not None and len(trades) else 0.0

    return {
        'Start': nav.index[0].date().isoformat(),
        'End': nav.index[-1].date().isoformat(),
        'Years': years,
        'Final_NAV': float(nav.iloc[-1]),
        'Cumulative_Return': float(nav.iloc[-1] / nav.iloc[0] - 1),
        'CAGR': float(cagr),
        'Ann_Vol': float(vol),
        'MDD': mdd,
        'MDD_Peak': peak_date.date().isoformat(),
        'MDD_Trough': trough.date().isoformat(),
        'MDD_Recovery': recovery.date().isoformat() if pd.notna(recovery) else 'UNRECOVERED',
        'MDD_Recovery_Days': recovery_days,
        'Longest_Underwater_Days': int(longest),
        'Sharpe_excess_DTB3': float(sharpe),
        'Sortino_MAR0': float(sortino),
        'Calmar': float(calmar),
        'Monthly_Win_Rate': float((monthly > 0).mean()),
        'Worst_Year': worst_year,
        'Worst_Year_Return': worst_year_ret,
        'Avg_Annual_Rebalance_Turnover': avg_turnover,
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


def plot_growth(frame):
    configure_korean_font()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in frame.columns:
        ax.plot(frame.index, frame[col], label=col, linewidth=1.6)
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
    ax.set_title('달러현금·S&P500 50:50 연 1회 리밸런싱 — 누적자산')
    ax.set_ylabel('포트폴리오 가치 (로그2)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / '누적자산_로그2.png', dpi=180)
    plt.close(fig)


def plot_drawdown(dd_frame):
    configure_korean_font()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in dd_frame.columns:
        ax.plot(dd_frame.index, dd_frame[col] * 100, label=col, linewidth=1.4)
    ax.set_title('달러현금·S&P500 50:50 — 드로다운')
    ax.set_ylabel('고점 대비 하락률 (%)')
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / '드로다운.png', dpi=180)
    plt.close(fig)


def main():
    spy = load_spy()
    end = spy.index[-1]
    rates = load_tbill(spy.index[0], end)
    rf_nav = simulate_tbill100(spy.index, rates)

    nav_cash0_gross, tr0_gross = simulate(spy, None, 0)
    nav_cash0_net, tr0_net = simulate(spy, None, BASE_COST_BPS)
    nav_tbill_gross, trt_gross = simulate(spy, rates, 0)
    nav_tbill_net, trt_net = simulate(spy, rates, BASE_COST_BPS)
    nav_spy = simulate_spy100(spy)

    rows = []
    annuals = {}
    dds = {}
    series_map = {
        '현금0%+S&P500 50:50 비용전': (nav_cash0_gross, tr0_gross),
        '현금0%+S&P500 50:50 비용후(5bp)': (nav_cash0_net, tr0_net),
        '3M T-Bill+S&P500 50:50 비용전': (nav_tbill_gross, trt_gross),
        '3M T-Bill+S&P500 50:50 비용후(5bp)': (nav_tbill_net, trt_net),
        'S&P500 100%': (nav_spy, None),
    }
    for name, (nav, trades) in series_map.items():
        m, annual, dd = metrics(nav, rf_nav, trades)
        m['Strategy'] = name
        rows.append(m)
        annuals[name] = annual
        dds[name] = dd

    summary = pd.DataFrame(rows).set_index('Strategy')
    summary.to_csv(OUT / 'summary.csv', encoding='utf-8-sig')
    pd.DataFrame(annuals).to_csv(OUT / 'annual_returns.csv', encoding='utf-8-sig')

    sens = []
    for bps in [0, 5, 10]:
        for label, rate in [('현금0%', None), ('3M T-Bill', rates)]:
            nav, trades = simulate(spy, rate, bps)
            m, _, _ = metrics(nav, rf_nav, trades)
            sens.append({
                'Cash_Leg': label,
                'Cost_bps': bps,
                'Final_NAV': m['Final_NAV'],
                'CAGR': m['CAGR'],
                'MDD': m['MDD'],
            })
    pd.DataFrame(sens).to_csv(OUT / 'cost_sensitivity.csv', index=False, encoding='utf-8-sig')

    nav_frame = pd.DataFrame({
        '현금 0% + S&P500 50:50': nav_cash0_net,
        '3개월 T-Bill + S&P500 50:50': nav_tbill_net,
        'S&P500 100%': nav_spy,
    })
    nav_frame.to_csv(OUT / 'daily_nav.csv', encoding='utf-8-sig')
    dd_frame = pd.DataFrame({
        '현금 0% + S&P500 50:50': dds['현금0%+S&P500 50:50 비용후(5bp)'],
        '3개월 T-Bill + S&P500 50:50': dds['3M T-Bill+S&P500 50:50 비용후(5bp)'],
        'S&P500 100%': dds['S&P500 100%'],
    })
    plot_growth(nav_frame)
    plot_drawdown(dd_frame)

    assumptions = f'''# Backtest assumptions\n\n- Period: {spy.index[0].date()} to {end.date()} (latest SPY observation in repository)\n- Initial capital: $10,000\n- Equity: SPY adjusted close (dividends/splits reflected)\n- Allocation: S&P500 50% / cash leg 50%\n- Rebalance: once per year, at close of first SPY trading day of each calendar year\n- Cash version A: 0% return\n- Cash version B: repository FRED DTB3 3-month Treasury bill secondary-market discount yield; previous available day's rate; converted approximately to investment-basis annual yield using a 91-day bill and accrued by calendar day\n- Base trading cost: 5 bp on SPY notional traded at each annual rebalance; sensitivity 0/5/10 bp\n- Taxes: excluded\n- MDD: daily NAV\n- Sharpe: daily excess return over DTB3 cash proxy, annualized with 252 trading days\n- Sortino: MAR=0, annualized with 252 trading days\n- 2026 return: partial year through latest repository date\n'''
    (OUT / 'ASSUMPTIONS.md').write_text(assumptions, encoding='utf-8')
    print(summary.to_string())


if __name__ == '__main__':
    main()
