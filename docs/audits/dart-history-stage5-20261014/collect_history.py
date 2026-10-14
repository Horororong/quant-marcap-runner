"""One bounded official OpenDART history acquisition, using stdlib only.

Credentials exist only in memory and request authentication. No URL, exception
text or response message is logged. Raw replies are stored only after checking
that the credential has not been echoed. No retry or automatic resume.
"""
import argparse, csv, hashlib, json, os, re, time
from datetime import datetime
from pathlib import Path
from urllib import request, error, parse
from zoneinfo import ZoneInfo

HOME=Path(__file__).resolve().parent
REPO=HOME.parents[2]
MAX_REQUESTS=80
MAX_PAGES_PER_CORP=5
MAX_RESPONSE_BYTES=2*1024*1024
MAX_TOTAL_BYTES=32*1024*1024
MAX_SECONDS=600
class Stop(Exception):
    def __init__(self,kind,http_status=None,dart_status=None):
        self.kind,self.http_status,self.dart_status=kind,http_status,dart_status
        super().__init__(kind)
class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise Stop('HTTP_REDIRECT_BLOCKED',code)
def fetch(params,key):
    # URL never crosses a logging boundary. Keep native proxy/CA/TLS behavior.
    url='https://opendart.fss.or.kr/api/list.json?'+parse.urlencode({**params,'crtfc_key':key})
    try:
        opener=request.build_opener(NoRedirect())
        with opener.open(request.Request(url,headers={'Accept':'application/json'}),timeout=25) as r:
            code=r.status;payload=r.read(MAX_RESPONSE_BYTES+1)
    except Stop:raise
    except error.HTTPError as e:raise Stop('HTTP_FAILURE',e.code) from None
    except Exception:raise Stop('TRANSPORT_FAILURE') from None
    if code!=200:raise Stop('HTTP_FAILURE',code)
    if len(payload)>MAX_RESPONSE_BYTES:raise Stop('RESPONSE_SIZE_LIMIT',code)
    return code,payload
def reply(payload,key):
    variants=[key.encode(),parse.quote(key,safe='').encode()]
    if any(v and v in payload for v in variants):raise Stop('CREDENTIAL_ECHO_BLOCKED',200)
    try:d=json.loads(payload.decode('utf-8'))
    except Exception:raise Stop('INVALID_JSON',200) from None
    if not isinstance(d,dict):raise Stop('INVALID_RESPONSE',200)
    if key in json.dumps(d,ensure_ascii=False):raise Stop('CREDENTIAL_ECHO_BLOCKED',200)
    status=str(d.get('status',''))
    if not re.fullmatch(r'\d{3}',status):raise Stop('INVALID_DART_STATUS',200)
    return d,status
def atomic_json(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)
def load_targets(original40,holdout20):
    wanted=json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/selection20.json').read_text())['samples']
    source=json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/results/source_facts.json').read_text())
    source={s['sample_id']:s for s in source};samples={}
    for folder in [original40,holdout20]:
        for s in json.loads((folder/'selection.json').read_text())['samples']:samples[s['sample_id']]=s
    out=[]
    for chosen in wanted:
        s=samples[chosen['sample_id']];f=source[s['sample_id']]
        assert s['corp_code']==f['document_dart_corp_code']
        assert s['rcept_no']==f['rcept_no'] and s['document_sha256']==f['document_sha256']
        assert re.fullmatch(r'\d{8}',s['corp_code']) and re.fullmatch(r'\d{14}',s['rcept_no'])
        # Include original period and all subsequent regular filings to this run.
        first_year=min(int(s['rcept_dt'][:4]),int(s['period_end'][:4]))
        out.append({'sample_id':s['sample_id'],'corp_code':s['corp_code'],'rcept_no':s['rcept_no'],
            'index_receipt_date':s['rcept_dt'],'report_nm':s['report_nm'],
            'begin_date':f'{first_year}0101','declared_original_submission_date':f['declared_original_submission_date']})
    assert len(out)==20 and len({s['corp_code']for s in out})==20
    return out
