"""Literal source viewing only: no production parser imports or numeric extraction."""
import argparse,hashlib,html,json,io,re,zipfile
from html.parser import HTMLParser
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--workdir",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
root=a.workdir/"review";out=a.output;out.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
selection=json.loads((root/"selection.json").read_text())
source_manifest=json.loads((root/"source_manifest.json").read_text())
for name in ["selection.json","source_manifest.json","selected_metrics.csv","selected_metrics.json"]:
 (out/name).write_bytes((root/name).read_bytes())
class View(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.tables=[];self.stack=[];self.history=[];self.tags=[]
 def handle_starttag(self,tag,attrs):
  if tag in {"company-name","document","document-name","period","date","company-code","stock-code","correction"}:
   self.tags.append({"tag":tag,"attributes":dict(attrs),"source_line":self.getpos()[0]})
  if tag=="table":
   t={"table_index":len(self.tables),"source_line":self.getpos()[0],"context":" ".join(self.history)[-2600:],"rows":[],"row":None,"cell":None}
   self.tables.append(t);self.stack.append(t)
  elif self.stack and tag=="tr":
   self.stack[-1]["row"]={"source_line":self.getpos()[0],"cells":[]}
  elif self.stack and tag in {"td","th","te","tu"} and self.stack[-1]["cell"] is None:
   self.stack[-1]["cell"]={"tag":tag,"text":"","attributes":dict(attrs),"source_line":self.getpos()[0]}
 def handle_data(self,data):
  self.history.append(data)
  if self.stack and self.stack[-1]["cell"] is not None:self.stack[-1]["cell"]["text"]+=data+" "
 def handle_endtag(self,tag):
  if not self.stack:return
  t=self.stack[-1]
  if tag in {"td","th","te","tu"} and t["cell"] is not None and t["cell"]["tag"]==tag:
   t["cell"]["text"]=" ".join(t["cell"]["text"].split())
   if t["row"] is not None:t["row"]["cells"].append(t["cell"])
   t["cell"]=None
  elif tag=="tr" and t["row"] is not None:
   t["rows"].append(t["row"]);t["row"]=None
  elif tag=="table":self.stack.pop()
keywords=("매출","영업활동","영업이익","영업손실","당기순","분기순","반기순","자본총","자산총","부채총","총자산","총부채","자본계","현금흐름","연결","별도","개별","정정","단위")
summaries=[]
for sample in selection["samples"]:
 sid=sample["sample_id"];receipt=sample["rcept_no"]
 evidence=next(e for e in source_manifest if e["sample_id"]==sid)
 if not evidence["source_available"]:raise ValueError("missing selected source")
 paths=list((root/"originals").glob(receipt+"-*.zip"))
 if len(paths)!=1 or sha(paths[0].read_bytes())!=evidence["sha256"]:raise ValueError("selected source SHA mismatch")
 result={"sample":sample,"evidence":evidence,"members":[]}
 with zipfile.ZipFile(paths[0]) as z:
  for mi,n in enumerate([n for n in z.namelist() if not n.endswith("/")]):
   b=z.read(n);encoding=None
   declaration=re.search(br'encoding\s*=\s*["\x27]([^"\x27]+)',b[:500],re.I)
   candidates=([declaration.group(1).decode("ascii")] if declaration else [])+["utf-8","cp949","euc-kr"]
   for enc in dict.fromkeys(candidates):
    try:text=b.decode(enc);encoding=enc;break
    except (UnicodeDecodeError,LookupError):continue
   if encoding is None:
    result["members"].append({"name":n,"sha256":sha(b),"decode_status":"UNVERIFIED"});continue
   view=View();view.feed(text)
   tables=[]
   for t in view.tables:
    rowtexts=[" ".join(c["text"] for c in row["cells"]) for row in t["rows"]]
    hits=[i for i,s in enumerate(rowtexts) if any(k in s for k in keywords)]
    if hits:
     keep=set(range(min(8,len(t["rows"]))))
     for i in hits:keep.update(range(max(0,i-1),min(len(t["rows"]),i+2)))
     tables.append({"table_index":t["table_index"],"source_line":t["source_line"],"context":t["context"],
                    "row_count":len(t["rows"]),"rows":[{"row_index":i,**t["rows"][i]} for i in sorted(keep)]})
   prefix=sid+"-member"+str(mi).zfill(2)
   for ci,start in enumerate(range(0,len(text),100000)):
    (out/(prefix+"-source-"+str(ci).zfill(3)+".txt")).write_text(text[start:start+100000],encoding="utf-8")
   (out/(prefix+"-all-tables.json")).write_text(json.dumps(view.tables,ensure_ascii=False,indent=2)+"\n")
   for table in view.tables:
    table_copy={k:v for k,v in table.items() if k not in {"row","cell"}}
    (out/(prefix+"-table-"+str(table["table_index"]).zfill(4)+".json")).write_text(json.dumps(table_copy,ensure_ascii=False,indent=2)+"\n")
   result["members"].append({"name":n,"sha256":sha(b),"encoding":encoding,"declared_encoding":declaration.group(1).decode("ascii") if declaration else "",
       "table_count":len(view.tables),"document_text_head":" ".join(view.history)[:2500],"metadata_tags":view.tags,"focused_tables":tables})
 (out/(sid+"-source-view.json")).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 rows=[r for r in json.loads((root/"selected_metrics.json").read_text()) if r["rcept_no"]==receipt]
 (out/(sid+"-extracted.json")).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
 summaries.append({"sample_id":sid,"rcept_no":receipt,"status":sample["status"],"category":sample["category"],"metrics":len(rows),"members":len(result["members"])})
(out/"review_index.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"samples":len(summaries),"metric_rows":sum(r["metrics"] for r in summaries),"source_views_complete":True,"independent_judgments_complete":False}),flush=True)
