"""Bounded missing 2021 lifecycle proof only; no history/price recollection."""
import argparse,hashlib,importlib.util,json,os,re
from pathlib import Path
from urllib import request,parse,error
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
s=importlib.util.spec_from_file_location('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py')
safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 key=os.getenv('DART_API_KEY','');state=dict(requests=0,retries=0,responses=[],errors=[],candidates=[],investment_approved=False)
 def save():
  (a.output/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 def capture(url,name,data=None,archive=False):
  if state['requests']>=16:raise ValueError('REQUEST_BUDGET16')
  state['requests']+=1
  try:
   with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url,data=data),timeout=25) as r:
    raw=r.read(safe.safe.MAX_BYTES+1);http=r.status;ct=r.headers.get('Content-Type','')
   if not raw or len(raw)>safe.safe.MAX_BYTES:raise ValueError('EMPTY_OR_OVERSIZE')
   if key and key.encode() in raw:raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   if archive:safe.inspect_archive(raw,key)
   else:
    text=safe.safe.decode(raw)
    if key and key in safe.unescape(text):raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   (a.output/name).write_bytes(raw)
   state['responses'].append(dict(file=name,http=http,content_type=ct,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),source='OpenDART document.xml' if archive else url));save()
   return None if archive else text
  except error.HTTPError as e:
   state['errors'].append(dict(file=name,http=e.code,reason='HTTP_FAILURE'));save();raise RuntimeError('HTTP_FAILURE_STOP') from None
  except Exception as e:
   state['errors'].append(dict(file=name,http=None,reason=type(e).__name__));save();raise RuntimeError('SOURCE_VALIDATION_STOP') from None
 try:
  if not re.fullmatch(r'[A-Za-z0-9]{40}',key):raise ValueError('AUTH_ENV_MISSING')
  for code,receipt in [('068270','20210326802215'),('091990','20210326901313')]:
   rows=json.loads((ROOT/f'docs/research/stage12-stock-dividend-20261016/official_metadata/{code}_page1.json').read_text())['list']
   assert any(r['rcept_no']==receipt and r['report_nm']=='정기주주총회결과' for r in rows)
   capture('https://opendart.fss.or.kr/api/document.xml?'+parse.urlencode(dict(crtfc_key=key,rcept_no=receipt)),receipt+'.zip',archive=True)
  targets=[]
  for code,name in [('068270','셀트리온'),('091990','셀트리온헬스케어')]:
   params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate='2021-03-27',toDate='2021-04-30',searchCodeType='char',repIsuSrtCd='A'+code,searchCorpName=name,oldSearchCorpName=name,reportNm='추가상장',reportNmTemp='추가상장')
   text=capture('https://kind.krx.co.kr/disclosure/details.do',code+'_listing_search.html',parse.urlencode(params).encode())
   for row in re.findall(r'<tr\b.*?</tr>',text,re.S|re.I):
    if name not in row or '주식배당' not in row:continue
    for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})",row):
     targets.append(receipt);state['candidates'].append(dict(code=code,receipt=receipt,row=re.sub('<[^>]+>',' ',row)))
  if len(set(targets))>4:raise ValueError('TOO_MANY_DISTINCT_LISTING_CANDIDATES')
  if not targets:raise ValueError('NO_STOCK_DIVIDEND_LISTING_CANDIDATE')
  for receipt in dict.fromkeys(targets):
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html')
   m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",text)
   if not m:raise ValueError('NO_RETURNED_DOCNO')
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html')
   urls=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",text)
   if not urls:raise ValueError('NO_RETURNED_BODY_PATH')
   capture(urls[0],receipt+'_body.html')
 except Exception as e:
  state['errors'].append(dict(reason=type(e).__name__,detail='bounded collection stopped; key/request URL never logged'))
 finally:
  save();safe.emit_bundle(a.output,state)
 return int(bool(state['errors']))
if __name__=='__main__':raise SystemExit(main())
