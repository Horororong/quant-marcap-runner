"""Three finite source-only observations, leased before HTTP; never publishes metrics.

Terminal unsupported documents are durably isolated, not global quality failures.
Service/worker/schema/hash/lease failures stop the observation. A failed final
commit leaves a RUNNING lease, so no later schedule can silently resume.
"""
import argparse,base64,csv,gzip,hashlib,io,json,os,re,sys,zipfile
from collections import Counter
from datetime import datetime,timedelta,timezone,date
from decimal import Decimal
from pathlib import Path
from urllib import request,error
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.financial_rollout import atomic,read_csv,run_batch,select_new,TERMINAL
from scripts.financial_validation_batch import review_selection
CONFIG=Path('config/financial_limited_resume_v1.json')
STATE=Path('data/status/dart_legacy_limited_resume_v1.json')
BASE=Path('data/financials/legacy_2000_2014/quality_v9/limited_resume_v1')
INDEX=Path('data/financials/legacy_2000_2014/legacy_filings.csv.gz')
OLD=Path('data/status/dart_legacy_backfill_state.csv')
CONTRACT='limited-source-observation-v1'
SEED='limited-source-observation-20261019-v1'
UTC=timezone.utc;KST=timezone(timedelta(hours=9))
def sha(b):return hashlib.sha256(b).hexdigest()
def git_blob_sha(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def raw(o):return (json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def stamp():return datetime.now(UTC).isoformat()
def local_day(now):return now.astimezone(KST).date().isoformat()
def initial():return dict(contract=CONTRACT,phase='READY_FIRST',last_checkpoint='20100331001757',runs=[],completed_receipts=[],automatic_financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',first_review=None)
def check_gate(config,state,now,event):
    if config['contract']!=CONTRACT or config['mode']!='LIMITED_OBSERVATION':raise ValueError('LIMITED_GATE_CLOSED')
    if config['max_documents_per_run']!=100 or config['max_runs']!=3 or config['max_total_documents']!=300 or config['document_seconds']!=90 or config['run_seconds']!=600:raise ValueError('LIMIT_CONTRACT_CHANGED')
    if config['automatic_financial_publication']!='HOLD' or config['backtest_eligible']is not False:raise ValueError('PUBLICATION_OR_INVESTMENT_GATE')
    if state['contract']!=CONTRACT or state['phase']not in {'READY_FIRST','READY_NEXT'}:raise ValueError('OBSERVATION_STOPPED_OR_UNREVIEWED')
    if len(state['runs'])>=3 or sum(r['reserved_documents']for r in state['runs'])>=300:raise ValueError('AUTHORIZED_OBSERVATION_EXHAUSTED')
    if any(r['day_kst']==local_day(now)for r in state['runs']):raise ValueError('ONCE_PER_KST_DAY')
    if state['runs']:
        if (state.get('first_review')or{}).get('status')!='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION':raise ValueError('FIRST_ACTUAL_REVIEW_REQUIRED')
    elif event!='first-approved-push':raise ValueError('FIRST_RUN_REQUIRES_APPROVED_PUSH')
    if now>datetime.fromisoformat(config['expires_at_utc']):raise ValueError('OBSERVATION_WINDOW_EXPIRED')
def freeze(root,state,run_id):
    index=read_csv(root/INDEX);old=read_csv(root/OLD)
    previous=[json.loads(p.read_text())for p in sorted((root/'data/financials/legacy_2000_2014/quality_v9/collection').glob('*.json'))]
    previous.extend(dict(rcept_no=r,source_status='DURABLE')for r in state['completed_receipts'])
    samples=select_new(index,old,previous,100)
    if not samples or any(s['rcept_no']<=state['last_checkpoint']for s in samples):raise ValueError('CHECKPOINT_QUEUE_MISMATCH')
    if len({s['rcept_no']for s in samples})!=len(samples):raise ValueError('DUPLICATE_QUEUE')
    receipts=[s['rcept_no']for s in samples]
    return dict(contract=CONTRACT,run_id=run_id,seed=SEED,start_checkpoint=state['last_checkpoint'],samples=samples,selection_sha256=sha(raw(samples)),input_sha256={str(p):sha((root/p).read_bytes())for p in [INDEX,OLD]},primary_review=sorted(receipts,key=lambda r:sha((SEED+'|'+r).encode()))[:20],independent_review_rule='First20 hash-ranked receipts before HTTP; add first2 of every result class and at least10 extracted (all if<=20). Raw cells/semantic controls precede reading candidate amounts.',publication='ALL_NEW_CANDIDATES_HELD',before_HTTP=True)
def validate_result(meta,result,out):
    from scripts.legacy_native_financials import PARSER_VERSION
    from scripts.legacy_document_quality import DIAGNOSTIC_VERSION
    receipt=meta['rcept_no'];state=result['state'];status=state['status'];rows=result['rows']
    if state['rcept_no']!=receipt or result['parser_version']!=PARSER_VERSION:raise ValueError('COMMON_IDENTITY_OR_VERSION_FAILURE')
    if status in {'ERROR','DEFERRED','RATE_LIMIT'}:
        if rows:raise ValueError('SERVICE_FAILURE_WITH_CANDIDATES')
        return
    if status not in TERMINAL:raise ValueError('UNKNOWN_EXTRACTION_STATE')
    if status=='NO_DOCUMENT':
        if rows:raise ValueError('API014_WITH_VALUES')
        return
    archives=list((out/'native').glob(receipt+'-*.zip'))
    if len(archives)!=1 or sha(archives[0].read_bytes())!=state['document_sha256']:raise ValueError('COMMON_SOURCE_HASH_FAILURE')
    if status in {'SOURCE_GAP','NO_METRICS','EXTRACTION_FAILED','UNVERIFIED_FINANCIALS'}and rows:raise ValueError('ISOLATED_SOURCE_HAS_VALUES')
    with zipfile.ZipFile(archives[0])as z:
        if z.testzip()is not None:raise ValueError('COMMON_SOURCE_CRC_FAILURE')
        for r in rows:
            if r['rcept_no']!=receipt or r['corp_code']!=str(meta['corp_code'])or r['document_sha256']!=state['document_sha256']or r['source_member_sha256']!=sha(z.read(r['source_member'])):raise ValueError('COMMON_ROW_SOURCE_FAILURE')
            if r['parser_version']!=PARSER_VERSION or r['source_diagnostic_version']!=DIAGNOSTIC_VERSION or r['backtest_eligible']is not False or r['availability_status']!='UNVERIFIED':raise ValueError('COMMON_QUALITY_PROMOTION')
            if r['scope']not in {'CFS','OFS'}or r['statement']not in {'BS','IS','CF'}or not Decimal(str(r['amount_krw'])).is_finite()or Decimal(str(r['unit_multiplier']))<=0:raise ValueError('COMMON_NUMERIC_SCHEMA_FAILURE')
            end=date.fromisoformat(r['period_end']);start=r['period_start']
            if start and date.fromisoformat(start)>end:raise ValueError('COMMON_PERIOD_FAILURE')
            if r['structural_status']!='PASS'or r['unit_known']is not True or not r['raw_amount']:raise ValueError('COMMON_SOURCE_CONTRACT_FAILURE')
def summarize(folder,plan):
    status=json.loads((folder/'run_status.json').read_text());collections=[];qualities=[];held=[]
    for p in sorted((folder/'collection').glob('*.json')):
        c=json.loads(p.read_text());q=json.loads((folder/'quality'/p.name).read_text());collections.append(c);qualities.append(q)
        if q['extraction_state']not in {'PARSED_4F','PARSED_PARTIAL'}:held.append(dict(receipt=c['rcept_no'],scope='DOCUMENT',reason=q['extraction_state'],source_status=c['source_status'],evidence=c['archives'],detail=q['rejection_reason']))
    durable=[c['rcept_no']for c,q in zip(collections,qualities)if c['source_status']in {'DURABLE','API014'}and q['extraction_state']in TERMINAL]
    counts=dict(Counter(q['extraction_state']for q in qualities))
    status_by={q['rcept_no']:q for q in qualities}
    chosen=set(plan['primary_review'])
    ranked=lambda rs:sorted(rs,key=lambda r:sha((SEED+'|'+r).encode()))
    extracted=ranked([r for r,q in status_by.items()if q['field_count']>0]);chosen.update(extracted if len(extracted)<=20 else extracted[:10])
    for st in counts:chosen.update(ranked([r for r,q in status_by.items()if q['extraction_state']==st])[:2])
    result=dict(contract=CONTRACT,run_status=status,collection=collections,quality=qualities,quarantine=held,counts=counts,processed_results=len(qualities),durable_terminal_documents=len(durable),completed_receipts=durable,extracted_documents=len(extracted),candidate_fields=sum(q['field_count']for q in qualities),independently_verified_fields=0,published_financial_fields=0,review_selection=[s['rcept_no']for s in plan['samples']if s['rcept_no']in chosen],review_rule=plan['independent_review_rule'],source_absence_certification='UNVERIFIED',automatic_financial_publication='HOLD',backtest_eligible=False)
    atomic(folder/'limited_summary.json',result);return result
class GitHub:
    def __init__(self):
        self.base='https://api.github.com/repos/Horororong/quant-marcap-runner';self.token=os.environ['GH_TOKEN']
    def call(self,path,method='GET',body=None):
        b=json.dumps(body).encode()if body is not None else None
        req=request.Request(self.base+path,data=b,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
        try:
            with request.urlopen(req,timeout=60)as r:return json.load(r)
        except error.HTTPError as e:raise RuntimeError('GITHUB_HTTP_'+str(e.code))from None
    def head(self):return self.call('/git/ref/heads/main')['object']['sha']
    def content(self,path,revision):
        try:o=self.call('/contents/'+str(path)+'?ref='+revision)
        except RuntimeError as e:
            if str(e)=='GITHUB_HTTP_404':return None
            raise
        return base64.b64decode(o['content'])
    def commit(self,files,expected_state,root,message):
        # One bounded CAS-race recovery, never a repeated HTTP failure. Preserve
        # unrelated recent-DART commits by basing each tree on freshly read main.
        guards=[CONFIG,INDEX,OLD,Path('scripts/financial_rollout.py'),Path('scripts/financial_limited_resume.py'),Path('scripts/legacy_native_financials.py'),Path('scripts/legacy_document_quality.py')]
        for race in range(2):
            parent=self.head();current=self.content(STATE,parent)
            if current!=expected_state:raise ValueError('LEASE_OR_CHECKPOINT_CHANGED')
            parent_tree=self.call('/git/commits/'+parent)['tree']['sha']
            entries={x['path']:x['sha']for x in self.call('/git/trees/'+parent_tree+'?recursive=1')['tree']}
            for p in guards:
                if entries.get(str(p))!=git_blob_sha((root/p).read_bytes()):raise ValueError('RUN_INPUT_CHANGED:'+str(p))
            elements=[dict(path=str(p),mode='100644',type='blob',**(b if isinstance(b,dict)else dict(content=b.decode())))for p,b in files.items()]
            tree=self.call('/git/trees','POST',dict(base_tree=parent_tree,tree=elements))
            commit=self.call('/git/commits','POST',dict(message=message,tree=tree['sha'],parents=[parent]))['sha']
            try:self.call('/git/refs/heads/main','PATCH',dict(sha=commit,force=False))
            except RuntimeError as e:
                actual=self.head()
                if actual==commit:return commit
                if str(e)in {'GITHUB_HTTP_409','GITHUB_HTTP_422'}and race==0:continue
                raise
            if self.head()!=commit:raise ValueError('POST_COMMIT_HEAD_MOVED_REVIEW_REQUIRED')
            for p,b in files.items():
                if isinstance(b,dict):
                    if self.call('/contents/'+str(p)+'?ref='+commit)['sha']!=b['sha']:raise ValueError('POST_COMMIT_SOURCE_BLOB_FAILURE')
                elif self.content(p,commit)!=b:raise ValueError('POST_COMMIT_READBACK_FAILURE')
            return commit
        raise ValueError('CONCURRENT_MAIN_CHANGED_TWICE')
def run(root,out,event):
    if os.getenv('GITHUB_REF')!='refs/heads/main'or os.getenv('GITHUB_RUN_ATTEMPT','1')!='1':raise ValueError('MAIN_FIRST_ATTEMPT_ONLY')
    api=GitHub();head=api.head();current=api.content(STATE,head)
    state=json.loads(current)if current else initial();config=json.loads((root/CONFIG).read_text());now=datetime.now(UTC)
    try:check_gate(config,state,now,event)
    except ValueError as e:
        out.mkdir(parents=True,exist_ok=False);atomic(out/'gate.json',dict(status='NO_COLLECTION',reason=str(e),observed_head=head,observed_state=state));print(json.dumps(dict(status='NO_COLLECTION',reason=str(e))));return 0
    run_id=os.environ['GITHUB_RUN_ID']
    try:plan=freeze(root,state,run_id)
    except ValueError as exc:
        state.update(phase='HOLD_PRECHECK_FAILURE',precheck_error=str(exc),failed_run_id=run_id)
        out.mkdir(parents=True,exist_ok=False);atomic(out/'gate.json',state)
        api.commit({STATE:raw(state)},current,root,'Hold finite source observation after queue/checkpoint precheck failure [skip ci]')
        raise
    out.mkdir(parents=True,exist_ok=False);atomic(out/'batch_plan.json',plan)
    slot=dict(run_id=run_id,day_kst=local_day(now),started_at_utc=stamp(),reserved_documents=len(plan['samples']),status='RUNNING',selection_sha256=plan['selection_sha256'],start_checkpoint=state['last_checkpoint'])
    state['runs'].append(slot);state['phase']='RUNNING';reserved=raw(state)
    reservation=api.commit({STATE:reserved,BASE/'runs'/run_id/'selection.json':raw(plan)},current,root,'Reserve bounded source observation '+run_id+' [skip ci]')
    atomic(out/'reservation.json',dict(commit=reservation,state_sha256=sha(reserved)))
    batch=out/'batch';code=1;failure=''
    try:code=run_batch(plan['samples'],batch,result_validator=validate_result)
    except Exception as e:failure=type(e).__name__+':'+str(e) if isinstance(e,ValueError)else type(e).__name__
    if not(batch/'run_status.json').exists():raise ValueError('NO_BATCH_CHECKPOINT_LEASE_STAYS_RUNNING')
    summary=summarize(batch,plan);atomic(out/'summary.json',summary)
    # Reuse the bounded public-source blob transfer; up to100 documents can
    # exceed its old2/20-document bound, so make fixed chunks <=20 without HTTP.
    from scripts.financial_rollout_transfer import main as transfer
    transfers=[]
    for i in range(0,len(plan['samples']),20):
        folder=out/f'preserved{i//20:02d}';folder.mkdir();subset={s['rcept_no']for s in plan['samples'][i:i+20]}
        for base in ['native','results','collection','quality']:
            for p in (batch/base).glob('*'):
                if any(p.name.startswith(r)for r in subset):
                    dest=folder/base/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
        atomic(folder/'selection.json',dict(samples=[s for s in plan['samples']if s['rcept_no']in subset]))
        atomic(folder/'run_status.json',summary['run_status']);transfer(folder);transfers.append(json.loads((folder/'transfer.json').read_text()))
    slot.update(status='COMPLETE'if code==0 else'STOPPED',completed_at_utc=stamp(),durable_documents=summary['durable_terminal_documents'],counts=summary['counts'],candidate_fields=summary['candidate_fields'],reservation_commit=reservation,transfers=transfers,stop_reason=failure or summary['run_status']['stop_reason'])
    state['completed_receipts'].extend(summary['completed_receipts'])
    ordered=[s['rcept_no']for s in plan['samples']if s['rcept_no']in set(summary['completed_receipts'])]
    if ordered:state['last_checkpoint']=ordered[-1]
    state['phase']='WAIT_FIRST_REVIEW'if code==0 and len(state['runs'])==1 else('READY_NEXT'if code==0 and len(state['runs'])<3 else'OBSERVATION_COMPLETE'if code==0 else'HOLD_FAILURE')
    if len(state['completed_receipts'])!=len(set(state['completed_receipts'])):raise ValueError('DUPLICATE_DURABLE_RECEIPTS')
    manifest=dict(summary=summary,transfers=transfers,plan_sha256=sha(raw(plan)),financial_publication='HOLD',code_sha=os.environ['GITHUB_SHA'])
    output_files={STATE:raw(state),BASE/'runs'/run_id/'manifest.json':raw(manifest)}
    output_files.update({BASE/'runs'/run_id/f'sources{i:02d}.json.gz.b64':dict(sha=t['blob_sha'])for i,t in enumerate(transfers)})
    final=api.commit(output_files,reserved,root,'Preserve bounded source candidates '+run_id+'; financial publication HOLD [skip ci]')
    atomic(out/'final_commit.json',dict(sha=final,phase=state['phase'],last_checkpoint=state['last_checkpoint'],source_preserved=True,financial_fields_published=0))
    print(json.dumps(dict(status=state['phase'],commit=final,processed=summary['processed_results'],durable=summary['durable_terminal_documents'],counts=summary['counts'],candidate_fields=summary['candidate_fields'],financial_fields_published=0)))
    return code
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--event',choices=['first-approved-push','schedule'],required=True);a=p.parse_args();raise SystemExit(run(ROOT,a.output,a.event))
