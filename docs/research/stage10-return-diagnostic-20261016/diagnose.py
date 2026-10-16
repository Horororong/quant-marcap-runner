"""Read-only Stage 10 census. No NAV, correction, registry or gate writes.

Run with the verified original kit Python; import CURRENT repository code.
Only this diagnostic's output directory may be written.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import platform

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from strategy_dsl import load_strategy_spec, compile_execution_plan
from strategy_dsl_runner import load_project_engine, required_panel_columns, engine_inputs
from strategy_dsl_deciles import build_decile_target_weights_from_panel
from krx_history_audit import require_session_coverage
from corporate_action_registry import load_corporate_actions
from execution_contract import HELD_RETURN_TOLERANCE_BPS

STRATEGY = 'docs/research/stage8-2019-2020-20261015/deciles_research_only.json'
BASELINE = '6dfa430128b37cd49990232acf43f2882fcf20dc'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def stats(frame):
    valid = frame[frame.comparison_status.eq('comparable')]
    bad = valid[valid.mismatch]
    numeric_bad = frame[frame.numeric_mismatch]
    return dict(observations=len(frame), comparable=len(valid),
                not_comparable=len(frame)-len(valid), mismatches=len(bad),
                mismatch_codes=bad.Code.nunique(), mismatch_dates=bad.Date.nunique(),
                numeric_mismatches_including_nontrading=len(numeric_bad),
                statuses={str(k): int(v) for k, v in frame.comparison_status.value_counts().items()})


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    spec = load_strategy_spec(ROOT / STRATEGY)
    engine = load_project_engine(ROOT)
    panel = engine.load_krx_equity_panel(start=spec.period.start, end=spec.period.end,
        markets=spec.universe.markets,
        columns=sorted(set(required_panel_columns(spec) + ['Stocks', 'Changes'])), repo_root=ROOT)
    coverage = require_session_coverage(panel, spec.period.start, spec.period.end, spec.universe.markets)
    assert not panel.duplicated(['Date', 'Code']).any()
    dates = pd.DatetimeIndex(sorted(panel.Date.unique()))
    targets, membership, partition = build_decile_target_weights_from_panel(panel, spec, ROOT)
    _, _, execution = engine_inputs(spec, engine)
    events = load_corporate_actions(ROOT, start=dates[0], end=dates[-1])
    selected = set(membership.Code)
    relevant_events = events[events.predecessor_code.isin(selected)]
    # The simple positive-membership tracer below must not silently ignore transfers.
    assert relevant_events.empty, 'Selected event lineage requires explicit review before tracing'
    schedules, exposure, targets_at_close = [], [], []
    for label, weights in targets.items():
        schedule = engine._schedule_signal_execution_dates(dates, weights.index, execution.execution_lag_sessions)
        executions = {dt: signal for signal, dt in schedule.items()}
        holdings = {}
        for date in dates:
            for code, origin in holdings.items():
                exposure.append(dict(Date=date, Code=code, decile=label, origin_signal=origin))
            if date in executions:
                signal = executions[date]
                target = weights.loc[signal]
                holdings = {str(code): signal for code in target.index[target.gt(execution.weight_tolerance)]}
                schedules.append(dict(decile=label, signal_date=signal, execution_date=date,
                                      selected_count=len(holdings)))
                for code in holdings:
                    targets_at_close.append(dict(Date=date, Code=code, target_decile=label))
    exp = pd.DataFrame(exposure)
    assert not exp.duplicated(['Date', 'Code', 'decile']).any()
    assert not exp.duplicated(['Date', 'Code']).any(), 'Each prior holding must be in exactly one bucket'
    p = panel.sort_values(['Code', 'Date']).copy()
    g = p.groupby('Code', sort=False)
    for source, dest in [('Date', 'previous_date'), ('Close', 'previous_close'),
                         ('Volume', 'previous_volume'), ('Stocks', 'previous_stocks')]:
        p[dest] = g[source].shift(1)
    session_ids = pd.Series(np.arange(len(dates)), index=dates)
    p['session_gap'] = p.Date.map(session_ids) - p.previous_date.map(session_ids)
    finite = np.isfinite(p.Close) & np.isfinite(p.previous_close) & np.isfinite(p.ChangesRatio)
    numeric = finite & p.Close.gt(0) & p.previous_close.gt(0) & p.session_gap.eq(1)
    p['close_return'] = np.nan
    p.loc[numeric, 'close_return'] = p.loc[numeric, 'Close'] / p.loc[numeric, 'previous_close'] - 1
    p['difference_bps'] = (p.close_return - p.ChangesRatio / 100) * 10000
    p['absolute_difference_bps'] = p.difference_bps.abs()
    p['numeric_mismatch'] = p.absolute_difference_bps.gt(HELD_RETURN_TOLERANCE_BPS)
    p['comparison_status'] = np.select(
        [p.previous_date.isna(), p.session_gap.ne(1), ~finite | p.Close.le(0) | p.previous_close.le(0),
         p.Volume.le(0) | p.previous_volume.le(0) | ~np.isfinite(p.Volume) | ~np.isfinite(p.previous_volume)],
        ['first_observation_UNVERIFIED', 'nonconsecutive_UNVERIFIED', 'invalid_value_UNVERIFIED',
         'nontrading_boundary_UNVERIFIED'], default='comparable')
    p['mismatch'] = p.numeric_mismatch & p.comparison_status.eq('comparable')
    p = p.merge(exp, on=['Date', 'Code'], how='left', validate='one_to_one')
    p['planned_holding'] = p.decile.notna()
    p = p.merge(pd.DataFrame(targets_at_close), on=['Date', 'Code'], how='left', validate='one_to_one')
    p['possible_exposure'] = p.planned_holding | p.target_decile.notna()
    p['shares_change_ratio'] = p.Stocks / p.previous_stocks - 1
    # Descriptive clues only. No price ratio becomes an executable event.
    p['cause_candidate'] = 'unknown'
    p['evidence_grade'] = 'UNVERIFIED'
    p['cause_clue'] = 'No primary event/price evidence reviewed for this code-date'
    p['evidence_reference'] = ''
    known = p.Code.eq('091990') & p.Date.eq(pd.Timestamp('2019-12-27'))
    p.loc[known, 'cause_candidate'] = 'stock_dividend'
    p.loc[known, 'cause_clue'] = '5% dividend proposal, approval and issuance evidenced; exact ex-date/reference price still unverified'
    p.loc[known, 'evidence_reference'] = 'docs/research/stage9-followup-20261015/followup_report.md'
    for case in json.loads((Path(__file__).parent / 'case_evidence.json').read_text())['cases']:
        match = p.Code.eq(case['code']) & p.Date.eq(pd.Timestamp(case['date']))
        p.loc[match, 'cause_candidate'] = case['cause_candidate']
        p.loc[match, 'cause_clue'] = case['clue']
        p.loc[match, 'evidence_reference'] = case['reference']
    registry_rows = []
    for event in events.to_dict('records'):
        match = p.Code.eq(event['predecessor_code']) & p.Date.eq(event['event_date'])
        p.loc[match, 'cause_clue'] = 'Exact registered event; raw-close diagnostic is not economic event-return reconciliation'
        p.loc[match, 'evidence_reference'] = event.get('source', '')
        registry_rows.append(event)
    held = p[p.planned_holding].copy()
    # Check expected holdings against the source explicitly, not by an inner join.
    missing = exp.merge(panel[['Date', 'Code']], on=['Date', 'Code'], how='left', indicator=True)
    missing = missing[missing._merge.eq('left_only')].drop(columns='_merge')
    missing['comparison_status'] = 'missing_held_source_row_UNVERIFIED'
    mismatches = p[p.mismatch].sort_values(['absolute_difference_bps', 'Date', 'Code'], ascending=[False, True, True])
    held_bad = mismatches[mismatches.planned_holding]
    cols = ['Date','Code','Name','Market','previous_date','previous_close','Close','ChangesRatio',
            'close_return','difference_bps','absolute_difference_bps','Volume','previous_volume','Stocks',
            'previous_stocks','shares_change_ratio','Changes','comparison_status','numeric_mismatch',
            'planned_holding','possible_exposure','decile','origin_signal','target_decile',
            'evidence_grade','cause_candidate','cause_clue','evidence_reference']
    membership.to_csv(out / 'membership.csv', index=False)
    partition.to_csv(out / 'partition_audit.csv', index=False)
    pd.DataFrame(schedules).to_csv(out / 'schedule.csv', index=False)
    held[cols].to_csv(out / 'planned_holding_observations.csv.gz', index=False,
        compression={'method':'gzip', 'mtime':0, 'compresslevel':9})
    held_bad[cols].to_csv(out / 'planned_holding_mismatches.csv', index=False)
    held_bad[cols].head(20).to_csv(out / 'planned_top20.csv', index=False)
    mismatches[cols].to_csv(out / 'panel_mismatches.csv', index=False)
    p[p.numeric_mismatch][cols].to_csv(out / 'panel_numeric_mismatches.csv', index=False)
    p[~p.comparison_status.eq('comparable')][cols].to_csv(out / 'panel_unverified.csv.gz', index=False,
        compression={'method':'gzip', 'mtime':0, 'compresslevel':9})
    missing.to_csv(out / 'missing_planned_observations.csv', index=False)
    p[p.possible_exposure & ~p.planned_holding][cols].to_csv(out / 'target_only_observations.csv', index=False)
    pd.DataFrame(registry_rows).to_csv(out / 'registered_events_in_period.csv', index=False)
    by_code = held_bad.groupby(['Code', 'Name']).agg(count=('Date','size'),
        maximum_absolute_difference_bps=('absolute_difference_bps','max')).reset_index()
    by_code.to_csv(out / 'planned_by_code.csv', index=False)
    held_bad.groupby('Date').size().rename('count').to_csv(out / 'planned_by_date.csv')
    summary = dict(classification='RESEARCH_ONLY_DIAGNOSTIC', investment_use_allowed=False,
        baseline_commit=BASELINE, strategy=STRATEGY, tolerance_bps=HELD_RETURN_TOLERANCE_BPS,
        full_panel=stats(p), planned_holdings=stats(held), unheld_panel=stats(p[~p.planned_holding]),
        planned_expected=len(exp), missing_planned_observations=len(missing), selected_codes=len(selected),
        target_only=stats(p[p.possible_exposure & ~p.planned_holding]),
        per_decile={str(k):stats(v) for k,v in held.groupby('decile')},
        requested_start=spec.period.start, requested_end=spec.period.end,
        first_observed=dates[0], last_observed=dates[-1], market_sessions=len(dates),
        exact_registered_events_affecting_selections=len(relevant_events),
        planned_exposed_sessions=held.Date.nunique(),
        candidate_categories={str(k):int(v) for k,v in held_bad.cause_candidate.value_counts().items()},
        raw_numeric_categories={str(k):int(v) for k,v in p[p.numeric_mismatch].cause_candidate.value_counts().items()},
        planned_mismatch_rate=len(held_bad)/len(held[held.comparison_status.eq('comparable')]),
        plan_limit='Positive target membership before daily rebalance; no NAV/drift/cost/liquidity/unsupported-event rights ledger. Not completed holdings or certified investable results.',
        python=platform.python_version())
    dump(out / 'summary.json', summary)
    dump(out / 'history_coverage.json', coverage)
    dump(out / 'execution_plan.json', compile_execution_plan(spec))
    paths = [STRATEGY, 'data/krx_equities/yearly/marcap-2019.parquet',
             'data/krx_equities/yearly/marcap-2020.parquet', 'config/kr_corporate_actions.csv',
             'config/kr_corporate_action_gaps.json']
    paths += sorted(str(x.relative_to(ROOT)) for x in (ROOT / 'scripts').glob('*.py'))
    dump(out / 'input_sha256.json', {path:dict(bytes=(ROOT/path).stat().st_size,
         sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()) for path in paths})
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
