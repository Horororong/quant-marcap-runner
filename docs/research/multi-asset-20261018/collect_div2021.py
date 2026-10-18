"""Two newly exposed2021 dividends only: proposals,2022 AGM, references/listings.

Existing2019/2020 documents and prices are NOT requested. Max32 requests, one
pass, stop on HTTP/auth/format failure. Credentials never enter logs/manifests.
"""
import argparse,base64,hashlib,importlib.util,json,os,re
from pathlib import Path
from urllib import request,parse,error
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
s=importlib.util.spec_from_file_location('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py');safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)

def main(out):
 out.mkdir(parents=True,exist_ok=False);state=dict(requests=0,retries=0,responses=[],candidates=[],errors=[],investment_approved=False);key=os.getenv('DART_API_KEY','')
 def capture(url,name,data=None,archive=False,public_source=None):
  if state['requests']>=32:raise ValueError('REQUEST_BUDGET32')
  state['requests']+=1
  try:
   with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url,data=data),timeout=25) as r:raw=r.read(safe.safe.MAX_BYTES+1);http=r.status;ct=r.headers.get('Content-Type','')
   if not raw or len(raw)>safe.safe.MAX_BYTES:raise ValueError('EMPTY_OR_OVERSIZE')
   if key and (key.encode() in raw or parse.quote(key,safe='').encode() in raw):raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   if archive:safe.inspect_archive(raw,key)
   text=None if archive else safe.safe.decode(raw)
   if text and key and key in safe.unescape(text):raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   stored=base64.b64encode(raw)+b'\n' if archive else raw;file=name+'.b64' if archive else name;(out/file).write_bytes(stored)
   pin=dict(file=file,http=http,content_type=ct,bytes=len(stored),sha256=hashlib.sha256(stored).hexdigest(),source=public_source or url)
   if archive:pin.update(storage_encoding='base64',raw_bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest())
   state['responses'].append(pin);return text
  except error.HTTPError as e:
   state['errors'].append(dict(file=name,http=e.code,reason='HTTP_FAILURE_STOP'));raise RuntimeError('HTTP_FAILURE_STOP') from None
 try:
  if not re.fullmatch(r'[A-Za-z0-9]{40}',key):raise ValueError('AUTH_ENV_MISSING')
  receipts=[]
  for code in ['068270','091990']:
   corp=json.loads((ROOT/f'docs/research/stage12-stock-dividend-20261016/official_metadata/{code}_page1.json').read_bytes())['list'][0]['corp_code']
   for start,end,title in [('20211201','20211231','주식배당결정'),('20220301','20220331','정기주주총회결과')]:
    for page in [1,2]:
     public=dict(corp_code=corp,bgn_de=start,end_de=end,last_reprt_at='N',page_count=100,page_no=page)
     raw=capture('https://opendart.fss.or.kr/api/list.json?'+parse.urlencode(dict(crtfc_key=key,**public)),f'{code}_{start}_page{page}.json',public_source='OpenDART list.json '+json.dumps(public,sort_keys=True))
     payload=json.loads(raw)
     if payload.get('status')!='000':raise ValueError('DART_STATUS_'+str(payload.get('status')))
     for row in payload['list']:
      if row['corp_code']!=corp or row.get('stock_code')!=code:raise ValueError('OFFICIAL_IDENTITY_MISMATCH')
      if title in row['report_nm']:
       receipts.append(row['rcept_no']);state['candidates'].append(dict(code=code,report=row))
     if payload['total_page']<=page:break
     if page==2:raise ValueError('METADATA_PAGE_LIMIT2_HISTORY_INCOMPLETE')
  targets=list(dict.fromkeys(receipts))
  if not 4<=len(targets)<=6:raise ValueError('EXPECTED_4_TO_6_PROPOSAL_AND_AGM_DOCUMENTS')
  for receipt in targets:capture('https://opendart.fss.or.kr/api/document.xml?'+parse.urlencode(dict(crtfc_key=key,rcept_no=receipt)),receipt+'.zip',archive=True,public_source='OpenDART document.xml rcept_no='+receipt)
  targets=[]
  for code,name in [('068270','셀트리온'),('091990','셀트리온헬스케어')]:
   for start,end,title in [('2021-12-28','2021-12-30','배당락'),('2022-03-28','2022-04-30','추가상장')]:
    params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate=start,toDate=end,searchCodeType='char',repIsuSrtCd='A'+code,searchCorpName=name,oldSearchCorpName=name,reportNm=title,reportNmTemp=title)
    text=capture('https://kind.krx.co.kr/disclosure/details.do',code+'_'+title+'_search.html',parse.urlencode(params).encode())
    for row in re.findall(r'<tr\b.*?</tr>',text,re.S|re.I):
     if name not in row or (title=='추가상장' and '주식배당' not in row):continue
     for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})",row):targets.append(receipt);state['candidates'].append(dict(code=code,receipt=receipt,row=re.sub('<[^>]+>',' ',row)))
  targets=list(dict.fromkeys(targets))
  if not 4<=len(targets)<=6:raise ValueError('EXPECTED_4_TO_6_REFERENCE_AND_LISTING_DOCUMENTS')
  for receipt in targets:
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html');m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",text);assert m
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html');urls=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",text);assert urls
   capture(urls[0],receipt+'_body.html')
 except Exception as e:state['errors'].append(dict(reason=type(e).__name__,detail=str(e) if isinstance(e,ValueError) else 'bounded collection stopped without retry'))
 (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');safe.emit_bundle(out,state);return int(bool(state['errors']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(main(a.output))
