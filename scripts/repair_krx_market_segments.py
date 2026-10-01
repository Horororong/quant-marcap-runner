"""Append only evidenced omitted segment observations; dry-run unless --apply."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import pandas as pd

from execution_contract import KRX_MARKET_NORMALIZATION_VERSION
from update_krx_equities_daily import _standardize


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_observation_evidence(source_path: Path, repaired: pd.DataFrame, report: dict, target: Path) -> None:
    """Independent original-source projection, without the updater's normalizer."""
    raw = pd.read_parquet(source_path)
    if 'Date' not in raw:
        raw = raw.reset_index()
    raw['Date'] = pd.to_datetime(raw['Date'])
    raw['Code'] = raw.Code.astype(str).str.zfill(6)
    rows = raw[raw.Market.eq('KOSDAQ GLOBAL') & raw.Date.between(report['stored_start'], report['stored_end'])].copy()
    rows['SourceMarket'], rows['Market'] = 'KOSDAQ GLOBAL', 'KOSDAQ'
    if 'ChangesRatio' not in rows:
        rows['ChangesRatio'] = rows['ChagesRatio']
    fields = ['Date', 'Code', 'SourceMarket', 'Market', 'Close', 'Volume', 'ChangesRatio', 'Stocks']
    rows = rows[fields].sort_values(['Date', 'Code']).reset_index(drop=True)
    if len(rows) != report['added_rows']:
        raise ValueError('Evidence export requires the inventoried complete segment omission')
    actual = repaired.set_index(['Date', 'Code']).loc[rows.set_index(['Date', 'Code']).index].reset_index()[fields]
    pd.testing.assert_frame_equal(actual, rows, check_dtype=False, check_index_type=False, check_exact=True)
    with target.open('wb') as stream, gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as compressed:
        compressed.write(rows.to_csv(index=False, date_format='%Y-%m-%d').encode())
    report['added_observations_file'] = target.name
    report['added_observations_sha256'] = sha256(target)


def prepare_repair(existing_path: Path, source_path: Path, record: dict) -> tuple[pd.DataFrame, dict]:
    if sha256(source_path) != record['upstream_sha256']:
        raise ValueError('Pinned upstream SHA256 mismatch')
    old = pd.read_parquet(existing_path)
    raw = pd.read_parquet(source_path)
    if 'Date' not in raw:
        raw = raw.reset_index()
    if raw.duplicated(['Date', 'Code']).any() or old.duplicated(['Date', 'Code']).any():
        raise ValueError('Duplicate source or stored Date/Code observations')
    source = _standardize(source_path.read_bytes())
    if old.empty or not source.Date.dt.year.eq(record['year']).all():
        raise ValueError('Empty stored window or source dates outside the inventory year')
    start, end = pd.Timestamp(old.Date.min()), pd.Timestamp(old.Date.max())
    # Repair the stored window; never silently refresh or extend the current year.
    source = source[source.Date.between(start, end)].set_index(['Date', 'Code']).sort_index()
    retained = old.set_index(['Date', 'Code']).sort_index()
    if not retained.index.isin(source.index).all():
        raise ValueError('Pinned source omits previously stored observations')
    fields = list(retained.columns)
    if any(c not in source for c in fields):
        raise ValueError('Pinned source cannot verify all stored fields')
    pd.testing.assert_frame_equal(retained[fields], source.loc[retained.index, fields], check_dtype=False, check_names=False, check_exact=True)
    missing = source.loc[~source.index.isin(retained.index)].copy()
    if not missing.SourceMarket.eq('KOSDAQ GLOBAL').all():
        raise ValueError('Unexpected missing non-segment rows; this repair cannot guess their cause')
    before = sha256(existing_path)
    if len(missing) and before != record['stored_sha256']:
        raise ValueError('Stored file moved since repair inventory')
    preserved = retained.copy()
    preserved['SourceMarket'] = source.loc[retained.index, 'SourceMarket']
    result = pd.concat([preserved, missing], axis=0).sort_index().reset_index()
    assert not result.duplicated(['Date', 'Code']).any()
    pd.testing.assert_frame_equal(result.set_index(['Date', 'Code']).loc[retained.index, fields], retained[fields], check_dtype=False, check_exact=True)
    report = {'year': record['year'], 'source_url': record['url'], 'source_sha256': record['upstream_sha256'],
              'before_sha256': before, 'before_rows': len(old), 'after_rows': len(result),
              'added_rows': len(missing), 'added_codes': int(missing.reset_index().Code.nunique()),
              'retained_fields_verified': fields, 'retained_observations_unchanged': True,
              'stored_start': str(start.date()), 'stored_end': str(end.date()),
              'added_first': str(missing.index.get_level_values('Date').min().date()) if len(missing) else None,
              'added_last': str(missing.index.get_level_values('Date').max().date()) if len(missing) else None,
              'action': 'append_verified_segment_rows' if len(missing) else 'already_complete'}
    return result, report


