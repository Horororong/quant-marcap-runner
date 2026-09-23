from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pandas as pd

YEARLY_DIR = Path('data/krx_equities/yearly')
DEFAULT_OUTPUT_DIR = Path('exports/krx_symbols')

OUTPUT_COLUMNS = [
    'date', 'open', 'high', 'low', 'close', 'volume',
    'change', 'updown', 'comp', 'amount', 'marcap', 'shares',
]


def _load_year(path: Path, code: str | None = None) -> pd.DataFrame:
    df = pd.read_parquet(path)

    if code is not None:
        code = str(code).zfill(6)
        df = df[df['Code'].astype(str).str.zfill(6) == code].copy()

    if df.empty:
        return df

    ratio = None
    if 'Change' in df.columns:
        ratio = pd.to_numeric(df['Change'], errors='coerce')
    elif 'ChangesRatio' in df.columns:
        ratio = pd.to_numeric(df['ChangesRatio'], errors='coerce') / 100.0
    elif 'ChagesRatio' in df.columns:
        ratio = pd.to_numeric(df['ChagesRatio'], errors='coerce') / 100.0

    updown = (
        df['UpDown']
        if 'UpDown' in df.columns
        else df['ChangeCode']
        if 'ChangeCode' in df.columns
        else pd.Series(index=df.index, dtype='object')
    )

    comp = (
        pd.to_numeric(df['Comp'], errors='coerce')
        if 'Comp' in df.columns
        else pd.to_numeric(df['Changes'], errors='coerce')
        if 'Changes' in df.columns
        else pd.Series(index=df.index, dtype='float64')
    )

    out = pd.DataFrame({
        'date': pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d'),
        'code': df['Code'].astype(str).str.zfill(6),
        'open': pd.to_numeric(df.get('Open'), errors='coerce'),
        'high': pd.to_numeric(df.get('High'), errors='coerce'),
        'low': pd.to_numeric(df.get('Low'), errors='coerce'),
        'close': pd.to_numeric(df.get('Close'), errors='coerce'),
        'volume': pd.to_numeric(df.get('Volume'), errors='coerce'),
        'change': ratio,
        'updown': updown,
        'comp': comp,
        'amount': pd.to_numeric(df.get('Amount'), errors='coerce'),
        'marcap': pd.to_numeric(df.get('Marcap'), errors='coerce'),
        'shares': pd.to_numeric(df.get('Stocks'), errors='coerce'),
    })
    return out.dropna(subset=['date', 'code'])


def _all_year_files() -> list[Path]:
    files = sorted(YEARLY_DIR.glob('marcap-*.parquet'))
    if not files:
        raise RuntimeError(f'No yearly parquet files found under {YEARLY_DIR}')
    return files


def export_one(code: str, output_dir: Path) -> Path:
    code = str(code).zfill(6)
    chunks = []
    for path in _all_year_files():
        x = _load_year(path, code=code)
        if not x.empty:
            chunks.append(x)

    if not chunks:
        raise RuntimeError(f'No observations found for code={code}')

    df = pd.concat(chunks, ignore_index=True)
    df = (
        df.sort_values('date')
        .drop_duplicates(['date'], keep='last')
        .reset_index(drop=True)
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f'fdr_KRX_p1d_{code}.csv'
    df[OUTPUT_COLUMNS].to_csv(out_path, index=False, encoding='utf-8-sig')
    return out_path


def export_all(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build code list from all yearly files so delisted securities are included.
    codes = set()
    for path in _all_year_files():
        x = pd.read_parquet(path, columns=['Code'])
        codes.update(x['Code'].astype(str).str.zfill(6).unique().tolist())

    count = 0
    for i, code in enumerate(sorted(codes), start=1):
        try:
            export_one(code, output_dir)
            count += 1
        except RuntimeError:
            continue
        if i % 100 == 0:
            print(f'exported {i}/{len(codes)} symbols', flush=True)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Export canonical KRX yearly PIT panels to per-symbol CSVs.'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--code', help='Single six-digit KRX code, e.g. 005930')
    group.add_argument('--all', action='store_true', help='Export every historical code')
    parser.add_argument(
        '--output-dir',
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})',
    )
    parser.add_argument(
        '--zip',
        action='store_true',
        help='Create a ZIP archive after export',
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.code:
        path = export_one(args.code, output_dir)
        print(path)
    else:
        n = export_all(output_dir)
        print(f'Exported {n} symbols to {output_dir}')

    if args.zip:
        archive = shutil.make_archive(
            str(output_dir),
            'zip',
            root_dir=output_dir,
        )
        print(f'ZIP: {archive}')


if __name__ == '__main__':
    main()