def acquire(targets,key,output,transport=fetch,clock=time.monotonic,pause=time.sleep):
    output.mkdir(parents=True,exist_ok=True);raw=output/'raw';raw.mkdir(exist_ok=True)
    if (output/'run_state.json').exists():raise Stop('EXISTING_RUN_REQUIRES_REVIEW')
    cutoff=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d')
    started=clock();state={'code_sha':os.environ.get('GITHUB_SHA','LOCAL_TEST'),
        'checked_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'end_date':cutoff,
        'endpoint':'https://opendart.fss.or.kr/api/list.json','last_reprt_at':'N','pblntf_ty':'A',
        'limits':{'requests':MAX_REQUESTS,'pages_per_corp':MAX_PAGES_PER_CORP,'seconds':MAX_SECONDS,'total_bytes':MAX_TOTAL_BYTES},
        'requests':0,'bytes':0,'pilot_samples':[s['sample_id']for s in targets[:2]],
        'pilot_complete':False,'completed_samples':[],'responses':[],'status':'STARTED',
        'backtest_eligible':False,'coverage_limit':'Regular-disclosure category A, bounded start through run cutoff only; later filings and other categories not covered. API has no exact public clock or explicit predecessor receipt links.'}
    results=[];atomic_json(output/'run_state.json',state)
    def save():atomic_json(output/'run_state.json',state)
    try:
        if not key:raise Stop('AUTH_ENV_MISSING')
        if not re.fullmatch(r'[A-Za-z0-9]{40}',key):raise Stop('AUTH_ENV_INVALID_FORMAT')
        for index,s in enumerate(targets):
            state['active_sample']=s['sample_id'];state['phase']='PILOT' if index<2 else 'EXPANSION';save()
            rows=[];expected_total=None;expected_pages=None;page=1
            while True:
                if state['requests']>=MAX_REQUESTS or page>MAX_PAGES_PER_CORP:raise Stop('REQUEST_OR_PAGE_LIMIT')
                if clock()-started>MAX_SECONDS:raise Stop('TIME_LIMIT')
                params={'corp_code':s['corp_code'],'bgn_de':s['begin_date'],'end_de':cutoff,
                    'last_reprt_at':'N','pblntf_ty':'A','sort':'date','sort_mth':'asc','page_count':'100','page_no':str(page)}
                state['requests']+=1;save()
                http,payload=transport(params,key);d,status=reply(payload,key)
                if state['bytes']+len(payload)>MAX_TOTAL_BYTES:raise Stop('TOTAL_SIZE_LIMIT',http,status)
                file=f'{s["sample_id"]}_page{page:03d}.json';(raw/file).write_bytes(payload)
                receipt={'sample_id':s['sample_id'],'corp_code':s['corp_code'],'parameters':params,
                    'http_status':http,'dart_status':status,'file':'raw/'+file,
                    'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),
                    'received_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}
                state['bytes']+=len(payload);state['responses'].append(receipt);save()
                if status!='000':raise Stop('DART_FAILURE',http,status)
                try:
                    total=int(d['total_count']);pages=int(d['total_page']);actual_page=int(d['page_no']);count=int(d['page_count'])
                    part=d['list']
                    assert isinstance(part,list) and actual_page==page and count==100
                    assert total>=1 and pages==(total+99)//100
                    assert len(part)==min(100,total-(page-1)*100)
                    if expected_total is not None:assert (total,pages)==(expected_total,expected_pages)
                    assert all(isinstance(r,dict) and r.get('corp_code')==s['corp_code'] for r in part)
                    assert all(re.fullmatch(r'\d{14}',str(r.get('rcept_no',''))) and re.fullmatch(r'\d{8}',str(r.get('rcept_dt',''))) for r in part)
                    assert all(s['begin_date']<=str(r['rcept_dt'])<=cutoff for r in part)
                    for row in part:datetime.strptime(str(row['rcept_dt']),'%Y%m%d')
                except Exception:raise Stop('PAGE_OR_IDENTITY_VALIDATION_FAILURE',http,status) from None
                expected_total,expected_pages=total,pages;rows.extend(part)
                if pages>MAX_PAGES_PER_CORP:raise Stop('PAGINATION_SCOPE_EXCEEDS_LIMIT',http,status)
                if page==pages:break
                page+=1;pause(0.6)
            if len(rows)!=expected_total or len({r['rcept_no']for r in rows})!=len(rows):raise Stop('COUNT_OR_DUPLICATE_FAILURE',200,'000')
            matches=[r for r in rows if r['rcept_no']==s['rcept_no']]
            if len(matches)!=1:raise Stop('TARGET_RECEIPT_NOT_FOUND',200,'000')
            matched=matches[0];official_date=datetime.strptime(matched['rcept_dt'],'%Y%m%d').date().isoformat()
            verdict='PASS' if official_date==s['index_receipt_date'] else 'FAIL'
            # Similar names/periods suggest candidates, never an attested version chain.
            clean=lambda title:re.sub(r'^\[[^]]+\]','',title).replace(' ','')
            candidates=[{k:r.get(k,'')for k in ['corp_code','rcept_no','rcept_dt','report_nm','rm']}for r in rows if clean(str(r['report_nm']))==clean(s['report_nm'])]
            item={**s,'api_response_verdict':'PASS','receipt_corp_match':'PASS','official_receipt_date':official_date,
                'receipt_date_comparison':verdict,'official_report_name':matched['report_nm'],'official_rm':matched.get('rm',''),
                'all_pages_verified':True,'scope_begin':s['begin_date'],'scope_end':cutoff,'listed_rows':len(rows),
                'version_candidates':candidates,'correction_chain_verdict':'UNVERIFIED',
                'exact_public_time_verdict':'UNVERIFIED','daily_available_date':'',
                'daily_availability_verdict':'UNVERIFIED','historical_krx_mapping_verdict':'UNVERIFIED',
                'reason':'Official receipt day is proved, not an intraday public time. No attested predecessor link or official KRX session calendar.','backtest_eligible':False}
            results.append(item);atomic_json(output/(s['sample_id']+'_history.json'),{'target':s,'filings':rows,'assessment':item})
            state['completed_samples'].append(s['sample_id'])
            if index==1:state['pilot_complete']=True
            save();pause(0.6)
        state['status']='COMPLETE_WITH_CERTIFICATION_GAPS';save()
    except Stop as e:
        state['status']='STOPPED';state['error']={'kind':e.kind,'http_status':e.http_status,'dart_status':e.dart_status};save()
    atomic_json(output/'assessments.json',results)
    atomic_json(output/'response_manifest.json',state['responses'])
    # Unattempted or incomplete samples are explicit, never silently omitted.
    complete={r['sample_id']:r for r in results};csvrows=[]
    for s in targets:
        r=complete.get(s['sample_id']);csvrows.append({'sample_id':s['sample_id'],'corp_code':s['corp_code'],'rcept_no':s['rcept_no'],
            'api_response':r['api_response_verdict']if r else'UNVERIFIED','receipt_corp_match':r['receipt_corp_match']if r else'UNVERIFIED',
            'official_receipt_date':r['official_receipt_date']if r else'','receipt_date':r['receipt_date_comparison']if r else'UNVERIFIED',
            'correction_chain':'UNVERIFIED','exact_public_time':'UNVERIFIED','daily_available_date':'','daily_availability':'UNVERIFIED',
            'historical_krx_mapping':'UNVERIFIED','collection_state':'COMPLETE_IN_QUERY_SCOPE'if r else'INCOMPLETE_OR_NOT_ATTEMPTED',
            'backtest_eligible':False})
    with (output/'stage5_details.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
    return state
def main():
    p=argparse.ArgumentParser()
    for k in ['original40','holdout20','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();targets=load_targets(a.original40,a.holdout20)
    # Load only the expressly bound Actions credential; no CLI key or fallback auth.
    key=os.environ.get('DART_API_KEY','').strip()
    try:state=acquire(targets,key,a.output)
    except Stop as e:
        print(json.dumps({'status':'STOPPED','error':e.kind}));return 2
    print(json.dumps({'status':state['status'],'requests':state['requests'],'completed_samples':len(state['completed_samples']),
        'pilot_complete':state['pilot_complete'],'error':state.get('error'),'backtest_eligible':False}))
    return 0 if state['status']=='COMPLETE_WITH_CERTIFICATION_GAPS'else 2
if __name__=='__main__':raise SystemExit(main())
