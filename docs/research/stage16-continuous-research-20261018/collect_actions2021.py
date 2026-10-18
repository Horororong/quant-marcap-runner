"""One bounded primary-source discovery for the first 2021 blockers.

Public issuer/KIND only, no credentials or price/history recollection. Preserve
returned links; do not guess body paths or infer events from returns.
"""
import argparse,hashlib,json,importlib.util,re
from pathlib import Path
from urllib import request,parse,error
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
s=importlib.util.spec_from_file_location('safe14',ROOT/'docs/research/stage14-celltrion-2019-20261017/collect_sources.py');safe=importlib.util.module_from_spec(s);s.loader.exec_module(safe)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--reference-only',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 state=dict(requests=0,retries=0,responses=[],errors=[],candidates=[],investment_approved=False)
 def capture(url,name,data=None):
  if state['requests']>=16:raise ValueError('REQUEST_BUDGET16')
  state['requests']+=1
  try:
   with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url,data=data),timeout=25) as r:raw=r.read(safe.safe.MAX_BYTES+1);http=r.status;ct=r.headers.get('Content-Type','')
   if not raw or len(raw)>safe.safe.MAX_BYTES:raise ValueError('EMPTY_OR_OVERSIZE')
   text=safe.safe.decode(raw);(a.output/name).write_bytes(raw)
   state['responses'].append(dict(file=name,http=http,content_type=ct,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),source=url));return text
  except error.HTTPError as e:state['errors'].append(dict(file=name,http=e.code,reason='HTTP_FAILURE'));raise RuntimeError('HTTP_FAILURE_STOP') from None
 try:
  if not a.reference_only:capture('https://www.kakaocorp.com/ir/noticeView?boardIdx=10326&currentGroup=1&currentPage=1','kakao_split_issuer.html')
  targets=[]
  queries=([('035720','카카오','기준가격','2021-04-14','2021-04-14')] if a.reference_only else [('035720','카카오','변경상장','2021-04-01','2021-04-16'),('003550','LG','매매거래정지','2021-04-20','2021-05-04')])
  for code,name,title,first,last in queries:
   params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate=first,toDate=last,searchCodeType='char',repIsuSrtCd='A'+code,searchCorpName=name,oldSearchCorpName=name,reportNm=title,reportNmTemp=title)
   text=capture('https://kind.krx.co.kr/disclosure/details.do',code+'_search.html',parse.urlencode(params).encode())
   for row in re.findall(r'<tr\b.*?</tr>',text,re.S|re.I):
    if title not in row:continue
    for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})",row):targets.append(receipt);state['candidates'].append(dict(code=code,receipt=receipt,row=re.sub('<[^>]+>',' ',row)))
  if len(set(targets))>4:raise ValueError('CANDIDATE_BUDGET4')
  for receipt in dict.fromkeys(targets):
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchInitInfo',acptNo=receipt)),receipt+'_viewer.html')
   m=re.search(r"<option value=['\"](\d{14})\|Y['\"]",text)
   if not m:raise ValueError('NO_RETURNED_DOCNO')
   text=capture('https://kind.krx.co.kr/common/disclsviewer.do?'+parse.urlencode(dict(method='searchContents',docNo=m[1])),receipt+'_path.html')
   urls=re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']",text)
   if not urls:raise ValueError('NO_RETURNED_BODY_PATH')
   capture(urls[0],receipt+'_body.html')
 except Exception as e:state['errors'].append(dict(reason=type(e).__name__,detail=str(e) if isinstance(e,ValueError) else 'bounded collection stopped; no retry'))
 (a.output/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');safe.emit_bundle(a.output,state);return int(bool(state['errors']))
if __name__=='__main__':raise SystemExit(main())
