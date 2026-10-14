"""Restore original pinned offline kit and existing source artifact; stdlib transport only."""
import argparse,hashlib,json,os,urllib.request,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--workdir",type=Path,required=True);a=p.parse_args()
root=a.workdir;root.mkdir(parents=True,exist_ok=True)
def download(url,dest,sha=None,token=False):
 h={"Authorization":"Bearer "+os.environ["GH_TOKEN"]} if token else {}
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=120) as r, dest.open("wb") as f:
  while True:
   b=r.read(1024*1024)
   if not b:break
   f.write(b)
 digest=hashlib.sha256(dest.read_bytes()).hexdigest()
 if sha and digest!=sha:raise ValueError("archive SHA mismatch: "+dest.name)
 print(dest.name,dest.stat().st_size,digest,flush=True)
 return digest
artifact=root/"batch.zip"
download("https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11866183704/zip",artifact,"4d7ba8748a50a78d5fc15304b16072258105bbdb5c90c5374901e023943b61e5",True)
kit=root/"original-kit.zip"
download("https://github.com/Horororong/quant-marcap-runner/releases/download/quant-report-26e4ec02e569/quant-sandbox-26e4ec02e569.zip",kit,"f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784")
with zipfile.ZipFile(kit) as z:
 if z.testzip() is not None:raise ValueError("kit CRC failure")
 z.extractall(root/"kit-parts")
