"""Narrow, explicit simultaneous-listing demerger research contract.

A halted cum-right basket is marked at its observed unchanged last close. It is
not two separately observed market prices or a broker-credit assertion. At the
joint listing close both share legs are delivered once; no cash is fabricated.
"""
from pathlib import Path
import hashlib,json,math,re
import pandas as pd
CATALOG='config/research/spinoffs_v1.json'
POLICY='defer_full_rebalance_events_v1'
CONTRACT=dict(version='1',scope='RESEARCH_ONLY continuous quantities before distribution taxes',
 suspension='Every original session must observe flat last close, zero volume and zero/missing reference. Combined cum-right basket mark, not a forward-filled child price.',
 settlement='Virtual simultaneous parent change-listing and child re-listing close; neither actual account receipt nor integer/fractional cash settlement',
 valuation='Frozen combined cum-right last observed value until joint listing; then retained-parent and new-child observed close values. No use of future prices during halt.',
 orders='Both issued share legs become holdings before pending close orders; unpaid proceeds never fund buys',
 unsupported='Non-simultaneous listings, intervening tradable parent, missing suspension rows, integer accounts, fractional cash/tax flows, unknown share terms or reference evidence fail')


def validate(c):
 required={'version','scope','parent','child','last_trade_date','record_date','legal_date','listing_date','parent_ratio','child_ratio','parent_reference','child_reference','quantity_basis','halt_valuation','settlement','evidence'}
 if set(c)!=required or c['version']!=1 or c['scope'] not in ['synthetic','modeled_research']:raise ValueError('invalid spin-off contract')
 if not all(re.fullmatch(r'\d{6}',c[k]) for k in ['parent','child']) or c['parent']==c['child']:raise ValueError('spin-off distinct securities required')
 for k in ['last_trade_date','record_date','legal_date','listing_date']:pd.Timestamp(c[k])
 if not c['last_trade_date']<=c['record_date']<c['legal_date']<c['listing_date']:raise ValueError('invalid spin-off entitlement/listing chronology')
 for k in ['parent_ratio','child_ratio','parent_reference','child_reference']:
  if type(c[k]) not in [int,float] or not math.isfinite(c[k]) or c[k]<=0:raise ValueError('finite positive spin-off quantities and references required')
 if (c['quantity_basis'],c['halt_valuation'],c['settlement'])!=('continuous_pro_rata','observed_frozen_cum_right_basket','virtual_on_simultaneous_listing_close'):raise ValueError('unsupported spin-off valuation/settlement/quantity model')
 for e in c['evidence']:
  if set(e)!={'path','sha256','source','publication_date','location','role'} or not e['location'] or not re.fullmatch('[a-f0-9]{64}',e['sha256']):raise ValueError('explicit spin-off evidence required')
  if e['role'] not in ['terms','parent_listing','child_listing','parent_reference_method','child_reference_method','official_quote']:raise ValueError('unknown spin-off evidence role')
  if pd.Timestamp(e['publication_date'])>pd.Timestamp(c['listing_date']):raise ValueError('future spin-off evidence cannot authorize earlier research settlement')
 if c['scope']=='modeled_research':
  if {e['role'] for e in c['evidence']}!={'terms','parent_listing','child_listing','parent_reference_method','child_reference_method','official_quote'}:raise ValueError('all independently evidenced spin-off roles required')
  if next(e for e in c['evidence'] if e['role']=='terms')['publication_date']>c['last_trade_date']:raise ValueError('spin-off proposal not available to cum-right holder')
 return c


