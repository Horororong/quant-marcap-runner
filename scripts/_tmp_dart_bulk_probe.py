from pathlib import Path
import json, re, requests

url="https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/list.do"
r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=60)
html=r.text
snips=[]
for m in re.finditer("2020", html):
    snips.append(html[max(0,m.start()-800):min(len(html),m.start()+3500)])
hrefs=re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
out={
  "status":r.status_code,
  "length":len(html),
  "hrefs":[h for h in hrefs if "dwld" in h.lower() or "down" in h.lower() or "file" in h.lower()][:200],
  "snippets_2020":snips[:5]
}
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_bulk_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:30000])
