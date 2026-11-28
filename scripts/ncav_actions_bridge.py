"""Approval-gated private NCAV bridge, using the existing deployed GitHub adapter.

No destination, source response, plan content, ledger or credential is public.
Import this only after deploying against the reviewed current operational main.
This file does not activate a grant, create a schedule, or change other budgets.
"""
import argparse, base64, copy, gzip, hashlib, json, os, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib import request, parse
from ncav_collection_queue import run, fingerprint, save, classify_response

def digest(body): return hashlib.sha256(body).hexdigest()

def source_spec(t):
    if t['endpoint']=='official':return t['request']
    params={'rcept_no':t['receipt']}if t['endpoint']=='document.xml'else{k:t[k]for k in ['corp_code','bsns_year','reprt_code','fs_div']}
    return dict(method='GET',url='https://opendart.fss.or.kr/api/'+t['endpoint'],params=params)

def same_request(a,b):
    return a.get('method','GET')==b.get('method','GET') and a.get('url')==b.get('url') and a.get('params',{})==b.get('params',{})

def validate_envelope(envelope, expected):
    p=envelope['plan']
    if envelope.get('approved') is not True or fingerprint(p)!=expected:
        raise PermissionError('REVIEWED_APPROVAL_REQUIRED')
    if p.get('grant_id','').startswith(('fy20','b2','b-')) or not p.get('grant_id','').startswith('ncav-'):
        raise ValueError('SEPARATE_NCAV_GRANT_REQUIRED')
    if type(p.get('max_runs')) is not int or p['max_runs'] not in (1, 2) or p.get('retries')!=0 or p.get('seconds_per_execution')!=600:
        raise ValueError('FINITE_LIMITS_CHANGED')
    if not 0<p.get('max_http',0)<=479 or not 0<p.get('max_http_per_run',0)<=p['max_http']:
        raise ValueError('HTTP_LIMITS')
    if p.get('financial_publication')!='HOLD' or p.get('classification')!='RESEARCH_ONLY':
        raise ValueError('QUALITY_GATES_CHANGED')
    caps=p.get('per_run_http_caps',[p['max_http_per_run']]*p['max_runs'])
    if len(caps)!=p['max_runs'] or any(not isinstance(c,int)or not 0<c<=p['max_http_per_run']for c in caps):raise ValueError('PER_RUN_HTTP_CAPS')
    return p

