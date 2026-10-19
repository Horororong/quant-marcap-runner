"""Group saved planned-exposure symptoms without certifying corporate events.

Intervals merge only when they overlap on the SAME security and causal family.
Disjoint return jumps are never joined merely because the ticker is the same.
Cross-strategy duplicates retain all exposure links. No input is altered.
"""
from collections import Counter
import hashlib,json

VERSION='planned-incident-groups-v1'
def summarize_saved(envelopes):
    unique={};seen=set();duplicates=[]
    for name,obj in envelopes.items():
        if not isinstance(obj,dict)or not isinstance(obj.get('issues'),list):continue
        fingerprint=hashlib.sha256(json.dumps(obj['issues'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if fingerprint in seen:duplicates.append(name);continue
        seen.add(fingerprint);unique[name]=obj
    if not unique:return None
    result=summarize(unique);result['duplicate_input_envelopes_not_counted']=duplicates;return result
def family(issue):
    kind=issue['kind']
    if kind=='held_return_reference_gap':return 'UNEXPLAINED_PRICE_REFERENCE'
    if kind=='known_unresolved_event':return 'REGISTERED_UNRESOLVED_ACTION'
    if kind=='missing_held_quote':return 'MISSING_HELD_PRICE'
    if kind=='planned_trade_not_tradable':return 'TRADE_UNAVAILABLE_LEGAL_CAUSE_UNVERIFIED'
    if kind=='pending_order_event_contract_gap':return 'PENDING_ORDER_LINEAGE_OR_POLICY'
    return 'OTHER_'+kind.upper()
def summarize(preflights):
    rows=[];buckets={};symptoms=set()
    for strategy,result in sorted(preflights.items()):
        # Even a resolved schedule is only a planned prefix, not executed NAV.
        first={}
        for i in result['issues']:
            if not i.get('diagnostic_only') and i.get('date'):
                p=i.get('portfolio')or'';first[p]=min(first.get(p,i['date']),i['date'])
        for i in result['issues']:
            x=dict(i,strategy=strategy);x['security']=i.get('security')or'';x['portfolio']=i.get('portfolio')or''
            symptoms.add((i['kind'],x['security'],i.get('date')))
            cutoff=first.get(x['portfolio'])
            x['exposure_scope']='POTENTIAL_AFTER_UNRESOLVED_PATH'if i.get('diagnostic_only')or(cutoff and i['date']>cutoff)else'PLANNED_PREFIX_UNRESOLVED_BOUNDARY'
            x['executed_holding_certified']=False
            x['cause_family']=family(i);rows.append(x)
            # A pending order without a security cannot be linked across
            # portfolios using its conflict date alone.
            k=(x['security'],x['cause_family'],''if x['security']else strategy+'|'+x['portfolio']+'|'+str(i.get('origin_signal')))
            buckets.setdefault(k,[]).append(x)
    groups=[]
    for (code,cause,context),items in sorted(buckets.items()):
        components=[]
        for x in sorted(items,key=lambda x:(x['date'],x.get('affected_through',x['date']))):
            end=x.get('affected_through',x['date'])
            if components and x['date']<=components[-1]['through']:
                components[-1]['through']=max(components[-1]['through'],end);components[-1]['members'].append(x)
            else:components.append(dict(start=x['date'],through=end,members=[x]))
        for c in components:
            ms=c.pop('members');identity=(code,cause,context,c['start'],c['through'])
            groups.append(dict(group_id=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20],security=code,cause_family=cause,**c,
                record_count=len(ms),unique_symptoms=len({(m['kind'],m['security'],m['date'])for m in ms}),
                affected_strategy_count=len({m['strategy']for m in ms}),strategies=sorted({m['strategy']for m in ms}),
                portfolio_exposures=sorted({m['strategy']+'|'+m['portfolio']for m in ms}),
                planned_boundary_records=sum(m['exposure_scope']=='PLANNED_PREFIX_UNRESOLVED_BOUNDARY'for m in ms),
                occurrence_sum=sum(m.get('occurrences',1)for m in ms),
                sample_requirements=sorted({m.get('required','')for m in ms}),
                corporate_event_certification='UNVERIFIED',executed_holding_certified=False))
    groups.sort(key=lambda x:(-x['affected_strategy_count'],-x['planned_boundary_records'],-x['record_count'],x['start'],x['security']))
    work={}
    for g in groups:
        k=(g['security'],g['cause_family'])
        w=work.setdefault(k,dict(security=g['security'],cause_family=g['cause_family'],episode_groups=[],record_count=0,strategies=set(),planned_boundary_records=0))
        w['episode_groups'].append(g['group_id']);w['record_count']+=g['record_count'];w['strategies'].update(g['strategies']);w['planned_boundary_records']+=g['planned_boundary_records']
    items=[]
    for w in work.values():
        w['strategies']=sorted(w['strategies']);w['affected_strategy_count']=len(w['strategies']);w['episode_count']=len(w['episode_groups']);w['is_one_certified_event']=False;items.append(w)
    items.sort(key=lambda w:(-w['affected_strategy_count'],-w['planned_boundary_records'],-w['record_count'],w['security'],w['cause_family']))
    return dict(contract=VERSION,records=len(rows),unique_cross_strategy_symptoms=len(symptoms),diagnostic_groups=len(groups),
        investigation_work_items=len(items),work_items=items,
        groups_by_family=dict(Counter(g['cause_family']for g in groups)),
        exposure_records=dict(Counter(x['exposure_scope']for x in rows)),groups=groups,
        certified_corporate_event_count=0,new_strategy_completions=0,investment_approved=False,
        scope='Overlapping symptom intervals only; group count is not an event count or executed holding count.')
