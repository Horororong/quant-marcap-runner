from __future__ import annotations

import pandas as pd

import backfill_dart_legacy_quarterly as legacy

LEGACY_MAP_FILE = legacy.ROOT / 'dart_legacy_code_map.csv'


def build_full_legacy_mapping(corp: pd.DataFrame) -> pd.DataFrame:
    """Build from the full marcap life table, not the 2015+ DART map.

    The 2015+ backfill map intentionally excludes securities that disappeared
    before 2015. Reusing it here would create survivorship bias for a
    2001-2015 backtest, so the legacy collector always remaps the complete
    historical security-life table.
    """
    if not legacy.LIFE_FILE.exists():
        raise FileNotFoundError(legacy.LIFE_FILE)

    life = pd.read_csv(legacy.LIFE_FILE, dtype={'Code': str})
    life['Code'] = life['Code'].astype(str).str.zfill(6)
    life['first_date'] = pd.to_datetime(life['first_date'], errors='coerce')
    life['last_date'] = pd.to_datetime(life['last_date'], errors='coerce')
    life = life[(life['first_date'] <= pd.Timestamp('2015-12-31')) &
                (life['last_date'] >= pd.Timestamp('2001-01-01'))].copy()
    life['norm_name'] = life['name'].map(legacy.normalize_name)

    by_code = (
        corp[corp['stock_code'] != '']
        .drop_duplicates('stock_code', keep='last')
        .set_index('stock_code')
    )
    counts = corp[corp['norm_name'] != ''].groupby('norm_name')['corp_code'].nunique()
    unique_names = set(counts[counts == 1].index)
    by_name = (
        corp[corp['norm_name'].isin(unique_names)]
        .drop_duplicates('norm_name', keep='last')
        .set_index('norm_name')
    )

    rows = []
    for _, r in life.iterrows():
        corp_code = ''
        dart_name = ''
        method = 'unmatched'
        if r['Code'] in by_code.index:
            d = by_code.loc[r['Code']]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'stock_code'
        elif r['norm_name'] and r['norm_name'] in by_name.index:
            d = by_name.loc[r['norm_name']]
            corp_code = str(d['corp_code'])
            dart_name = str(d['corp_name'])
            method = 'normalized_name_unique'

        rows.append({
            'stock_code': r['Code'],
            'marcap_name': r['name'],
            'corp_code': corp_code,
            'dart_name': dart_name,
            'mapping_method': method,
            'first_date': r['first_date'],
            'last_date': r['last_date'],
        })

    out = pd.DataFrame(rows).sort_values(['first_date', 'stock_code']).reset_index(drop=True)
    out.to_csv(LEGACY_MAP_FILE, index=False, encoding='utf-8-sig')
    return out


legacy.build_mapping = build_full_legacy_mapping
legacy.main()
