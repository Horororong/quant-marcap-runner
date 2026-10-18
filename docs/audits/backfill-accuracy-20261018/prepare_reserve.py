"""One small DISTINCT existing artifact; additive blinded cohort, no recollection."""
import argparse,base64,csv,gzip,hashlib,json,os,sys,zipfile
from pathlib import Path
from urllib import request
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];sys.path.insert(0,str(HOME))
from prepare_sources import restore,sha,csvrows

def main(out):
 out.mkdir(parents=True,exist_ok=False);plan=json.loads((HOME/'reserve_plan.json').read_text());pinned=json.loads((HOME/'holdout_selection.json').read_text());excluded=set(pinned['excluded_receipts'])|{r['rcept_no'] for r in pinned['samples']}
 root=restore(plan['artifact'],plan['artifact_sha256'],out/'existing-subset')
 with gzip.open(ROOT/'data/financials/legacy_2000_2014/legacy_filings.csv.gz','rt',encoding='utf-8-sig')as f:index={r['rcept_no']:r for r in csv.DictReader(f)}
 available={p.name[:14] for p in root.rglob('*.zip')};states=csvrows(root/'effective-state.csv');chosen=[]
 for status,limit in plan['strata'].items():
  candidates=[dict(index.get(r['rcept_no'],{}),**r) for r in states if r['rcept_no'] in available and r['rcept_no'] not in excluded and r['status']==status];candidates.sort(key=lambda r:sha((plan['seed']+':'+r['rcept_no']).encode()));used=set()
  for r in candidates:
   if r.get('corp_code') and r['corp_code'] in used:continue
   used.add(r.get('corp_code'));chosen.append(dict(r,sample='R'+str(len(chosen)+1).zfill(2),stratum=status));limit-=1
   if limit==0:break
 selection=dict(plan=plan,samples=chosen,excluded_receipts=sorted(excluded));(out/'selected_receipts.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
 data=dict(selection=selection,files={},manifest=[],metrics=[]);want={r['rcept_no']for r in chosen};data['metrics']=[r for r in csvrows(root/'new-metrics.csv') if r['rcept_no']in want]
 for r in chosen:
  archives=[]
  for p in sorted(root.rglob(r['rcept_no']+'-*.zip')):
   b=p.read_bytes();name=p.name;data['files'][name]=base64.b64encode(b).decode();archives.append(dict(path=name,bytes=len(b),sha256=sha(b)))
  data['manifest'].append(dict(receipt=r['rcept_no'],sample=r['sample'],cohort='reserve',archives=archives))
 raw=gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),mtime=0);assert len(raw)<2*1024*1024;encoded=base64.b64encode(raw).decode()+'\n';(out/'reserve_originals.json.gz.b64').write_text(encoded)
 req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=encoded,encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with request.urlopen(req,timeout=60)as response:blob=json.load(response)
 result=dict(blob_sha=blob['sha'],compressed_sha256=sha(raw),bytes=len(raw),selected=[r['rcept_no']for r in chosen],new_DART_calls=0);(out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
