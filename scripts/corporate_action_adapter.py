from __future__ import annotations

"""Verified corporate-action adapter for KRX equity backtests.

The registry converts an old security claim into successor stock and/or cash.
It does not guess unregistered delistings. Missing held returns remain fatal
unless an explicit verified corporate-action event supplies the settlement.
"""

from pathlib import Path
import pandas as pd
import numpy as np

CORPORATE_ACTION_REGISTRY = "config/corporate_actions.csv"
SUPPORTED_ACTION_TYPES = {"merger", "cash_delisting"}


def load_corporate_action_registry(repo_root: str | Path) -> pd.DataFrame:
    path = Path(repo_root) / CORPORATE_ACTION_REGISTRY
    if not path.exists():
        return pd.DataFrame(columns=[
            "event_id", "action_type", "source_code", "settlement_date",
            "target_code", "share_ratio", "cash_per_share", "source_url", "notes",
        ])
    x = pd.read_csv(path, dtype={"source_code": str, "target_code": str})
    required = {
        "event_id", "action_type", "source_code", "settlement_date",
        "target_code", "share_ratio", "cash_per_share",
    }
    missing = required - set(x.columns)
    if missing:
        raise KeyError(f"{path}: missing columns {sorted(missing)}")
    x["event_id"] = x["event_id"].astype(str).str.strip()
    x["action_type"] = x["action_type"].astype(str).str.strip().str.lower()
    bad_types = set(x["action_type"]) - SUPPORTED_ACTION_TYPES
    if bad_types:
        raise ValueError(f"unsupported corporate action types: {sorted(bad_types)}")
    x["source_code"] = x["source_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    x["target_code"] = (
        x["target_code"].fillna("").astype(str).str.replace(".0", "", regex=False).str.strip()
    )
    x.loc[x["target_code"] != "", "target_code"] = x.loc[
        x["target_code"] != "", "target_code"
    ].str.zfill(6)
    x["settlement_date"] = pd.to_datetime(x["settlement_date"], errors="raise").dt.normalize()
    x["share_ratio"] = pd.to_numeric(x["share_ratio"], errors="raise").astype(float)
    x["cash_per_share"] = pd.to_numeric(x["cash_per_share"], errors="raise").astype(float)
    if (x["share_ratio"] < 0).any() or (x["cash_per_share"] < 0).any():
        raise ValueError("corporate action share_ratio/cash_per_share cannot be negative")
    if x["event_id"].duplicated().any():
        raise ValueError("corporate action event_id must be unique")
    if x.duplicated(["source_code", "settlement_date"]).any():
        raise ValueError("duplicate source_code + settlement_date corporate action")
    return x.sort_values(["settlement_date", "source_code"]).reset_index(drop=True)


def build_corporate_action_inputs(
    close_prices: pd.DataFrame,
    repo_root: str | Path,
) -> dict[str, pd.DataFrame]:
    """Build explicit missing returns + weight-transfer events.

    For a stock merger:
    - missing source returns after its final quote and before settlement are 0%
      (claim carried at last observed value while conversion is pending);
    - settlement-day source return equals successor-stock value plus cash,
      relative to the source's last observed close;
    - after that return is realized, the source portfolio weight is transferred
      to the successor stock and/or cash without trading cost.

    Unregistered trailing disappearances are untouched and still fail in v2-16.
    """
    px = close_prices.copy()
    px.index = pd.to_datetime(px.index).normalize()
    px = px.sort_index().apply(pd.to_numeric, errors="coerce")
    registry = load_corporate_action_registry(repo_root)
    explicit = pd.DataFrame(np.nan, index=px.index, columns=px.columns, dtype=float)
    transfer_rows: list[dict] = []
    audit_rows: list[dict] = []

    for _, event in registry.iterrows():
        source = str(event["source_code"]).zfill(6)
        target = str(event.get("target_code", "") or "").strip()
        dt = pd.Timestamp(event["settlement_date"]).normalize()
        if source not in px.columns:
            continue
        if dt not in px.index:
            # Event outside the loaded trading window or settlement is not a
            # market session in this panel. Ignore only if outside the window.
            if dt < px.index.min() or dt > px.index.max():
                continue
            raise ValueError(f"{event['event_id']}: settlement date {dt.date()} missing from price index")

        before = px.loc[px.index < dt, source].dropna()
        if before.empty:
            raise ValueError(f"{event['event_id']}: no source price before settlement")
        last_dt = pd.Timestamp(before.index[-1])
        last_price = float(before.iloc[-1])
        if not np.isfinite(last_price) or last_price <= 0:
            raise ValueError(f"{event['event_id']}: invalid last source price")

        waiting = px.index[(px.index > last_dt) & (px.index < dt)]
        missing_wait = [d for d in waiting if pd.isna(px.at[d, source])]
        for d in missing_wait:
            explicit.at[d, source] = 0.0

        share_ratio = float(event["share_ratio"])
        cash_per_share = float(event["cash_per_share"])
        target_value = 0.0
        target_price = np.nan
        if target:
            if target not in px.columns:
                raise KeyError(f"{event['event_id']}: target code {target} absent from price panel")
            target_price = float(px.at[dt, target]) if pd.notna(px.at[dt, target]) else np.nan
            if not np.isfinite(target_price) or target_price <= 0:
                raise ValueError(f"{event['event_id']}: target price unavailable on settlement date")
            target_value = share_ratio * target_price

        settlement_value = target_value + cash_per_share
        if settlement_value < 0:
            raise ValueError(f"{event['event_id']}: invalid settlement value")
        event_return = settlement_value / last_price - 1.0
        if event_return < -1.0:
            raise ValueError(f"{event['event_id']}: event return below -100%")
        explicit.at[dt, source] = event_return

        if settlement_value > 0:
            target_fraction = target_value / settlement_value
            cash_fraction = cash_per_share / settlement_value
        else:
            target_fraction = 0.0
            cash_fraction = 1.0

        transfer_rows.append({
            "event_id": str(event["event_id"]),
            "event_date": dt,
            "source_asset": source,
            "target_asset": target,
            "target_value_fraction": target_fraction,
            "cash_value_fraction": cash_fraction,
        })
        audit_rows.append({
            "event_id": str(event["event_id"]),
            "action_type": str(event["action_type"]),
            "source_code": source,
            "target_code": target,
            "last_source_date": last_dt,
            "last_source_close": last_price,
            "settlement_date": dt,
            "target_close": target_price,
            "share_ratio": share_ratio,
            "cash_per_share": cash_per_share,
            "settlement_value_per_source_share": settlement_value,
            "event_return": event_return,
            "waiting_sessions_zero_return": len(missing_wait),
            "source_url": event.get("source_url", ""),
            "notes": event.get("notes", ""),
        })

    transfers = pd.DataFrame(transfer_rows)
    audit = pd.DataFrame(audit_rows)
    return {
        "explicit_returns": explicit,
        "transfers": transfers,
        "audit": audit,
    }
