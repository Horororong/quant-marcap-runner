from __future__ import annotations

import io
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

# -----------------------------------------------------------------------------
# KRX individual-stock panel updater for point-in-time backtests
# -----------------------------------------------------------------------------
# Primary source: FinanceData/marcap yearly parquet.
#
# Storage policy
# - Missing historical years (1995~prior year): backfill once, then keep immutable.
# - Current year: download the full current-year parquet and overwrite that single
#   file on each scheduled refresh. This is simple and prevents accidental loss of
#   delisted/disappeared securities.
# - Current-year wide matrices are regenerated for convenience; canonical
#   backtests should read yearly parquet panels.
#
# Source fields retained include OHLCV, trading amount, market cap, listed shares,
# price change, change code and daily change ratio.
# -----------------------------------------------------------------------------

REPO_ROOT = Path('.')
RAW_DIR = REPO_ROOT / 'data' / 'krx_equities' / 'yearly'
DERIVED_DIR = REPO_ROOT / 'data' / 'krx_equities' / 'derived'
STATUS_DIR = REPO_ROOT / 'data' / 'status'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DERIVED_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)

START_YEAR = 1995
BASE_URL = 'https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet'

KEEP_COLUMNS = [
    'Date', 'Rank', 'Code', 'Name', 'Market', 'Dept', 'MarketId',
    'Open', 'High', 'Low', 'Close',
    'Volume', 'Amount',
    'Changes', 'ChangeCode', 'ChangesRatio', 'ChagesRatio',
    'Marcap', 'Stocks',
]
NUMERIC_COLUMNS = [
    'Rank', 'Open', 'High', 'Low', 'Close',
    'Volume', 'Amount', 'Changes', 'ChangesRatio', 'ChagesRatio',
    'Marcap', 'Stocks',
]
STRING_COLUMNS = ['Code', 'Name', 'Market', 'Dept', 'MarketId', 'ChangeCode']


def _download_year(year: int) -> bytes:
    url = BASE_URL.format(year=year)
    last_error = None
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            if len(r.content) < 1_000:
                raise RuntimeError(
                    f'Upstream parquet unexpectedly small for {year}: {len(r.content)} bytes'
                )
            return r.content
        except Exception as exc:
            last_error = exc
            print(f'WARN download failed year={year} attempt={attempt}: {exc}', flush=True)
    raise RuntimeError(f'Failed to download marcap-{year}.parquet: {last_error!r}')


def _standardize(raw: bytes) -> pd.DataFrame:
    df = pd.read_parquet(io.BytesIO(raw))
    if 'Date' not in df.columns:
        df = df.reset_index()
    if 'Date' not in df.columns:
        df = df.rename(columns={df.columns[0]: 'Date'})

    # FinanceData/marcap historically used the typo "ChagesRatio". Newer source
    # code uses "ChangesRatio". Normalize to the correctly spelled canonical name.
    if 'ChangesRatio' not in df.columns and 'ChagesRatio' in df.columns:
        df['ChangesRatio'] = df['ChagesRatio']

    missing = [c for c in ['Date', 'Code', 'Close', 'Market'] if c not in df.columns]
    if missing:
        raise RuntimeError(f'Missing required columns: {missing}')

    cols = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df[cols].copy()

    # If both spellings exist, keep only the canonical spelling in our panel.
    if 'ChagesRatio' in df.columns:
        if 'ChangesRatio' not in df.columns:
            df['ChangesRatio'] = df['ChagesRatio']
        df = df.drop(columns=['ChagesRatio'])

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    df['Market'] = df['Market'].astype(str).str.upper().str.strip()

    for c in STRING_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype('string')

    for c in NUMERIC_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # KOSPI/KOSDAQ individual securities only. Preferred stocks are deliberately
    # preserved. ETF/ETN/KONEX stay outside this base equity panel.
    df = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])].copy()
    df = df[df['Date'].notna() & df['Code'].notna()].copy()

    # Convenience aliases matching the user's uploaded per-symbol CSV convention.
    # change: decimal return (10.66% -> 0.1066)
    # updown: source change code
    # comp: absolute price change vs prior close
    if 'ChangesRatio' in df.columns:
        df['Change'] = pd.to_numeric(df['ChangesRatio'], errors='coerce') / 100.0
    if 'ChangeCode' in df.columns:
        df['UpDown'] = df['ChangeCode']
    if 'Changes' in df.columns:
        df['Comp'] = pd.to_numeric(df['Changes'], errors='coerce')

    df = (
        df.sort_values(['Date', 'Code'])
        .drop_duplicates(['Date', 'Code'], keep='last')
        .reset_index(drop=True)
    )
    return df


