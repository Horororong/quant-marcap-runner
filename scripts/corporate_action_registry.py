from __future__ import annotations

"""Verified Korean equity corporate-action registry loader.

Events are data, not strategy code. The execution engine consumes normalized
events so merger/successor continuity can be handled without silently filling
missing prices.
"""

from pathlib import Path

import pandas as pd

from execution_contract import CORPORATE_ACTION_REGISTRY_VERSION

CORPORATE_ACTION_FILE = "config/kr_corporate_actions.csv"
REQUIRED_COLUMNS = {
    "event_date",
    "event_type",
    "predecessor_code",
    "successor_code",
    "share_ratio",
    "cash_per_share",
    "source",
}


def load_corporate_actions(
    repo_root: str | Path,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    asset_codes: set[str] | list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    path = Path(repo_root) / CORPORATE_ACTION_FILE
    if not path.exists():
        return pd.DataFrame(columns=sorted(REQUIRED_COLUMNS))

    x = pd.read_csv(
        path,
        dtype={
            "predecessor_code": str,
            "successor_code": str,
            "event_type": str,
            "source": str,
        },
    )
    missing = REQUIRED_COLUMNS - set(x.columns)
    if missing:
        raise KeyError(f"{path}: missing corporate-action columns {sorted(missing)}")

    x["event_date"] = pd.to_datetime(x["event_date"], errors="coerce").dt.normalize()
    if x["event_date"].isna().any():
        raise ValueError(f"{path}: invalid event_date")

    for col in ("predecessor_code", "successor_code"):
        x[col] = x[col].fillna("").astype(str).str.replace(".0", "", regex=False).str.zfill(6)

    x["event_type"] = x["event_type"].astype(str).str.strip().str.lower()
    x["share_ratio"] = pd.to_numeric(x["share_ratio"], errors="coerce")
    x["cash_per_share"] = pd.to_numeric(x["cash_per_share"], errors="coerce").fillna(0.0)

    if (x["event_type"] != "stock_merger").any():
        bad = sorted(x.loc[x["event_type"] != "stock_merger", "event_type"].unique())
        raise ValueError(f"unsupported corporate action types: {bad}")
    if x["share_ratio"].isna().any() or (x["share_ratio"] <= 0).any():
        raise ValueError("stock_merger share_ratio must be > 0")
    if (x["cash_per_share"] < 0).any():
        raise ValueError("cash_per_share must be >= 0")
    if x.duplicated(["event_date", "predecessor_code"]).any():
        raise ValueError("duplicate corporate action for event_date + predecessor_code")

    if start is not None:
        x = x[x["event_date"] >= pd.Timestamp(start).normalize()]
    if end is not None:
        x = x[x["event_date"] <= pd.Timestamp(end).normalize()]
    if asset_codes is not None:
        codes = {str(c).zfill(6) for c in asset_codes}
        x = x[x["predecessor_code"].isin(codes)]

    return x.sort_values(["event_date", "predecessor_code"]).reset_index(drop=True)
