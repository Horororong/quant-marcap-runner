from __future__ import annotations
import io, json, requests, pandas as pd
from pathlib import Path

ROOT='https://huggingface.co/datasets/eddmpython/dartlab-data/resolve/main/dart/{kind}/{code}.parquet'
CODES=['005930','000660','000010','000030','097230','001230','004140']

def summarize(code, kind):
    url=ROOT.format(kind=kind,code=code)
    r=requests.get(url,timeout=120)
    rec={'code':code,'kind':kind,'status':r.status_code,'bytes':len(r.content)}
    if r.status_code != 200 or len(r.content) <= 100:
        return rec
    df=pd.read_parquet(io.BytesIO(r.content))
    rec['columns']=list(df.columns)
    rec['rows']=len(df)
    for c in ['rcept_no','rceptNo','rcept_date','rceptDate','year','period','bsns_year','report_type','reprt_code','corp_name','corp','stock_code']:
        if c in df.columns:
            vals=df[c].dropna().astype(str)
            rec[c+'_min']=vals.min() if len(vals) else None
            rec[c+'_max']=vals.max() if len(vals) else None
            rec[c+'_unique_head']=vals.drop_duplicates().head(20).tolist()
    # Look for target accounting labels/text in docs without dumping whole documents.
    text_cols=[c for c in ['content','contentRaw','section_title','sectionLeaf','blockLeaf','account_nm'] if c in df.columns]
    targets=['매출액','영업수익','당기순이익','분기순이익','반기순이익','자본총계','영업활동현금흐름','영업활동으로인한현금흐름']
    hits={}
    for t in targets:
        mask=pd.Series(False,index=df.index)
        for c in text_cols:
            mask |= df[c].fillna('').astype(str).str.contains(t,regex=False)
        z=df.loc[mask]
        hits[t]={'rows':int(len(z))}
        for c in ['rcept_no','rceptNo','rcept_date','rceptDate','year','period','corp_name','corp','report_type','section_title','sectionLeaf','blockLeaf']:
            if c in z.columns:
                hits[t][c+'_samples']=z[c].dropna().astype(str).drop_duplicates().head(10).tolist()
    rec['target_hits']=hits
    return rec

def main():
    out=[]
    for code in CODES:
        for kind in ['finance','docs']:
            try:
                out.append(summarize(code,kind))
            except Exception as e:
                out.append({'code':code,'kind':kind,'error':repr(e)})
    Path('results').mkdir(exist_ok=True)
    Path('results/dartlab_hf_diagnostic.json').write_text(
        json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    concise=[]
    for x in out:
        concise.append({k:v for k,v in x.items() if k in {
            'code','kind','status','bytes','rows','rcept_no_min','rcept_no_max',
            'rceptNo_min','rceptNo_max','rcept_date_min','rcept_date_max',
            'rceptDate_min','rceptDate_max','year_min','year_max','period_min','period_max',
            'bsns_year_min','bsns_year_max','corp_name_unique_head','corp_unique_head','target_hits'}})
    print(json.dumps(concise,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
