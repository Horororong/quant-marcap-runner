"""Verify the real two-document prerequisite from immutable Actions evidence.

No DART HTTP. Never treat a green workflow with0collection as qualification.
"""
import argparse,hashlib,io,json,os,sys,tempfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_limited_resume as operating
REPO='Horororong/quant-marcap-runner';TRIAL='39863731314';ARTIFACT=12462438642
ARTIFACT_SHA256='792ebb5767cd93bae59dad33c3e1a69145d201e3b25897ac478f15b7cea01263'
RECEIPTS=['20100331002062','20100331002063'];BEFORE='7912455f138abf3d1ce9762f8de6a67c70e5b835';AFTER='56514a4631fc5d677af732e90b382fb5937504c6'
class SafeRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  out=super().redirect_request(req,fp,code,msg,headers,newurl)
  if out is not None:out.remove_header('Authorization')
  return out

def inspect_extracted(folder,before,after):
 summaries=list(folder.rglob('summary.json'));assert len(summaries)==1,'EXACT_TRIAL_SUMMARY_REQUIRED'
 base=summaries[0].parent;summary=json.loads(summaries[0].read_text());batch=base/'batch';status=summary['run_status']
 assert summary['completed_receipts']==RECEIPTS and summary['durable_terminal_documents']==2 and summary['extracted_documents']==2
 assert status['status']=='PAUSED_CANDIDATES_HELD'and status['stop_reason']=='BATCH_DOCUMENT_LIMIT'and status['completed']==2 and status['elapsed_seconds']<600
 assert after['last_checkpoint']==RECEIPTS[-1] and before['last_checkpoint']=='20100331002054'
 assert len(after['completed_receipts'])==len(set(after['completed_receipts'])) and after['completed_receipts']==before['completed_receipts']+RECEIPTS
 assert len(after['runs'])==len(before['runs'])
 for old,new in zip(before['runs'],after['runs']):
  assert all(new[k]==v for k,v in old.items()),'ORIGINAL_RUN_HISTORY_CHANGED'
 segments=after['runs'][-1]['resume_segments'];assert len(segments)==1 and segments[0]['run_id']==TRIAL and segments[0]['status']=='PAUSED'and segments[0]['durable_documents']==2
 documents=[];identities=[];http=0;retry=0
 for receipt in RECEIPTS:
  result=json.loads((batch/'results'/str(receipt+'.json')).read_text());assert result['state']['status']in {'PARSED_4F','PARSED_PARTIAL'}and result['rows']
  operating.validate_result(result['meta'],result,batch)
  archives=list((batch/'native').glob(receipt+'-*.zip'));assert len(archives)==1
  with zipfile.ZipFile(archives[0])as z:assert z.testzip()is None
  progress=batch/'workers'/receipt/'progress.jsonl';events=[json.loads(s)for s in progress.read_text().splitlines()];attempts=sum(e['stage']=='http_start'for e in events);retried=sum(e['stage']=='http_retry'for e in events)
  assert 1<=attempts<=2;http+=attempts;retry+=retried
  for row in result['rows']:identities.append(tuple(row.get(k)for k in ['rcept_no','metric','scope','statement','period_start','period_end','measurement_basis']))
  documents.append(dict(receipt=receipt,stock_code_hint=result['meta']['stock_code'],company_hint=result['meta']['corp_name'],source_sha256=hashlib.sha256(archives[0].read_bytes()).hexdigest(),zip_crc='PASS',candidate_fields=len(result['rows']),status=result['state']['status'],HTTP_requests_including_retries=attempts,retries=retried,progress_sha256=hashlib.sha256(progress.read_bytes()).hexdigest()))
 assert len(identities)==len(set(identities)),'DUPLICATE_CANDIDATE_IDENTITIES';assert http<=4 and sum(d['candidate_fields']for d in documents)==summary['candidate_fields']
 for key,value in [('automatic_financial_publication','HOLD'),('backtest_eligible',False),('investment_PIT','0/6')]:assert before[key]==after[key]==value
 return dict(status='PASS_REAL_TRIAL_PREREQUISITES',run_id=TRIAL,artifact_id=ARTIFACT,artifact_sha256=ARTIFACT_SHA256,code_sha=BEFORE,after_commit=AFTER,documents=documents,HTTP_requests_including_retries=http,retries=retry,new_originals=2,new_candidates=summary['candidate_fields'],duplicate_receipts=0,duplicate_candidates=0,source_elapsed_seconds=status['elapsed_seconds'],normal_exit=True,checkpoint_before=before['last_checkpoint'],checkpoint_after=after['last_checkpoint'],remaining_documents=len(status['remaining_receipts']),original_attempts=3,financial_publication='HOLD',investment_PIT='0/6',classification='RESEARCH_ONLY',semantic_validation='NOT_PERFORMED',PIT_validation='NOT_PERFORMED')

def verify_remote():
 token=os.environ['GH_TOKEN'];api='https://api.github.com/repos/'+REPO;opener=urllib.request.build_opener(SafeRedirect())
 def get(path):
  req=urllib.request.Request(api+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
  with opener.open(req,timeout=60)as r:return r.read()
 run=json.loads(get('/actions/runs/'+TRIAL));assert run['conclusion']=='success'and run['head_sha']==BEFORE
 blob=get('/actions/artifacts/'+str(ARTIFACT)+'/zip');assert len(blob)<=4*1024*1024 and hashlib.sha256(blob).hexdigest()==ARTIFACT_SHA256
 def state_at(ref):
  import base64
  return json.loads(base64.b64decode(json.loads(get('/contents/'+str(operating.STATE)+'?ref='+ref))['content']))
 before,after=state_at(BEFORE),state_at(AFTER)
 with tempfile.TemporaryDirectory(prefix='finite-trial-evidence-')as t:
  folder=Path(t)
  with zipfile.ZipFile(io.BytesIO(blob))as z:
   assert z.testzip()is None and sum(x.file_size for x in z.infolist())<=16*1024*1024
   assert all(not n.startswith('/')and'..'not in Path(n).parts for n in z.namelist());z.extractall(folder)
  return inspect_extracted(folder,before,after)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=verify_remote();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('TRIAL_QUALIFICATION_JSON='+json.dumps(result,ensure_ascii=False,separators=(',',':')))
