import json,csv,gzip,hashlib,subprocess
from pathlib import Path
from collections import Counter,defaultdict
import pyarrow.parquet as pq
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
def read(p):
 op=gzip.open if p.suffix=='.gz' else open
 with op(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
state=read(ROOT/'data/status/dart_legacy_backfill_state.csv');index=read(ROOT/'data/financials/legacy_2000_2014/legacy_filings.csv.gz')
current={s['rcept_no']:s for s in state if (s['source_version']=='opendart-document-v1' or (not s['source_version'] and s['parser_version']=='legacy-v4-book')) and (s['parser_version']=='legacy-v5-single-amount' or s['status']=='NO_DOCUMENT')}
metrics=[]
for p in (ROOT/'data/financials/legacy_2000_2014/normalized').glob('*.gz'):metrics.extend(read(p))
byreceipt=defaultdict(list)
for m in metrics:
 if m['parser_version']=='legacy-v5-single-amount':byreceipt[m['rcept_no']].append(m)
done={s['rcept_no'] for s in current.values() if s['status'] in ['NO_METRICS','NO_DOCUMENT']};lost=[]
for s in current.values():
 if s['status'] in ['PARSED_4F','PARSED_PARTIAL']:
  group=byreceipt[s['rcept_no']]
  if len(group)==int(s['metric_rows']) and s['document_sha256'] and all(m['document_sha256']==s['document_sha256'] for m in group):done.add(s['rcept_no'])
  else:lost.append(s['rcept_no'])
eligible={s['rcept_no'] for s in index if len(s['stock_code'])==6 and s['stock_code'].isdigit()};pending=eligible-done
modern=read(ROOT/'data/status/dart_full_backfill_state.csv');keys=['stock_code','corp_code','year','period','fs_div'];unique={tuple(r[k] for k in keys):r for r in modern};groups=defaultdict(Counter)
for r in unique.values():groups[(r['year'],r['period'],r['fs_div'])][r['status']]+=1
modern_table=[dict(year=y,period=p,scope=s,**dict(counts)) for (y,p,s),counts in sorted(groups.items())]
with (OUT/'modern_task_coverage.csv').open('w',newline='') as f:
 cols=['year','period','scope']+sorted({k for r in modern_table for k in r if k not in ['year','period','scope']});w=csv.DictWriter(f,cols);w.writeheader();w.writerows(modern_table)
prices=[]
for path in sorted((ROOT/'data/krx_equities/yearly').glob('*.parquet')):
 df=pq.read_table(path,columns=['Date','Code','Market','Close']).to_pandas();df['Date']=pd.to_datetime(df['Date']);markets={str(m):dict(first=str(g.Date.min().date()),latest=str(g.Date.max().date()),sessions=g.Date.nunique(),codes=g.Code.nunique(),rows=len(g)) for m,g in df.groupby('Market')}
 prices.append(dict(file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(df),first=str(df.Date.min().date()),latest=str(df.Date.max().date()),unique_codes=df.Code.nunique(),duplicates=int(df.duplicated(['Date','Code']).sum()),missing_close=int(df.Close.isna().sum()),markets=markets))
 print('price audited',path.name,flush=True)
bench=[]
for name in ['KOSPI','KOSDAQ','KOSPI200','KOSDAQ150']:
 path=ROOT/'data/indices'/f'{name}.csv';df=pd.read_csv(path);col=next(c for c in df.columns if c.lower()=='date');ds=pd.to_datetime(df[col]);bench.append(dict(symbol=name,first=str(ds.min().date()),latest=str(ds.max().date()),rows=len(df),return_basis='price_index_close',includes_dividends=False))
result=dict(repository_baseline=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),legacy=dict(indexed=len(index),mapped=len(eligible),current_state=len(current),durable_done=len(done),pending=len(pending),parsed_records_missing_or_hash_mismatch=lost,current_statuses=dict(Counter(r['status'] for r in current.values())),normalized_all_parser_versions=len(metrics),normalized_v5=len([r for r in metrics if r['parser_version']=='legacy-v5-single-amount']),source_filing_min=min(r['rcept_dt'] for r in index),source_filing_max=max(r['rcept_dt'] for r in index)),modern=dict(unique_tasks=len(unique),statuses=dict(Counter(r['status'] for r in unique.values())),latest_checkpoint=max(r['updated_at_utc'] for r in unique.values()),scope_note='task terminal NO_DATA is not usable financial data; expected task universe must be regenerated from current supported period availability before remaining count',full_shards=len(list((ROOT/'data/financials/full_history').glob('*.gz')))),krx=prices,benchmarks=bench)
(OUT/'coverage_snapshot.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='krx'},ensure_ascii=False,indent=2))

import json,csv,datetime,collections,re,gzip
from pathlib import Path
import pyarrow.parquet as pq
R=ROOT;O=OUT
def read(p):
 with open(p,encoding='utf-8-sig') as f:return list(csv.DictReader(f))
x=json.loads((O/'coverage_snapshot.json').read_text());mapping=read(R/'data/financials/dart_historical_code_map.csv');tasks=set()
for r in mapping:
 if not re.fullmatch(r'\d{8}',r['corp_code']):continue
 first=int(r['first_date'][:4]);last=int(r['last_date'][:4])
 for year in range(max(2015,first-1),min(2026,last)+1):
  for period in ['FY'] if year<first else ['Q1','H1','Q3','FY']:
   cutoff=f'{year+1}-04-01' if period=='FY' else f'{year}-'+{'Q1':'05-16','H1':'08-16','Q3':'11-16'}[period]
   if cutoff>'2026-10-04':continue
   for scope in ['CFS','OFS']:tasks.add((r['stock_code'],r['corp_code'],str(year),period,scope))
state=read(R/'data/status/dart_full_backfill_state.csv');done={tuple(r[k] for k in ['stock_code','corp_code','year','period','fs_div']) for r in state if r['status'] in ['OK','NO_DATA']};missing=tasks-done
byperiod=collections.Counter((y,p,s) for code,corp,y,p,s in missing)
x['modern'].update(expected_tasks_current_mapping=len(tasks),completed_expected_tasks=len(tasks&done),pending_expected_tasks=len(missing),completed_outside_current_mapping=len(done-tasks),historical_mapping_rows=len(mapping),historical_mapping_unmatched=sum(not bool(re.fullmatch(r'\d{8}',r['corp_code'])) for r in mapping),task_generator_definition='scripts/backfill_dart_full_financials.py build_tasks; collection cutoffs are NOT PIT availability dates',pending_by_period=[dict(year=y,period=p,scope=s,count=n) for (y,p,s),n in sorted(byperiod.items())],actual_shard_periods=sorted({re.search(r'dart_full_(\d{4}_[A-Z0-9]+_[A-Z]+)',p.name).group(1) for p in (R/'data/financials/full_history').glob('*.gz')}))
df=pq.read_table(R/'data/krx_equities/yearly/marcap-1997.parquet').to_pandas();x['price_missing_close_records']=df.loc[df.Close.isna()].astype(str).to_dict('records');x['legacy']['current_state_scope_note']='Current state includes transport-only receipts outside the mapped universe; intersect durable_done with mapped receipts before comparing processed status.';(O/'coverage_snapshot.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in x['modern'].items() if k not in ['pending_by_period','actual_shard_periods']},ensure_ascii=False,indent=2));print('MISSING_CLOSE',x['price_missing_close_records']);print('SHARD_PERIODS',x['modern']['actual_shard_periods'])
