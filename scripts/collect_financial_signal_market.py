"""Four necessary 2010 official cash-market replies; reuse existing transport.

No financial collection, original data update, retries or rights-price service.
"""
import argparse,base64,gzip,hashlib,json,os,sys
from pathlib import Path
from urllib import request
sys.path.insert(0,str(Path(__file__).resolve().parent))
import collect_stock_dividend_krx as owner
def main(out):
    owner.DATES=('20100401','20100430');owner.MARKETS=(('stk_bydd_trd','007160'),('ksq_bydd_trd','089890'))
    state=owner.acquire(out,os.getenv('KRX_AUTH_KEY','').strip())
    state['scope']='Explicit two2010 dates x KOSPI/KOSDAQ, max4; first auth/service failure stops; no price overwrite or PIT approval.'
    state['plan']={'dates':owner.DATES,'markets_and_controls':owner.MARKETS,'official_next_day_and_actual_signal_only':True}
    (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    files={p.name:base64.b64encode(p.read_bytes()).decode()for p in sorted(out.glob('*.json'))}
    token=os.environ['GH_TOKEN']
    if any(token.encode()in base64.b64decode(v)for v in files.values()):raise ValueError('SECRET_TRANSFER_REFUSED')
    packed=gzip.compress(json.dumps(dict(files=files),separators=(',',':')).encode(),mtime=0)
    (out/'public-evidence.json.gz.b64').write_bytes(base64.b64encode(packed)+b'\n')
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=base64.b64encode(packed).decode()+'\n',encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30)as r:blob=json.load(r)
    result=dict(blob_sha=blob['sha'],compressed_sha256=hashlib.sha256(packed).hexdigest(),bytes=len(packed),status=state['status'],requests=state['requests'],error=state.get('error'))
    (out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if state['status']=='COMPLETE_OFFICIAL_PRICE_ROWS_ONLY'else 2
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);raise SystemExit(main(p.parse_args().output))
