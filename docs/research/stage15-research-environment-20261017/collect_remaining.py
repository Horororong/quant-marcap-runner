"""At most20 NEW official source requests, zero retries, no prices/history lists."""
import argparse,hashlib,importlib.util,json,os,re
from pathlib import Path
from urllib import request,parse,error
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
s=importlib.util.spec_from_file_location('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py')
safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 state=dict(requests=0,retries=0,responses=[],errors=[],candidates=[],investment_approved=False)
 key=os.getenv('DART_API_KEY','')
 def capture(url,name,data=None,archive=False):
  if state['requests']>=20:raise ValueError('REQUEST_BUDGET')
  state['requests']+=1
  try:
   with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url,data=data),timeout=25) as r:
    raw=r.read(safe.safe.MAX_BYTES+1);http=r.status;ct=r.headers.get('Content-Type','')
   if len(raw)>safe.safe.MAX_BYTES or not raw:raise ValueError('EMPTY_OR_OVERSIZE')
   if key and key.encode() in raw:raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   if archive:members,texts=safe.inspect_archive(raw,key)
   else:
    text=safe.safe.decode(raw)
    if key and key in safe.unescape(text):raise ValueError('CREDENTIAL_ECHO_BLOCKED')
   (a.output/name).write_bytes(raw)
   state['responses'].append(dict(file=name,http=http,content_type=ct,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),source='OpenDART document.xml' if archive else url))
   return None if archive else text
  except error.HTTPError as e:state['errors'].append(dict(file=name,reason='HTTP_FAILURE',http=e.code))
  except Exception as e:state['errors'].append(dict(file=name,reason=type(e).__name__,http=None))
  return None
 if os.getenv('STAGE15_COMPLETION')=='1':
  # Only a newly identified AGM result and actual listing receipt from the
  # preceding saved search. No repeated searches, proposals or prices.
  receipt='20200327902239'
  catalog=json.loads((ROOT/'docs/research/stage12-stock-dividend-20261016/official_metadata/091990_page1.json').read_text())['list']
  assert any(r['rcept_no']==receipt and r['report_nm']=='정기주주총회결과' for r in catalog)
  if not re.fullmatch(r'[A-Za-z0-9]{40}',key):raise ValueError('AUTH_ENV_MISSING')
  capture('https://opendart.fss.or.kr/api/document.xml?'+parse.urlencode(dict(crtfc_key=key,rcept_no=receipt)),receipt+'.zip',archive=True)
  receipt='20200421000430'
  shell=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html')
  m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",shell or '')
  if not m:raise ValueError('NO_SOURCE_DOCNO')
  body=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html')
  paths=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",body or '')
  if not paths:raise ValueError('NO_RETURNED_BODY')
  capture(paths[0],receipt+'_body.html')
  assert state['requests']==4
  (a.output/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
  safe.emit_bundle(a.output,state)
  return int(bool(state['errors']))
 # Three new proposal documents, proved by frozen official metadata; never the rejected ex-notices.
 for code,receipt in [('091990','20191217900478'),('091990','20201216900990'),('068270','20201216801088')]:
  rows=json.loads((ROOT/f'docs/research/stage12-stock-dividend-20261016/official_metadata/{code}_page1.json').read_bytes())['list']
  row=next(r for r in rows if r['rcept_no']==receipt);assert row['stock_code']==code and row['report_nm']=='주식배당결정'
  if not re.fullmatch(r'[A-Za-z0-9]{40}',key):state['errors'].append(dict(file=receipt,reason='AUTH_ENV_MISSING'));break
  capture('https://opendart.fss.or.kr/api/document.xml?'+parse.urlencode(dict(crtfc_key=key,rcept_no=receipt)),receipt+'.zip',archive=True)
 targets=[]
 searches=[('2019-12-26','2019-12-26','배당락','',''),('2020-12-28','2020-12-28','배당락','',''),('2020-03-27','2020-04-30','추가상장','A091990','셀트리온헬스케어')]
 for i,(start,end,title,code,name) in enumerate(searches):
  params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate=start,toDate=end,searchCodeType='char',repIsuSrtCd=code,searchCorpName=name,oldSearchCorpName=name,reportNm=title,reportNmTemp=title)
  body=capture('https://kind.krx.co.kr/disclosure/details.do',f'search_{i}.html',parse.urlencode(params).encode())
  for row in re.findall(r'<tr\b.*?</tr>',body or '',re.S|re.I):
   if '셀트리온' not in row:continue
   if i==0 and '셀트리온헬스케어' not in row:continue # CT2019 base already preserved
   if i==2 and '주식배당' not in row:continue
   receipts=re.findall(r"openDisclsViewer\(['\"](\d{14})",row)
   for receipt in receipts:
    targets.append(receipt);state['candidates'].append(dict(receipt=receipt,search=i,row=re.sub('<[^>]+>',' ',row)))
 for receipt in list(dict.fromkeys(targets))[:4]:
  shell=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html')
  m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",shell or '')
  if not m:state['errors'].append(dict(file=receipt,reason='DOCNO_NOT_FOUND'));continue
  path=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html')
  paths=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",path or '')
  if paths:capture(paths[0],receipt+'_body.html')
  else:state['errors'].append(dict(file=receipt,reason='BODY_PATH_NOT_RETURNED'))
 (a.output/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 safe.emit_bundle(a.output,state)
 return int(bool(state['errors']))
if __name__=='__main__':raise SystemExit(main())