def load_events(root,*,start=None,end=None,asset_codes=None):
 root=Path(root).resolve();path=root/CATALOG
 if not path.exists():return pd.DataFrame()
 catalog=json.loads(path.read_bytes())
 if set(catalog)!={'version','contract','events'} or catalog['version']!=1 or catalog['contract']!=CONTRACT:raise ValueError('spin-off catalog/model contract drift')
 rows=[];seen=set()
 for raw in catalog['events']:
  c=validate(raw)
  if c['scope']!='modeled_research':raise ValueError('synthetic spin-off cannot enter evidence catalog')
  key=(c['parent'],c['listing_date'])
  if key in seen:raise ValueError('duplicate spin-off')
  seen.add(key)
  for e in c['evidence']:
   p=(root/e['path']).resolve()
   if not p.is_relative_to(root) or hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:raise ValueError('spin-off evidence hash/path mismatch')
  if start is not None and pd.Timestamp(c['listing_date'])<pd.Timestamp(start):continue
  if end is not None and pd.Timestamp(c['listing_date'])>pd.Timestamp(end):continue
  if asset_codes is not None and c['parent'] not in asset_codes:continue
  rows.append(dict(event_type='stock_spinoff',event_date=pd.Timestamp(c['listing_date']),predecessor_code=c['parent'],successor_code=c['parent'],share_ratio=c['parent_ratio'],cash_per_share=0.,child_code=c['child'],source=next(e['source'] for e in c['evidence'] if e['role']=='terms'),spin_off_contract=json.dumps(c,sort_keys=True)))
 return pd.DataFrame(rows)


def expand_successors(root,spec,codes,start,end):
 result=set(codes)
 if spec.execution.nontradable_policy!=POLICY:return result
 events=load_events(root,start=start,end=end)
 while not events.empty:
  extra=set(events.loc[events.predecessor_code.isin(result),'child_code'])
  if extra.issubset(result):break
  result.update(extra)
 return result


def normalize(prices,events,mask,volumes,references,targets):
 if events.empty:return pd.DataFrame()
 if mask is None or volumes is None or references is None:raise ValueError('spin-off requires original tradability, volumes and references')
 rows=[]
 for event in events.to_dict('records'):
  c=validate(json.loads(event['spin_off_contract']));parent,child=c['parent'],c['child'];dt=pd.Timestamp(c['listing_date']);last=pd.Timestamp(c['last_trade_date'])
  if event['event_type']!='stock_spinoff' or event['predecessor_code']!=parent or event['successor_code']!=parent or pd.Timestamp(event['event_date'])!=dt or event['share_ratio']!=c['parent_ratio'] or event['cash_per_share']!=0:raise ValueError('spin-off row/contract identity mismatch')
  if not any(d<dt and float(w.get(parent,0))>0 for d,w in targets.items()):continue
  if parent not in prices or child not in prices or dt not in prices.index or last not in prices.index:raise ValueError('spin-off exact observed source dates and both securities required')
  old=float(prices.at[last,parent])
  if not math.isfinite(old) or old<=0 or not mask.at[last,parent]:raise ValueError('spin-off last traded quote required')
  halted=prices.index[(prices.index>last)&(prices.index<dt)]
  if not len(halted):raise ValueError('spin-off simultaneous-listing contract requires observed halt interval')
  for date in halted:
   ref=references.at[date,parent]
   if prices.at[date,parent]!=old or volumes.at[date,parent]!=0 or mask.at[date,parent] or (pd.notna(ref) and ref!=0):raise ValueError('spin-off suspension source gap/change; no filling or inferred mark')
   # Child has no tradable price before its evidenced listing. A future price
   # must not enter the cum-right mark or the historical eligible population.
   if bool(mask.at[date,child]):raise ValueError('child tradable before simultaneous listing; different contract needed')
  pv,cv=float(prices.at[dt,parent]),float(prices.at[dt,child])
  if not all(math.isfinite(x) and x>0 for x in [pv,cv]) or not mask.at[dt,parent] or not mask.at[dt,child]:raise ValueError('both spin-off legs need observed tradable listing-close quotes')
  for code,refprice in [(parent,c['parent_reference']),(child,c['child_reference'])]:
   exchange=references.at[dt,code]
   if not math.isfinite(exchange) or abs(prices.at[dt,code]/refprice-1-exchange)*10000>1.:raise ValueError('spin-off official price/reference mismatch; unchanged1bp')
  value=c['parent_ratio']*pv+c['child_ratio']*cv
  rows.append(dict(**event,last_trade_date=last,last_price=old,successor_price=pv,event_return=value/old-1,child_price=cv,child_ratio=c['child_ratio'],parent_reference=c['parent_reference'],child_reference=c['child_reference'],basket_value_per_old_share=value))
 return pd.DataFrame(rows)
