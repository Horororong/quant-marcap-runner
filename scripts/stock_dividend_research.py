"""Explicit real-data research policy and separate fact-file adapter.

No operational registry mutation, return override, price inference or account
credit assertion. Conditional-right marks are MODEL values, not observations.
"""
import hashlib
import json
from pathlib import Path
from decimal import Decimal

VERSION='1'
FIELDS={'version','event_file','event_sha256','quantity_basis','rights_valuation','conditional_fraction','settlement_basis','settlement_lag_sessions','distribution_tax_basis'}

def selected_action_scope(repo_root, spec, targets, start, end):
 """Positive selections plus verified successors, never universe filtering.

 All source rows still participate in selection. Unheld dividend catalogs must
 not block an unrelated portfolio, but held rights retain the full lifecycle.
 """
 from corporate_action_registry import load_corporate_actions
 frames=targets.values() if isinstance(targets,dict) else [targets]
 used=set()
 for weights in frames:used.update(weights.columns[weights.ne(0).any(axis=0)])
 if spec.research is not None:
  events=load_corporate_actions(repo_root,start=start,end=end)
  while not events.empty:
   successors=set(events.loc[events.predecessor_code.isin(used)&events.event_type.eq('stock_merger'),'successor_code'])
   if successors.issubset(used):break
   used.update(successors)
 return used

def model_schema():
 return {'type':'object','additionalProperties':False,'required':sorted(FIELDS),'properties':{
  'version':{'const':VERSION},'event_file':{'type':'string','pattern':r'^config/research/[A-Za-z0-9_/-]+\.json$'},
  'event_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},'quantity_basis':{'const':'continuous_pro_rata'},
  'rights_valuation':{'const':'underlying_close_share_equivalent'},'conditional_fraction':{'type':'number','minimum':0,'maximum':1},
  'settlement_basis':{'const':'virtual_on_official_listing_close'},'settlement_lag_sessions':{'type':'integer','minimum':0,'maximum':20},
  'distribution_tax_basis':{'const':'before_distribution_tax'}}}

def validate_model(model):
 from jsonschema import Draft202012Validator
 from math import isfinite
 Draft202012Validator(model_schema()).validate(model)
 if type(model['conditional_fraction']) not in {int,float} or not isfinite(model['conditional_fraction']) or type(model['settlement_lag_sessions']) is not int:
  raise ValueError('strict finite research model numbers required')
 return model

def load_strategy_actions(repo_root,spec,*,start=None,end=None,asset_codes=None,registry_loader=None):
 from corporate_action_registry import load_corporate_actions
 import pandas as pd
 from quant_backtest_template_CURRENT import expected_market_sessions
 # Preserve the common caller's operational-registry dependency (including
 # fail-closed missing-registry tests); research facts only compose with it.
 base=(registry_loader or load_corporate_actions)(repo_root,start=start,end=end,asset_codes=asset_codes)
 model=spec.research
 if model is None:return base
 validate_model(model)
 if spec.metadata.get('classification')!='RESEARCH_ONLY' or spec.metadata.get('investment_use_allowed') is not False:
  raise ValueError('research contract requires explicit RESEARCH_ONLY/investment_use_allowed=false')
 root=Path(repo_root).resolve();path=(root/model['event_file']).resolve()
 if not path.is_relative_to(root):raise ValueError('research event path escapes repository')
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=model['event_sha256']:raise ValueError('research event-file SHA256 mismatch; new facts require new fingerprint')
 facts=json.loads(raw)
 if set(facts)!={'version','events','pending_lifecycle_supported_through'} or facts['version']!=1:raise ValueError('invalid research fact catalog')
 # The execution sessions come from verified exchange-calendar coverage, not weekdays.
 dates=expected_market_sessions(pd.Timestamp(spec.period.start),pd.Timestamp(spec.period.end),'XKRX')
 sessions=[str(d.date()) for d in dates]
 def first_on_or_after(d):return next((s for s in sessions if s>=d),None)
 def evidence(e):
  if set(e)!={'source','sha256','location','publication_date'}:raise ValueError('fact evidence needs explicit public date; no backdated historical document')
  available=next((s for s in sessions if s>e['publication_date']),None)
  return dict(source=e['source'],sha256=e['sha256'],location=e['location'],usable_session=available or '9999-12-31',kind='primary')
 added=[];seen=set()
 for fact in facts['events']:
  if set(fact)!={'event_id','security','ex_date','record_date','rate','terms_evidence','reference_price','reference_evidence','decision','listing'}:raise ValueError('fact catalog missing/unknown fields')
  key=(fact['security'],fact['ex_date'])
  if key in seen:raise ValueError('duplicate research security/ex-date')
  seen.add(key)
  if start is not None and fact['ex_date']<str(pd.Timestamp(start).date()):continue
  if end is not None and fact['ex_date']>str(pd.Timestamp(end).date()):continue
  if asset_codes is not None and fact['security'] not in asset_codes:continue
  if spec.period.end>facts['pending_lifecycle_supported_through'] and (fact['decision'] is None or fact['listing'] is None):
   raise ValueError('data_gap: pending dividend lifecycle beyond catalog support '+facts['pending_lifecycle_supported_through']+'; approval/listing must be obtained, never modeled indefinitely')
  ev=evidence(fact['terms_evidence'])
  if ev['usable_session']>fact['ex_date']:raise ValueError('proposal terms unavailable before ex-date')
  reference=evidence(fact['reference_evidence'])
  if reference['usable_session']>fact['ex_date']:raise ValueError('official reference price unavailable by ex-date close')
  decisions=[]
  if fact['decision']:
   d=fact['decision'];de=evidence(d['evidence']);recognition=first_on_or_after(max(d['actual_date'],de['usable_session']))
   if recognition:decisions=[dict(actual_date=d['actual_date'],recognition_date=recognition,approved=d['approved'],evidence=de,**d.get('cancellation',{}))]
  listing=None
  if fact['listing']:
   l=fact['listing'];le=evidence(l['evidence'])
   session=first_on_or_after(l['date'])
   if session:
    i=sessions.index(session)+model['settlement_lag_sessions']
    if i<len(sessions):
     modeled=sessions[i]
     if le['usable_session']>modeled:raise ValueError('listing evidence not yet public at virtual settlement')
     listing=dict(date=l['date'],model_settlement_date=modeled,evidence=le)
  contract=dict(scope='modeled_research',quantity_policy='research_pro_rata',
   terms={k:fact[k] for k in ['event_id','security','ex_date','record_date','rate']},decisions=decisions,credits=[],listings=[],marks=[],
   market_reference=dict(reference_price=fact['reference_price'],evidence=reference),research_model=dict(contract=model,official_listing=listing))
  contract['terms']['evidence']=ev
  added.append(dict(event_date=pd.Timestamp(fact['ex_date']),event_type='stock_dividend',predecessor_code=fact['security'],successor_code=fact['security'],share_ratio=float(Decimal(fact['rate'])),cash_per_share=0.,source=fact['terms_evidence']['source'],stock_dividend_contract=json.dumps(contract)))
 out=pd.concat([base,pd.DataFrame(added)],ignore_index=True) if added else base
 if not out.empty and out.duplicated(['event_date','predecessor_code']).any():raise ValueError('research and operational events overlap')
 return out
