"""Four necessary 2010 official cash-market replies; reuse existing transport.

No financial collection, original data update, retries or rights-price service.
"""
import argparse,base64,gzip,hashlib,json,os,sys
from pathlib import Path
from urllib import request
sys.path.insert(0,str(Path(__file__).resolve().parent))
import collect_stock_dividend_krx as owner
def main(out,dart_section=False):
    if dart_section:
        out.mkdir(parents=True,exist_ok=False)
        url='https://dart.fss.or.kr/report/viewer.do?rcpNo=20100331001582&dcmNo=2591068&eleId=25&offset=592088&length=125209&dtd=dart3.xsd'
        state=dict(status='UNVERIFIED',requests=1,retries=0,scope='One exact existing official viewer XI node; no list/ZIP/market queries',url=url,source_node='publication-proof 20100331001582-viewer.html node25')
        try:
            with request.build_opener(owner.NoRedirect()).open(url,timeout=25)as response:
                raw=response.read(2*1024*1024+1);state['http_status']=response.status;state['content_type']=response.headers.get('Content-Type','')
            if len(raw)>2*1024*1024:raise ValueError('SIZE_LIMIT')
            (out/'sajo-primary-XI.html').write_bytes(raw)
            state['sha256']=hashlib.sha256(raw).hexdigest();state['bytes']=len(raw)
            text=raw.decode('utf-8',errors='strict')
            if all(token in text for token in ['131,053,210,651','328,527,137,799','34,326,086,558','15,922,637,039']):state['status']='COMPLETE_OFFICIAL_SECTION_ONLY'
            else:state['error']='EXPECTED_SECTION_NOT_CONFIRMED'
        except Exception as exc:
            state['error']=type(exc).__name__
            if isinstance(exc,owner.error.HTTPError):state['http_status']=exc.code
    else:
        owner.DATES=('20100401','20100430');owner.MARKETS=(('stk_bydd_trd','007160'),('ksq_bydd_trd','089890'))
        state=owner.acquire(out,os.getenv('KRX_AUTH_KEY','').strip())
        state['scope']='Explicit two2010 dates x KOSPI/KOSDAQ, max4; first auth/service failure stops; no price overwrite or PIT approval.'
        state['plan']={'dates':owner.DATES,'markets_and_controls':owner.MARKETS,'official_next_day_and_actual_signal_only':True}
    (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    files={p.name:base64.b64encode(p.read_bytes()).decode()for p in sorted(out.iterdir())if p.is_file()}
    token=os.environ['GH_TOKEN']
    if any(token.encode()in base64.b64decode(v)for v in files.values()):raise ValueError('SECRET_TRANSFER_REFUSED')
    packed=gzip.compress(json.dumps(dict(files=files),separators=(',',':')).encode(),mtime=0)
    (out/'public-evidence.json.gz.b64').write_bytes(base64.b64encode(packed)+b'\n')
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=base64.b64encode(packed).decode()+'\n',encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30)as r:blob=json.load(r)
    result=dict(blob_sha=blob['sha'],compressed_sha256=hashlib.sha256(packed).hexdigest(),bytes=len(packed),status=state['status'],requests=state['requests'],error=state.get('error'))
    (out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if state['status']in{'COMPLETE_OFFICIAL_PRICE_ROWS_ONLY','COMPLETE_OFFICIAL_SECTION_ONLY'}else 2
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--dart-section',action='store_true');a=p.parse_args();raise SystemExit(main(a.output,a.dart_section))
