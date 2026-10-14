"""Restore immutable Stage2 replay/audit output only; no package installation."""
import argparse,hashlib,json,os,urllib.request,zipfile
from pathlib import Path
from urllib.parse import urlsplit
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,url):
  target=super().redirect_request(req,fp,code,msg,headers,url)
  if target and urlsplit(req.full_url).netloc!=urlsplit(url).netloc:target.remove_header('Authorization')
  return target
req=urllib.request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11884849665/zip',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']})
dest=a.output/'stage2-results.zip'
with urllib.request.build_opener(Redirect()).open(req,timeout=120)as response,dest.open('wb')as f:
 while data:=response.read(1024**2):f.write(data)
assert dest.stat().st_size==200076
assert hashlib.sha256(dest.read_bytes()).hexdigest()=='ac3c3830dc66238b32354aa27dfd8ceb8388a60eed06b7f7c4da40419db8cd6b'
with zipfile.ZipFile(dest)as z:
 assert z.testzip()is None
 assert all(not Path(n).is_absolute()and'..'not in Path(n).parts for n in z.namelist())
 z.extractall(a.output)
p=a.output/'results/validation_summary.json';summary=json.loads(p.read_text())
assert summary['field_rows']==700 and summary['field_counts']=={'PASS':518,'FAIL':0,'UNVERIFIED':182}
assert len(list((a.output/'replay60').glob('[SN]*.json')))==60
print('immutable Stage2 SHA/CRC and700/518 baseline verified')