class Journal:
    def __init__(self, api, module, root, plan_hash):
        self.api,self.m,self.root=api,module,Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root.chmod(0o700)
        meta=api('GET','/repos/'+module.PRIVATE)
        if meta.get('full_name')!=module.PRIVATE or meta.get('private')is not True or not meta.get('permissions',{}).get('push'):
            raise PermissionError('EXISTING_PRIVATE_ACCESS_REQUIRED')
        # Reuse the existing private accounting object. No branch/file discovery
        # or creation on a missing/denied destination.
        b,self.blob=module.content(api,module.PRIVATE,module.PREFIX+'budget.json',module.BRANCH)
        self.outer=json.loads(b)
        envelope=self.outer.get('prepared_ncav_plans',{}).get(plan_hash)
        if not envelope:raise PermissionError('PRIVATE_APPROVED_PLAN_NOT_INSTALLED')
        self.plan=validate_envelope(envelope,plan_hash)
        self.followups=envelope.get('reviewed_followups',[])
        self.holding_review=envelope.get('holding_review')
        if len(self.followups)>self.plan.get('max_reviewed_followups',0):raise ValueError('FOLLOWUP_CAP')
        for role,cap in self.plan.get('followup_role_caps',{}).items():
            if sum(t.get('role')==role for t in self.followups)>cap:raise ValueError('FOLLOWUP_ROLE_CAP')
        self.grant=self.plan['grant_id']
        self.initial=copy.deepcopy(self.outer)
        old=self.outer.get('additional_finite_grants',{}).get(self.grant)
        if old:
            state=old['queue_state']
            if state['plan_hash']!=plan_hash:raise ValueError('NO_BUDGET_RESET')
            if (self.root/'ledger.json').exists() and json.loads((self.root/'ledger.json').read_text())!=state:
                raise ValueError('LOCAL_REMOTE_ACCOUNTING_CONFLICT')
            save(self.root/'ledger.json',state)
            for r in state['tasks'].values():
                if not r.get('response_file'):continue
                target=self.root/r['response_file']
                if target.is_absolute() and not target.is_relative_to(self.root):raise ValueError('CACHE_PATH')
                if '..'in Path(r['response_file']).parts:raise ValueError('CACHE_PATH')
                packed,_=module.content(api,module.PRIVATE,module.PREFIX+'raw/'+r['sha256']+'.bin.gz',module.BRANCH)
                body=gzip.decompress(packed)
                if digest(body)!=r['sha256']:raise ValueError('PRIVATE_RESPONSE_CHANGED')
                target.parent.mkdir(exist_ok=True,mode=0o700);target.write_bytes(body);target.chmod(0o600)
        elif (self.root/'ledger.json').exists():raise ValueError('LOCAL_HISTORY_WITHOUT_REMOTE_NO_RESET')

    def verify_requests(self):
        from ncav_official_requests import validate
        prior=list(self.outer.get('requests',[]))
        for grant,value in self.outer.get('additional_finite_grants',{}).items():
            if grant!=self.grant:prior.extend(value.get('requests',[]))
        for t in [*self.plan['tasks'],*self.followups]:
            if any(same_request(source_spec(t),r.get('request',{}))for r in prior):
                raise ValueError('PRIOR_SOURCE_ATTEMPT_REUSE_OR_REVIEW_REQUIRED_NO_HTTP')
            if t in self.followups and t.get('role')not in self.plan.get('followup_roles',[]):raise ValueError('FOLLOWUP_PURPOSE_NOT_APPROVED')
            if t.get('role','').startswith('held_'):
                review=self.holding_review
                if not review or review.get('strategy_sha256')!=self.plan.get('strategy_sha256') or review.get('selected_corp')!=t.get('corp_code') or review.get('status')!='ADMITTED_COHORT_SELECTION_BEFORE_PERFORMANCE':
                    raise ValueError('ACTUAL_ADMITTED_HOLDING_REVIEW_REQUIRED')
                h=review.get('evidence_sha256','')
                if not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('HOLDING_REVIEW_SOURCE_BINDING')
                packed,_=self.m.content(self.api,self.m.PRIVATE,self.m.PREFIX+'raw/'+h+'.bin.gz',self.m.BRANCH)
                b=gzip.decompress(packed)
                if digest(b)!=h:raise ValueError('HOLDING_REVIEW_CHANGED')
                evidence=json.loads(b)
                if evidence.get('strategy_sha256')!=review['strategy_sha256'] or evidence.get('selected_corp')!=review['selected_corp'] or set(evidence.get('eligible_cohort_corps',[]))!=set(self.plan['cohort_corps']):
                    raise ValueError('FULL_COHORT_SELECTION_BINDING')
            if t['endpoint']!='official':
                if self.plan.get('scope')!='arithmetic_coverage':raise ValueError('CROSS_BUDGET_TASK')
                continue
            validate(t,self.plan)
            if t in self.followups and not t.get('source_binding'):raise ValueError('FOLLOWUP_REQUIRES_REVIEWED_INVENTORY')
            bind=t.get('source_binding')
            if not bind:continue
            if not re.fullmatch('[0-9a-f]{64}',bind.get('sha256','')):raise ValueError('SOURCE_BINDING_HASH')
            packed,_=self.m.content(self.api,self.m.PRIVATE,self.m.PREFIX+'raw/'+bind['sha256']+'.bin.gz',self.m.BRANCH)
            body=gzip.decompress(packed)
            if digest(body)!=bind['sha256']:raise ValueError('BOUND_SOURCE_CHANGED')
            params=t['request']['params']
            if bind['kind']=='viewer_node':
                text=body.decode('utf8')
                nodes=re.split(r'var node\d+ = \{\};',text)
                valid=False
                for node in nodes:
                    values=dict(re.findall(r"node\d+\['(\w+)'\]\s*=\s*\"([^\"]*)\"",node))
                    if all(values.get(k)==v for k,v in params.items()):valid=True
                if not valid:raise ValueError('VIEWER_NODE_NOT_IN_RETAINED_SOURCE')
            elif bind['kind']=='dart_list':
                rows=json.loads(body).get('list',[])
                if not any(r.get('corp_code')==t['corp_code'] and r.get('rcept_no')==params.get('rcept_no') for r in rows):
                    raise ValueError('DOCUMENT_NOT_IN_ISSUER_INVENTORY')
            else:raise ValueError('UNKNOWN_SOURCE_BINDING')

    def mirror(self,state):
        from ncav_collection_queue import key
        defined={key(t):t for t in [*self.plan['tasks'],*self.followups]}
        for r in state['runs']:
            r.setdefault('github_run_id',os.environ.get('GITHUB_RUN_ID',''))
        outer=copy.deepcopy(self.outer)
        outer.setdefault('additional_finite_grants',{})[self.grant]={
            'queue_state':copy.deepcopy(state),
            'executions':[dict(id=r['id'],run_id=r.get('github_run_id',''),day_kst=datetime.fromisoformat(r['day']).astimezone(timezone(timedelta(hours=9))).date().isoformat(),
                               status='RUNNING'if r['status']=='STARTED'else r['status']) for r in state['runs']],
            'requests':[dict(id=k,status=v['status'],request=source_spec(defined[k]),sha256=v.get('sha256'),
                private_remote_preserved=bool(v.get('response_file'))) for k,v in state['tasks'].items() if v.get('run_id')],
        }
        # Preserve all old grant bytes semantically; only this separate grant changes.
        check=copy.deepcopy(outer);prior=copy.deepcopy(self.initial)
        check.get('additional_finite_grants',{}).pop(self.grant,None)
        prior.get('additional_finite_grants',{}).pop(self.grant,None)
        if check!=prior:raise ValueError('OTHER_HISTORY_MUTATION')
        b=json.dumps(outer,sort_keys=True,separators=(',',':')).encode()
        result=self.api('PUT',f'/repos/{self.m.PRIVATE}/contents/{self.m.PREFIX}budget.json',dict(
            message='Private finite request checkpoint',branch=self.m.BRANCH,sha=self.blob,content=base64.b64encode(b).decode()))
        self.blob=result['content']['sha'];self.outer=outer

    def reconcile_completed_runner(self,public):
        old=self.outer.get('additional_finite_grants',{}).get(self.grant)
        if not old:return
        state=copy.deepcopy(old['queue_state']);changed=False
        for r in state['runs']:
            if r['status']!='STARTED':continue
            rid=r.get('github_run_id','')
            if not re.fullmatch(r'\d+',rid) or rid==os.environ.get('GITHUB_RUN_ID'):
                raise PermissionError('UNCERTAIN_RUN_REQUIRES_ACTUAL_TERMINATION_EVIDENCE')
            evidence=public('GET',f'/repos/{self.m.PUBLIC}/actions/runs/{rid}')
            if evidence.get('status')!='completed':raise PermissionError('PRIOR_RUN_STILL_ACTIVE')
            r['status']='INTERRUPTED_CONFIRMED_RUNNER_COMPLETE';changed=True
        if changed:
            for t in state['tasks'].values():
                if t['status']=='SENDING':t['status']='UNKNOWN'
            self.mirror(state);save(self.root/'ledger.json',state)

    def preserve(self,body):
        name=self.m.PREFIX+'raw/'+digest(body)+'.bin.gz'
        try:
            packed, _ = self.m.content(self.api, self.m.PRIVATE, name, self.m.BRANCH)
        except self.m.Missing:
            result = self.api('PUT', f'/repos/{self.m.PRIVATE}/contents/{name}', dict(
                message='Private retained response', branch=self.m.BRANCH,
                content=base64.b64encode(gzip.compress(body, mtime=0)).decode()))
            # Read back the immutable result of this upload. A branch read can
            # briefly miss a file whose commit was already accepted.
            commit = result['commit']['sha']
            blob = result['content']['sha']
            if not re.fullmatch(r'[0-9a-f]{40}', commit) or not re.fullmatch(r'[0-9a-f]{40}', blob):
                raise ValueError('PRIVATE_WRITE_RECEIPT_INVALID')
            try:
                packed, actual_blob = self.m.content(self.api, self.m.PRIVATE, name, commit)
            except self.m.Missing:
                stored_blob = self.api('GET', f'/repos/{self.m.PRIVATE}/git/blobs/{blob}')
                if stored_blob['encoding'] != 'base64':
                    raise ValueError('PRIVATE_BLOB_ENCODING')
                packed, actual_blob = base64.b64decode(stored_blob['content']), stored_blob['sha']
            if actual_blob != blob:
                raise ValueError('PRIVATE_BLOB_CHANGED')
        if digest(gzip.decompress(packed)) != digest(body):
            raise ValueError('PRIVATE_READBACK_CHANGED')

