"""Prepared GitHub adapter. Not deployed; never discovers secret values.

Public repository: read ONLY. All raw responses and the B budget journal go
to the exact private backup repository. No artifact/release/public-raw path.
"""
import base64,gzip,json,os,time
from pathlib import Path
from urllib import request,error,parse
from datetime import datetime,timezone
from bounded_official_evidence import Stop,NoRedirect,raw,sha,atomic,private_root,stamp,day,check_history,validate_grant,Collector,run_inventory

PUBLIC='Horororong/quant-marcap-runner'
PRIVATE='Horororong/quant-private-backup'
BRANCH='research/b-official-evidence-20261028'
PREFIX='private-evidence/fixed-three-20261028/'
OLD_STATES=('data/status/dart_legacy_limited_resume_v1.json','data/status/dart_legacy_supplemental_41_v1.json','data/status/dart_q3_three_v1.json')
SOURCE_WORKFLOWS={'.github/workflows/backfill-dart-legacy-2000-2014.yml','.github/workflows/collect-b-official-evidence.yml'}

class Missing(Stop):pass
class API:
    def __init__(self,token,deadline):
        if not token:raise Stop('GITHUB_CONTROL_CREDENTIAL_NOT_CONFIGURED')
        self.token=token;self.deadline=deadline
    def __call__(self,method,path,body=None):
        if not path.startswith('/repos/')or '?'in path and 'access_token'in path:raise Stop('CONTROL_API_PATH_SCOPE')
        if method not in {'GET','POST','PUT'}:raise Stop('CONTROL_API_METHOD_SCOPE')
        if method!='GET'and not path.startswith('/repos/'+PRIVATE+'/'):raise Stop('PUBLIC_REPOSITORY_WRITE_FORBIDDEN')
        remaining=self.deadline-time.monotonic()
        if remaining<3:raise Stop('CONTROL_DEADLINE_NO_RETRY')
        req=request.Request('https://api.github.com'+path,method=method,data=raw(body)if body is not None else None,
            headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'})
        try:
            with request.build_opener(NoRedirect()).open(req,timeout=min(15,remaining-1))as resp:
                data=resp.read(64*1024*1024+1)
                if len(data)>64*1024*1024:raise Stop('CONTROL_RESPONSE_SIZE_LIMIT')
                return json.loads(data)
        except error.HTTPError as exc:
            if exc.code==404:raise Missing('CONTROL_RESOURCE_NOT_FOUND')from None
            raise Stop('CONTROL_HTTP_'+str(exc.code)+'_NO_RETRY')from None
        except Stop:raise
        except Exception:raise Stop('CONTROL_TRANSPORT_FAILURE_NO_RETRY')from None

def content(api,repo,path,ref):
    obj=api('GET',f'/repos/{repo}/contents/{parse.quote(path,safe="/")}?ref={parse.quote(ref,safe="")}')
    # GitHub Contents omits inline bytes for files over1MB. Use the exact
    # returned blob object, not a signed download URL or another source fetch.
    if obj.get('type')=='file'and obj.get('encoding')=='none'and obj.get('sha'):
        blob=api('GET',f'/repos/{repo}/git/blobs/{obj["sha"]}')
        if blob.get('sha')!=obj['sha']:raise Stop('CONTROL_BLOB_IDENTITY_MISMATCH')
        obj={**blob,'type':'file'}
    if obj.get('type')!='file'or obj.get('encoding')!='base64':raise Stop('INLINE_CONTROL_FILE_REQUIRED')
    return base64.b64decode(obj['content'],validate=False),obj['sha']

def shared_history(api,now,run_id):
    """Fail closed unless all three old approved finite channels are closed."""
    head=api('GET',f'/repos/{PUBLIC}/commits/main')['sha'];states=[];hashes={};executions=[]
    for path in OLD_STATES:
        b,_=content(api,PUBLIC,path,head);states.append(json.loads(b));hashes[path]=sha(b)
    old,supp,q3=states
    if (old.get('contract')!='limited-source-observation-v1'or supp.get('contract')!='supplemental-finite-source-v1'
            or q3.get('contract')!='q3-fixed-source-v1'
            or any(x.get('backtest_eligible')is not False or x.get('investment_PIT')!='0/6'for x in states)
            or old.get('automatic_financial_publication')!='HOLD'
            or any(x.get('financial_publication')!='HOLD'for x in [supp,q3])):
        raise Stop('EXISTING_SOURCE_GATE_CONTRACT_CHANGED')
    closed=(old.get('phase')=='OBSERVATION_COMPLETE'and supp.get('phase')=='COMPLETE'
            and supp.get('remaining_receipts')==[]and len(supp.get('attempts',[]))==2
            and all(a.get('status')=='COMPLETE'for a in supp['attempts'])
            and q3.get('phase')=='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW'and q3.get('executions_remaining')==0
            and q3.get('remaining_receipts')==[])
    # Flatten execution history, including resumed segments. Do not invent a
    # new opportunity from a calendar rollover or from a zero-HTTP failure.
    def visit(x):
        if isinstance(x,dict):
            if x.get('day_kst'):executions.append(dict(day_kst=x['day_kst'],run_id=str(x.get('run_id',x.get('id','')))))
            for v in x.values():visit(v)
        elif isinstance(x,list):
            for v in x:visit(v)
    for state in states:visit(state)
    active=[]
    for status in ('in_progress','queued','waiting','requested','pending'):
        runs=api('GET',f'/repos/{PUBLIC}/actions/runs?status={status}&per_page=100')
        if runs.get('total_count',0)>100:raise Stop('ACTIVE_RUN_PAGINATION_NOT_COMPLETE')
        active.extend(str(r['id'])for r in runs.get('workflow_runs',[])if str(r['id'])!=str(run_id)and r.get('path')in SOURCE_WORKFLOWS)
    out=dict(contract='fixed-three-shared-source-history-v1',observed_at=stamp(now),day_kst=day(now),main_sha=head,
             state_sha256=hashes,executions=executions,active_source_runs=active,old_authorized_channels_exhausted=closed)
    check_history(out,now);return out

class PrivateJournal:
    """CAS journal; durable charge before source HTTP, private readback after raw."""
    def __init__(self,api,root):
        self.api=api;self.root=private_root(root);self.state_sha=None
        meta=api('GET','/repos/'+PRIVATE)
        if meta.get('full_name')!=PRIVATE or meta.get('private')is not True:raise Stop('RAW_DESTINATION_NOT_EXACT_PRIVATE_REPOSITORY')
        if not meta.get('permissions',{}).get('push'):raise Stop('PRIVATE_REPOSITORY_WRITE_ACCESS_REQUIRED')
        try:api('GET',f'/repos/{PRIVATE}/git/ref/heads/{BRANCH}')
        except Missing:
            # New private branch only. Existing backup branches and main stay.
            ref=api('GET',f'/repos/{PRIVATE}/git/ref/heads/{meta["default_branch"]}')
            api('POST',f'/repos/{PRIVATE}/git/refs',dict(ref='refs/heads/'+BRANCH,sha=ref['object']['sha']))
        try:
            b,self.state_sha=content(api,PRIVATE,PREFIX+'budget.json',BRANCH)
        except Missing:
            if (self.root/'budget.json').exists():raise Stop('LOCAL_LEDGER_WITHOUT_REMOTE_COUNTERPART_NO_RESET')
            return
        state=json.loads(b)
        if (self.root/'budget.json').exists()and (self.root/'budget.json').read_bytes()!=b:
            raise Stop('LOCAL_REMOTE_LEDGER_DISAGREEMENT_NO_OVERWRITE')
        for row in state.get('requests',[]):
            if row.get('body_path'):
                name=row['body_path']
                if not name.startswith('raw/')or Path(name).name!=row.get('sha256','')+'.bin':raise Stop('PRIVATE_REMOTE_CACHE_PATH_NOT_HASH_BOUND')
                local=self.root/name
                if local.exists():
                    if sha(local.read_bytes())!=row['sha256']:raise Stop('PRIVATE_LOCAL_CACHE_CHANGED')
                    continue
                # A response whose raw preservation failed remains held. Never
                # silently call its source again to reconstruct missing bytes.
                packed,_=content(api,PRIVATE,PREFIX+name+'.gz',BRANCH)
                data=gzip.decompress(packed)
                if sha(data)!=row['sha256']:raise Stop('PRIVATE_REMOTE_RAW_HASH_MISMATCH')
                atomic(local,data,binary=True)
        atomic(self.root/'budget.json',state)
    def mirror(self,state,deadline):
        body=dict(message='B finite journal; no source or financial certification',content=base64.b64encode(raw(state)).decode(),branch=BRANCH)
        if self.state_sha:body['sha']=self.state_sha
        result=self.api('PUT',f'/repos/{PRIVATE}/contents/{PREFIX}budget.json',body)
        self.state_sha=result['content']['sha']
    def preserve(self,location,data,deadline):
        expected='raw/'+sha(data)+'.bin'
        if location!=expected:raise Stop('PRIVATE_RAW_PATH_NOT_CONTENT_ADDRESSED')
        path=PREFIX+location+'.gz';packed=gzip.compress(data,mtime=0)
        try:
            existing,_=content(self.api,PRIVATE,path,BRANCH)
            if sha(gzip.decompress(existing))!=sha(data):raise Stop('EXISTING_PRIVATE_RAW_CONFLICT')
            return
        except Missing:pass
        self.api('PUT',f'/repos/{PRIVATE}/contents/{path}',dict(message='B official evidence; PRIVATE raw',content=base64.b64encode(packed).decode(),branch=BRANCH))
        downloaded,_=content(self.api,PRIVATE,path,BRANCH)
        if sha(gzip.decompress(downloaded))!=sha(data):raise Stop('PRIVATE_RAW_READBACK_HASH_MISMATCH')

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--private-root',required=True);parser.add_argument('--grant',required=True);parser.add_argument('--b2-amendment')
    args=parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY')!=PUBLIC or os.environ.get('GITHUB_REF')!='refs/heads/main'or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':
        raise Stop('REVIEWED_MAIN_FIRST_ATTEMPT_ONLY')
    missing=[k for k in ('DART_API_KEY','KRX_AUTH_KEY','B_PRIVATE_BACKUP_TOKEN','GITHUB_TOKEN')if not os.environ.get(k)]
    if missing:
        # Names only. This is not an authentication probe or source request.
        raise Stop('REQUIRED_ACTIONS_SECRET_NOT_INJECTED_NO_LEASE:'+','.join(missing))
    deadline=time.monotonic()+600
    pub=API(os.environ['GITHUB_TOKEN'],deadline);priv=API(os.environ['B_PRIVATE_BACKUP_TOKEN'],deadline)
    now=datetime.now(timezone.utc);history=shared_history(pub,now,os.environ['GITHUB_RUN_ID'])
    grant=json.loads(Path(args.grant).read_bytes())
    validate_grant(grant)
    journal=PrivateJournal(priv,args.private_root)
    if args.b2_amendment:
        from b2_official_execution import B2Collector,run_b2
        amendment=json.loads(Path(args.b2_amendment).read_bytes())
        # The retained official form is PRIVATE evidence, never a new public
        # source-data dependency. Read exact bytes without a source request.
        packed,_=content(priv,PRIVATE,PREFIX+'raw/'+amendment['form_sha256']+'.bin.gz',BRANCH)
        form_body=gzip.decompress(packed)
        if sha(form_body)!=amendment['form_sha256']:raise Stop('PRIVATE_RETAINED_FORM_HASH_MISMATCH')
        try:
            with B2Collector(args.private_root,grant,history,source_ready=True,mirror=journal.mirror,preserve=journal.preserve,
                             amendment=amendment,form_body=form_body)as c:
                c.deadline=deadline;c.started=deadline-600;out=run_b2(c)
            # Full outcome and inventory hashes stay PRIVATE; public summary
            # contains status/counters only, no private paths or source bytes.
            safe=dict(status=out['status'],source_collection_complete=False,source_HTTP_this_run=out['source_HTTP_this_run'],
                      remaining=out['remaining'],new_financial_values=0,financial_eligible=False,
                      classification='RESEARCH_ONLY',financial_publication='HOLD')
        except __import__('bounded_official_evidence').Deadline:
            safe=dict(status='STOPPED_TIME',source_collection_complete=False,financial_eligible=False,
                      classification='RESEARCH_ONLY',financial_publication='HOLD',remaining=c.remaining())
        print(json.dumps(safe,ensure_ascii=False));return
    # This first operational draft only performs the fixed initial inventory.
    # KIND criteria/pagination must be derived from its returned official form;
    # no guessed form, incomplete inventory freeze, or conditional HTTP occurs.
    with Collector(args.private_root,grant,history,source_ready=True,mirror=journal.mirror,preserve=journal.preserve)as c:
        c.deadline=deadline;out=run_inventory(c)
    print(json.dumps(dict(**out,classification='RESEARCH_ONLY',raw_destination='PRIVATE_REPOSITORY',financial_publication='HOLD'),ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Stop as exc:
        print(json.dumps(dict(status='BLOCKED_OR_HELD',reason=str(exc),source_collection_complete=False,financial_publication='HOLD')))
        raise SystemExit(2)
