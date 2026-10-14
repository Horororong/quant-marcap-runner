"""Freeze twenty uninspected receipts from completed batch metadata; no parsing."""
import argparse,csv,gzip,hashlib,io,json,os,urllib.request,zipfile
from pathlib import Path
from urllib.parse import urlsplit
p=argparse.ArgumentParser();p.add_argument("--workdir",type=Path,required=True);a=p.parse_args()
root=a.workdir
sha=lambda b:hashlib.sha256(b).hexdigest()
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  out=super().redirect_request(req,fp,code,msg,headers,newurl)
  if out is not None and urlsplit(req.full_url).netloc!=urlsplit(newurl).netloc:out.remove_header("Authorization")
  return out
archive=root/"batch.zip"
if not archive.exists():
 req=urllib.request.Request("https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/11866183704/zip",headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"]})
 with urllib.request.build_opener(Redirect()).open(req,timeout=120) as r,archive.open("wb") as f:
  while True:
   b=r.read(1024*1024)
   if not b:break
   f.write(b)
assert sha(archive.read_bytes())=="4d7ba8748a50a78d5fc15304b16072258105bbdb5c90c5374901e023943b61e5"
old=json.loads((root/"review/selection.json").read_text())["samples"]
exclude={s["rcept_no"] for s in old};companies={s["corp_code"] for s in old}
out=root/"heldout";out.mkdir(exist_ok=True);(out/"originals").mkdir(exist_ok=True)
seed=2026101402
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 names=[n for n in z.namelist() if "audit-subset" not in Path(n).parts]
 def load(suffix):
  ns=[n for n in names if n.endswith(suffix)]
  assert len(ns)==1,(suffix,ns)
  b=z.read(ns[0])
  if suffix.endswith(".gz"):b=gzip.decompress(b)
  return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
 states=load("changed-state.csv");metrics=load("new-metrics.csv")
 indices={r["rcept_no"]:r for r in load("legacy_filings.csv.gz")}
 assert len(states)==2000 and len({r["rcept_no"] for r in states})==2000
 selected=[]
 for status,n in [("PARSED_4F",10),("PARSED_PARTIAL",6),("NO_METRICS",4)]:
  pool=[{**indices[r["rcept_no"]],**r} for r in states if r["status"]==status and r["rcept_no"] not in exclude]
  pool.sort(key=lambda r:sha((str(seed)+":"+status+":"+r["rcept_no"]).encode()))
  chosen=[]
  for r in pool:
   if r["corp_code"] in companies:continue
   r={**r,"sample_id":"N"+str(len(selected)+len(chosen)+1).zfill(2),"category":"heldout_"+status}
   chosen.append(r);companies.add(r["corp_code"])
   if len(chosen)==n:break
  assert len(chosen)==n,(status,len(chosen))
  selected.extend(chosen)
 selection={"seed":seed,"selection_method":"SHA256 rank per status; 10 full / 6 partial / 4 NO_METRICS; exclude all prior 40 receipts AND corporations; fixed before originals opened","batch_run":38498706052,"samples":selected}
 (out/"selection.json").write_text(json.dumps(selection,ensure_ascii=False,indent=2)+"\n")
 evidence=[]
 for s in selected:
  ns=[n for n in names if "/native/" in "/"+n and Path(n).name.startswith(s["rcept_no"]+"-") and n.endswith(".zip")]
  assert len(ns)==1
  b=z.read(ns[0]);digest=sha(b);assert digest==s["document_sha256"]
  (out/"originals"/Path(ns[0]).name).write_bytes(b)
  with zipfile.ZipFile(io.BytesIO(b)) as native:
   assert native.testzip() is None
   members=[{"name":n,"sha256":sha(native.read(n)),"bytes":len(native.read(n))} for n in native.namelist() if not n.endswith("/")]
  evidence.append({"sample_id":s["sample_id"],"rcept_no":s["rcept_no"],"expected_sha256":digest,"sha256":digest,"source_available":True,"zip_crc_ok":True,"artifact_member":ns[0],"members":members})
 rows=[{**r,"sample_id":s["sample_id"],"category":s["category"]} for s in selected for r in metrics if r["rcept_no"]==s["rcept_no"]]
 (out/"selected_metrics.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
 with (out/"selected_metrics.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
 (out/"source_manifest.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"heldout":len(selected),"overlap_receipts":len(exclude&{r["rcept_no"] for r in selected}),"new_collection":0,"batch_reprocessing":0,"seed":seed}),flush=True)
