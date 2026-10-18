"""Official GitHub artifact reads, ONE attempt each; credentials never forwarded.
Existing large artifact first; distinct small review subset only if unavailable.
"""
import argparse,hashlib,json,os,zipfile
from pathlib import Path
from urllib import request,error,parse
class NoRedirect(request.HTTPRedirectHandler):
 def redirect_request(self,*a):return None

def main(out,subset=False):
 out.mkdir(parents=True,exist_ok=False);state=dict(attempts=[],new_dart_calls=0)
 for artifact,digest in ([(12122461579,None)] if subset else [(12122416836,'6faea3647a128da272d76aa0d315f4bdb93c7e46ba4554a8314add2d5b8f2f65'),(12122461579,None)]):
  rec=dict(artifact_id=artifact,attempts=1);state['attempts'].append(rec)
  try:
   url=f'https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/{artifact}/zip'
   try:
    response=request.build_opener(NoRedirect()).open(request.Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}),timeout=25)
    raise ValueError('Expected official302 archive redirect')
   except error.HTTPError as e:
    rec['api_http']=e.code
    if e.code!=302:raise ValueError('ARTIFACT_API_HTTP_'+str(e.code)) from None
    location=e.headers.get('Location','');parsed=parse.urlparse(location)
   if parsed.scheme!='https' or not (parsed.hostname.endswith('.blob.core.windows.net') or parsed.hostname.endswith('.actions.githubusercontent.com') or parsed.hostname.endswith('.githubusercontent.com')):raise ValueError('Unapproved archive redirect host')
   rec['storage_host']=parsed.hostname;p=out/(str(artifact)+'.zip');size=0;h=hashlib.sha256()
   # No Authorization header on the signed storage request; no query logging.
   with request.build_opener(NoRedirect()).open(location,timeout=60) as response,p.open('xb') as f:
    rec['storage_http']=response.status
    while True:
     b=response.read(1024*1024)
     if not b:break
     size+=len(b)
     if size>260*1024*1024:raise ValueError('Archive size limit')
     f.write(b);h.update(b)
   rec.update(bytes=size,sha256=h.hexdigest())
   if digest and h.hexdigest()!=digest:raise ValueError('Pinned archive digest mismatch')
   with zipfile.ZipFile(p) as z:
    if z.testzip() is not None:raise ValueError('Archive CRC mismatch')
    if any(Path(n).is_absolute() or '..' in Path(n).parts for n in z.namelist()):raise ValueError('Unsafe archive member')
    z.extractall(out/'evidence')
   rec['status']='RESTORED_VERIFIED_ARCHIVE';state['selected_artifact']=artifact;break
  except Exception as e:
   rec.update(status='UNVERIFIED_ACCESS',error_type=type(e).__name__,http=e.code if isinstance(e,error.HTTPError) else None)
  finally:(out/'restore.json').write_text(json.dumps(state,indent=2)+'\n')
 print(json.dumps(state));return int('selected_artifact' not in state)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--subset',action='store_true');a=p.parse_args();raise SystemExit(main(a.output,a.subset))
