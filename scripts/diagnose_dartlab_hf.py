from __future__ import annotations
import io, json, requests, pandas as pd

BASE='https://huggingface.co/datasets/eddmpython/dartlab-data/resolve/main/dart/finance/{code}.parquet'
CODES=['005930','000660','000010','097230','001230','004140']

def main():
    out=[]
    for code in CODES:
        url=BASE.format(code=code)
        try:
            r=requests.get(url,timeout=90)
            rec={'code':code,'status':r.status_code,'bytes':len(r.content)}
            if r.status_code==200 and len(r.content)>100:
                df=pd.read_parquet(io.BytesIO(r.content))
                rec['columns']=list(df.columns)
                rec['rows']=len(df)
                for c in ['rcept_no','rcept_date','rceptDate','filing_date','date','period','year','quarter','bsns_year','report_type','sj_div','account_nm','account_id']:
                    if c in df.columns:
                        vals=df[c].dropna().astype(str)
                        rec[c+'_min']=vals.min() if len(vals) else None
                        rec[c+'_max']=vals.max() if len(vals) else None
                        rec[c+'_sample']=vals.head(5).tolist()
                rec['head']=df.head(5).astype(str).to_dict('records')
                rec['tail']=df.tail(5).astype(str).to_dict('records')
            out.append(rec)
        except Exception as e:
            out.append({'code':code,'error':repr(e)})
    print(json.dumps(out,ensure_ascii=False,indent=2))
    with open('results/dartlab_hf_diagnostic.json','w',encoding='utf-8') as f:
        json.dump(out,f,ensure_ascii=False,indent=2)

if __name__=='__main__':
    from pathlib import Path
    Path('results').mkdir(exist_ok=True)
    main()
