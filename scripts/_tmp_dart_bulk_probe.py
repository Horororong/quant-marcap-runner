from pathlib import Path
import json, io, zipfile, requests, pandas as pd

url="https://opendart.fss.or.kr/cmm/downloadFnlttZip.do?fl_nm=2023_4Q_PL_20260814044456.zip"
out={"url":url}
try:
    r=requests.get(url,timeout=120)
    out["status"]=r.status_code; out["bytes"]=len(r.content); out["content_type"]=r.headers.get("content-type")
    r.raise_for_status()
    out["members"]=[]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for info in z.infolist():
            b=z.read(info)
            item={"raw_name":info.filename,"bytes":len(b)}
            parsed=None
            for enc in ("cp949","euc-kr","utf-8-sig","utf-8"):
                try:
                    s=b.decode(enc)
                    df=pd.read_csv(io.StringIO(s),sep="\t",dtype=str,low_memory=False)
                    parsed=df
                    item["encoding"]=enc; item["columns"]=list(df.columns); item["rows"]=len(df)
                    item["head"]=df.head(3).fillna("").to_dict(orient="records")
                    item["fs_types"]=df.get("재무제표종류",pd.Series(dtype=str)).dropna().astype(str).value_counts().head(10).to_dict()
                    item["account_codes"]=df.get("항목코드",pd.Series(dtype=str)).dropna().astype(str).value_counts().head(20).to_dict()
                    break
                except Exception as e: item["last_error"]=repr(e)
            out["members"].append(item)
    out["ok"]=True
except Exception as e:
    out["ok"]=False; out["error"]=repr(e)
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_sample_schema.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:50000])
