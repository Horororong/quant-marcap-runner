"""Use unchanged supplied CURRENT v2-16 as the sole metric/chart source."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import exchange_calendars as xc
import super_value_audited_nav as strategy

C=strategy.C;OUT=strategy.OUT

def summarize(daily, baseline, label):
    cfg=C.BacktestConfig(title='슈퍼가치 전략 · 부분기간 탐색적 검증',initial_capital=10_000_000.,risk_free_rate=0.,as_of_date='2026-09-24',market_calendar='XKRX')
    expected=xc.get_calendar('XKRX').sessions_in_range(daily.index[0],daily.index[-1]).tz_localize(None)
    assert daily.index.equals(expected)
    month_end=daily.index[-1].to_period('M').end_time.normalize()
    last_session=xc.get_calendar('XKRX').sessions_in_range(month_end.to_period('M').start_time,month_end)[-1]
    assert daily.index[-1]==last_session, 'Incomplete terminal month cannot enter formal metrics'
    monthly=daily.resample('ME').last()
    monthly.attrs['performance_baseline_date']=pd.Timestamp(baseline)
    daily.attrs['coverage_verified']=True
    metrics=C.calculate_metrics(monthly,cfg,daily)
    payload=C.build_chat_payload(monthly,cfg,'exploratory',label,daily)
    return metrics,payload,monthly,cfg

def main():
    d=pd.read_csv(OUT/'daily_nav.csv',parse_dates=['Date']).set_index('Date')
    metrics,payload,m,cfg=summarize(d,'2016-10-31','탐색적 부분기간 2016-11~2020-04 · 현금배당 제외·신주인수권 포기')
    metrics.to_csv(OUT/'metrics_CURRENT_v216.csv',encoding='utf-8-sig')
    (OUT/'chat_payload_CURRENT_v216.json').write_text(json.dumps(payload,ensure_ascii=False))
    m.to_csv(OUT/'monthly_nav.csv')
    # The standard call must refuse an invented book period or a truncated fixed period.
    try:
        C.run_four_periods(m,cfg,d)
    except ValueError as e:
        (OUT/'standard_run_blocker.txt').write_text(str(e))
    else:
        raise AssertionError('Expected standard-window coverage gate to fail')
    status=[
        ('book_validation','NOT_AVAILABLE','첨부 사진·PDF에서 이 전략의 정확한 책 검증기간 확인 불가'),
        ('from_2000','NOT_AVAILABLE','2000~2014 재무 및 2021~최신 재무 미완성'),
        ('from_2021','NOT_AVAILABLE','2021~최신 리밸런싱별 전체 횡단면 수집 미완성'),
        ('longest_to_latest','NOT_AVAILABLE','고정 스냅샷에서 2019-10 신호까지 감사; 새 백필은 2020-10 수집완료, 2021-04 미완성'),
        ('exploratory_partial','EXPLORATORY','2016-11-01~2020-04-29, 기업행위 6건 보정, 현금배당 제외·신주인수권 포기 가정')]
    pd.DataFrame(status,columns=['period','status','reason']).to_csv(OUT/'standard_4period_status.csv',index=False,encoding='utf-8-sig')
    # Yearly returns use observed baseline wealth. Inception/final years are partial.
    y=d.groupby(d.index.year).last();annual=y.div(y.shift().fillna(1)).sub(1)
    annual.index.name='Year';annual.to_csv(OUT/'annual_returns.csv',encoding='utf-8-sig')
    # Time-ordered subperiod diagnostic. This is NOT genuine unseen OOS.
    diag=[]
    for label,start,end in [('2016-11~2018-12','2016-11-01','2018-12-31'),('2019-01~2020-04','2019-01-01','2020-04-29')]:
        sub=d.loc[start:end].copy();prev=d[d.index<sub.index[0]]
        baseline=prev.index[-1] if len(prev) else pd.Timestamp('2016-10-31')
        if len(prev):sub=sub.div(prev.iloc[-1])
        dm,_,_,_=summarize(sub,baseline,label);dm.insert(0,'period',label);diag.append(dm)
    pd.concat(diag).to_csv(OUT/'chronological_diagnostics.csv',encoding='utf-8-sig')
    # No metric formula is implemented in the strategy; compare monthly co-movement here.
    r=m.pct_change().dropna();ex=r.Top20_base-r.KOSPI
    beta=r.Top20_base.cov(r.KOSPI)/r.KOSPI.var()
    tracking=float(ex.std(ddof=1)*np.sqrt(12))
    comparison={'tracking_error_monthly_annualized':tracking,'information_ratio_monthly_annualized':float(ex.mean()/ex.std(ddof=1)*np.sqrt(12)),'beta_monthly':float(beta),'alpha_monthly_annualized_arithmetic':float((r.Top20_base.mean()-beta*r.KOSPI.mean())*12),'return_definition':'monthly price return, dividends excluded, rf=0','sample_months':len(r)}
    (OUT/'benchmark_comparison.json').write_text(json.dumps(comparison,indent=2))
    print(metrics[['CAGR','누적수익률','MDD','Sharpe','연환산_표준편차','최대회복기간_일','최종자산']].to_string())

if __name__=='__main__':main()
