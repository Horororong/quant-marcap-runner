"""Freeze 40 samples and their original evidence; no financial parsing or judgments."""
import argparse,csv,gzip,hashlib,io,json,random,zipfile,os
from pathlib import Path
from decimal import Decimal,InvalidOperation
p=argparse.ArgumentParser();p.add_argument("--workdir",type=Path,required=True);a=p.parse_args()
root=a.workdir;out=root/"review";out.mkdir(parents=True,exist_ok=True)
seed=20261014
sha=lambda b:hashlib.sha256(b).hexdigest()
z=zipfile.ZipFile(root/"batch.zip")
if z.testzip() is not None:raise ValueError("source artifact CRC failure")
names=z.namelist()
def find(suffix):
 matches=[n for n in names if n.endswith(suffix) and "audit-subset" not in Path(n).parts]
 if len(matches)!=1:raise ValueError("ambiguous or missing artifact member: "+suffix+str(matches))
 return matches[0]
def csvdata(name):
 b=z.read(name)
 if name.endswith(".gz"):b=gzip.decompress(b)
 return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
changed=csvdata(find("changed-state.csv"))
metrics=csvdata(find("new-metrics.csv"))
idxnames=[n for n in names if "before/" in n and n.endswith("legacy_filings.csv.gz")]
if len(idxnames)!=1:raise ValueError("filing index not unique")
index={r["rcept_no"]:r for r in csvdata(idxnames[0])}
if len(changed)!=2000 or len({r["rcept_no"] for r in changed})!=2000:raise ValueError("not a distinct 2000-receipt cohort")
byreceipt={}
for r in metrics:byreceipt.setdefault(r["rcept_no"],[]).append(r)
cohort=[]
for r in changed:
 item={**index.get(r["rcept_no"],{}),**r}
 rows=byreceipt.get(r["rcept_no"],[])
 item["risk_flags"]=[]
 if "정정" in item.get("report_nm",""):item["risk_flags"].append("correction")
 if any(t.get("scope")=="CFS" for t in rows):item["risk_flags"].append("CFS")
 for t in rows:
  try:
   if Decimal(t.get("amount_krw","NaN")).is_finite() and Decimal(t["amount_krw"])<0:
    item["risk_flags"].append("negative");break
  except InvalidOperation:pass
 if any(t.get("unit") in {"백만원","억원"} for t in rows):item["risk_flags"].append("large_unit")
 cohort.append(item)
def rank(r,category):return sha((str(seed)+":"+category+":"+r["rcept_no"]).encode())
chosen=[];used=set();seen=set()
def select(pool,count,category):
 groups={}
 for r in pool:
  if r["rcept_no"] not in used:groups.setdefault((r.get("fiscal_year",""),r.get("period","")),[]).append(r)
 queues=[sorted(v,key=lambda r:rank(r,category)) for k,v in sorted(groups.items())]
 got=[]
 while queues and len(got)<count:
  rest=[]
  for q in queues:
   eligible=next((r for r in q if (r.get("corp_code") or r.get("stock_code") or r["rcept_no"]) not in seen),None)
   if eligible is None:eligible=q[0]
   if len(got)<count:
    q.remove(eligible)
    corp=eligible.get("corp_code") or eligible.get("stock_code") or eligible["rcept_no"]
    eligible={**eligible,"category":category,"diversity_relaxed":corp in seen}
    got.append(eligible);used.add(eligible["rcept_no"]);seen.add(corp)
   if q:rest.append(q)
  queues=rest
 if len(got)!=count:raise ValueError("category shortage "+category+": "+str(len(got)))
 chosen.extend(got)
