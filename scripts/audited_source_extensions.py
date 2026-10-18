"""Append-only, pinned official data extensions; immutable original files.

Registry is an explicit data revision. Overlaps, changed bases/evidence,
unknown fields/dates and non-finite required values fail, never overwrite/fill.
"""
import base64,gzip,hashlib,io,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
REGISTRY='config/research/official_source_extensions_v1.json'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def records(root,dataset,start,end):
 root=Path(root);p=root/REGISTRY
 if not p.exists():return []
 doc=json.loads(p.read_bytes())
 if doc['version']!=1:raise ValueError('unknown source extension version')
 out=[]
 for r in doc['datasets']:
  if r['dataset']!=dataset or pd.Timestamp(r['end'])<pd.Timestamp(start) or pd.Timestamp(r['start'])>pd.Timestamp(end):continue
  out.append(r)
 return out

def append(root,dataset,base,path,start,end):
 if start is None or end is None:return base
 root=Path(root);items=records(root,dataset,start,end)
 for r in items:
  if str(Path(path).relative_to(root))!=r['base']['path']:continue
  if digest(root/r['base']['path'])!=r['base']['sha256']:raise ValueError('source extension base changed; explicit revision needed')
  data=root/r['data']['path']
  if digest(data)!=r['data']['sha256']:raise ValueError('extension transport SHA mismatch')
  raw=gzip.decompress(base64.b64decode(data.read_bytes()))
  if hashlib.sha256(raw).hexdigest()!=r['data']['csv_sha256']:raise ValueError('extension CSV SHA mismatch')
  for evidence in r['evidence']:
   if digest(root/evidence['path'])!=evidence['sha256']:raise ValueError('extension primary evidence changed')
  extra=pd.read_csv(io.BytesIO(raw),dtype={'Code':str})
  extra['Date']=pd.to_datetime(extra.Date,errors='raise')
  import numpy as np
  numeric=['Close'] if dataset.startswith('index:') else ['Open','High','Low','Close','Volume','Amount','Changes','ChangesRatio','Marcap','Stocks']
  for name in numeric:
   values=pd.to_numeric(extra[name],errors='raise')
   if not np.isfinite(values).all():raise ValueError('nonfinite required extension field: '+name)
  if dataset.startswith('index:') and not extra.Close.gt(0).all():raise ValueError('nonpositive index extension close')
  if dataset=='equities' and (not extra.Code.str.fullmatch(r'[0-9A-Z]{6}').all() or not extra.Market.isin(['KOSPI','KOSDAQ']).all()):raise ValueError('invalid official extension security/market')
  if not extra.Date.between(r['start'],r['end']).all():raise ValueError('extension outside declared period')
  keys=['Date','Code'] if dataset=='equities' else ['Date']
  if extra.duplicated(keys).any():raise ValueError('duplicate extension observations')
  if extra.Date.isin(pd.to_datetime(base.Date)).any():raise ValueError('append extension overlaps original dates; no overwrite')
  if len(extra)!=r['data']['rows']:raise ValueError('extension row count mismatch')
  extra=extra[extra.Date.between(pd.Timestamp(start),pd.Timestamp(end))]
  if not set(base.columns).issubset(extra.columns):raise ValueError('extension misses requested original fields')
  base=pd.concat([base,extra[base.columns]],ignore_index=True)
 return base

def provenance(root,start,end):
 items=records(root,'equities',start,end)+records(root,'index:KOSPI',start,end)
 if not items:return []
 paths=[REGISTRY]+[r['data']['path'] for r in items]
 return [dict(path=p,bytes=(Path(root)/p).stat().st_size,sha256=digest(Path(root)/p)) for p in sorted(set(paths))]
