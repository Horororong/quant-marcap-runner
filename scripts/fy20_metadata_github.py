"""Manual main-only FY20 adapter. Never prints raw or private identifiers."""
import argparse,base64,copy,gzip,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
from bounded_official_evidence import Stop,Deadline,atomic,private_root,raw,sha,stamp,day,check_history
from bounded_official_github import API,content,PRIVATE,PUBLIC,BRANCH,PREFIX,Missing,shared_history
from fy20_metadata_collection import APPROVAL,FYCollector,collect_metadata,validate_grant

def control_stage(stage,operation):
    try:return operation()
    except Stop as exc:
        match=re.fullmatch(r'CONTROL_HTTP_(\d{3})_NO_RETRY',str(exc))
        status=404 if isinstance(exc,Missing)else int(match[1])if match else None
        held=Stop('FY20_PRIVATE_CONTROL_STAGE_FAILED:'+stage)
        held.control_diagnostic=dict(stage=stage,http_status=status,retry_attempted=False)
        raise held from None

class FYJournal:
    """CAS extension of the existing private ledger. B/B2 bytes are preserved.

    No new storage destination, credential or public data channel is created.
    Paths and journal fingerprints are deliberately absent from public output.
    """
    def __init__(self,api,root):
        self.api=api;self.root=private_root(root)
        meta=api('GET','/repos/'+PRIVATE)
        if meta.get('full_name')!=PRIVATE or meta.get('private')is not True or not meta.get('permissions',{}).get('push'):
            raise Stop('FY20_EXISTING_PRIVATE_DESTINATION_REQUIRED')
        body,self.blob=content(api,PRIVATE,PREFIX+'budget.json',BRANCH)
        self.outer=json.loads(body);self.original=copy.deepcopy(self.outer)
        self.original.pop('additional_finite_grants',None)
        for value in self.outer.get('additional_finite_grants',{}).values():
            if not isinstance(value,dict)or not isinstance(value.get('executions'),list):
                raise Stop('FY20_SHARED_ADDITIONAL_HISTORY_INVALID')
        existing=self.outer.get('additional_finite_grants',{}).get(APPROVAL)
        local=self.root/'budget.json'
        if not existing:
            if local.exists():raise Stop('FY20_LOCAL_HISTORY_WITHOUT_REMOTE_NO_RESET')
            return
        if local.exists()and local.read_bytes()!=raw(existing):raise Stop('FY20_LOCAL_REMOTE_HISTORY_CONFLICT')
        atomic(local,existing)
        for r in existing['requests']:
            if not r.get('body_path'):continue
            if r['body_path']!='raw/'+r.get('sha256','')+'.bin':raise Stop('FY20_CACHE_PATH_NOT_CONTENT_BOUND')
            target=self.root/r['body_path']
            if target.exists():body=target.read_bytes()
            else:
                packed,_=content(api,PRIVATE,PREFIX+r['body_path']+'.gz',BRANCH);body=gzip.decompress(packed)
            if sha(body)!=r['sha256']:raise Stop('FY20_PRIVATE_CACHE_HASH_MISMATCH')
            if not target.exists():atomic(target,body,binary=True)
    def mirror(self,state,deadline):
        check=copy.deepcopy(self.outer);check.pop('additional_finite_grants',None)
        if check!=self.original:raise Stop('FY20_PRIOR_BUDGET_MUTATION_FORBIDDEN')
        self.outer.setdefault('additional_finite_grants',{})[APPROVAL]=copy.deepcopy(state)
        result=control_stage('JOURNAL_CAS_WRITE',lambda:self.api('PUT',f'/repos/{PRIVATE}/contents/{PREFIX}budget.json',
            dict(message='Private finite metadata accounting; no financial admission',branch=BRANCH,sha=self.blob,
                content=base64.b64encode(raw(self.outer)).decode())))
        self.blob=result['content']['sha']
    def preserve(self,location,body,deadline):
        if location!='raw/'+sha(body)+'.bin':raise Stop('FY20_PRIVATE_RAW_PATH_MISMATCH')
        path=PREFIX+location+'.gz'
        try:
            old,_=control_stage('RAW_EXISTING_READ',lambda:content(self.api,PRIVATE,path,BRANCH))
        except Stop as exc:
            # Only an observed 404 allows CREATE; no other denial is retried.
            if getattr(exc,'control_diagnostic',{}).get('http_status')!=404:raise
        else:
            if sha(gzip.decompress(old))!=sha(body):raise Stop('FY20_PRIVATE_RAW_CONFLICT')
            return
        packed=gzip.compress(body,mtime=0)
        control_stage('RAW_CREATE',lambda:self.api('PUT',f'/repos/{PRIVATE}/contents/{path}',
            dict(message='Private official metadata response',branch=BRANCH,content=base64.b64encode(packed).decode())))
        back,_=control_stage('RAW_READBACK',lambda:content(self.api,PRIVATE,path,BRANCH))
        if sha(gzip.decompress(back))!=sha(body):raise Stop('FY20_PRIVATE_READBACK_HASH_MISMATCH')

