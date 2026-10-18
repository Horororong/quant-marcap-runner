"""Bounded NEW official sources only. No retry, key logs, backfill or data overwrite."""
import argparse,hashlib,json,os,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib import request,parse,error
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];HOME=Path(__file__).resolve().parent;sys.path.insert(0,str(HOME))
from evidence_transport import emit
class NoRedirect(request.HTTPRedirectHandler):
 def redirect_request(self,*a):raise ValueError('REDIRECT_BLOCKED')

def main(out,mode):
 out.mkdir(parents=True,exist_ok=False);state=dict(requests=0,retries=0,responses=[],errors=[],mode=mode,investment_approved=False);key=os.getenv('KRX_AUTH_KEY','')
 def capture(url,name,auth=False):
  if state['requests']>=32:raise ValueError('REQUEST_LIMIT32')
  state['requests']+=1
  headers={'AUTH_KEY':key,'Accept':'application/json'} if auth else {}
  if auth and not key:raise ValueError('KRX_AUTH_ENV_MISSING')
  try:
   with request.build_opener(NoRedirect()).open(request.Request(url,headers=headers),timeout=25) as r:b=r.read(8*1024*1024+1);http=r.status;ct=r.headers.get('Content-Type','')
  except error.HTTPError as e:raise ValueError('HTTP_'+str(e.code)+'_NO_RETRY') from None
  if not b or len(b)>8*1024*1024:raise ValueError('EMPTY_OR_OVERSIZE')
  if key and key.encode() in b:raise ValueError('CREDENTIAL_ECHO_BLOCKED')
  (out/name).write_bytes(b);state['responses'].append(dict(file=name,source=url,http=http,content_type=ct,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
  if auth:
   obj=json.loads(b);rows=obj.get('OutBlock_1')
   if not isinstance(rows,list) or not rows:raise ValueError('NO_OFFICIAL_ROWS_SCHEMA_'+','.join(sorted(obj)))
   date=url.rsplit('=',1)[1];assert all(str(r.get('BAS_DD','')).replace('-','').replace('/','')==date for r in rows),'DATE_MISMATCH'
  return b
 try:
  if mode=='bio':
   urls=[('reference.html','https://kind.krx.co.kr/external/2022/02/25/000917/20220225002100/99301.htm'),('prospectus_initial.html','https://kind.krx.co.kr/external/2022/01/28/000862/20220128001831/10001.htm'),('prospectus_feb25.html','https://kind.krx.co.kr/external/2022/02/25/000689/20220225001679/10001.htm'),('final_terms_apr05.html','https://kind.krx.co.kr/external/2022/04/05/000247/20220405000489/11306.htm'),('actual_result_apr15.html','https://kind.krx.co.kr/external/2022/04/15/000655/20220415001446/10800.htm')]
   for name,url in urls:capture(url,name)
   for day in ['20220225','20220228']:capture('https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd?basDd='+day,'stk_'+day+'.json',True)
  elif mode=='rights':
   for dt in ['20220323','20220324','20220325','20220328','20220329']:
    capture('https://data-dbg.krx.co.kr/svc/apis/sto/sr_bydd_trd?basDd='+dt,'rights_'+dt+'.json',True)
  else:
   import exchange_calendars as xcals
   end=pd.Timestamp('2026-10-16');assert end.date()<datetime.now(timezone.utc).date()
   sessions=pd.DatetimeIndex(xcals.get_calendar('XKRX',start='2025-12-20',end='2026-12-31').sessions_in_range('2026-01-01',end)).tz_localize(None)
   sessions=sessions.difference(pd.to_datetime(['2026-06-03','2026-07-17']))
   prior=ROOT/'docs/research/multi-asset-20261018/evidence_quotes/kospi_dd_trd_20260918.json';state['reused_index_response']=dict(path=str(prior.relative_to(ROOT)),sha256=hashlib.sha256(prior.read_bytes()).hexdigest())
   for day in sessions[sessions>pd.Timestamp('2026-09-18')]:
    dt=day.strftime('%Y%m%d');capture('https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd?basDd='+dt,'kospi_'+dt+'.json',True)
   for day in sessions[sessions>pd.Timestamp('2026-10-08')]:
    for endpoint in ['stk_bydd_trd','ksq_bydd_trd']:
     dt=day.strftime('%Y%m%d');capture('https://data-dbg.krx.co.kr/svc/apis/sto/'+endpoint+'?basDd='+dt,endpoint+'_'+dt+'.json',True)
   state['validated_through']=str(end.date());state['expected_sessions']=list(sessions.strftime('%Y-%m-%d'))
 except Exception as e:state['errors'].append(dict(type=type(e).__name__,reason=str(e) if isinstance(e,ValueError) else 'Response validation failed; raw evidence preserved where valid'))
 (out/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');emit(out,'OFFICIAL_'+mode.upper());return int(bool(state['errors']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=['bio','2026','rights'],required=True);a=p.parse_args();raise SystemExit(main(a.output,a.mode))
