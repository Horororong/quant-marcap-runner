"""Restore original pinned offline kit and existing source artifact; stdlib transport only."""
import argparse,hashlib,json,os,urllib.request,zipfile
from pathlib import Path
from urllib.parse import urlsplit
class SourceRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
  if redirected is not None and urlsplit(req.full_url).netloc!=urlsplit(newurl).netloc:
   redirected.remove_header('Authorization')
  return redirected
opener=urllib.request.build_opener(SourceRedirect())
p=argparse.ArgumentParser();p.add_argument("--workdir",type=Path,required=True);a=p.parse_args()
root=a.workdir;root.mkdir(parents=True,exist_ok=True)
def download(url,dest,sha=None,token=False):
 h={"Authorization":"Bearer "+os.environ["GH_TOKEN"]} if token else {}
 with opener.open(urllib.request.Request(url,headers=h),timeout=120) as r, dest.open("wb") as f:
  while True:
   b=r.read(1024*1024)
   if not b:break
   f.write(b)
 digest=hashlib.sha256(dest.read_bytes()).hexdigest()
 if sha and digest!=sha:raise ValueError("archive SHA mismatch: "+dest.name)
 print(dest.name,dest.stat().st_size,digest,flush=True)
 return digest
artifact=root/"review-packet.zip"
download("https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11871753367/zip",artifact,"44b9ba097cc8c724be3b6025a4964b8be223f364d5ddf6204487497e101736fa",True)
ledgerzip=root/"ledger.zip"
download("https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11871948035/zip",ledgerzip,"13ae94569bb80878800fc700eea4fd3539ec0771f3af77f91cd5126614e7a15f",True)
with zipfile.ZipFile(ledgerzip) as z:
 name=[n for n in z.namelist() if n.endswith("transport_manifest.json")]
 if len(name)!=1:raise ValueError("transport ledger not unique")
 ledger=json.loads(z.read(name[0]))
with zipfile.ZipFile(artifact) as z:
 if z.testzip() is not None:raise ValueError("review packet CRC")
 name=[n for n in z.namelist() if n.endswith("review.part001")]
 if len(name)!=1:raise ValueError("review segment not unique")
 data=z.read(name[0])
if len(ledger["parts"])!=1 or hashlib.sha256(data).hexdigest()!=ledger["zip_sha256"] or len(data)!=ledger["zip_bytes"]:raise ValueError("review identity mismatch")
with zipfile.ZipFile(__import__("io").BytesIO(data)) as z:
 if z.testzip() is not None:raise ValueError("review CRC")
 z.extractall(root/"review")
(root/"transport_manifest.json").write_text(json.dumps(ledger,indent=2)+"\n")
kit=root/"original-kit.zip"
download("https://github.com/Horororong/quant-marcap-runner/releases/download/quant-report-26e4ec02e569/quant-sandbox-26e4ec02e569.zip",kit,"f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784")
with zipfile.ZipFile(kit) as z:
 if z.testzip() is not None:raise ValueError("kit CRC failure")
 z.extractall(root/"kit-parts")
