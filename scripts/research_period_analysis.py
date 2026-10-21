"""Re-report an immutable checked NAV through CURRENT; never runs the engine."""
import hashlib,json,shutil
from datetime import date
from pathlib import Path

def period_request(start,end):
    for value in (start,end):
        if not isinstance(value,str)or date.fromisoformat(value).isoformat()!=value:raise ValueError('정확한 YYYY-MM-DD 날짜가 필요합니다')
    if start>end:raise ValueError('시작일은 종료일보다 늦을 수 없습니다')
    return [dict(id='selection',label='기존 NAV 하위기간 · 엔진 재실행 없음',start=start,end=end),
            dict(id='source_full',label='원래 백테스트 전체 기간',start='longest',end='latest')]

def analyze_saved_nav(root,store,job,folder):
    # Imports remain in the bounded worker, not the local HTTP request thread.
    from research_web import Workspace,write,read
    from strategy_dsl import StrategySpec
    from strategy_dsl_run import _check_requested_report_artifacts
    from strategy_dsl_runner import run_current_postprocess
    from quant_backtest_postprocess import load_daily_nav
    from quant_backtest_template_CURRENT import BacktestConfig,requested_period_readiness
    w=Workspace(root,store)
    try:
        source=w.status(job['source_job_id'])
        if w.comparison_snapshot(source)!=job['source_snapshot']:raise ValueError('ANALYSIS_SOURCE_CHANGED')
    finally:w.pool.shutdown()
    original=Path(store)/'runs'/source['id']/'run';out=folder/'run';out.mkdir(exist_ok=False)
    # A full source NAV copy preserves history/holdings. No clipping, resets,
    # fills or engine execution. CURRENT alone chooses the prior NAV baseline.
    for name in ['strategy_normalized.json','preflight.json','execution_plan.json','artifacts/daily_nav.csv']:
        p=original/name
        if p.is_file():
            target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    spec=StrategySpec.from_dict(read(out/'strategy_normalized.json'))
    daily=load_daily_nav(out/'artifacts/daily_nav.csv','Date',None,preserve_origin=True)
    periods=period_request(job['period']['start'],job['period']['end'])
    cfg=BacktestConfig(initial_capital=10000,market_calendar='XKRX',as_of_date=spec.period.as_of_date or spec.period.end)
    readiness=requested_period_readiness(daily.index,periods,cfg)
    context=dict(operation='existing_nav_analysis',engine_rerun=False,analysis_id=job['id'],source_job_id=source['id'],
        source_engine_run_id=source['provenance'].get('run_id'),source_strategy_fingerprint=source['fingerprint'],
        source_backtest_period=source['period'],requested_analysis_period=job['period'],
        source_nav_sha256=hashlib.sha256((out/'artifacts/daily_nav.csv').read_bytes()).hexdigest(),
        position_rule='Retain source holdings/cash/fees; never reset at analysis start. CURRENT rebases to preceding observed NAV.',
        metrics_owner='CURRENT',classification='RESEARCH_ONLY',investment_approved=False)
    write(out/'analysis_context.json',context);write(out/'report_periods.json',periods)
    state={**read(original/'run_status.json'),'mode':'existing_nav_analysis','analysis_id':job['id'],
        'phase':'analysis','report_ready':False,'operation':context,'period_readiness':readiness}
    write(out/'run_status.json',state)
    if not readiness['periods']['selection']['ready']:
        state.update(status='data_gap');write(out/'run_status.json',state)
        return dict(status='data_gap',error=dict(type='CURRENT_ANALYSIS_PERIOD_UNAVAILABLE',message=readiness['periods']['selection']['reason']),operation=context)
    report=out/'report';report.mkdir()
    result=run_current_postprocess(spec,root,report,daily,capture_output=True,daily_csv=out/'artifacts/daily_nav.csv',report_periods=out/'report_periods.json',isolated=True)
    (out/'postprocess.log').write_text((result.stdout or'')+(result.stderr or''))
    verified=_check_requested_report_artifacts(report,daily,spec,periods)
    # Check again after the report: a concurrent source mutation cannot publish
    # a success referencing different original inputs.
    w=Workspace(root,store)
    try:
        if w.comparison_snapshot(w.status(source['id']))!=job['source_snapshot']:raise ValueError('ANALYSIS_SOURCE_CHANGED_DURING_REPORT')
    finally:w.pool.shutdown()
    state.update(status='ok',phase='complete',nav_ready=True,report_ready=True,period_readiness=verified)
    write(out/'run_status.json',state)
    return dict(status='ok',operation=context,nav_ready=True,report_ready=True,report_complete=verified['complete'])
