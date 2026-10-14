"""Download only the already frozen holdout source packet; stdlib transport."""
import argparse,hashlib,os,urllib.request,zipfile
from urllib.parse import urlsplit
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,url):
  target=super().redirect_request(req,fp,code,msg,headers,url)
  if target and urlsplit(req.full_url).netloc!=urlsplit(url).netloc:target.remove_header('Authorization')
  return target
req=urllib.request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11883255192/zip',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']})
dest=a.output/'heldout-source.zip'
with urllib.request.build_opener(Redirect()).open(req,timeout=120)as response,dest.open('wb')as f:
 while b:=response.read(1024**2):f.write(b)
assert dest.stat().st_size==16646306
assert hashlib.sha256(dest.read_bytes()).hexdigest()=='4fdb23600a2ce6e3cde106ff93382f74aa92da90fb9a040e8bf02f77b7dd2b23'
with zipfile.ZipFile(dest)as z:
 assert z.testzip()is None
 assert all(not Path(n).is_absolute()and'..'not in Path(n).parts for n in z.namelist())
 z.extractall(a.output)
print('frozen holdout artifact SHA/CRC verified')
