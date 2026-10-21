"""Transfer bounded PUBLIC originals/candidates for independent review, no refs."""
import argparse,base64,gzip,hashlib,json,os
from pathlib import Path
from urllib import request
def main(folder):
    files={}
    for pattern in ['native/*.zip','service-responses/*.xml','results/*.json','collection/*.json','quality/*.json','selection.json','run_status.json','batch_plan.json']:
        for p in folder.glob(pattern): files[str(p.relative_to(folder))]=base64.b64encode(p.read_bytes()).decode()
    raw=json.dumps(dict(files=files),separators=(',',':')).encode()
    for name in ['DART_API_KEY','GH_TOKEN']:
        secret=os.getenv(name,'')
        if secret and len(secret)>=12:
            for encoded in files.values():
                if secret.encode() in base64.b64decode(encoded):raise ValueError('Possible credential in candidate; transfer refused')
    packed=gzip.compress(raw,mtime=0)
    if len(packed)>12*1024*1024:raise ValueError('Bounded transfer too large')
    encoded=base64.b64encode(packed).decode()+'\n'
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=encoded,encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/json'})
    with request.urlopen(req,timeout=60)as response:blob=json.load(response)
    result=dict(blob_sha=blob['sha'],compressed_sha256=hashlib.sha256(packed).hexdigest(),bytes=len(packed),financial_certification='UNVERIFIED',automatic_publication=False)
    (folder/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);main(p.parse_args().folder)