def collect_source(task, deadline, key_value, opener, plan=None, krx_key=None):
    # This bridge currently covers the frozen arithmetic financial/document
    # queue only. PIT/KRX/KIND requests must NOT be disguised as this endpoint.
    if task['endpoint']=='official':
        from ncav_official_requests import validate, classify
        validate(task,plan)
        s=task['request'];params=dict(s['params']);headers={}
        host=parse.urlsplit(s['url']).hostname
        if host=='opendart.fss.or.kr':params['crtfc_key']=key_value
        if host=='data-dbg.krx.co.kr':
            if not krx_key:raise PermissionError('KRX_SECRET_REQUIRED')
            headers['AUTH_KEY']=krx_key
        remaining=deadline-time.monotonic()
        if remaining<30:raise TimeoutError('SOURCE_RESERVE')
        url=s['url']+'?'+parse.urlencode(params)
        with opener.open(request.Request(url,headers=headers),timeout=min(15,remaining-15))as r:
            if r.status!=200:raise ValueError('SOURCE_HTTP_STATUS')
            b=r.read(32*1024*1024+1)
        if len(b)>32*1024*1024 or any(v and v.encode()in b for v in [key_value,krx_key]):
            raise ValueError('SOURCE_SIZE_OR_SECRET')
        return classify(task,b)
    if task['endpoint']=='document.xml':
        if not re.fullmatch(r'\d{14}',task['receipt']):raise ValueError('RECEIPT')
        params={'rcept_no':task['receipt']}
    elif task['endpoint']=='fnlttSinglAcntAll.json':
        if not re.fullmatch(r'\d{8}',task['corp_code']) or int(task['bsns_year'])<2015:
            raise ValueError('ISSUER_OR_API_PERIOD')
        if task['fs_div']not in {'CFS','OFS'} or task['reprt_code']not in {'11011','11012','11013','11014'}:
            raise ValueError('FINANCIAL_SCOPE')
        params={k:task[k]for k in ['corp_code','bsns_year','reprt_code','fs_div']}
    else:raise ValueError('UNIMPLEMENTED_ENDPOINT_NO_HTTP')
    remaining=deadline-time.monotonic()
    if remaining<30:raise TimeoutError('SOURCE_RESERVE')
    params['crtfc_key']=key_value
    url='https://opendart.fss.or.kr/api/'+task['endpoint']+'?'+parse.urlencode(params)
    with opener.open(request.Request(url),timeout=min(15,remaining-15))as r:
        if r.status!=200:raise ValueError('SOURCE_HTTP_STATUS')
        b=r.read(32*1024*1024+1)
    if len(b)>32*1024*1024 or key_value.encode()in b:raise ValueError('SOURCE_SIZE_OR_SECRET')
    return classify_response(task,b)

