"""Field-scoped financial as-of readiness, separate from investment approval.

This is a validation boundary, not a replacement factor provider or PIT gate.
Attestations are source-linked audit inputs. A missing attestation never becomes
true because the collector or CI succeeded. No existing row is mutated.
"""
from datetime import date
import hashlib,json

VERSION='financial-record-readiness-v1'
DIMENSIONS=('financial_accuracy','publication','version_relationship','historical_security_mapping')
def key(row):
    return tuple(row.get(k)for k in ('corp_code','metric','scope','period_start','period_end','measurement_basis'))
def binding(row):
    return {k:row.get(k)for k in ('rcept_no','document_sha256','source_member','source_member_sha256','corp_code','stock_code','metric','scope','statement','period_start','period_end','measurement_basis','unit','unit_multiplier','amount_krw')}
def first_usable_close(publication_date,calendar):
    """Only a closed, attested official-calendar interval can establish a day.

    A list of weekdays or observed prices alone cannot set verified=True.
    Publication day is always excluded; execution is not assumed at this close.
    """
    pub=date.fromisoformat(publication_date)
    if calendar.get('verdict')!='PASS' or not calendar.get('evidence'):return None
    start=date.fromisoformat(calendar['coverage_start']);end=date.fromisoformat(calendar['coverage_end'])
    if not start<=pub<end:return None
    sessions=[date.fromisoformat(s)for s in calendar['sessions']]
    if sessions!=sorted(set(sessions)) or any(not start<=s<=end for s in sessions):raise ValueError('INVALID_CALENDAR_INTERVAL')
    return next((s.isoformat()for s in sessions if s>pub),None)
def assess(row,signal_date,attestation,calendar):
    signal=date.fromisoformat(signal_date);attestation=attestation or {}
    bound=attestation.get('binding')==binding(row)
    dimensions={}
    for dim in DIMENSIONS:
        item=attestation.get(dim,{})
        verdict=item.get('verdict','UNVERIFIED')if bound and item.get('evidence')else'UNVERIFIED'
        if verdict not in {'PASS','FAIL','UNVERIFIED'}:raise ValueError('INVALID_VERDICT')
        dimensions[dim]=verdict
    # Accuracy is field-specific; neither an OCF conflict nor a late CFS member
    # certifies or automatically invalidates independently reviewed OFS equity.
    if row.get('structural_status')!='PASS':dimensions['financial_accuracy']='UNVERIFIED'
    pub=attestation.get('publication',{});available=None
    if dimensions['publication']=='PASS':
        available=first_usable_close(pub['date'],calendar)
    closed=attestation.get('version_relationship',{}).get('asof_closed_through','')
    if dimensions['version_relationship']=='PASS' and(not closed or date.fromisoformat(closed)<signal):
        dimensions['version_relationship']='UNVERIFIED'
    mapping=attestation.get('historical_security_mapping',{})
    if dimensions['historical_security_mapping']=='PASS':
        if(mapping.get('stock_code')!=row.get('stock_code')or not date.fromisoformat(mapping['from'])<=signal<=date.fromisoformat(mapping['through'])):
            dimensions['historical_security_mapping']='UNVERIFIED'
    temporal='PASS'if available and signal>=date.fromisoformat(available)else'FAIL'if available else'UNVERIFIED'
    if available and signal_date not in calendar.get('sessions',[]):
        temporal='UNVERIFIED'
    dimensions['signal_availability']=temporal
    ready=all(v=='PASS'for v in dimensions.values())
    return dict(contract=VERSION,binding=binding(row),signal_date=signal_date,dimensions=dimensions,
                usable_from_close=available,exact_publication_time='UNVERIFIED',
                research_record_ready=ready,investment_approved=False,operating_gate_unchanged=True,
                blockers=[k for k,v in dimensions.items()if v!='PASS'],
                evidence_fingerprint=hashlib.sha256(json.dumps(dict(attestation=attestation,calendar=calendar),sort_keys=True,separators=(',',':')).encode()).hexdigest())
def select_asof(records,signal_date,calendar):
    """Select version BEFORE checking its financial accuracy; no stale fallback.

    All supplied rows must be the SAME field/scope/period identity and explicitly
    certified chain. Incomplete chains refuse selection, not just bad operands.
    """
    if not records:return dict(status='UNVERIFIED',reason='NO_RECORDS',selected=None)
    if len({key(r['row'])for r in records})!=1:raise ValueError('MIXED_FIELD_SCOPE_OR_PERIOD')
    chains=set();available=[]
    for record in records:
        row,a=record['row'],record['attestation'];proof=a.get('version_relationship',{})
        check=assess(row,signal_date,a,calendar)
        if check['dimensions']['version_relationship']!='PASS':
            return dict(status='UNVERIFIED',reason='CHAIN_NOT_CLOSED_AT_SIGNAL',selected=None)
        chain=proof.get('chain_id');rank=proof.get('version_rank')
        if not chain or type(rank)is not int:return dict(status='UNVERIFIED',reason='CHAIN_ORDER_UNVERIFIED',selected=None)
        chains.add(chain)
        if check['dimensions']['publication']!='PASS' or not check['usable_from_close']:
            return dict(status='UNVERIFIED',reason='PUBLICATION_OR_CALENDAR_UNVERIFIED',selected=None)
        if check['dimensions']['signal_availability']=='PASS':available.append((rank,record,check))
    if len(chains)!=1:return dict(status='UNVERIFIED',reason='UNLINKED_CANDIDATE_CHAINS',selected=None)
    if not available:return dict(status='UNAVAILABLE',reason='NOT_YET_PUBLIC_UNDER_NEXT_SESSION_RULE',selected=None)
    ranks=[x[0]for x in available]
    if len(ranks)!=len(set(ranks)):return dict(status='UNVERIFIED',reason='DUPLICATE_VERSION_ORDER',selected=None)
    _,record,check=max(available,key=lambda x:x[0])
    return dict(status='PASS'if check['research_record_ready']else'UNVERIFIED',
                reason='LATEST_AVAILABLE_VERSION'if check['research_record_ready']else'LATEST_VERSION_NOT_READY_NO_STALE_FALLBACK',
                selected=record['row']if check['research_record_ready']else None,readiness=check)
