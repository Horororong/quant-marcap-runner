"""Read a pinned main clone and EXISTING batch evidence, without calling collectors.
No API, financial parsing or writes to main. Pre-value sample plan is immutable.
"""
import argparse,base64,gzip,hashlib,json,re,sys,zipfile
from pathlib import Path
from html.parser import HTMLParser
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];HOME=Path(__file__).resolve().parent

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return pd.read_csv(p,dtype=str,keep_default_na=False)
class Grid(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.tables=[];self.stack=[];self.cell=None;self.history=''
 def handle_starttag(self,tag,attrs):
  if tag.lower()=='table':self.tables.append(dict(index=len(self.tables),context=self.history[-1500:],rows=[]));self.stack.append(self.tables[-1])
  if tag.lower()=='tr' and self.stack:self.stack[-1]['rows'].append([])
  if tag.lower() in ['td','th','te'] and self.stack:self.cell=[]
 def handle_data(self,data):
  self.history+=' '+data
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag.lower() in ['td','th','te'] and self.cell is not None:
   if self.stack and self.stack[-1]['rows']:self.stack[-1]['rows'][-1].append(' '.join(' '.join(self.cell).split()))
   self.cell=None
  if tag.lower()=='table' and self.stack:self.stack.pop()

def main(snapshot,evidence,out):
 out.mkdir(parents=True,exist_ok=False);plan=json.loads((HOME/'sample_plan.json').read_bytes())
 state=read(snapshot/'data/status/dart_legacy_backfill_state.csv');effective=read(evidence/'effective-state.csv');changed=read(evidence/'changed-state.csv');index=read(snapshot/'data/financials/legacy_2000_2014/legacy_filings.csv.gz').drop_duplicates('rcept_no')
 info=effective.merge(index,on='rcept_no',how='left',suffixes=('','_index'));chosen=[];used=set()
 for status,n in plan['strata'].items():
  if status=='QUARANTINED_ERROR':
   candidate=info[info.status.eq('ERROR')].copy();attempt=next((c for c in ['error_attempts','attempts','attempt_count'] if c in candidate),None)
   if attempt:candidate=candidate[pd.to_numeric(candidate[attempt],errors='coerce').ge(3)]
  else:candidate=info[info.rcept_no.isin(changed.rcept_no)&info.status.eq(status)].copy()
  candidate=candidate[~candidate.rcept_no.isin(used)].copy();candidate['rank']=candidate.rcept_no.map(lambda r:sha((plan['seed']+':'+r).encode()))
  groups=[g.sort_values('rank').to_dict('records') for _,g in candidate.groupby(['fiscal_year','period'],sort=True,dropna=False)];seen=set();picked=[]
  while groups and len(picked)<n:
   rest=[]
   for g in groups:
    while g and g[0].get('corp_code') in seen:g.pop(0)
    if g and len(picked)<n:
     row=g.pop(0);seen.add(row.get('corp_code'));row.update(audit_stratum=status,cohort='LATEST_CHANGED' if row['rcept_no'] in set(changed.rcept_no) else 'OLDER_QUARANTINE');picked.append(row);used.add(row['rcept_no'])
    if g:rest.append(g)
   groups=rest
  chosen.extend(picked)
 # Additive access-limited subset cohort was declared before reading values.
 available={p.name[:14] for p in evidence.glob('*.zip')}|{p.name[:14] for p in (evidence/'native').glob('*.zip')}
 if not (evidence/'before').exists():
  for status in ['PARSED_4F','PARSED_PARTIAL']:
   candidates=info[info.rcept_no.isin(changed.rcept_no)&info.rcept_no.isin(available)&info.status.eq(status)&~info.rcept_no.isin(used)].copy()
   candidates['rank']=candidates.rcept_no.map(lambda r:sha((plan['seed']+':available:'+r).encode()))
   for row in candidates.sort_values('rank').drop_duplicates('corp_code').head(4).to_dict('records'):
    row.update(audit_stratum=status,cohort='ADDITIONAL_AVAILABLE_SOURCE_PRE_VALUE');chosen.append(row);used.add(row['rcept_no'])
 pd.DataFrame(chosen).to_csv(out/'selected_state.csv',index=False)
 # Selection is now durably frozen BEFORE reading any monetary outputs.
 selection=dict(plan=plan,selected=[dict(sample=f'A{i+1:02}',receipt=x['rcept_no'],stratum=x['audit_stratum'],cohort=x['cohort']) for i,x in enumerate(chosen)])
 (out/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
 metrics=read(evidence/'new-metrics.csv');metrics[metrics.rcept_no.isin(used)].to_csv(out/'selected_metrics.csv',index=False)
 before_path=evidence/'before/data/status/dart_legacy_backfill_state.csv';before=read(before_path) if before_path.exists() else pd.DataFrame(columns=state.columns);after_path=evidence/'after/data/status/dart_legacy_backfill_state.csv';after=read(after_path) if after_path.exists() else state
 def counts(frame):return dict(rows=len(frame),duplicate_receipts_across_all_versions=int(frame.rcept_no.duplicated().sum()),duplicate_receipt_version=int(frame.duplicated(['rcept_no','parser_version']).sum()),statuses=frame.status.value_counts().to_dict(),versions=frame.parser_version.value_counts().to_dict())
 before_last=before.drop_duplicates('rcept_no',keep='last').set_index('rcept_no');after_last=after.drop_duplicates('rcept_no',keep='last').set_index('rcept_no');transition={}
 for row in chosen:
  receipt=row['rcept_no'];a=before_last.loc[receipt].status if receipt in before_last.index else 'ABSENT';b=after_last.loc[receipt].status if receipt in after_last.index else 'ABSENT';transition[a+'->'+b]=transition.get(a+'->'+b,0)+1
 summary=dict(before_available=before_path.exists(),before=counts(before),after=counts(after),effective=counts(effective),changed=counts(changed),transitions_selected=transition,selected=len(chosen),source_originals_recollected=0)
 # Independent lossless cell TEXT export. No existing financial parser, account
 # aliases, sign conversion, period selection or unit calculation is invoked.
 grids=[];source=[]
 for row in chosen:
  receipt=row['rcept_no'];files=sorted((evidence/'native').glob(receipt+'-*.zip')) or sorted(evidence.glob(receipt+'-*.zip'));rec=dict(receipt=receipt,files=[])
  for p in files:
   b=p.read_bytes();entry=dict(path=str(p.relative_to(evidence)),bytes=len(b),sha256=sha(b),members=[])
   with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    for name in z.namelist():
     if name.endswith('/'):continue
     data=z.read(name)
     if len(data)>30*1024*1024:raise ValueError('member too large')
     text=None;encoding=None
     for enc in ['utf-8','cp949','euc-kr']:
      try:text=data.decode(enc);encoding=enc;break
      except UnicodeDecodeError:pass
     entry['members'].append(dict(name=name,bytes=len(data),sha256=sha(data),encoding=encoding))
     if text is not None:
      g=Grid();g.feed(text);grids.append(dict(receipt=receipt,archive_sha256=sha(b),member=name,member_sha256=sha(data),encoding=encoding,header_text=' '.join(g.history[:12000].split()),tables=g.tables))
   rec['files'].append(entry)
  source.append(rec)
 (out/'source_manifest.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n');(out/'source_grids.json.gz.b64').write_bytes(base64.b64encode(gzip.compress(json.dumps(grids,ensure_ascii=False).encode(),mtime=0))+b'\n')
 summary['source_receipts']=sum(bool(x['files']) for x in source);summary['missing_source_receipts']=[x['receipt'] for x in source if not x['files']]
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 for p in ['scripts/backfill_dart_legacy_2000_2014.py','scripts/legacy_financial_fields.py','scripts/legacy_backfill_runtime.py','scripts/backfill_super_value_fast.py','data/status/dart_status.csv','data/status/dart_rotation_state.csv','data/status/dart_full_backfill_status.csv']:
  b=(snapshot/p).read_bytes();dest=out/'main_snapshot'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 # Transport contains grids, selected state/metrics and source identities, not
 # the199MB archive or full checkpoint. Original artifact remains untouched.
 sys.path.insert(0,str(HOME));from evidence_transport import emit
 emit(out,'MAIN_EVIDENCE')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.snapshot,a.evidence,a.output)