def main(diag):
    diag['stage'] = 'workflow_inputs'
    p=argparse.ArgumentParser();p.add_argument('--plan-sha256',required=True);p.add_argument('--private-root',required=True);a=p.parse_args()
    if not re.fullmatch('[0-9a-f]{64}',a.plan_sha256):raise ValueError('PLAN_HASH')
    # Existing deployed helpers, not new copies of private destination constants.
    diag['stage'] = 'control_imports'
    import bounded_official_github as m
    from bounded_official_evidence import NoRedirect, check_history
    from fy20_metadata_github import complete_shared_history
    diag['stage'] = 'runner_identity'
    if os.environ.get('GITHUB_REPOSITORY')!=m.PUBLIC or os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':
        raise PermissionError('MAIN_FIRST_ATTEMPT_ONLY')
    diag['stage'] = 'runner_credentials'
    if not all(os.environ.get(k)for k in ['GITHUB_TOKEN','B_PRIVATE_BACKUP_TOKEN','DART_API_KEY']):
        raise PermissionError('EXISTING_SECRET_INJECTION_REQUIRED')
    deadline=time.monotonic()+600
    public=m.API(os.environ['GITHUB_TOKEN'],deadline);private=m.API(os.environ['B_PRIVATE_BACKUP_TOKEN'],deadline)
    diag['stage'] = 'private_plan'
    j=Journal(private,m,a.private_root,a.plan_sha256)
    j.reconcile_completed_runner(public)
    diag['stage'] = 'verify_requests'
    j.verify_requests()
    if any(t.get('request',{}).get('url','').startswith('https://data-dbg.krx.co.kr/')for t in j.plan['tasks'])and not os.environ.get('KRX_AUTH_KEY'):
        raise PermissionError('KRX_SECRET_REQUIRED_NO_LEASE')
    # Check all existing finite histories. Do not rewrite FY/B/B2 counters.
    now=datetime.now(timezone.utc)
    diag['stage'] = 'shared_history'
    h=complete_shared_history(public,private,now,os.environ['GITHUB_RUN_ID'],j)
    for status in ('in_progress','queued','waiting','requested','pending'):
        runs=public('GET',f'/repos/{m.PUBLIC}/actions/runs?status={status}&per_page=100')
        if runs.get('total_count',0)>100:raise ValueError('ACTIVE_PAGINATION_INCOMPLETE')
        if any(str(r['id'])!=os.environ['GITHUB_RUN_ID']and r.get('path')in {
            '.github/workflows/collect-ncav-reviewed.yml','.github/workflows/collect-fy20-completion.yml'}for r in runs.get('workflow_runs',[])):
            raise PermissionError('OTHER_FINITE_COLLECTION_ACTIVE')
    check_history(h,now)
    caps = j.plan.get('per_run_http_caps', [j.plan['max_http_per_run']] * j.plan['max_runs'])
    run_index = len(j.outer.get('additional_finite_grants', {}).get(j.grant, {}).get('executions', []))
    if run_index >= j.plan['max_runs']:
        raise PermissionError('Execution budget exhausted')
    diag['stage'] = 'queue'
    result=run(j.plan,j.root,approved=True,
        transport=lambda t:collect_source(t,deadline,os.environ['DART_API_KEY'],request.build_opener(NoRedirect()),j.plan,os.environ.get('KRX_AUTH_KEY')),
        acquire_shared_day=lambda *_:check_history(h,datetime.now(timezone.utc)),
        seconds=min(600,int(deadline-time.monotonic())),max_http=caps[run_index],
        now=now,mirror=j.mirror,preserve=j.preserve,reviewed_tasks=j.followups)
    print(json.dumps({**result,'new_PIT_values':0,'backtest_completed':False,'financial_publication':'HOLD'}))

if __name__=='__main__':
    diag = {'stage': 'startup'}
    try:
        main(diag)
    except Exception as exc:
        # Log a fixed stage and allowlisted identifiers only.
        message = str(exc)
        known = {'PRIVATE_APPROVED_PLAN_NOT_INSTALLED', 'REVIEWED_APPROVAL_REQUIRED',
                 'EXISTING_PRIVATE_ACCESS_REQUIRED', 'EXISTING_SECRET_INJECTION_REQUIRED',
                 'MAIN_FIRST_ATTEMPT_ONLY', 'ONCE_PER_KST_DAY', 'OTHER_FINITE_COLLECTION_ACTIVE',
                 'CONTROL_RESOURCE_NOT_FOUND', 'CONTROL_TRANSPORT_FAILURE_NO_RETRY'}
        reason = message if message in known or re.fullmatch(r'CONTROL_HTTP_[0-9]{3}_NO_RETRY', message) else 'UNCLASSIFIED'
        print(json.dumps(dict(status='HELD_NO_RETRY', stage=diag['stage'], reason=reason,
                              backtest_completed=False, financial_publication='HOLD')))
        raise SystemExit(2) from None