def repair(manifest_path: Path, source_dir: Path, repo_root: Path, output_path: Path, apply: bool = False) -> dict:
    manifest = json.loads(manifest_path.read_text())
    pin = manifest['upstream_commit']
    if not re.fullmatch('[a-f0-9]{40}', pin):
        raise ValueError('A full pinned upstream commit is required')
    years = manifest['years']
    if len({x['year'] for x in years}) != len(years):
        raise ValueError('Duplicate repair years')
    reports, staged, evidence = [], [], []
    with tempfile.TemporaryDirectory(prefix='krx-segment-repair-') as td:
        temp = Path(td)
        for row in years:
            year = row['year']
            expected_url = f'https://raw.githubusercontent.com/FinanceData/marcap/{pin}/data/marcap-{year}.parquet'
            if row['url'] != expected_url:
                raise ValueError('Source URL does not match the pinned commit/year')
            path = repo_root/f'data/krx_equities/yearly/marcap-{year}.parquet'
            df, report = prepare_repair(path, source_dir/f'marcap-{year}.parquet', row)
            target = temp/path.name
            if report['added_rows']:
                df.to_parquet(target, index=False, compression='snappy')
                report['after_sha256'] = sha256(target)
                proof = temp/f'added-observations-{year}.csv.gz'
                stage_observation_evidence(source_dir/f'marcap-{year}.parquet', df, report, proof)
                evidence.append(proof)
                backup = temp/f'before-{year}.parquet'
                if apply:
                    shutil.copyfile(path, backup)
                staged.append((path, target, backup))
            else:
                report['after_sha256'] = report['before_sha256']
            reports.append(report)
            del df
        result = {'status': 'applied' if apply else 'dry_run', 'upstream_commit': pin,
                  'krx_market_normalization_version': KRX_MARKET_NORMALIZATION_VERSION,
                  'scope': 'exact missing KOSDAQ GLOBAL observations inside stored windows; no values filled or previous observations revised',
                  'years': reports, 'total_added_rows': sum(x['added_rows'] for x in reports)}
        changed = []
        try:
            if apply:
                for path, target, backup in staged:
                    # Copy to the target filesystem, then replace atomically.
                    adjacent = path.with_suffix('.repair.tmp')
                    shutil.copyfile(target, adjacent)
                    os.replace(adjacent, path)
                    changed.append((path, backup))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            for proof in evidence:
                shutil.copyfile(proof, output_path.parent/proof.name)
            output_path.write_text(json.dumps(result, indent=2)+'\n')
        except Exception:
            for path, backup in reversed(changed):
                shutil.copyfile(backup, path)
            for path, _, _ in staged:
                path.with_suffix('.repair.tmp').unlink(missing_ok=True)
            raise
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--source-dir', type=Path, required=True)
    p.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    result = repair(a.manifest, a.source_dir, a.repo_root, a.output, a.apply)
    print(json.dumps({'status':result['status'], 'total_added_rows':result['total_added_rows'],
                      'years':[{k:x[k] for k in ('year','before_rows','after_rows','added_rows','added_codes','stored_end')} for x in result['years']]}, indent=2))


if __name__ == '__main__':
    main()
