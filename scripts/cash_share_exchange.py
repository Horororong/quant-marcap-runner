from __future__ import annotations

"""Cash-only exchanges: verified entitlement and payment are separate events.

This contract values a fixed, undisputed KRW receivable at nominal value. It
supports no interest, withholding, appraisal rights, defaults or partial payments.
A planned payment date is insufficient evidence for this execution contract.
"""

import numpy as np
import pandas as pd

CASH_EVENT = "cash_share_exchange"
PAYMENT_COLUMNS = ["payment_date", "payment_status", "payment_source"]


def validate_cash_exchanges(events: pd.DataFrame) -> pd.DataFrame:
    x = events.loc[events["event_type"].eq(CASH_EVENT)].copy()
    if x.empty:
        return x
    missing = set(PAYMENT_COLUMNS + ["source"]) - set(x.columns)
    if missing:
        raise ValueError(f"cash exchange requires verified actual payment metadata: {sorted(missing)}")
    x["payment_date"] = pd.to_datetime(x["payment_date"], errors="coerce").dt.normalize()
    if (x["payment_date"].isna().any()
            or (x["payment_date"] < x["event_date"]).any()
            or not x["payment_status"].eq("verified_actual").all()):
        raise ValueError("cash exchange requires verified_actual payment_date on/after entitlement; planned dates are forbidden")
    for col in ("source", "payment_source"):
        if not x[col].fillna("").astype(str).str.match(r"^https://[^\s]+$").all():
            raise ValueError(f"cash exchange requires a primary evidence URL: {col}")
    if (x["successor_code"].fillna("").ne("").any()
            or x["share_ratio"].ne(0).any()
            or not np.isfinite(x["cash_per_share"]).all()
            or x["cash_per_share"].le(0).any()):
        raise ValueError("cash exchange requires no successor, share_ratio=0 and positive finite cash_per_share")
    return x


def normalize_cash_exchanges(prices, events, tradable, volumes, references, execution_targets, stock_actions=None):
    x = validate_cash_exchanges(events)
    rows = []
    for _, row in x.sort_values(["event_date", "predecessor_code"]).iterrows():
        date, code = pd.Timestamp(row["event_date"]), row["predecessor_code"]
        possible = any(code in target.index and target[code] != 0
                       for dt, target in execution_targets.items() if dt < date)
        if stock_actions is not None and not stock_actions.empty:
            possible = possible or bool(((stock_actions["event_date"] < date) & stock_actions["successor_code"].eq(code)).any())
        if not possible:
            continue
        if code not in prices or date not in prices.index:
            raise ValueError("cash exchange entitlement requires observed security and actual trading session")
        if tradable is None or volumes is None or references is None:
            raise ValueError("cash exchange requires source volumes, tradability and exchange reference returns")
        prior = prices.loc[prices.index < date, code]
        prior = prior[tradable.loc[prior.index, code]]
        if prior.empty:
            raise ValueError("cash exchange has no observed last traded price")
        last_date, last_price = prior.index[-1], float(prior.iloc[-1])
        if not np.isfinite(last_price) or last_price <= 0 or not np.isfinite(volumes.at[last_date, code]) or volumes.at[last_date, code] <= 0:
            raise ValueError("cash exchange requires an observed last traded close and positive source Volume")
        suspension = prices.index[(prices.index > last_date) & (prices.index <= date)]
        if not len(suspension):
            raise ValueError("cash exchange requires observed pre-entitlement suspension")
        # Never turn absent observations into a zero-return suspension.
        if (not prices.loc[suspension, code].eq(last_price).all()
                or not volumes.loc[suspension, code].eq(0).all()
                or tradable.loc[suspension, code].any()
                or not references.loc[suspension, code].eq(0).all()):
            raise ValueError("cash exchange suspension requires observed flat closes, Volume=0 and exchange return=0")
        rec = row.to_dict()
        rec.update(last_trade_date=last_date, last_price=last_price,
                   successor_price=0.0, event_return=float(row["cash_per_share"]) / last_price - 1)
        rows.append(rec)
    return pd.DataFrame(rows)
