"""Materialize exact archived originals into new offline replay directories only."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];OLD=ROOT/'docs/audits/financial-repair-20261014'
def main(source,out):
 out.mkdir(parents=True,exist_ok=False)
 with zipfile.ZipFile(source) as z:
  assert z.testzip() is None
  for prefix,label in [('original40','original40'),('holdout20','holdout20')]:
   folder=out/label;(folder/'originals').mkdir(parents=True)
   selection=(OLD/(prefix+'-selection.json')).read_bytes();manifest=(OLD/(prefix+'-source-manifest.json')).read_bytes()
   (folder/'selection.json').write_bytes(selection);(folder/'source_manifest.json').write_bytes(manifest)
   for item in json.loads(manifest):
    base=item['rcept_no']+'-'+item['sha256']+'.zip';matches=[n for n in z.namelist()if Path(n).name==base];assert len(matches)==1
    blob=z.read(matches[0]);assert hashlib.sha256(blob).hexdigest()==item['sha256']
    with zipfile.ZipFile(io.BytesIO(blob)) as inner:
     assert inner.testzip() is None
     for m in item['members']:assert hashlib.sha256(inner.read(m['name'])).hexdigest()==m['sha256']
    (folder/'originals'/base).write_bytes(blob)
 print('60 original SHA/CRC/member identities verified; fresh replay inputs only')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--originals',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.originals,a.output)