def complete_shared_history(public,private,now,run_id,journal):
    h=shared_history(public,now,run_id)
    h['executions'].extend(dict(day_kst=e['day_kst'],run_id=str(e.get('id','')))
        for e in journal.outer.get('executions',[]))
    for g in journal.outer.get('additional_finite_grants',{}).values():
        for e in g['executions']:
            if e.get('status')=='RUNNING':raise Stop('FY20_SHARED_RUNNING_LEASE_HELD')
            h['executions'].append(dict(day_kst=e['day_kst'],run_id=str(e.get('id',''))))
    for status in ('in_progress','queued','waiting','requested','pending'):
        runs=public('GET',f'/repos/{PUBLIC}/actions/runs?status={status}&per_page=100')
        if runs.get('total_count',0)>100:raise Stop('FY20_SHARED_RUN_PAGINATION_INCOMPLETE')
        h['active_source_runs'].extend(str(r['id'])for r in runs.get('workflow_runs',[])
            if str(r['id'])!=str(run_id)and r.get('path')=='.github/workflows/collect-fy20-asof-metadata.yml')
    h['observed_at']=stamp(now);check_history(h,now);return h

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--grant',required=True);parser.add_argument('--private-root',required=True)
    # Optional review is loaded from private storage, never a public workflow input.
    parser.add_argument('--use-private-correction-review',action='store_true');a=parser.parse_args()
    if (os.environ.get('GITHUB_REPOSITORY')!=PUBLIC or os.environ.get('GITHUB_REF')!='refs/heads/main'
        or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):raise Stop('FY20_REVIEWED_MAIN_FIRST_ATTEMPT_ONLY')
    if not all(os.environ.get(k)for k in ('GITHUB_TOKEN','DART_API_KEY','B_PRIVATE_BACKUP_TOKEN')):
        raise Stop('FY20_EXISTING_SECRET_NOT_INJECTED_NO_LEASE')
    g=json.loads(Path(a.grant).read_bytes());validate_grant(g);deadline=time.monotonic()+600
    public=API(os.environ['GITHUB_TOKEN'],deadline);private=API(os.environ['B_PRIVATE_BACKUP_TOKEN'],deadline)
    j=FYJournal(private,a.private_root)
    now=datetime.now(timezone.utc);h=complete_shared_history(public,private,now,os.environ['GITHUB_RUN_ID'],j)
    # Rehydration and all history checks consume the same 600-second window.
    corrections=None
    if a.use_private_correction_review:
        b,_=content(private,PRIVATE,PREFIX+'fy20-material-correction-review.json',BRANCH)
        review=json.loads(b)
        if review.get('approval_id')!=APPROVAL:raise Stop('FY20_PRIVATE_REVIEW_GRANT_MISMATCH')
        corrections=review['targets']
    c=None
    try:
        with FYCollector(a.private_root,g,h,source_ready=True,mirror=j.mirror,preserve=j.preserve)as c:
            c.deadline=deadline;c.started=deadline-600;out=collect_metadata(c,corrections)
    except Deadline:
        out=dict(status='PAUSED_AT_BOUNDED_CHECKPOINT',remaining=c.remaining()if c else None)
    except Stop:
        out=dict(status='HELD_NO_RETRY',remaining=c.remaining()if c else None)
        raise
    finally:
        if c:
            safe=dict(status=out['status']if'out'in locals()else'HELD_NO_RETRY',remaining=c.remaining(),
                HTTP_charged_this_run=sum(r['execution_id']==c.execution['id']for r in c.state['requests'])if c.execution else 0,
                transport_attempts_started=sum(r['execution_id']==c.execution['id']and r.get('transport_started',False)for r in c.state['requests'])if c.execution else 0,
                source_responses_this_run=sum(r['execution_id']==c.execution['id']and r['status']=='COMPLETE'for r in c.state['requests'])if c.execution else 0,
                source_collection_complete=False,new_PIT_values=0,new_provider_values=0,
                classification='RESEARCH_ONLY',financial_publication='HOLD',automatic_followup_dispatched=False)
            print(json.dumps(safe,ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except Stop as exc:
        # No arbitrary exception strings, body, headers, path or source digest.
        print(json.dumps(dict(status='BLOCKED_OR_HELD',reason=str(exc),new_PIT_values=0,
            new_provider_values=0,financial_publication='HOLD')));raise SystemExit(2)
    except Exception:
        print(json.dumps(dict(status='HELD_UNEXPECTED_ERROR_NO_RETRY',financial_publication='HOLD')))
        raise SystemExit(2)from None
