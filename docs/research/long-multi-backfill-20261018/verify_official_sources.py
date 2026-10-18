"""Independent transformation audit against raw official response fields."""
import base64,gzip,hashlib,io,json
from pathlib import Path
from decimal import Decimal
import pandas as pd
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def decode(path):return gzip.decompress(base64.b64decode(path.read_bytes()))
def verify():
 registry=json.loads((ROOT/'config/research/official_source_extensions_v1.json').read_bytes());counts={}
 for rec in registry['datasets']:
  raw=decode(ROOT/rec['data']['path']);assert hashlib.sha256(raw).hexdigest()==rec['data']['csv_sha256']
  df=pd.read_csv(io.BytesIO(raw),dtype=str,keep_default_na=False)
  rows={};field_count=0
  for pin in rec['evidence']:
   p=ROOT/pin['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==pin['sha256']
   original=decode(p) if pin.get('encoding') else p.read_bytes()
   if pin.get('original_sha256'):assert hashlib.sha256(original).hexdigest()==pin['original_sha256']
   for row in json.loads(original)['OutBlock_1']:
    if rec['dataset']=='index:KOSPI' and row['IDX_NM']!='코스피':continue
    key=(row['BAS_DD'],row.get('ISU_CD','KOSPI'))
    assert key not in rows;rows[key]=row
  for r in df.to_dict('records'):
   key=(r['Date'].replace('-',''),r.get('Code','KOSPI'));original=rows.pop(key)
   fields={'Close':'CLSPRC_IDX'} if rec['dataset']=='index:KOSPI' else {'Open':'TDD_OPNPRC','High':'TDD_HGPRC','Low':'TDD_LWPRC','Close':'TDD_CLSPRC','Changes':'CMPPREVDD_PRC','ChangesRatio':'FLUC_RT','Marcap':'MKTCAP','Stocks':'LIST_SHRS','Amount':'ACC_TRDVAL','Volume':'ACC_TRDVOL'}
   for normalized,field in fields.items():assert Decimal(r[normalized])==Decimal(original[field].replace(',','')),(key,field);field_count+=1
   if rec['dataset']=='equities':assert r['Name']==original['ISU_NM'] and r['SourceMarket']==original['MKT_NM']
  assert not rows,'No source securities may be excluded by conversion'
  counts[rec['dataset']]=dict(rows=len(df),numeric_fields_exact=field_count)
 # Official reference check is NOT an economic holding return override.
 ref=decode(HOME/'sources/bio__reference.html.gz.b64').decode('utf-8')
 assert '760,000' in ref and '2022-02-28' in ref
 source=json.loads(decode(HOME/'sources/bio__stk_20220228.json.gz.b64'))
 r=next(x for x in source['OutBlock_1'] if x['ISU_CD']=='207940')
 price=Decimal(r['TDD_CLSPRC']);quote=Decimal(r['FLUC_RT'])/100
 assert price==779000 and quote==Decimal('.025') and price/Decimal(760000)-1==quote
 return dict(status='PASS_SOURCE_FIELDS_AND_OFFICIAL_REFERENCE_ONLY',datasets=counts,bio_reference=760000,bio_close=779000,quote_return=str(quote),economic_holding_return='UNVERIFIED; no rights quotes/cash/subscription ledger executed',investment_approved=False)
if __name__=='__main__':print(json.dumps(verify()))
