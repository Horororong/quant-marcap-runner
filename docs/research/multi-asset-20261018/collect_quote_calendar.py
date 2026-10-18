"""One new LG/LX official market-day, one missing KOSPI day access probe,
and bounded official 2026 cash-market holiday notices. No retries or writes to data.
"""
import argparse,hashlib,importlib.util,json,os,re
from pathlib import Path
from urllib import request,parse,error
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
safe=module('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py')
quotes=module('quotes12',ROOT/'scripts/collect_stock_dividend_krx.py')

def main(out,stock_date="20210527",stock_codes=("003550","383800"),stock_only=False):
 out.mkdir(parents=True,exist_ok=False);key=os.environ.get('KRX_AUTH_KEY','').strip()
 state=dict(requests=0,retries=0,responses=[],target_rows=[],errors=[],scope='one new stock market-day and one index-service access probe; no raw data repair',investment_approved=False)
 def save(name,raw,url,http,ctype):
  if key and (key.encode() in raw or parse.quote(key,safe='').encode() in raw):raise ValueError('CREDENTIAL_ECHO_BLOCKED')
  (out/name).write_bytes(raw);state['responses'].append(dict(file=name,source=url,http=http,content_type=ctype,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 if not key:state['errors'].append(dict(route='KRX',reason='AUTH_ENV_MISSING'))
 else:
  try:
   state['requests']+=1;http,raw=quotes.fetch('stk_bydd_trd',stock_date,key)
   data=json.loads(raw);rows=data.get('OutBlock_1');assert isinstance(rows,list) and rows
   save('stk_bydd_trd_'+stock_date+'.json',raw,'https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd?basDd='+stock_date,http,'application/json')
   for code in stock_codes:
    matched=[dict(source_row_index=i,security=code,date=stock_date[:4]+'-'+stock_date[4:6]+'-'+stock_date[6:],raw_api_row=r) for i,r in enumerate(rows) if r.get('ISU_CD')==code or r.get('ISU_SRT_CD')==code]
    assert len(matched)==1;state['target_rows']+=matched
   if stock_only:
    (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');safe.emit_bundle(out,state);return 0
   url='https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd?basDd=20260918';state['requests']+=1
   try:
    with request.build_opener(quotes.NoRedirect()).open(request.Request(url,headers={'AUTH_KEY':key,'Accept':'application/json'}),timeout=25) as r:raw=r.read(quotes.MAX_BYTES+1);http=r.status
    assert len(raw)<=quotes.MAX_BYTES;data=json.loads(raw)
    save('kospi_dd_trd_20260918.json',raw,url,http,'application/json')
    state['index_probe']=dict(nonempty=isinstance(data.get('OutBlock_1'),list) and bool(data['OutBlock_1']))
   except error.HTTPError as e:state['errors'].append(dict(route='KRX index service',http=e.code,reason='HTTP_FAILURE_NO_RETRY'))
  except quotes.Stop as e:state['errors'].append(dict(route='KRX quotes',reason=e.kind,http=e.http))
  except Exception as e:state['errors'].append(dict(route='KRX response validation',reason=type(e).__name__))
 def capture(url,name,data=None):
  if state['requests']>=12:raise ValueError('REQUEST_BUDGET12')
  state['requests']+=1
  try:
   with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url,data=data),timeout=25) as r:raw=r.read(safe.safe.MAX_BYTES+1);http=r.status;ctype=r.headers.get('Content-Type','')
   assert raw and len(raw)<=safe.safe.MAX_BYTES;save(name,raw,url,http,ctype);return safe.safe.decode(raw)
  except error.HTTPError as e:raise ValueError('HTTP_'+str(e.code)+'_NO_RETRY') from None
 try:
  params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate='2026-05-20',toDate='2026-05-20',searchCodeType='char',repIsuSrtCd='',searchCorpName='',oldSearchCorpName='',reportNm='휴장안내',reportNmTemp='휴장안내')
  text=capture('https://kind.krx.co.kr/disclosure/details.do','holiday_search.html',parse.urlencode(params).encode())
  targets=[]
  for row in re.findall(r'<tr\b.*?</tr>',text,re.S|re.I):
   if not ('유가증권' in row or '코스닥' in row):continue
   for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})",row):
    if receipt not in targets:targets.append(receipt)
  if not 1<=len(targets)<=3:raise ValueError('EXPECTED_1_TO_3_CASH_MARKET_HOLIDAY_NOTICES')
  for receipt in targets:
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html');m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",text);assert m
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html');urls=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",text);assert urls
   capture(urls[0],receipt+'_body.html')
 except Exception as e:state['errors'].append(dict(route='KIND calendar',reason=str(e) if isinstance(e,ValueError) else type(e).__name__))
 (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');safe.emit_bundle(out,state)
 return int(not state['target_rows'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--stock-only',action='store_true');p.add_argument('--stock-date',choices=['20210527','20211129'],default='20210527');p.add_argument('--stock-codes',default='003550,383800');a=p.parse_args();codes=tuple(a.stock_codes.split(','));assert len(codes)==2 and all(re.fullmatch(r'\d{6}',c) for c in codes);raise SystemExit(main(a.output,a.stock_date,codes,a.stock_only))
