"""Bounded public primary-calendar investigation; no authentication or guessing.

Fetch the official page, then only literal 2007 download links actually present
in that HTML (at most two). No form emulation, AJAX endpoint guessing or retries.
"""
import argparse, hashlib, json, re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib import request, error, parse
URL='https://www.krx.co.kr/contents/MKD/01/0110/01100303/MKD01100303.jsp'
MAX_BYTES=4*1024*1024
class OfficialRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        host=parse.urlsplit(newurl).hostname or ''
        if not (host=='krx.co.kr' or host.endswith('.krx.co.kr')):raise ValueError('nonofficial redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)
class Links(HTMLParser):
    def __init__(self):super().__init__();self.attributes=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if any('2007' in (v or '')for v in values.values()):self.attributes.append({'tag':tag,'attributes':values})
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('existing research requires review')
    a.output.mkdir(parents=True)
    state={'checked_at':datetime.now(timezone.utc).isoformat(),'requests':0,'max_requests':3,'responses':[],
           'official_calendar_certified':False,'status':'STARTED'}
    def get(url,name):
        state['requests']+=1
        try:
            with request.build_opener(OfficialRedirect()).open(url,timeout=25)as r:
                raw=r.read(MAX_BYTES+1);status=r.status;final=r.geturl()
        except error.HTTPError as exc:
            state['error']={'kind':'HTTP_FAILURE','http_status':exc.code};return None
        except Exception:
            state['error']={'kind':'TRANSPORT_FAILURE','http_status':None};return None
        if len(raw)>MAX_BYTES:state['error']={'kind':'SIZE_LIMIT','http_status':status};return None
        (a.output/name).write_bytes(raw)
        state['responses'].append({'requested_url':url,'final_url':final,'file':name,'http_status':status,
                                   'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        return raw
    raw=get(URL,'official_calendar_page.html')
    if raw:
        parser=Links();parser.feed(raw.decode('utf-8',errors='replace'))
        state['literal_2007_attributes']=parser.attributes
        hrefs=[]
        for entry in parser.attributes:
            attrs=entry['attributes'];value=attrs.get('href','')
            if value and '2007'in value and re.search(r'\.(?:pdf|xls|xlsx|csv)(?:\?|$)',value):hrefs.append(parse.urljoin(URL,value))
        for index,url in enumerate(dict.fromkeys(hrefs)):
            host=parse.urlsplit(url).hostname or ''
            if index==2:break
            if (host=='krx.co.kr'or host.endswith('.krx.co.kr')) and get(url,'official_2007_asset_'+str(index)+'.bin')is None:break
        state['status']='PRIMARY_PAGE_RETRIEVED_CALENDAR_CONTENT_UNVERIFIED'
    else:state['status']='STOPPED'
    (a.output/'research_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:state[k]for k in ['status','requests','official_calendar_certified']}))
    # A recorded research gap is not a certified result; callers inspect state.
if __name__=='__main__':main()
