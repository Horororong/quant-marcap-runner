"""Explicit, opt-in all-or-none delayed close orders; no NAV or selection owner.

Observed liquidity controls execution only. Targets retain the original signal.
All pending orders must fill inside the requested window; conflicts fail closed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = "2"
CONTRACT = {
    "version": VERSION,
    "policy": "defer_full_rebalance",
    "earliest": "unchanged signal lag; old positions earn returns through actual execution close",
    "liquidity": "all prior positive holdings and positive targets require observed positive close and volume",
    "pending": "retain original target; no partial fills, cancellation, replacement, exclusion or cash advance",
    "failure": "overlapping pending orders, end-window pending orders, shorts or interacting illiquid action books fail",
    "scope": "RESEARCH_ONLY modeled close execution, not certified realizable brokerage fills",
}


class PendingOrderError(ValueError):
    def __init__(self, message, date, pending):
        super().__init__(message)
        self.date=date
        self.origin_signal=pending['signal']
        self.planned_date=pending['planned']
        self.blocked=pending['blocked'][-1] if pending['blocked'] else None


def resolve_deferred_schedule(schedule, target_weights, prices, tradable, tolerance=1e-10, *, events=None):
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("deferred schedule requires finite nonnegative tolerance")
    if not target_weights.index.is_unique or not np.isfinite(target_weights.to_numpy(float)).all():
        raise ValueError("deferred schedule requires unique finite target weights")
    if tradable is None:
        raise ValueError("defer_full_rebalance requires observed tradable mask")
    if not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError("deferred schedule requires unique sorted session dates")
    if not tradable.index.equals(prices.index) or not tradable.columns.equals(prices.columns):
        raise ValueError("deferred schedule requires aligned observed price/volume mask")
    if tradable.isna().any().any():
        raise ValueError("deferred schedule cannot infer missing tradability")
    if (target_weights < -tolerance).any().any():
        raise ValueError("deferred schedule supports long-only target weights")
    if set(target_weights.columns) != set(prices.columns):
        raise ValueError("deferred schedule target/price asset mismatch")
    at = {}
    for signal, date in schedule.items():
        if date in at or date not in prices.index or signal not in target_weights.index or date <= signal:
            raise ValueError("invalid/overlapping base execution schedule")
        at[date] = signal
    # Event plans are validated by the common book BEFORE use. The scheduler
    # tracks only whether a nonzero tradable position can exist, never value.
    records = [] if events is None or events.empty else events.to_dict('records')
    permitted = {'stock_split', 'stock_merger', 'cash_share_exchange', 'stock_dividend', 'stock_spinoff'}
    if any(x['event_type'] not in permitted for x in records):
        raise ValueError('pending_order_unsupported_event: independently evidenced event book required')
    dividends = None
    if any(x['event_type']=='stock_dividend' for x in records):
        from stock_dividend_execution import DividendExecution
        dividends = DividendExecution(events.loc[events.event_type.eq('stock_dividend')], prices.index, list(prices.columns))
    plans = [] if dividends is None else dividends.plans
    rights = {}
    held = set()
    pending = None
    resolved, audit = {}, []
    for date in prices.index:
        session = str(date.date())
        # Entitlement uses OPENING holdings; a close buyer receives no old right.
        for plan in plans:
            t = plan['terms']
            if t.ex_date == session and t.security in held:
                rights[t.event_id] = t.security
            if t.event_id not in rights:
                continue
            for decision in plan['decisions']:
                if decision.get('recognition_date', decision['actual_date'])==session and not decision['approved']:
                    rights.pop(t.event_id, None)
            if t.event_id not in rights:
                continue
            if plan['scope']=='modeled_research':
                listing = plan['research_model']['official_listing']
                released = listing is not None and listing['model_settlement_date']==session
            else:
                released = any(x['actual_date']==session for x in plan['listings'])
            if released:
                held.add(rights.pop(t.event_id))
        for event in records:
            if date != pd.Timestamp(event['event_date']):
                continue
            pred, succ = event['predecessor_code'], event.get('successor_code')
            if event['event_type']=='stock_spinoff':
                from research_spinoff import validate
                import json
                contract=validate(json.loads(event['spin_off_contract']))
                if pred in held:
                    held.add(contract['child'])
            if pred in held and event['event_type'] in {'stock_merger','cash_share_exchange'}:
                held.remove(pred)
                if event['event_type']=='stock_merger':
                    held.add(succ)
        if pending is not None:
            pending['required'] = held | pending['target']
        if date in at:
            if pending is not None:
                raise PendingOrderError(f"pending_order_conflict: original signal {pending['signal'].date()} remains unfilled at new execution {date.date()}",date,pending)
            signal = at[date]
            row = target_weights.loc[signal]
            target = set(row.index[row.gt(tolerance)])
            pending = dict(signal=signal, planned=date, target=target, required=held | target, blocked=[])
        if pending is None:
            continue
        codes = sorted(pending['required'])
        px = prices.loc[date, codes].to_numpy(float)
        ok = np.isfinite(px) & (px > 0) & tradable.loc[date, codes].to_numpy(bool)
        blocked = [c for c, valid in zip(codes, ok) if not valid]
        if blocked:
            pending['blocked'].append(dict(date=str(date.date()), securities=blocked))
            continue
        resolved[pending['signal']] = date
        audit.append(dict(signal_date=pending['signal'], planned_execution_date=pending['planned'],
                          execution_date=date, deferred_sessions=len(pending['blocked']),
                          blocked_observations=pending['blocked']))
        held = pending['target']
        pending = None
    if pending is not None:
        raise PendingOrderError(f"pending_order_at_requested_end: signal {pending['signal'].date()}, planned {pending['planned'].date()}, last {prices.index[-1].date()}, blocked {pending['blocked'][-1]}",prices.index[-1],pending)
    if len(resolved) != len(schedule):
        raise ValueError("deferred schedule did not account for every original signal")
    return resolved, audit


EVENT_CONTRACT = {
    "version": "1", "policy": "defer_full_rebalance_events_v1",
    "orders": CONTRACT["pending"], "liquidity": CONTRACT["liquidity"],
    "events": "Validated splits, stock mergers, fixed cash exchange, stock dividends and explicit simultaneous-listing research spin-offs; unknown events fail",
    "rights": "Ex-date opening holders only; cancellation removes right; listing creates tradable holding even after original-share sale",
    "allocation": "Requested weights apply to liquid NAV, separately for Gross/Net; claims remain outside cash budget; fees on pre-cost liquid targets, post-cost liquid allocation",
    "scope": "RESEARCH_ONLY continuous quantities, distribution taxes excluded; no actual brokerage settlement certification",
}
