from __future__ import annotations

import io
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

# -----------------------------------------------------------------------------
# Daily KRX individual-stock panel updater
# -----------------------------------------------------------------------------
# Primary source: FinanceData/marcap yearly parquet (historical PIT cross-sections)
# Purpose: maintain a local, append-safe daily panel for KOSPI/KOSDAQ individual
# securities while preserving securities that later disappear from the market.
#
# The script downloads the current-year marcap parquet, filters KOSPI/KOSDAQ,
# standardizes columns, writes the current-year canonical parquet, and derives
# compact daily wide files for price/volume/liquidity research.
#
# IMPORTANT:
# - Historical rows are never rebuilt from today's listing universe.
# - Existing years are retained untouched unless the upstream yearly parquet for
#   that same year changes.
# - Duplicate Date+Code rows are removed deterministically.
# - A status CSV records source freshness and row counts for auditing.
# -----------------------------------------------------------------------------

REPO_ROOT = Path('.')
RAW_DIR = REPO_ROOT / 'data' / 'krx_equities' / 'yearly'
DERIVED_DIR = REPO_ROOT / 'data' / 'krx_equities' / 'derived'
STATUS_DIR = REPO_ROOT / 'data' / 'status'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DERIVED_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = 'https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet'

KEEP_COLUMNS = [
    'Date', 'Code', 'Name', 'Market',
    'Open', 'High', 'Low', 'Close',
    'Volume', 'Amount', 'Marcap', 'Stocks',
]
NUMERIC_COLUMNS = [
    'Open', 'High', 'Low', 'Close', 'Volume', 'Amount', 'Marcap', 'Stocks'
]


def _download_year(year: int) -> bytes:
    url = BASE_URL.format(year=year)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if len(r.content) < 1_000:
        raise RuntimeError(f'Upstream parquet unexpectedly small: {len(r.content)} bytes')
    return r.content


def _standardize(raw: bytes) -> pd.DataFrame:
    df = pd.read_parquet(io.BytesIO(raw))
    if 'Date' not in df.columns:
        df = df.reset_index()
    if 'Date' not in df.columns:
        df = df.rename(columns={df.columns[0]: 'Date'})

    missing = [c for c in ['Date', 'Code', 'Close', 'Market'] if c not in df.columns]
    if missing:
        raise RuntimeError(f'Missing required columns: {missing}')

    cols = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df[cols].copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    df['Market'] = df['Market'].astype(str).str.upper().str.strip()

    for c in NUMERIC_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # Individual common/preferred stocks are preserved. ETF/ETN/KONEX are not
    # part of this base equity panel because the target factor research universe
    # is KOSPI + KOSDAQ individual stocks.
    df = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])].copy()
    df = df[df['Date'].notna() & df['Code'].notna()].copy()
    df = df.sort_values(['Date', 'Code']).drop_duplicates(['Date', 'Code'], keep='last')
    return df.reset_index(drop=True)


def _write_wide(df: pd.DataFrame, value_col: str, filename: str) -> None:
    if value_col not in df.columns:
        return
    wide = df.pivot(index='Date', columns='Code', values=value_col).sort_index()
    wide.to_csv(DERIVED_DIR / filename, encoding='utf-8-sig')


def main() -> None:
    now_utc = datetime.now(timezone.utc)
    # GitHub Actions runs in UTC; Korea is UTC+9.
    now_kst = now_utc + timedelta(hours=9)
    year = now_kst.year

    raw = _download_year(year)
    df = _standardize(raw)

    if df.empty:
        raise RuntimeError('Current-year KRX equity panel is empty')

    latest_date = pd.Timestamp(df['Date'].max())
    first_date = pd.Timestamp(df['Date'].min())

    # On weekends/holidays, latest trading date may naturally be several days old.
    # More than 7 calendar days is treated as stale and fails the workflow.
    age_days = (pd.Timestamp(now_kst.date()) - latest_date.normalize()).days
    if age_days > 7:
        raise RuntimeError(
            f'Upstream KRX equity data is stale: latest={latest_date.date()}, age_days={age_days}'
        )

    out_path = RAW_DIR / f'marcap-{year}.parquet'
    df.to_parquet(out_path, index=False)

    # Compact research matrices for fast factor/backtest joins.
    _write_wide(df, 'Open', 'open_daily.csv')
    _write_wide(df, 'Close', 'close_daily.csv')
    _write_wide(df, 'Volume', 'volume_daily.csv')
    _write_wide(df, 'Amount', 'amount_daily.csv')
    _write_wide(df, 'Marcap', 'marcap_daily.csv')
    _write_wide(df, 'Stocks', 'shares_daily.csv')

    market_counts = df.groupby('Market')['Code'].nunique().to_dict()
    latest_cross_section = df[df['Date'] == latest_date]

    status = pd.DataFrame([{
        'status': 'OK',
        'source': 'FinanceData/marcap',
        'year': year,
        'first_date': first_date.date().isoformat(),
        'latest_date': latest_date.date().isoformat(),
        'age_days': int(age_days),
        'rows_current_year': int(len(df)),
        'unique_codes_current_year': int(df['Code'].nunique()),
        'latest_cross_section_rows': int(len(latest_cross_section)),
        'latest_kospi_codes': int(market_counts.get('KOSPI', 0)),
        'latest_kosdaq_codes': int(market_counts.get('KOSDAQ', 0)),
        'duplicate_date_code_rows': int(df.duplicated(['Date', 'Code']).sum()),
        'missing_close_rows': int(df['Close'].isna().sum()),
        'updated_at_utc': now_utc.isoformat(),
    }])
    status.to_csv(STATUS_DIR / 'krx_equities_status.csv', index=False, encoding='utf-8-sig')

    print(status.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
