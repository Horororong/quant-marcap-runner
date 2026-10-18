"""Primary exchange reference versus economic split return: independent checks.

An official event-day reference is neither a holding return nor a NAV override.
Only an exact, already-public evidenced split may use it at the unchanged1bp
source check. Unknown events and ordinary dates retain the existing comparison.
"""
import hashlib,json,math,re
from pathlib import Path
from datetime import date
FIELDS={'version','scope','event_date','security','reference_price','publication_date','source','evidence_path','sha256','location'}
def validate_reference(value,event_date,security):
 c=json.loads(value) if isinstance(value,str) else dict(value)
 if set(c)!=FIELDS or type(c['version']) is not int or c['version']!=1 or c['scope'] not in ['primary','synthetic']:raise ValueError('invalid split market-reference contract')
 for k in ['event_date','publication_date']:date.fromisoformat(c[k])
 if c['event_date']!=str(date.fromisoformat(str(event_date)[:10])) or c['security']!=str(security):raise ValueError('split reference identity/date mismatch')
 if c['publication_date']>=c['event_date']:raise ValueError('date-only split reference unavailable before event close')
 if type(c['reference_price']) not in [int,float] or not math.isfinite(c['reference_price']) or c['reference_price']<=0:raise ValueError('finite positive official split reference required')
 if not re.fullmatch(r'\d{6}',c['security']) or not re.fullmatch('[a-f0-9]{64}',c['sha256']) or not all(c[k] for k in ['source','evidence_path','location']):raise ValueError('explicit split reference provenance required')
 return c

def attach_references(root,events):
 root=Path(root).resolve();file=root/'config/kr_corporate_action_references.json'
 if not file.is_file():return events
 rows=json.loads(file.read_text());seen=set();bykey={}
 for raw in rows:
  c=validate_reference(raw,raw['event_date'],raw['security']);key=(c['event_date'],c['security'])
  if key in seen or c['scope']!='primary':raise ValueError('operational split reference must be unique and primary')
  seen.add(key);p=(root/c['evidence_path']).resolve()
  if not p.is_relative_to(root) or hashlib.sha256(p.read_bytes()).hexdigest()!=c['sha256']:raise ValueError('split primary evidence hash/path mismatch')
  bykey[key]=c
 if not events.empty:
  out=events.copy();values=[]
  for r in out.to_dict('records'):
   c=bykey.get((str(r['event_date'].date()),r['predecessor_code']))
   if c and r['event_type']!='stock_split':raise ValueError('split reference cannot authorize another event type')
   values.append(json.dumps(c) if c else None)
  if any(values):out['market_reference_contract']=values
  return out
 return events
