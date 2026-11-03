"""Proposed manual main-only adapter; data and accounting stay private."""
import argparse,json,os,time,gzip,re
from pathlib import Path
from datetime import datetime,timezone
from bounded_official_evidence import Stop,Deadline,DataUnavailable,request_id,sha
from bounded_official_github import API,content,PRIVATE,PUBLIC,PREFIX,BRANCH
from fy20_metadata_github import FYJournal,complete_shared_history
from fy20_completion_collection import CompletionCollector,collect_queue,validate_plan

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-grant',required=True);p.add_argument('--amendment',required=True);p.add_argument('--private-root',required=True);a=p.parse_args()
    if(os.environ.get('GITHUB_REPOSITORY')!=PUBLIC or os.environ.get('GITHUB_REF')!='refs/heads/main'or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):
        raise Stop('REVIEWED_MAIN_FIRST_ATTEMPT_ONLY')
    if not all(os.environ.get(k)for k in ['GITHUB_TOKEN','B_PRIVATE_BACKUP_TOKEN','DART_API_KEY','KRX_AUTH_KEY']):raise Stop('EXISTING_COLLECTION_SECRETS_REQUIRED_NO_LEASE')
    deadline=time.monotonic()+600;public=API(os.environ['GITHUB_TOKEN'],deadline);private=API(os.environ['B_PRIVATE_BACKUP_TOKEN'],deadline)
    amendment=json.loads(Path(a.amendment).read_bytes());base=json.loads(Path(a.base_grant).read_bytes())
    # No queue may be installed until the user explicitly approves continuation.
    data,_=content(private,PRIVATE,PREFIX+'fy20-completion-reviewed-queue.json',BRANCH);plan=json.loads(data);validate_plan(amendment,plan)
    ids={request_id(s)for s in plan['targets']}|{key for s in plan['targets']for key in s.get('parent_ids',[])}
    journal=FYJournal(private,a.private_root,rehydrate_ids=ids)
    now=datetime.now(timezone.utc);history=complete_shared_history(public,private,now,os.environ['GITHUB_RUN_ID'],journal)
    for status in ['in_progress','queued','waiting','requested','pending']:
        runs=public('GET',f'/repos/{PUBLIC}/actions/runs?status={status}&per_page=100')
        if runs.get('total_count',0)>100:raise Stop('ACTIVE_RUN_PAGINATION_INCOMPLETE')
        if any(str(r['id'])!=os.environ['GITHUB_RUN_ID']and r.get('path')=='.github/workflows/collect-fy20-completion.yml'for r in runs.get('workflow_runs',[])):raise Stop('CONTINUATION_RUN_ALREADY_ACTIVE')
    # Same PRIVATE retained form as the existing B2 adapter. No new official
    # request, public HTML dependency or publication of its private identifier.
    form_hash=plan.get('retained_form_sha256','')
    if not re.fullmatch('[0-9a-f]{64}',form_hash):raise Stop('RETAINED_PRIVATE_FORM_BINDING_REQUIRED')
    packed,_=content(private,PRIVATE,PREFIX+'raw/'+form_hash+'.bin.gz',BRANCH)
    form=gzip.decompress(packed)
    if sha(form)!=form_hash:raise Stop('RETAINED_PRIVATE_FORM_HASH_MISMATCH')
    c=None
    try:
        with CompletionCollector(a.private_root,base,history,amendment,plan,form,source_ready=True,mirror=journal.mirror,preserve=journal.preserve)as c:
            c.deadline=deadline;c.started=deadline-600;out=collect_queue(c)
    except Deadline:out=dict(status='PAUSED_BEFORE_DEADLINE_NO_RETRY',backtest_completed=False)
    except Stop:
        out=dict(status='HELD_NO_RETRY',backtest_completed=False);raise
    finally:
        if c:
            print(json.dumps(dict(status=out['status']if'out'in locals()else'HELD_NO_RETRY',
                HTTP_this_run=sum(r['execution_id']==c.execution['id']for r in c.state['requests'])if c.execution else 0,
                total_HTTP_used=len(c.state['requests']),remaining_HTTP=70-len(c.state['requests']),
                total_executions_used=len(c.state['executions']),remaining_new_executions=4-len(c.state['executions']),
                new_financial_values_admitted=0,backtest_completed=False,financial_publication='HOLD',automatic_followup=False)))
if __name__=='__main__':main()
