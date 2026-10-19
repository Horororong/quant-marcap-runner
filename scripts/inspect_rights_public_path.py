"""One unauthenticated official page, not a retry of the denied rights API.

Inspect the actual public interface response; no guessed data endpoint, login
automation, OTP bypass, repeated request, or price inference. Preserve response
shape/SHA and the exact access obstacle. Does not certify an empty200 as data.
"""
import argparse,base64,gzip,hashlib,json,os,re
from pathlib import Path
from urllib import request,error
URL='https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201030201'
class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*a):raise ValueError('OFFICIAL_INTERFACE_REDIRECT_REQUIRES_REVIEW')
def main(out):
    out.mkdir(parents=True,exist_ok=False);state=dict(url=URL,requests=1,retries=0,status='UNVERIFIED',rights_price_rows=0,old401_API_retried=False)
    try:
        with request.build_opener(NoRedirect()).open(request.Request(URL,headers={'Accept':'text/html'}),timeout=25)as r:
            b=r.read(2*1024*1024+1);state.update(http_status=r.status,content_type=r.headers.get('Content-Type',''))
        if len(b)>2*1024*1024:raise ValueError('RESPONSE_SIZE_LIMIT')
        (out/'official-interface.html').write_bytes(b);state.update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        text=b.decode('utf-8',errors='replace');state['shape']={'title':re.findall(r'<title>(.*?)</title>',text,re.S)[:1],'script_tags':len(re.findall(r'<script\b',text,re.I)),'login_indicators':sorted(set(re.findall(r'(?i)login|로그인|인증',text)))[:8],'rights_label_present':'신주인수권증서'in text,'replacement_characters':text.count('\ufffd')}
        state['reason']='Official interactive HTML is not a rights-price dataset; requires authenticated/export interface and exact rights security. No data endpoint inferred.'
    except Exception as e:
        state['error']=type(e).__name__
        if isinstance(e,error.HTTPError):state['http_status']=e.code
        if isinstance(e,ValueError):state['reason']=str(e)
    (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    files={p.name:base64.b64encode(p.read_bytes()).decode()for p in sorted(out.iterdir())if p.is_file()}
    packed=gzip.compress(json.dumps(dict(files=files),separators=(',',':')).encode(),mtime=0);token=os.environ['GH_TOKEN']
    if any(token.encode()in base64.b64decode(v)for v in files.values()):raise ValueError('SECRET_ECHO_REFUSED')
    payload=base64.b64encode(packed).decode()+'\n'
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=payload,encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30)as r:o=json.load(r)
    result=dict(blob_sha=o['sha'],compressed_sha256=hashlib.sha256(packed).hexdigest(),bytes=len(packed),status=state['status'],rights_price_rows=0,requests=1)
    (out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    # Transport inspection succeeds, but the source status is still UNVERIFIED.
    return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
