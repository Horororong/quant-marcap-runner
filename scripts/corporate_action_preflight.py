from __future__ import annotations

"""Trace planned positive holdings through known evidence gaps, without NAV.

Selection and execution scheduling come from the same public builders/PROJECT
contract. This is a planned-exposure gate, not price/return/cost validation or a
certificate of complete corporate-action coverage.
"""
from pathlib import Path
from typing import Any
import pandas as pd

from corporate_action_registry import load_corporate_action_gaps, load_corporate_actions


class CorporateActionEvidenceGap(RuntimeError):
    def __init__(self, audit: dict[str, Any]):
        self.corporate_action_audit = audit
        details = ', '.join(f"{x['portfolio']}:{x['Code']}@{x['check_date']}" for x in audit['exposures'])
        super().__init__(f"planned holdings require unresolved corporate-action evidence: {details}; no event inference or universe exclusion")


def trace_planned_exposures(targets, dates, gaps, events, engine, execution):
    """Match known gaps to positive target cohorts, with exact close-event order.

    Before-close holdings are checked before actions and target replacement;
    an event-day target cannot retroactively sell a prior holding. Verified
    mergers preserve selection lineage; verified cash disposals retire stock.
    No price, drift, cash, transaction cost or NAV is computed.
    """
    dates = pd.DatetimeIndex(dates).sort_values()
    rows = []
    target_count = 0
    if not gaps.empty:
        gaps = gaps.copy()
        gaps['event_date'] = pd.to_datetime(gaps['event_date']).dt.normalize()
    events_by_date = {}
    if not events.empty:
        for row in events.sort_values(['event_date', 'predecessor_code']).to_dict('records'):
            events_by_date.setdefault(pd.Timestamp(row['event_date']), []).append(row)
    for label, weights in targets.items():
        schedule = engine._schedule_signal_execution_dates(dates, weights.index, execution.execution_lag_sessions)
        by_execution = {dt: sig for sig, dt in schedule.items()}
        target_count += len(schedule)
        holdings: dict[str, dict[str, set[str]]] = {}
        emitted = set()
        def check(date, positions, phase):
            for gap in gaps.to_dict('records'):
                code = gap['predecessor_code']
                key = (code, pd.Timestamp(gap['event_date']))
                if date < gap['event_date'] or code not in positions or key in emitted:
                    continue
                origin = positions[code]
                rows.append({
                    'portfolio': label, 'Code': code,
                    'event_date': pd.Timestamp(gap['event_date']).date().isoformat(),
                    'check_date': date.date().isoformat(), 'phase': phase,
                    'origin_signal_dates': sorted(origin['signals']),
                    'origin_selected_codes': sorted(origin['codes']),
                    'reason': gap['reason'], 'evidence': gap.get('evidence', ''),
                })
                emitted.add(key)
        for date in dates:
            check(date, holdings, 'prior_holding_before_close')
            for event in events_by_date.get(date, []):
                pred = event['predecessor_code']
                if pred not in holdings:
                    continue
                if event['event_type'] == 'cash_share_exchange':
                    holdings.pop(pred)
                elif event['event_type'] == 'stock_merger':
                    origin = holdings.pop(pred)
                    successor = event['successor_code']
                    existing = holdings.setdefault(successor, {'signals': set(), 'codes': set()})
                    existing['signals'].update(origin['signals'])
                    existing['codes'].update(origin['codes'])
            if date in by_execution:
                signal = by_execution[date]
                target = weights.loc[signal]
                holdings = {str(code): {'signals': {pd.Timestamp(signal).date().isoformat()}, 'codes': {str(code)}}
                            for code in target.index[target.gt(execution.weight_tolerance)]}
                check(date, holdings, 'target_at_close')
    return rows, target_count


def check_known_action_exposure(panel, spec, repo_root: Path, engine):
    dates = pd.DatetimeIndex(pd.to_datetime(panel['Date']).unique()).sort_values()
    gaps = load_corporate_action_gaps(repo_root)
    gaps = gaps[gaps['event_date'] <= dates[-1]] if not gaps.empty else gaps
    audit = {
        'coverage': 'known evidence gaps only; historical corporate-action completeness remains unverified',
        'policy': 'shared signal selection and lag; positive planned holdings; no NAV, drift or cost calculation',
        'selection_performed': False, 'known_gap_count': int(len(gaps)),
        'executed_target_count': 0, 'exposures': [],
    }
    if gaps.empty:
        return audit
    events = load_corporate_actions(repo_root, start=dates[0], end=dates[-1])
    possible_codes = set(panel['Code'].astype(str).str.zfill(6))
    if not events.empty:
        possible_codes.update(events['successor_code'])
    gaps = gaps[gaps['predecessor_code'].isin(possible_codes)]
    audit['known_gap_count'] = int(len(gaps))
    if gaps.empty:
        return audit
    # Imports here avoid coupling the no-known-gap source-only fast path to
    # factor construction. No strategy-specific interpretation is duplicated.
    from strategy_dsl_runner import build_target_weights_from_panel, engine_inputs
    _, _, execution = engine_inputs(spec, engine)
    if spec.portfolio.selection == 'deciles':
        from strategy_dsl_deciles import build_decile_target_weights_from_panel
        targets, _, _ = build_decile_target_weights_from_panel(panel, spec, repo_root)
    else:
        weights, _ = build_target_weights_from_panel(panel, spec, repo_root)
        targets = {'top_n': weights}
    audit['selection_performed'] = True
    exposures, target_count = trace_planned_exposures(targets, dates, gaps, events, engine, execution)
    audit['executed_target_count'] = target_count
    audit['exposures'] = exposures
    if exposures:
        raise CorporateActionEvidenceGap(audit)
    return audit