def _write_year(year: int, overwrite: bool) -> dict:
    out_path = RAW_DIR / f'marcap-{year}.parquet'

    if out_path.exists() and not overwrite:
        df = pd.read_parquet(out_path)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        return {
            'year': year,
            'action': 'kept_existing',
            'rows': int(len(df)),
            'first_date': str(df['Date'].min().date()) if len(df) else '',
            'latest_date': str(df['Date'].max().date()) if len(df) else '',
            'unique_codes': int(df['Code'].nunique()) if 'Code' in df.columns else 0,
        }

    raw = _download_year(year)
    df = _standardize(raw)
    if df.empty:
        raise RuntimeError(f'KRX equity panel is empty for {year}')

    df.to_parquet(out_path, index=False, compression='snappy')
    return {
        'year': year,
        'action': 'overwritten_current' if overwrite else 'backfilled_missing',
        'rows': int(len(df)),
        'first_date': str(pd.Timestamp(df['Date'].min()).date()),
        'latest_date': str(pd.Timestamp(df['Date'].max()).date()),
        'unique_codes': int(df['Code'].nunique()),
    }


def _write_wide(df: pd.DataFrame, value_col: str, filename: str) -> None:
    if value_col not in df.columns:
        return
    wide = df.pivot(index='Date', columns='Code', values=value_col).sort_index()
    wide.to_csv(DERIVED_DIR / filename, encoding='utf-8-sig')


def main() -> None:
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    current_year = now_kst.year

    manifest_rows = []

    # 1) One-time backfill for every missing historical year.
    for year in range(START_YEAR, current_year):
        print(f'HISTORY {year}', flush=True)
        manifest_rows.append(_write_year(year, overwrite=False))

    # 2) Current year is intentionally overwritten on every refresh.
    print(f'CURRENT {current_year}', flush=True)
    manifest_rows.append(_write_year(current_year, overwrite=True))

    current_path = RAW_DIR / f'marcap-{current_year}.parquet'
    current_df = pd.read_parquet(current_path)
    current_df['Date'] = pd.to_datetime(current_df['Date'], errors='coerce')

    latest_date = pd.Timestamp(current_df['Date'].max())
    first_date = pd.Timestamp(current_df['Date'].min())

    # Biweekly refresh means an age of up to roughly 14 days can be intentional.
    # Fail only if upstream freshness exceeds 21 calendar days.
    age_days = (pd.Timestamp(now_kst.date()) - latest_date.normalize()).days
    if age_days > 21:
        raise RuntimeError(
            f'Upstream KRX equity data is stale: latest={latest_date.date()}, age_days={age_days}'
        )

    # Current-year convenience matrices. Historical research should use the
    # yearly PIT panel so securities that later disappear remain available.
    _write_wide(current_df, 'Open', 'open_daily.csv')
    _write_wide(current_df, 'Close', 'close_daily.csv')
    _write_wide(current_df, 'Volume', 'volume_daily.csv')
    _write_wide(current_df, 'Amount', 'amount_daily.csv')
    _write_wide(current_df, 'Marcap', 'marcap_daily.csv')
    _write_wide(current_df, 'Stocks', 'shares_daily.csv')

    latest_cross_section = current_df[current_df['Date'] == latest_date].copy()
    latest_market_counts = latest_cross_section.groupby('Market')['Code'].nunique().to_dict()

    manifest = pd.DataFrame(manifest_rows).sort_values('year')
    manifest['updated_at_utc'] = now_utc.isoformat()
    manifest.to_csv(
        STATUS_DIR / 'krx_equities_manifest.csv',
        index=False,
        encoding='utf-8-sig',
    )

    all_year_files = sorted(RAW_DIR.glob('marcap-*.parquet'))
    status = pd.DataFrame([{
        'status': 'OK',
        'source': 'FinanceData/marcap',
        'history_start_year': START_YEAR,
        'current_year': current_year,
        'year_files_present': len(all_year_files),
        'first_date_current_year': first_date.date().isoformat(),
        'latest_date': latest_date.date().isoformat(),
        'age_days': int(age_days),
        'rows_current_year': int(len(current_df)),
        'unique_codes_current_year': int(current_df['Code'].nunique()),
        'latest_cross_section_rows': int(len(latest_cross_section)),
        'latest_kospi_codes': int(latest_market_counts.get('KOSPI', 0)),
        'latest_kosdaq_codes': int(latest_market_counts.get('KOSDAQ', 0)),
        'duplicate_date_code_rows': int(current_df.duplicated(['Date', 'Code']).sum()),
        'missing_close_rows': int(current_df['Close'].isna().sum()),
        'refresh_policy': 'biweekly; historical years immutable; current year overwritten',
        'updated_at_utc': now_utc.isoformat(),
    }])
    status.to_csv(
        STATUS_DIR / 'krx_equities_status.csv',
        index=False,
        encoding='utf-8-sig',
    )

    print(manifest.tail(5).to_string(index=False), flush=True)
    print(status.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
