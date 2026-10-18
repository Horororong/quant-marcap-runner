"""Bounded restore of EXISTING official evidence, no DART requests/collector.
Freeze holdout receipts before reading money or originals. Preserve exact bytes.
"""
import argparse,base64,csv,gzip,hashlib,io,json,os,sys,zipfile
from pathlib import Path
from urllib import request,error,parse
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'docs/research/long-multi-backfill-20261018'))
from restore_existing_evidence import NoRedirect
def sha(b):return hashlib.sha256(b).hexdigest()
def csvrows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def restore(artifact,digest,out):
 out.mkdir(parents=True,exist_ok=False)
 url=f'https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/{artifact}/zip'
 try:
  request.build_opener(NoRedirect()).open(request.Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}),timeout=25)
  raise ValueError('EXPECTED_ARCHIVE_302')
 except error.HTTPError as e:
  if e.code!=302:raise ValueError('ARTIFACT_HTTP_'+str(e.code)) from None
  location=e.headers.get('Location','');host=parse.urlparse(location).hostname
 if parse.urlparse(location).scheme!='https' or not host or not host.endswith(('.blob.core.windows.net','.actions.githubusercontent.com','.githubusercontent.com')):raise ValueError('Unapproved redirect')
 path=out/'original-artifact.zip';n=0;h=hashlib.sha256()
 with request.build_opener(NoRedirect()).open(location,timeout=60) as r,path.open('xb') as f:
  for b in iter(lambda:r.read(1048576),b''):
   n+=len(b)
   if n>260*1024*1024:raise ValueError('Archive bound')
   h.update(b);f.write(b)
 if h.hexdigest()!=digest:raise ValueError('Pinned digest mismatch')
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  assert all(not Path(x).is_absolute() and '..' not in Path(x).parts for x in z.namelist())
  z.extractall(out/'evidence')
 return out/'evidence'

def main(out):
 out.mkdir(parents=True,exist_ok=False);plan=json.loads((HOME/'holdout_plan.json').read_text())
 old=json.loads((ROOT/'docs/research/long-multi-backfill-20261018/independent_controls.json').read_text())['controls']
 old_selection=json.loads(gzip.decompress(base64.b64decode((ROOT/'docs/research/long-multi-backfill-20261018/sources/main_evidence-recovered__selection.json.gz.b64').read_bytes())))['selected']
 excluded={s['receipt'] for s in old_selection}
 for name in ('original40-selection.json','holdout20-selection.json'):
  excluded.update(s['rcept_no'] for s in json.loads((ROOT/'docs/audits/financial-repair-20261014'/name).read_text())['samples'])
 new=restore(plan['artifact'],plan['artifact_sha256'],out/'new-source')
 effective={r['rcept_no']:r for r in csvrows(new/'effective-state.csv')}
 changed=csvrows(new/'changed-state.csv');groups={};chosen=[]
 for status,count in plan['strata'].items():
  candidates=[dict(effective.get(r['rcept_no'],{}),**r) for r in changed if r['rcept_no'] not in excluded and effective.get(r['rcept_no'],r).get('status')==status]
  buckets={}
  for r in candidates:buckets.setdefault((r.get('fiscal_year',''),r.get('period','')),[]).append(r)
  for rows in buckets.values():rows.sort(key=lambda r:sha((plan['seed']+':'+r['rcept_no']).encode()))
  used=set();picked=[]
  while any(buckets.values()) and len(picked)<count:
   for key in sorted(buckets):
    rows=buckets[key]
    while rows and rows[0].get('corp_code') in used:rows.pop(0)
    if rows and len(picked)<count:
     r=rows.pop(0);used.add(r.get('corp_code'));picked.append(dict(r,stratum=status))
  chosen.extend(picked)
 for i,r in enumerate(chosen):r['sample']='H'+str(i+1).zfill(2)
 selection={'plan':plan,'samples':chosen,'excluded_receipts':sorted(excluded)}
 (out/'selected_receipts.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
 # Receipt list is durable BEFORE any amount file or document is opened.
 prior=restore(12122416836,'6faea3647a128da272d76aa0d315f4bdb93c7e46ba4554a8314add2d5b8f2f65',out/'prior-source')
 recs=[(s['receipt'],prior,'development',s['sample']) for s in old_selection if s['stratum'] in ('PARSED_4F','PARSED_PARTIAL','SOURCE_GAP')]
 recs += [(s['rcept_no'],new,'holdout',s['sample']) for s in chosen]
 payload={'selection':selection,'files':{},'manifest':[],'metrics':{}}
 for root,label in ((prior,'development'),(new,'holdout')):
  want={r for r,rr,_,_ in recs if rr==root}
  payload['metrics'][label]=[r for r in csvrows(root/'new-metrics.csv') if r['rcept_no'] in want]
 for receipt,root,cohort,sid in recs:
  paths=sorted((root/'native').glob(receipt+'-*.zip'))
  entry={'receipt':receipt,'sample':sid,'cohort':cohort,'archives':[]}
  for p in paths:
   b=p.read_bytes();name=cohort+'/'+p.name
   entry['archives'].append({'path':name,'bytes':len(b),'sha256':sha(b)})
   payload['files'][name]=base64.b64encode(b).decode()
  payload['manifest'].append(entry)
 raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();compressed=gzip.compress(raw,mtime=0)
 assert len(compressed)<12*1024*1024
 encoded=base64.b64encode(compressed).decode();(out/'selected_originals.json.gz.b64').write_text(encoded+'\n')
 # A single unreferenced Git blob is a public UTF8 transfer object, never a ref,
 # main commit or source modification. It contains only selected public originals.
 body=json.dumps({'content':encoded+'\n','encoding':'utf-8'}).encode()
 req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=body,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with request.urlopen(req,timeout=60) as r:blob=json.load(r)
 result={'blob_sha':blob['sha'],'compressed_sha256':sha(compressed),'compressed_bytes':len(compressed),'raw_bytes':len(raw),'documents':len(recs),'holdout_receipts':[r['rcept_no'] for r in chosen],'new_dart_calls':0,'selection_sha256':sha((out/'selected_receipts.json').read_bytes())}
 (out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
