"""Explicit, opt-in all-or-none delayed close orders; no NAV or selection owner.

Observed liquidity controls execution only. Targets retain the original signal.
All pending orders must fill inside the requested window; conflicts fail closed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = "1"
CONTRACT = {
    "version": VERSION,
    "policy": "defer_full_rebalance",
    "earliest": "unchanged signal lag; old positions earn returns through actual execution close",
    "liquidity": "all prior positive holdings and positive targets require observed positive close and volume",
    "pending": "retain original target; no partial fills, cancellation, replacement, exclusion or cash advance",
    "failure": "overlapping pending orders, end-window pending orders, shorts or interacting illiquid action books fail",
    "scope": "RESEARCH_ONLY modeled close execution, not certified realizable brokerage fills",
}


def resolve_deferred_schedule(schedule, target_weights, prices, tradable, tolerance=1e-10):
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
    held = set()
    pending = None
    resolved, audit = {}, []
    for date in prices.index:
        if date in at:
            if pending is not None:
                raise ValueError(f"pending_order_conflict: original signal {pending['signal'].date()} remains unfilled at new execution {date.date()}")
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
        raise ValueError(f"pending_order_at_requested_end: signal {pending['signal'].date()}, planned {pending['planned'].date()}, last {prices.index[-1].date()}, blocked {pending['blocked'][-1]}")
    if len(resolved) != len(schedule):
        raise ValueError("deferred schedule did not account for every original signal")
    return resolved, audit