select([r for r in cohort if r["risk_flags"] and r["status"] in {"PARSED_4F","PARSED_PARTIAL","NO_METRICS"}],5,"high_risk")
select([r for r in cohort if r["status"]=="PARSED_4F"],15,"full")
select([r for r in cohort if r["status"]=="PARSED_PARTIAL"],10,"partial")
select([r for r in cohort if r["status"]=="NO_METRICS"],10,"no_metrics")
chosen.sort(key=lambda r:({"full":0,"partial":1,"no_metrics":2,"high_risk":3}[r["category"]],rank(r,r["category"])))
for i,r in enumerate(chosen,1):r["sample_id"]="S"+str(i).zfill(2)
selection={"seed":seed,"selection_method":"SHA256 seeded fiscal_year/period round-robin; reserve risk first; prefer different companies; record relaxed diversity",
 "run_id":38498706052,"artifact_id":11866183704,"artifact_sha256":sha((root/"batch.zip").read_bytes()),
 "snapshot_main":"3e9c42a1d3e028874eefb84c958a65d23083d088","cohort_count":len(cohort),
 "cohort_status_counts":{s:sum(r["status"]==s for r in cohort) for s in sorted({r["status"] for r in cohort})},
 "samples":chosen,"judgments_complete":False}
(out/"selection.json").write_text(json.dumps(selection,ensure_ascii=False,indent=2)+"\n")
# Selection is persisted before native bytes are opened or source figures inspected.
selected_metrics=[{**t,"sample_id":r["sample_id"],"category":r["category"]} for r in chosen for t in byreceipt.get(r["rcept_no"],[])]
fields=list(dict.fromkeys(k for r in selected_metrics for k in r))
with (out/"selected_metrics.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(selected_metrics)
(out/"selected_metrics.json").write_text(json.dumps(selected_metrics,ensure_ascii=False,indent=2)+"\n")
original=out/"originals";original.mkdir(exist_ok=True);evidence=[]
for r in chosen:
 receipt=r["rcept_no"];expected=r.get("document_sha256","")
 matches=[n for n in names if "/native/" in "/"+n and Path(n).name.startswith(receipt+"-") and n.endswith(".zip")]
 entry={"sample_id":r["sample_id"],"rcept_no":receipt,"expected_sha256":expected,"source_available":False}
 if matches:
  matching=[n for n in matches if sha(z.read(n))==expected]
  if len(matching)!=1:raise ValueError("source identity missing or ambiguous "+receipt)
  b=z.read(matching[0]);dest=original/Path(matching[0]).name;dest.write_bytes(b)
  entry.update(source_available=True,artifact_member=matching[0],sha256=sha(b),bytes=len(b))
  with zipfile.ZipFile(io.BytesIO(b)) as source:
   entry["zip_crc_ok"]=source.testzip() is None
   entry["members"]=[{"name":n,"sha256":sha(source.read(n)),"bytes":len(source.read(n))} for n in source.namelist() if not n.endswith("/")]
 evidence.append(entry)
(out/"source_manifest.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
(root/"prepared_summary.json").write_text(json.dumps({"selected":40,"metric_rows":len(selected_metrics),"originals":sum(x["source_available"] for x in evidence),"status_counts":selection["cohort_status_counts"]},indent=2)+"\n")
print((root/"prepared_summary.json").read_text(),flush=True)
# Transport segmentation keeps each uploaded archive below the attachment limit.
archive=root/"review.zip"
with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as dest:
 for path in sorted(out.rglob("*")):
  if path.is_file():dest.write(path,path.relative_to(out).as_posix())
parts=root/"parts";parts.mkdir(exist_ok=True);entries=[]
with archive.open("rb") as stream:
 i=0
 while True:
  data=stream.read(24*1024*1024)
  if not data:break
  i+=1
  name="review.part"+str(i).zfill(3);(parts/name).write_bytes(data)
  entries.append({"name":name,"bytes":len(data),"sha256":sha(data)})
if len(entries)>8:raise ValueError("review exceeds bounded transport capacity")
ledger={"zip_bytes":archive.stat().st_size,"zip_sha256":sha(archive.read_bytes()),"parts":entries}
(root/"transport_manifest.json").write_text(json.dumps(ledger,indent=2)+"\n")
if os.getenv("GITHUB_OUTPUT"):
 with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write("parts="+str(len(entries))+"\n")
