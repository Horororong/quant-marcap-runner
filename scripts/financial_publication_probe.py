"""Bounded official relationship evidence for three already preserved filings.

No original ZIP downloads, no collection/publication checkpoint writes. Raw public
responses go to an artifact and a public Git blob for connector-based inspection.
Secrets remain only in request memory; errors never stringify keyed requests.
"""
import argparse,base64,gzip,hashlib,json,os,time
from pathlib import Path
from urllib import request,error,parse

SUBJECTS=[('20100331001578','00365934'),('20100331001580','00114826'),('20100331001582','00124799')]
def run(out):
    out.mkdir(parents=True,exist_ok=False);files={};log=[];count=0;started=time.monotonic()
    def get(label,url):
        nonlocal count
        if count>=20 or time.monotonic()-started>180:raise RuntimeError('PROBE_BUDGET')
        count+=1
        try:
            with request.urlopen(request.Request(url,headers={'User-Agent':'quant-source-evidence/1'}),timeout=25)as r:
                data=r.read(8*1024*1024+1);status=r.status;kind=r.headers.get('Content-Type','')
            if len(data)>8*1024*1024:raise RuntimeError('RESPONSE_SIZE_LIMIT')
        except error.HTTPError as e:
            log.append(dict(label=label,http_status=e.code,result='HTTP_ERROR'));raise RuntimeError('OFFICIAL_HTTP_ERROR')from None
        except (error.URLError,TimeoutError):
            log.append(dict(label=label,result='TRANSPORT_ERROR'));raise RuntimeError('OFFICIAL_TRANSPORT_ERROR')from None
        for secret in ['DART_API_KEY','GH_TOKEN']:
            value=os.getenv(secret,'')
            if len(value)>12 and value.encode()in data:raise RuntimeError('SECRET_IN_RESPONSE_REFUSED')
        files[label]=data
        log.append(dict(label=label,http_status=status,content_type=kind,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        return data
    code=0
    try:
        for receipt,corp in SUBJECTS:
            get(receipt+'-viewer.html','https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+receipt)
            for page in range(1,5):
                query=parse.urlencode(dict(crtfc_key=os.environ['DART_API_KEY'],corp_code=corp,bgn_de='20100301',end_de='20100501',last_reprt_at='N',page_count=100,page_no=page))
                raw=get(corp+f'-list{page}.json','https://opendart.fss.or.kr/api/list.json?'+query)
                obj=json.loads(raw)
                if obj.get('status')not in {'000','013'}:
                    log.append(dict(label=corp,dart_code=obj.get('status'),result='DART_SERVICE_STOP'));raise RuntimeError('OFFICIAL_DART_ERROR')
                if obj.get('status')=='013' or page>=int(obj['total_page']):break
            else:raise RuntimeError('UNFINISHED_PAGINATION')
    except (RuntimeError,ValueError,KeyError)as exc:
        # Only our fixed symbolic failures, never a URL-bearing exception.
        code=2;log.append(dict(result='STOPPED',error=exc.args[0]if isinstance(exc,RuntimeError)else type(exc).__name__))
    state=dict(requests=count,new_document_downloads=0,started_scope=SUBJECTS,date_range=['2010-03-01','2010-05-01'],complete=code==0,observed_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),log=log)
    files['state.json']=(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode()
    for name,data in files.items():(out/name).write_bytes(data)
    packed=gzip.compress(json.dumps(dict(files={k:base64.b64encode(v).decode()for k,v in files.items()}),separators=(',',':')).encode(),mtime=0)
    (out/'public-evidence.json.gz.b64').write_bytes(base64.b64encode(packed)+b'\n')
    payload=json.dumps(dict(content=base64.b64encode(packed).decode()+'\n',encoding='utf-8')).encode()
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=payload,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30)as r:blob=json.load(r)
    transfer=dict(blob_sha=blob['sha'],compressed_sha256=hashlib.sha256(packed).hexdigest(),bytes=len(packed),probe_exit_code=code)
    (out/'transfer.json').write_text(json.dumps(transfer,indent=2)+'\n');print(json.dumps(transfer));return code
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);raise SystemExit(run(p.parse_args().output))
