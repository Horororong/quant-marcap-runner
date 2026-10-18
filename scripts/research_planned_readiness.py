"""Bounded-memory, shared-selection planned exposure inspection; never NAV.

Annual source reads preserve every requested signal cross-section. Only after
selection are selected-code observations loaded for diagnostics. Nothing here
changes eligibility, prices, event records, execution weights or return guards.
"""
import hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from execution_contract import HELD_RETURN_TOLERANCE_BPS,PREFLIGHT_CONTRACT_VERSION

VERSION='1'
CONTRACT=dict(version=VERSION,scope='planned positive cohorts and pending rights; no NAV/cost/drift; not investment certification',
 source='annual bounded-memory reads, all historical signal cross-sections before selected-observation projection',
 failures='structured facts/model/definition/capability/contract incidents; no event inference or universe exclusion',
 limits='execution liquidity/weight drift still require common engine; possible trade constraints remain warnings')

def inspect_planned_strategy(strategy_json,repo_root):
 from strategy_dsl import load_strategy_spec,compile_execution_plan
 from strategy_dsl_runner import load_project_engine,required_panel_columns,scored_signals_from_panel,engine_inputs,benchmark_coverage_audit,signal_dates_from_panel,factor_provider_coverage_audit
 from strategy_dsl_deciles import partition_deciles
 from krx_history_audit import session_coverage_audit
 from corporate_action_registry import load_corporate_actions,load_corporate_action_gaps
 root=Path(repo_root).resolve();issues=[];warnings=[];by_key={}
 result=dict(preflight_contract_version=PREFLIGHT_CONTRACT_VERSION,planned_readiness_contract_version=VERSION,status='data_gap',ready_for_execution=False,
  phase='compile',contract=CONTRACT,issues=issues,warnings=warnings,investment_approved=False)
 def issue(kind,detail,*,code=None,date=None,portfolio=None,required=None,classification='historical_fact',verdict='UNVERIFIED',**extra):
  date=str(pd.Timestamp(date).date()) if date is not None else None
  # Preserve first exact incident and affected range rather than emitting one
  # indistinguishable missing-quote incident for every later session.
  key=(kind,code,portfolio,extra.get('event_id'),None if kind=='missing_held_quote' else date)
  if key in by_key:
   old=by_key[key];old['occurrences']+=1
   if date:old['affected_through']=max(old.get('affected_through') or date,date)
   return old
  row=dict(kind=kind,classification=classification,verdict=verdict,security=code,date=date,portfolio=portfolio,detail=detail,
   required=required or 'Inspect exact original source and common contract; never fill/exclude/override',occurrences=1,affected_through=date,**extra)
  row['incident_id']=hashlib.sha256(json.dumps({k:row.get(k) for k in ['kind','security','date','portfolio','event_id']},sort_keys=True).encode()).hexdigest()[:20]
  issues.append(row);by_key[key]=row;return row
 try:spec=load_strategy_spec(strategy_json);plan=compile_execution_plan(spec)
 except (ValueError,KeyError,TypeError) as e:
  result.update(status='capability_gap',error=dict(type=type(e).__name__,message=str(e)));issue('unsupported_strategy',str(e),classification='capability_gap');return result
 result.update(strategy_id=spec.strategy_id,strategy_fingerprint=spec.fingerprint(),requested_period=dict(start=spec.period.start,end=spec.period.end),versions={k:v for k,v in plan.items() if k.endswith('_version')},factor_sources=plan['data_contract']['factor_sources'],phase='sources')
 controls=['config/kr_corporate_actions.csv','config/kr_corporate_action_references.json','config/kr_corporate_action_gaps.json']
 if spec.research:controls.append(spec.research['event_file'])
 if spec.benchmark:controls.append('data/indices/'+spec.benchmark.symbol+'.csv')
 result['control_files']=[dict(path=name,bytes=(root/name).stat().st_size,sha256=hashlib.sha256((root/name).read_bytes()).hexdigest()) for name in controls if (root/name).is_file()]
 engine=load_project_engine(root);_,_,execution=engine_inputs(spec,engine)
 from krx_technical_factor_adapter import TECHNICAL_FACTOR_SPECS
 technical=sorted({f.field for f in spec.factors if f.field in TECHNICAL_FACTOR_SPECS}|{f.field for f in spec.universe.filters if f.field in TECHNICAL_FACTOR_SPECS})
 if technical:
  result['technical_lookback']={field:dict(required_sessions=TECHNICAL_FACTOR_SPECS[field].lookback_sessions,skip_sessions=TECHNICAL_FACTOR_SPECS[field].skip_sessions,owner='registered technical provider; exact original per-code window, no shortening') for field in technical}
  history=[]
  for year in range(pd.Timestamp(spec.period.start).year-2,pd.Timestamp(spec.period.end).year+1):
   p=root/f'data/krx_equities/yearly/marcap-{year}.parquet'
   if p.is_file():history.append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
  result['technical_history_files']=history
 provenance=[];coverage=[];populations=[];targets={};selected=set();date_parts=[];provider=[];total_rows=0
 for year in range(pd.Timestamp(spec.period.start).year,pd.Timestamp(spec.period.end).year+1):
  start=max(spec.period.start,f'{year}-01-01');end=min(spec.period.end,f'{year}-12-31');path=root/f'data/krx_equities/yearly/marcap-{year}.parquet'
  try:
   raw=path.read_bytes();provenance.append(dict(path=str(path.relative_to(root)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()));del raw
   panel=engine.load_krx_equity_panel(start=start,end=end,markets=spec.universe.markets,columns=required_panel_columns(spec),repo_root=root)
   total_rows+=len(panel)
   c=session_coverage_audit(panel,start,end,spec.universe.markets);coverage.append(c)
   if c['status']!='complete':issue('market_calendar_source_mismatch',json.dumps(c['markets']),date=start,required='Official cash-equity calendar and source-day agreement; no assumed weekdays or filling')
   dates=pd.DatetimeIndex(pd.to_datetime(panel.Date).unique()).sort_values();date_parts.extend(dates)
   audit=factor_provider_coverage_audit(panel,spec,root)
   if not audit.empty:
    provider.extend(json.loads(audit.to_json(orient='records',date_format='iso')))
    if 'raw_ok' in audit and not audit.raw_ok.all():issue('provider_lookback_incomplete','Registered provider reports insufficient original history',date=start,required='Complete registered lookback/source window; no shortening or substitute factor')
   expected_signals=signal_dates_from_panel(panel,spec)
   try:
    for signal,ranked in scored_signals_from_panel(panel,spec,root):
     n=len(ranked);minimum=10 if spec.portfolio.selection=='deciles' else spec.portfolio.number_of_positions
     populations.append(dict(signal_date=str(pd.Timestamp(signal).date()),eligible_count=n,required_minimum=minimum))
     if n<minimum:
      issue('insufficient_eligible_population',f'Original rules yield {n}, required {minimum}',date=signal,classification='strategy_definition',verdict='FAIL',required='Keep original strategy blocked; any separately predeclared broad-universe strategy needs its own DSL/fingerprint');continue
     groups=partition_deciles(ranked).groupby('decile',sort=True) if spec.portfolio.selection=='deciles' else [('top_n',ranked.head(minimum).assign(target_weight=1/minimum))]
     for label,group in groups:
      row=pd.Series(group.target_weight.to_numpy(float),index=group.Code.astype(str),name=pd.Timestamp(signal));targets.setdefault(label,[]).append(row);selected.update(row.index)
   except (ValueError,RuntimeError,KeyError,AssertionError) as e:
    issue('selection_or_lookback_gap',str(e),date=expected_signals[0] if len(expected_signals) else start,required='Inspect registered factor lookback/provider, exact source rows and original population; no shortened lookback')
   del panel
  except (OSError,ValueError,RuntimeError,KeyError,AssertionError) as e:
   issue('source_or_provider_gap',str(e),date=start,required=f'Provide exact {year} source/schema/provider inputs under original contract')
 result.update(source_files=provenance,history_coverage_by_year=coverage,signal_populations=populations,provider_coverage=provider)
 dates=pd.DatetimeIndex(date_parts).unique().sort_values()
 def finish():
  result['first_blocker']=min((x for x in issues if x['date']),key=lambda x:(x['date'],x['security'] or '',x['portfolio'] or '')) if any(x['date'] for x in issues) else (issues[0] if issues else None)
  if issues:
   b=result['first_blocker'];result['error']=dict(type='PlannedReadinessGap',message=f"{b['kind']}: {b['security']}@{b['date']}: {b['detail']}",incident_id=b['incident_id'])
  return result
 if not len(dates):return finish()
 try:result['benchmark']=benchmark_coverage_audit(root,spec.benchmark,dates)
 except (OSError,ValueError,RuntimeError,KeyError,AssertionError) as e:issue('benchmark_coverage_gap',str(e),required='Exact explicitly selected index closes on every requested session; no proxy/fill')
 result['observed_sessions']=len(dates);result['planned_portfolios']=len(targets);result['planned_selected_codes']=sorted(selected)
 result['krx_panel']=dict(actual_start=str(dates[0].date()),actual_end=str(dates[-1].date()),rows=total_rows,distinct_planned_codes=len(selected),markets=list(spec.universe.markets))
 result['signal_dates']=sorted({r['signal_date'] for r in populations})
 result['history_coverage']=dict(status='complete' if all(c['status']=='complete' for c in coverage) else 'incomplete',annual=coverage)
 if not selected:return finish()
 weights={label:pd.DataFrame(rows).reindex(columns=sorted(selected)).fillna(0).sort_index() for label,rows in targets.items()}
 events=load_corporate_actions(root,start=dates[0],end=dates[-1]);gaps=load_corporate_action_gaps(root)
 # Successor observations follow verified lineage AFTER selection. This does
 # not alter eligible cross-sections or force successor selection.
 while not events.empty:
  successors=set(events.loc[events.predecessor_code.isin(selected)&events.event_type.eq('stock_merger'),'successor_code'])
  if successors.issubset(selected):break
  selected.update(successors)
 result['observation_codes_with_verified_successors']=sorted(selected)
 pieces=[]
 for p in provenance:
  year=int(Path(p['path']).stem.split('-')[-1]);start=max(spec.period.start,f'{year}-01-01');end=min(spec.period.end,f'{year}-12-31')
  frame=engine.load_krx_equity_panel(start=start,end=end,markets=spec.universe.markets,columns=['Date','Code','Close','Volume','ChangesRatio'],repo_root=root)
  pieces.append(frame[frame.Code.astype(str).isin(selected)]);del frame
 observations=pd.concat(pieces,ignore_index=True);del pieces
 px=observations.pivot(index='Date',columns='Code',values='Close').reindex(index=dates,columns=sorted(selected));vol=observations.pivot(index='Date',columns='Code',values='Volume').reindex_like(px);refs=observations.pivot(index='Date',columns='Code',values='ChangesRatio').reindex_like(px)/100
 del observations
 catalog=[];support=None
 if spec.research:
  model=spec.research;file=root/model['event_file'];raw=file.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=model['event_sha256']:
   issue('research_fact_hash_mismatch','Fact file differs from explicit DSL SHA256',classification='contract');catalog=[]
  else:
   facts=json.loads(raw);catalog=facts['events'];support=facts['pending_lifecycle_supported_through']
 all_events=events.to_dict('records') if not events.empty else []
 names=sorted(selected);indices={c:i for i,c in enumerate(names)};p=px.to_numpy(float);v=vol.to_numpy(float);r=refs.to_numpy(float);raw_returns=px.pct_change(fill_method=None).to_numpy(float)
 explained=[];schedules=[]
 for label,w in weights.items():
  try:schedule=engine._schedule_signal_execution_dates(dates,w.index,execution.execution_lag_sessions)
  except (ValueError,RuntimeError) as e:issue('execution_schedule_gap',str(e),portfolio=label,classification='contract');continue
  at={d:s for s,d in schedule.items()};schedules.extend(dict(portfolio=label,signal_date=str(s.date()),execution_date=str(d.date())) for s,d in schedule.items())
  executable={d:w.loc[s] for s,d in schedule.items()};normal={}
  for event in all_events:
   if event['predecessor_code'] not in selected or event['event_type'] not in ['stock_split','stock_merger']:continue
   try:
    x=engine._normalize_corporate_action_events(px,pd.DataFrame([event]),px.notna()&px.gt(0)&vol.gt(0),executable)
    for a in x.to_dict('records'):normal[(pd.Timestamp(a['event_date']),a['predecessor_code'])]=a
   except (ValueError,RuntimeError,KeyError) as e:issue('registered_event_source_gap',str(e),code=event['predecessor_code'],date=event['event_date'],portfolio=label)
  held={};claims={}
  for i,dt in enumerate(dates):
   session=str(dt.date());prior=set(held)|{q['security'] for q in claims.values()}
   for fact in catalog:
    code=fact['security'];eid=fact['event_id']
    if fact['ex_date']==session and code in held:
     claims[eid]=dict(security=code,origin=held[code])
     if support and spec.period.end>support and (not fact['decision'] or not fact['listing']):
      issue('missing_dividend_lifecycle','Pending rights need approval/listing beyond catalog support '+support,code=code,date=dt,portfolio=label,event_id=eid,required='Original AGM approval/cancellation and official additional-listing date; preserve date-only availability and explicit virtual settlement model')
    if eid in claims and fact['decision'] and not fact['decision']['approved'] and fact['decision']['actual_date']<=session and fact['decision']['evidence']['publication_date']<session:claims.pop(eid)
    if eid in claims and fact['listing'] and fact['decision'] and fact['decision']['approved']:
     listing=pd.Timestamp(fact['listing']['date']);idx=dates.searchsorted(listing)+spec.research['settlement_lag_sessions']
     if idx<len(dates) and dt==dates[idx] and fact['listing']['evidence']['publication_date']<session and fact['decision']['evidence']['publication_date']<session:
      held.setdefault(code,claims[eid]['origin']);claims.pop(eid)
   for gap in gaps.to_dict('records') if not gaps.empty else []:
    if dt>=pd.Timestamp(gap['event_date']) and gap['predecessor_code'] in prior:
     issue('known_unresolved_event',gap['reason'],code=gap['predecessor_code'],date=dt,portfolio=label,required=gap.get('evidence','Official event and settlement evidence'))
   for code in sorted(prior):
    j=indices[code];value=raw_returns[i,j];reference=r[i,j];basis='raw_close';event=normal.get((dt,code));exempt=False
    if event:
     value=event['event_return'];basis=event['event_type'];exempt=basis=='stock_merger'
     contract=event.get('market_reference_contract')
     if isinstance(contract,str) and contract:
      from corporate_action_reference import validate_reference
      c=validate_reference(contract,session,code);value=p[i,j]/c['reference_price']-1;basis='official_split_reference'
    for (end,security),a in normal.items():
     if security==code and pd.Timestamp(a['last_trade_date'])<dt<end and not math.isfinite(value):value=0;exempt=not math.isfinite(reference);basis='registered_suspension'
    fact=next((f for f in catalog if f['security']==code and f['ex_date']==session),None)
    if fact:
     available=fact['reference_evidence']['publication_date']<session
     if available and math.isfinite(p[i,j]) and p[i,j]>0:
      value=p[i,j]/float(fact['reference_price'])-1;basis='official_dividend_reference'
     else:issue('missing_available_event_reference','Official reference not usable by this close',code=code,date=dt,portfolio=label)
    difference=abs(value-reference)*10000 if math.isfinite(value) and math.isfinite(reference) else None
    known_quote_contract=basis in ['stock_merger','registered_suspension'] and math.isfinite(value)
    if (not math.isfinite(p[i,j]) or p[i,j]<=0) and not known_quote_contract:issue('missing_held_quote','Positive planned holding has no finite positive close',code=code,date=dt,portfolio=label,origin_signal=held.get(code),required='Exact historical observations or independently verified cessation/disposal contract; never interpolate or remove security')
    elif not exempt and (difference is None or difference>HELD_RETURN_TOLERANCE_BPS):
     issue('held_return_reference_gap','Planned holding fails unchanged1bp source/event comparison',code=code,date=dt,portfolio=label,previous_date=str(dates[i-1].date()) if i else None,previous_close=float(p[i-1,j]) if i and math.isfinite(p[i-1,j]) else None,close=float(p[i,j]),exchange_return=float(reference) if math.isfinite(reference) else None,effective_comparison_return=float(value) if math.isfinite(value) else None,difference_bps=difference,basis=basis,origin_signal=held.get(code),required='Official ex-date/reference and action terms, or original-price correction evidence; no inferred split/return override')
    elif basis!='raw_close':explained.append(dict(portfolio=label,security=code,date=session,basis=basis,difference_bps=difference))
   for event in all_events:
    if pd.Timestamp(event['event_date'])==dt and event['predecessor_code'] in held and event['event_type']=='stock_merger':
     origin=held.pop(event['predecessor_code']);held[event['successor_code']]=origin
   if dt in at:
    sig=at[dt];nextheld={c:str(sig.date()) for c in w.columns[w.loc[sig].gt(execution.weight_tolerance)]}
    for code in set(held)|set(nextheld):
     j=indices[code]
     if not math.isfinite(p[i,j]) or p[i,j]<=0 or not math.isfinite(v[i,j]) or v[i,j]<=0:
      if code not in held or code not in nextheld:
       zero_volume=math.isfinite(v[i,j]) and v[i,j]==0
       issue('planned_trade_not_tradable','Entering/exiting planned position has no tradable close',code=code,date=dt,portfolio=label,origin_signal=str(sig.date()),classification='execution_constraint' if zero_volume else 'historical_fact',verdict='FAIL' if zero_volume else 'UNVERIFIED',required='Original exact execution day has zero volume. A separately specified halt-aware execution/settlement contract would change this strategy; no silent delay or exclusion.' if zero_volume else 'Exact execution-day quote/volume and official suspension/resumption information; original lag stays unchanged')
      else:warnings.append(dict(kind='possible_drift_trade_constraint',security=code,date=session,portfolio=label,detail='Same planned member; actual drifting weight determines whether a trade is required'))
    held=nextheld
 result.update(phase='planned_exposure',planned_execution_schedule=schedules,explained_registered_prices=explained,
  full_panel_diagnostics='separate source audit; these incidents concern planned selected cohorts only',price_validation='1bp source/reference diagnostic; economic rights/cash/NAV not simulated or certified',
  runtime_checks_still_required=['actual held quantities and price path','rights economic value','settled cash and costs','drift-dependent trades','unregistered events beyond this planned trace'])
 if not issues:result.update(status='ok',phase='planned_ready',ready_for_execution=True)
 return finish()
