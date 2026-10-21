"""Source-attested calendar-FY IS query using existing snapshot owners.

A diagnostic, not a registered strategy provider. Annual flows are never
relabeled as Q4, and population, publication and investment gates stay intact.
"""
import math
from datetime import date
import pandas as pd
from financial_record_readiness import select_asof
from dart_value_factor_adapter import report_snapshots,latest_snapshot

CONCEPTS={'revenue':'매출액','net_income':'당기순이익(손실)'}
def inspect_annual_income_asof(records,signal_date,calendar):
    result=select_asof(records,signal_date,calendar)
    response=dict(status=result['status'],reason=result['reason'],signal_date=signal_date,
        provider_owner='dart_value_factor_adapter.report_snapshots/latest_snapshot',
        readiness_owner='financial_record_readiness.select_asof',period_semantics='calendar_FY_annual_flow_not_standalone_quarter',
        strategy_population_ready=False,operating_store_modified=False,investment_approved=False,classification='RESEARCH_ONLY')
    if result['status']!='PASS':return {**response,'value':None}
    row=result['selected'];metric=row.get('metric')
    if(metric not in CONCEPTS or row.get('statement')!='IS'or row.get('scope')!='OFS'or row.get('measurement_basis')!='duration'or row.get('unit')not in {'원','KRW'}or row.get('unit_multiplier')not in {'1',1}):
        raise ValueError('ONLY_ATTESTED_CALENDAR_FY_OFS_INCOME_SUPPORTED')
    start=date.fromisoformat(row['period_start']);end=date.fromisoformat(row['period_end'])
    if start.year!=end.year or(start.month,start.day)!=(1,1)or(end.month,end.day)!=(12,31):raise ValueError('NOT_A_CALENDAR_FY_FLOW')
    attestation=next(x['attestation']for x in records if x['row']==row);publication=attestation['publication']['date']
    if end>date.fromisoformat(publication):raise ValueError('ACCOUNTING_PERIOD_AFTER_PUBLICATION')
    raw=pd.DataFrame([dict(stock_code=row['stock_code'],fs_div_requested='OFS',rcept_no=row['rcept_no'],filing_date=pd.Timestamp(publication),sj_div='IS',account_id='',account_nm=CONCEPTS[metric],thstrm_amount=row['amount_krw'],thstrm_add_amount='')])
    snapshot=latest_snapshot(report_snapshots(raw),pd.Timestamp(signal_date))
    if len(snapshot)!=1:raise ValueError('EXISTING_PROVIDER_DID_NOT_SELECT_EXACT_SOURCE')
    selected=snapshot.iloc[0];amount=float(selected[metric+'_current'])
    if selected['rcept_no']!=row['rcept_no']:raise ValueError('PROVIDER_SOURCE_IDENTITY_CHANGED')
    if not math.isfinite(amount):raise ValueError('NONFINITE_AUDITED_ANNUAL_VALUE')
    return {**response,'value':dict(stock_code=selected['Code'],scope='OFS',metric=metric,annual_amount_krw=amount,
        source_amount_krw=row['amount_krw'],period_start=row['period_start'],period_end=row['period_end'],receipt=row['rcept_no'],
        publication_date=publication,usable_from_close=result['readiness']['usable_from_close'],source_binding=result['readiness']['binding'],
        evidence_fingerprint=result['readiness']['evidence_fingerprint'],quarterly_amount=None,
        quarter_requirement='Same-scope independently attestedQ3 required before any Q4 subtraction; not provided by this annual query')}
