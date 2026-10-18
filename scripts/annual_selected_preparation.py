"""Opt-in bounded-memory preparation using original full annual universes.

Selection belongs to existing builders; execution/NAV belongs to PROJECT.
Projection occurs only after every original cross-section has been selected.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import pandas as pd

VERSION = "1"
CONTRACT = {
    "version": VERSION,
    "policy": "annual_selected_projection",
    "selection": "existing builders on complete original annual panels, before observation projection",
    "calendar": "full requested market calendars from complete annual panels, not selected securities",
    "observations": "selected union and verified recursive merger successors only; no synthetic rows or filling",
    "unsupported": "DART providers remain on original PIT-gated preparation path",
}


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare_annual_selected(spec, root, engine):
    from strategy_dsl_runner import (required_panel_columns, build_target_weights_from_panel,
                                     factor_provider_coverage_audit)
    from strategy_dsl_deciles import build_decile_target_weights_from_panel
    from corporate_action_registry import load_corporate_actions
    from krx_history_audit import require_session_coverage
    from factor_registry import external_sources, external_filter_sources
    if 'dart' in set(external_sources(spec.factors)) | set(external_filter_sources(spec.universe.filters)):
        raise ValueError('annual_selected_projection does not support DART preparation; original PIT gates remain required')
    root = Path(root)
    annual, selection, partitions, audits, provider = [], [], [], [], []
    targets = {}
    date_parts = []
    selected = set()
    source_assets = set()
    source_rows = 0
    for year in range(pd.Timestamp(spec.period.start).year, pd.Timestamp(spec.period.end).year + 1):
        start, end = max(spec.period.start, f'{year}-01-01'), min(spec.period.end, f'{year}-12-31')
        source = root / f'data/krx_equities/yearly/marcap-{year}.parquet'
        pin = dict(path=str(source.relative_to(root)), bytes=source.stat().st_size, sha256=file_sha(source))
        panel = engine.load_krx_equity_panel(start=start, end=end, markets=spec.universe.markets,
                                           columns=required_panel_columns(spec), repo_root=root)
        coverage = require_session_coverage(panel, start, end, spec.universe.markets)
        annual.append(dict(year=year, source=pin, history_coverage=coverage))
        source_rows += len(panel)
        source_assets.update(panel.Code.astype(str))
        date_parts.extend(pd.to_datetime(panel.Date).unique())
        # An annual fragment without a requested rebalance month is still
        # required for observation/calendar coverage, but has no new targets.
        months = set(pd.to_datetime(panel.Date).dt.month)
        if months.intersection(spec.rebalance.months):
            if spec.portfolio.selection == 'deciles':
                weights, membership, partition = build_decile_target_weights_from_panel(panel, spec, root)
                partitions.append(partition)
                selection.append(membership)
            else:
                weights, membership = build_target_weights_from_panel(panel, spec, root)
                weights = {'top_n': weights}
                selection.append(membership)
            for label, w in weights.items():
                positive = w.columns[w.gt(0).any()]
                selected.update(positive)
                targets.setdefault(label, []).append(w.loc[:, positive])
            c = factor_provider_coverage_audit(panel, spec, root)
            if not c.empty:
                if 'raw_ok' in c and not c.raw_ok.all():
                    raise ValueError(f'registered provider coverage incomplete: {year}')
                provider.append(c)
        del panel
    if not selected or not targets:
        raise ValueError('no selected holdings for requested full period')
    dates = pd.DatetimeIndex(date_parts).unique().sort_values()
    events = load_corporate_actions(root, start=dates[0], end=dates[-1])
    observation_codes = set(selected)
    while not events.empty:
        extra = set(events.loc[events.predecessor_code.isin(observation_codes) & events.event_type.eq('stock_merger'), 'successor_code'])
        if extra.issubset(observation_codes):
            break
        observation_codes.update(extra)
    from research_spinoff import expand_successors
    observation_codes = expand_successors(root,spec,observation_codes,dates[0],dates[-1])
    pieces = []
    for entry in annual:
        year = entry['year']
        source = root / entry['source']['path']
        if file_sha(source) != entry['source']['sha256']:
            raise ValueError(f'annual source changed between selection and observation: {year}')
        panel = engine.load_krx_equity_panel(start=max(spec.period.start, f'{year}-01-01'),
                                           end=min(spec.period.end, f'{year}-12-31'),
                                           markets=spec.universe.markets, columns=required_panel_columns(spec), repo_root=root)
        pieces.append(panel.loc[panel.Code.astype(str).isin(observation_codes)].copy())
        del panel
    panel = pd.concat(pieces, ignore_index=True)
    weights = {k: pd.concat(rows).reindex(columns=sorted(observation_codes)).fillna(0).sort_index() for k, rows in targets.items()}
    for label, w in weights.items():
        if not w.index.is_unique:
            raise ValueError(f'annual preparation produced duplicate original signals: {label}')
    audit = dict(contract=CONTRACT, source_rows=source_rows, observation_rows=len(panel),
                 selected_codes=sorted(selected), observation_codes=sorted(observation_codes),
                 sessions=len(dates), annual=annual, strategy_fingerprint=spec.fingerprint(),
                 investment_approved=False)
    if spec.execution.nontradable_policy == 'defer_full_rebalance_events_v1':
        import json
        from research_spinoff import CATALOG,CONTRACT as spin_contract
        from execution_scheduling import EVENT_CONTRACT
        from execution_contract import EXECUTION_ENGINE_VERSION
        catalog=root/CATALOG
        binding=dict(strategy_fingerprint=spec.fingerprint(),engine=EXECUTION_ENGINE_VERSION,pending_order_contract=EVENT_CONTRACT,spinoff_model=spin_contract,event_catalog=dict(path=CATALOG,sha256=file_sha(catalog)))
        binding['numeric_reduction']='Original full-source zero-weight asset order for top_n; per-bucket positive/successor order for deciles. Zero padding only, no unselected price reads or universe filtering.'
        binding['source_assets']=sorted(source_assets)
        audit['research_execution_binding']=binding
        audit['research_execution_fingerprint']=hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    from audited_source_extensions import provenance as extension_provenance
    from audited_krx_calendar import provenance as calendar_provenance
    extra=extension_provenance(root,spec.period.start,spec.period.end)
    correction=calendar_provenance(spec.period.start,spec.period.end)
    if extra or correction:
        audit['official_data_revision']=dict(extensions=extra,calendar=correction)
        import json
        audit['official_data_revision_fingerprint']=hashlib.sha256(json.dumps(audit['official_data_revision'],sort_keys=True).encode()).hexdigest()
    return dict(panel=panel, source_assets=sorted(source_assets), targets=weights, selections=pd.concat(selection, ignore_index=True),
                partition_audit=pd.concat(partitions, ignore_index=True) if partitions else pd.DataFrame(),
                provider_coverage=pd.concat(provider, ignore_index=True) if provider else pd.DataFrame(),
                dates=dates, history_coverage=dict(status='complete', annual=[x['history_coverage'] for x in annual]),
                preparation_audit=audit)
