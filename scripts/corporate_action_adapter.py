from __future__ import annotations

"""Explicit corporate-action continuations for deterministic backtests.

Missing prices are never silently filled. A continuation is applied only when a
reviewed event exists in config/corporate_actions.json. v1 supports stock
mergers with a fixed share-exchange ratio.
"""

from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd

REGISTRY_FILE = "config/corporate_actions.json"
SUPPORTED_EVENT_TYPES = {"stock_merger"}


def load_corporate_actions(repo_root: str | Path) -> list[dict[str, Any]]:
    path = Path(repo_root) / REGISTRY_FILE
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError(f"{path}: root must be an array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            raise TypeError(f"{path}: every corporate action must be an object")
        required = {
            "event_id", "event_type", "old_code", "successor_code",
            "suspension_start", "effective_date", "successor_trade_date",
            "share_ratio",
        }
        missing = required - set(row)
        if missing:
            raise KeyError(f"{path}: missing fields {sorted(missing)}")
        event_id = str(row["event_id"])
        if event_id in seen:
            raise ValueError(f"{path}: duplicate event_id {event_id}")
        seen.add(event_id)
        event_type = str(row["event_type"])
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"unsupported corporate action type: {event_type}")
        ratio = float(row["share_ratio"])
        if not np.isfinite(ratio) or ratio <= 0:
            raise ValueError(f"{event_id}: share_ratio must be > 0")
        normalized = dict(row)
        normalized["old_code"] = str(row["old_code"]).zfill(6)
        normalized["successor_code"] = str(row["successor_code"]).zfill(6)
        normalized["share_ratio"] = ratio
        for key in ("suspension_start", "effective_date", "successor_trade_date"):
            normalized[key] = pd.Timestamp(row[key]).normalize()
        if not (
            normalized["suspension_start"]
            <= normalized["effective_date"]
            <= normalized["successor_trade_date"]
        ):
            raise ValueError(f"{event_id}: invalid event date order")
        out.append(normalized)
    return out


def apply_corporate_action_continuations(
    close_prices: pd.DataFrame,
    tradable_mask: pd.DataFrame,
    target_weights: pd.DataFrame,
    repo_root: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    px = close_prices.copy()
    tradable = tradable_mask.copy()
    if not px.index.equals(tradable.index) or list(px.columns) != list(tradable.columns):
        raise AssertionError("close_prices/tradable_mask shape mismatch")

    held_or_targeted = set(
        target_weights.columns[
            (target_weights.abs().max(axis=0) > 1e-12).to_numpy()
        ]
    )
    audit_rows: list[dict[str, Any]] = []

    for event in load_corporate_actions(repo_root):
        old = event["old_code"]
        successor = event["successor_code"]
        if old not in held_or_targeted:
            continue
        if old not in px.columns:
            raise KeyError(f"{event['event_id']}: old_code {old} missing from price matrix")
        if successor not in px.columns:
            raise KeyError(
                f"{event['event_id']}: successor_code {successor} missing from price matrix"
            )

        suspension_start = event["suspension_start"]
        trade_date = event["successor_trade_date"]
        ratio = float(event["share_ratio"])

        pre = px.loc[px.index < suspension_start, old].dropna()
        if pre.empty:
            raise RuntimeError(
                f"{event['event_id']}: no pre-suspension price for {old}"
            )
        last_old_date = pd.Timestamp(pre.index[-1])
        last_old_price = float(pre.iloc[-1])

        effective_date = event["effective_date"]
        suspension_idx = px.index[
            (px.index >= suspension_start) & (px.index < effective_date)
        ]
        observed_during_suspend = px.loc[suspension_idx, old].dropna()
        if len(observed_during_suspend):
            raise RuntimeError(
                f"{event['event_id']}: old_code has prices during declared suspension: "
                f"{observed_during_suspend.index[0].date()}"
            )
        # Before legal effectiveness, the old share is suspended and its last
        # observable market value is carried for valuation only.
        px.loc[suspension_idx, old] = last_old_price
        tradable.loc[suspension_idx, old] = False

        # From the legal effective date, the holder owns a fixed claim on the
        # successor shares. Value therefore follows the successor immediately,
        # even though the newly issued shares remain non-tradable until their
        # listed/trading date.
        claim_idx = px.index[px.index >= effective_date]
        successor_prices = px.loc[claim_idx, successor]
        px.loc[claim_idx, old] = successor_prices * ratio

        locked_claim_idx = px.index[
            (px.index >= effective_date) & (px.index < trade_date)
        ]
        tradable.loc[locked_claim_idx, old] = False
        post_idx = px.index[px.index >= trade_date]
        tradable.loc[post_idx, old] = tradable.loc[post_idx, successor].astype(bool)

        first_successor = successor_prices.dropna()
        if first_successor.empty:
            raise RuntimeError(
                f"{event['event_id']}: no successor price on/after effective date "
                f"{effective_date.date()}"
            )
        first_successor_date = pd.Timestamp(first_successor.index[0])
        first_successor_price = float(first_successor.iloc[0])
        first_claim_value = first_successor_price * ratio

        audit_rows.append({
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "old_code": old,
            "successor_code": successor,
            "suspension_start": suspension_start,
            "effective_date": event["effective_date"],
            "successor_trade_date": trade_date,
            "share_ratio": ratio,
            "last_old_trade_date": last_old_date,
            "last_old_price": last_old_price,
            "first_claim_valuation_date": first_successor_date,
            "first_successor_price": first_successor_price,
            "first_claim_value_per_old_share": first_claim_value,
            "implied_return_from_last_old_close": first_claim_value / last_old_price - 1.0,
            "source_url": event.get("source_url", ""),
            "source_note": event.get("source_note", ""),
        })

    audit = pd.DataFrame(audit_rows)
    return px, tradable, audit
