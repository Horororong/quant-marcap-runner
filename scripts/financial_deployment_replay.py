"""Common collector subjects on exact original archives, transport replaced only."""
import argparse,base64,gzip,hashlib,io,json,os,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import backfill_dart_legacy_2000_2014 as collector
def main(source,out):
    out.mkdir(parents=True,exist_ok=False)
    payload=json.loads(gzip.decompress(base64.b64decode(source.read_bytes())))
    metadata={r['rcept_no']:r for r in payload['selection']['samples']};results=[]
    for rec in payload['manifest']:
        # Each original receipt archive can have multiple members. No amounts or
        # expected controls enter the production processing path.
        allrows=[];states=[]
        for a in rec['archives']:
            blob=base64.b64decode(payload['files'][a['path']]);digest=hashlib.sha256(blob).hexdigest();assert digest==a['sha256']
            collector.fetch_document=lambda receipt,b=blob,d=digest:(b,d)
            rows,state=collector.process_filing(metadata[rec['receipt']]);allrows.extend(rows);states.append(state)
        results.append(dict(receipt=rec['receipt'],sample=rec['sample'],rows=allrows,states=states,parser_version=collector.PARSER_VERSION))
    (out/'replay.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(filings=len(results),rows=sum(len(x['rows'])for x in results),new_HTTP_calls=0)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
