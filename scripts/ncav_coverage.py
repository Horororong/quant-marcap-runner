"""Offline NCAV pairs; never mixes filings, periods, scopes, currencies or units.

Coverage is not PIT eligibility. No HTTP, deployment, or production-data writes.
"""
from decimal import Decimal, InvalidOperation
import re
import pandas as pd

ASSETS={'ifrs-full_CurrentAssets','ifrs_CurrentAssets'}
LIABILITIES={'ifrs-full_Liabilities','ifrs_Liabilities'}
KEY=['corp','rcept_no','fs','bsns_year','reprt_code','thstrm_nm','currency']

def amount(value):
    token=str(value).strip().replace(',','')
    if not re.fullmatch(r'-?\d+(?:\.\d+)?',token):return None
    try:return Decimal(token)
    except InvalidOperation:return None

def financial_pairs(frame,default_scope=None,currencies=("KRW",)):
    x=frame.copy().fillna('')
    for c in ['corp_code','_corp_code','_fs_div_requested','fs_div','sj_div','currency','account_id','account_nm','thstrm_amount','thstrm_nm','source_path','rcept_no','bsns_year','reprt_code']:
        if c not in x:x[c]=''
    x['corp']=x.corp_code.where(x.corp_code.ne(''),x._corp_code)
    x['fs']=x.fs_div.where(x.fs_div.ne(''),x._fs_div_requested)
    if default_scope:x.loc[x.fs.eq(''),'fs']=default_scope
    x=x[x.sj_div.eq('BS')&x.currency.isin(currencies)&x.fs.isin(['CFS','OFS'])]
    x['field']=x.account_id.map({**{k:'current_assets'for k in ASSETS},**{k:'total_liabilities'for k in LIABILITIES}})
    # Exact labels only when no recognized alternative standard ID contradicts them.
    no_standard=~x.account_id.str.startswith(('ifrs_','ifrs-full_'))
    x.loc[no_standard,'field']=x.loc[no_standard,'account_nm'].map({'유동자산':'current_assets','부채총계':'total_liabilities'})
    x=x[x.field.notna()];x['parsed']=x.thstrm_amount.map(amount);out=[]
    for key,g in x.groupby(KEY,dropna=False):
        record=dict(zip(KEY,key));record['accounts']={};valid=True
        for field in ['current_assets','total_liabilities']:
            cells=g[g.field.eq(field)];values=set(cells.parsed.dropna())
            if len(values)!=1:valid=False;record[field+'_reason']='missing_or_conflicting';continue
            v=next(iter(values));record[field]=str(v)
            record['accounts'][field]=cells[['account_id','account_nm','thstrm_amount','source_path']].to_dict('records')
        record['status']='paired'if valid else'held'
        record['ncav']=str(Decimal(record['current_assets'])-Decimal(record['total_liabilities']))if valid else None
        record['filing_date_from_receipt']=record['rcept_no'][:8]
        record['publication_date_independently_verified']=False;record['pit_eligible']=False
        out.append(record)
    return out
