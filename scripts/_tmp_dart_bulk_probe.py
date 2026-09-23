from pathlib import Path
import json, re, requests
from bs4 import BeautifulSoup

url="https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/main.do"
r=requests.get(url,timeout=60)
out={"status_code":r.status_code,"url":r.url,"length":len(r.text),"links":[],"onclick":[]}
soup=BeautifulSoup(r.text,"html.parser")
for a in soup.find_all("a"):
    txt=" ".join(a.get_text(" ",strip=True).split())
    href=a.get("href")
    onclick=a.get("onclick")
    if "다운로드" in txt or (onclick and ("down" in onclick.lower() or ".zip" in onclick.lower())):
        out["links"].append({"text":txt,"href":href,"onclick":onclick})
for m in re.findall(r"onclick=[\"']([^\"']+)[\"']",r.text,re.I):
    if "down" in m.lower() or ".zip" in m.lower():
        out["onclick"].append(m)
out["links"]=out["links"][:100]
out["onclick"]=out["onclick"][:100]
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_bulk_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:20000])
