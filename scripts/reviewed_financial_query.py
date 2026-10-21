"""Field-scoped source inspection through existing DART snapshot owners.

Not registered as a strategy provider. No raw store, universe coverage status,
source approval or operating PIT/publication gate is changed by this query.
"""
import math
from datetime import date
import pandas as pd
from financial_record_readiness import select_asof
from dart_value_factor_adapter import report_snapshots,latest_snapshot

def inspect_equity_asof(records,signal_date,calendar):
    result=select_asof(records,signal_date,calendar)
    response=dict(status=result['status'],reason=result['reason'],signal_date=signal_date,
        provider_owner='dart_value_factor_adapter.report_snapshots/latest_snapshot',
        readiness_owner='financial_record_readiness.select_asof',strategy_population_ready=False,
        operating_store_modified=False,investment_approved=False,classification='RESEARCH_ONLY')
    if result['status']!='PASS':return {**response,'value':None}
    row=result['selected']
    if(row.get('metric')!='equity'or row.get('statement')!='BS'or row.get('scope')not in {'CFS','OFS'}or row.get('measurement_basis')!='instant'or row.get('unit')not in {'원','KRW'}or row.get('unit_multiplier')not in {'1',1}):
        raise ValueError('ONLY_ATTESTED_INSTANT_KRW_EQUITY_SUPPORTED')
    selected_record=next(x for x in records if x['row']==row)
    publication=selected_record['attestation']['publication']['date']
    if date.fromisoformat(row['period_end'])>date.fromisoformat(publication):raise ValueError('ACCOUNTING_PERIOD_AFTER_PUBLICATION')
    raw=pd.DataFrame([dict(stock_code=row['stock_code'],fs_div_requested=row['scope'],rcept_no=row['rcept_no'],
        filing_date=pd.Timestamp(publication),sj_div='BS',account_id='',account_nm='자본총계',thstrm_amount=row['amount_krw'],thstrm_add_amount='')])
    snapshot=latest_snapshot(report_snapshots(raw),pd.Timestamp(signal_date))
    if len(snapshot)!=1:raise ValueError('EXISTING_PROVIDER_DID_NOT_SELECT_EXACT_SOURCE')
    value=snapshot.iloc[0]
    if value['rcept_no']!=row['rcept_no']:raise ValueError('PROVIDER_SOURCE_IDENTITY_CHANGED')
    if not math.isfinite(float(value['equity_current'])):raise ValueError('NONFINITE_AUDITED_EQUITY')
    return {**response,'value':dict(stock_code=value['Code'],scope=value['fs_div'],equity_current=float(value['equity_current']),
        source_amount_krw=row['amount_krw'],period_end=row['period_end'],receipt=row['rcept_no'],publication_date=publication,
        usable_from_close=result['readiness']['usable_from_close'],source_binding=result['readiness']['binding'],
        evidence_fingerprint=result['readiness']['evidence_fingerprint'],concept_mapping='Existing exact Korean total-equity alias; no invented IFRS source ID')}
