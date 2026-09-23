from __future__ import annotations
import io, os, zipfile
import requests

key=os.getenv("DART_API_KEY","").strip()
if not key:
    raise SystemExit("DART_API_KEY missing")
base="https://opendart.fss.or.kr/api"

params={
    "crtfc_key":key,
    "bgn_de":"20050301",
    "end_de":"20050531",
    "pblntf_ty":"A",
    "pblntf_detail_ty":"A001",
    "last_reprt_at":"N",
    "page_no":"1",
    "page_count":"10",
    "sort":"date",
    "sort_mth":"asc",
}
r=requests.get(base+"/list.json",params=params,timeout=30)
r.raise_for_status()
obj=r.json()
print("LIST_STATUS",obj.get("status"),obj.get("message"))
print("TOTAL_COUNT",obj.get("total_count"))
print("SAMPLE",[(x.get("rcept_no"),x.get("corp_name"),x.get("report_nm"),x.get("rcept_dt"),x.get("corp_cls")) for x in obj.get("list",[])[:5]])

if obj.get("list"):
    rcept=obj["list"][0]["rcept_no"]
    d=requests.get(base+"/document.xml",params={"crtfc_key":key,"rcept_no":rcept},timeout=60)
    print("DOC_HTTP",d.status_code,"LEN",len(d.content),"MAGIC",d.content[:4])
    print("DOC_TYPE",d.headers.get("Content-Type"))
    if d.content[:2]==b"PK":
        z=zipfile.ZipFile(io.BytesIO(d.content))
        print("ZIP_FILES",z.namelist()[:10])
        if z.namelist():
            sample=z.read(z.namelist()[0])
            print("FIRST_FILE_LEN",len(sample),"FIRST_100",repr(sample[:100]))
