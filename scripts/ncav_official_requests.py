"""Bounded, explicit official request contracts; no network on import.

Successful transport means retained evidence, never financial/PIT admission.
All source URLs omit authentication; redirects and retries are forbidden.
"""
import json, re
from urllib.parse import urlsplit

def validate(task, plan):
    s=task['request'];u=urlsplit(s['url']);p=s['params']
    if u.scheme!='https' or u.query or u.fragment or u.username or u.port or s['method']not in {'GET','POST'}:
        raise ValueError('OFFICIAL_URL_CONTRACT')
    if any(any(w in k.lower()for w in ['key','token','secret','password','auth'])for k in p):
        raise ValueError('AUTH_MUST_NOT_BE_IN_PLAN')
    if task.get('corp_code')not in plan['cohort_corps'] and task.get('role')!='signal_market':
        raise ValueError('OUTSIDE_FIXED_COHORT')
    if u.hostname=='data-dbg.krx.co.kr':
        if s['method']!='GET' or u.path not in {'/svc/apis/sto/stk_bydd_trd','/svc/apis/sto/ksq_bydd_trd'} or set(p)!={'basDd'} or p['basDd']!=plan['signal_date'].replace('-',''):
            raise ValueError('EXACT_SIGNAL_MARKET_ONLY')
    elif u.hostname=='opendart.fss.or.kr':
        if s['method']!='GET':raise ValueError('DART_GET_ONLY')
        if u.path=='/api/list.json':
            if set(p)!={'corp_code','bgn_de','end_de','last_reprt_at','page_count','page_no'}:
                raise ValueError('LIST_PARAMETERS')
            if p['corp_code']!=task['corp_code'] or not plan['inventory_start']<=p['bgn_de']<=p['end_de']<=plan['inventory_end']:
                raise ValueError('LIST_CORP_DATE')
            if p['last_reprt_at']!='N' or p['page_count']!='100' or p['page_no']not in {'1','2'}:
                raise ValueError('LIST_COMPLETENESS_POLICY')
        elif u.path=='/api/document.xml':
            if set(p)!={'rcept_no'} or not re.fullmatch(r'\d{14}',p['rcept_no']):raise ValueError('EXACT_DOCUMENT')
            if not task.get('source_binding'):raise ValueError('LIST_BOUND_DOCUMENT_REQUIRED')
        else:raise ValueError('UNAPPROVED_DART_ENDPOINT')
    elif u.hostname=='dart.fss.or.kr':
        if s['method']!='GET' or u.path!='/report/viewer.do' or set(p)!={'rcpNo','dcmNo','eleId','offset','length','dtd'}:
            raise ValueError('EXACT_RETAINED_VIEWER_NODE_ONLY')
        if not re.fullmatch(r'\d{14}',p['rcpNo']) or any(not str(p[k]).isdigit()for k in ['dcmNo','eleId','offset','length']) or p['dtd']!='dart3.xsd' or not task.get('source_binding'):
            raise ValueError('VIEWER_SOURCE_BINDING')
    else:
        # KIND follow-ups are deliberately not silently mapped to a guessed form.
        raise ValueError('ENDPOINT_ADAPTER_NOT_VERIFIED')

def classify(task, body):
    s=task['request'];u=urlsplit(s['url']);p=s['params']
    if u.path=='/api/document.xml':
        from ncav_collection_queue import classify_response
        return classify_response({'endpoint':'document.xml'},body)
    if u.hostname=='data-dbg.krx.co.kr':
        rows=json.loads(body).get('OutBlock_1')
        if not rows or any(r.get('BAS_DD')!=p['basDd']for r in rows) or len({r['ISU_CD']for r in rows})!=len(rows):
            raise ValueError('EMPTY_WRONG_OR_DUPLICATE_MARKET')
        return dict(status='STORED',body=body,metadata={'rows':len(rows),'date':p['basDd']})
    if u.path=='/api/list.json':
        x=json.loads(body)
        if x.get('status')=='013':
            if x.get('list') or int(x.get('total_count',0)):raise ValueError('CONTRADICTORY_EMPTY_LIST')
            return dict(status='NO_DATA',body=body,metadata={'total_pages':0,'complete_evidence':False})
        if x.get('status')!='000':raise ValueError('DART_SERVICE_ERROR')
        try:
            page,pages,count=int(x['page_no']),int(x['total_page']),int(x['total_count']);rows=x['list']
        except (KeyError,TypeError,ValueError):raise ValueError('MALFORMED_LIST_PAGINATION')from None
        if page!=int(p['page_no']) or not rows or pages!=(count+99)//100 or pages<page or len(rows)>100:
            raise ValueError('LIST_PAGINATION')
        if any(r.get('corp_code')!=p['corp_code'] or not p['bgn_de']<=r.get('rcept_dt','')<=p['end_de']for r in rows):
            raise ValueError('LIST_SCOPE')
        if len({r['rcept_no']for r in rows})!=len(rows):raise ValueError('DUPLICATE_RECEIPT')
        return dict(status='STORED',body=body,metadata={'total_pages':pages,'total_count':count,'page':page,
            'page_cap_exceeded':pages>2,'complete_evidence':False})
    if not body or b'<html'not in body.lower() or b'<table'not in body.lower():
        raise ValueError('NOT_VIEWER_FINANCIAL_BODY')
    return dict(status='STORED',body=body,metadata={'source_comparison_required':True})
