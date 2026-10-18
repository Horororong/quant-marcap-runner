"""Official date-specific cash-equity closures over the pinned calendar.
No inferred weekdays, package upgrade, trading-state or investment certification.
"""
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];REGISTRY='config/research/official_calendar_corrections_v1.json'

def apply(dates,market='XKRX'):
 dates=pd.DatetimeIndex(dates)
 if market!='XKRX' or dates.empty or dates[-1]<pd.Timestamp('2026-01-01') or dates[0]>pd.Timestamp('2026-12-31'):return dates
 p=ROOT/REGISTRY
 if not p.exists():return dates
 doc=json.loads(p.read_bytes())
 if doc['version']!=1:raise ValueError('unknown official calendar correction version')
 closures=[]
 for row in doc['closures']:
  if row['market']!='XKRX' or row['scope']!='KOSPI_AND_KOSDAQ_CASH_EQUITIES':raise ValueError('unsupported calendar scope')
  day=pd.Timestamp(row['date'])
  if not dates[0]<=day<=dates[-1]:continue
  if pd.Timestamp(row['publication_date'])>=day:raise ValueError('closure evidence not published before effective date')
  for pin in row['evidence']:
   file=ROOT/pin['path']
   if hashlib.sha256(file.read_bytes()).hexdigest()!=pin['sha256']:raise ValueError('official calendar evidence SHA mismatch')
  closures.append(day)
 return dates.difference(pd.DatetimeIndex(closures)).sort_values()

def provenance(start,end):
 p=ROOT/REGISTRY
 if not p.exists() or pd.Timestamp(end)<pd.Timestamp('2026-01-01') or pd.Timestamp(start)>pd.Timestamp('2026-12-31'):return None
 return dict(path=REGISTRY,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),scope='Date-specific official cash-market corrections; no legal/security/PIT certification')
