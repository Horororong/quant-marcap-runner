"""Explicit source-label mapping; segment membership is never an eligibility filter."""
from __future__ import annotations

import pandas as pd

from execution_contract import KRX_MARKET_NORMALIZATION_VERSION

MARKET_LABELS = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "KOSDAQ GLOBAL": "KOSDAQ", "KONEX": "KONEX"}
MARKET_IDS = {"KOSPI": "STK", "KOSDAQ": "KSQ", "KONEX": "KNX"}


def normalize_markets(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    labels = out["Market"].astype("string").str.upper().str.strip()
    unknown = labels.isna() | ~labels.isin(MARKET_LABELS)
    if unknown.any():
        raise ValueError(f"Unknown KRX market labels: {out.loc[unknown, 'Market'].drop_duplicates().tolist()}")
    canonical = labels.map(MARKET_LABELS).astype("string")
    if "MarketId" in out:
        observed = out["MarketId"].astype("string").str.upper().str.strip()
        if (observed.isna() | observed.ne(canonical.map(MARKET_IDS))).any():
            raise ValueError("KRX MarketId disagrees with the evidenced market/segment label")
    # Preserve the original observed label, including historical segment changes.
    if "SourceMarket" not in out:
        out["SourceMarket"] = out["Market"].astype("string")
    else:
        provenance = out["SourceMarket"].astype("string").str.upper().str.strip()
        if (provenance.isna() | ~provenance.isin(MARKET_LABELS) | provenance.map(MARKET_LABELS).ne(canonical)).any():
            raise ValueError("SourceMarket provenance disagrees with canonical Market")
    out["Market"] = canonical
    out.attrs['krx_market_normalization_version'] = KRX_MARKET_NORMALIZATION_VERSION
    return out
