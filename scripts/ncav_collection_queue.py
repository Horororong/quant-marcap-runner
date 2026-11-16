"""Private finite queue. HTTP transport and shared KST lease are injected.

No production CLI/network dispatch is exposed before an approved operational
adapter connects the actual shared ledger, credentials and private destination.
"""
import fcntl,hashlib,json,os,time,uuid
from pathlib import Path
from datetime import datetime,timezone
TERMINAL={'STORED','NO_DATA','NO_PAIR','FAILED','UNKNOWN'}
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(value,sort_keys=True,indent=2));os.chmod(t,0o600);os.replace(t,p)
def key(task):
    if task['endpoint']=='official':
        return 'official:'+fingerprint({k:task['request'][k]for k in ['method','url','params']})
    if task['endpoint']=='document.xml':return 'document:'+task['receipt']
    if task['endpoint']!='fnlttSinglAcntAll.json':raise ValueError('Endpoint outside fixed NCAV scope')
    return ':'.join(str(task[x])for x in ['corp_code','bsns_year','reprt_code','fs_div'])
def run(plan,destination,*,approved,transport,acquire_shared_day,seconds=600,max_http=0,now=None,clock=time.monotonic,mirror=None,preserve=None,reviewed_tasks=()):
    if approved is not True:raise PermissionError('NCAV collection is not approved')
    now=now or datetime.now(timezone.utc);now=now.astimezone(timezone.utc)
    if not datetime.fromisoformat(plan['valid_from'])<=now<=datetime.fromisoformat(plan['valid_until']):raise PermissionError('Outside approved window')
    if not 0<seconds<=600 or not 0<max_http<=plan['max_http']:raise ValueError('Invalid per-run budget')
    d=Path(destination);d.mkdir(parents=True,exist_ok=True);os.chmod(d,0o700)
    with(d/'.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        p=d/'ledger.json';state=json.loads(p.read_text())if p.exists()else dict(plan_hash=fingerprint(plan),used_http=0,runs=[],tasks={})
        def checkpoint():
            save(p,state)
            # Remote durable charge must succeed BEFORE any source request.
            # A CAS failure propagates; never re-read and overwrite another writer.
            if mirror is not None:mirror(state)
        if state['plan_hash']!=fingerprint(plan):raise ValueError('Scope changed; do not reset ledger')
        if len(state['runs'])>=plan['max_runs']:raise PermissionError('Execution budget exhausted')
        tasks={}
        if len(reviewed_tasks)>plan.get('max_reviewed_followups',0):raise ValueError('Followup task cap')
        for task in [*plan['tasks'],*reviewed_tasks]:
            k=key(task)
            if k in tasks and tasks[k]!=task:raise ValueError('Contradictory duplicate target')
            tasks[k]=task
        previous=state.setdefault('resolved_tasks',{})
        for k,h in previous.items():
            if k not in tasks or fingerprint(tasks[k])!=h:raise ValueError('Previously frozen request changed or disappeared')
        previous.update({k:fingerprint(t)for k,t in tasks.items()})
        # Interrupted requests have unknown external side effects. Never resend.
        for k,row in state['tasks'].items():
            if row['status']=='SENDING':row['status']='UNKNOWN'
        for row in state['tasks'].values():
            if row.get('response_file'):
                raw=d/row['response_file']
                if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Saved response missing/changed; no automatic refetch')
        # Conditional OFS for a previously incomplete CFS needs a source-bound
        # offline primary review, not merely a missing-account guess.
        for task in tasks.values():
            receipt=task.get('review_gate_receipt')
            if not receipt:continue
            review=d/'reviews'/(receipt+'.json');source=state['tasks'].get('document:'+receipt,{})
            if not review.exists():continue
            decision=json.loads(review.read_text())
            if source.get('status')!='STORED' or decision.get('document_sha256')!=source.get('sha256'):raise ValueError('Primary review is not source-bound')
            if decision.get('corp_code')!=task['corp_code'] or decision.get('bsns_year')!=task['bsns_year'] or decision.get('reprt_code')!=task['reprt_code']:raise ValueError('Primary review period mismatch')
            if decision.get('status')=='CFS_UNUSABLE_OFS_NOT_CACHED':
                state['tasks'][task['depends_on']]=dict(status='NO_PAIR',source='offline_review',review_sha256=hashlib.sha256(review.read_bytes()).hexdigest())
        pending=[(k,t)for k,t in tasks.items()if k not in state['tasks']]
        def page_ready(t):
            if not t.get('page_parent'):return True
            parent=state['tasks'].get(t['page_parent'],{})
            return parent.get('status')=='STORED' and parent.get('metadata',{}).get('total_pages',0)>=int(t['request']['params']['page_no'])
        eligible=[]
        for k,t in pending:
            if not page_ready(t):continue
            if t.get('depends_on'):
                parent=state['tasks'].get(t['depends_on'])
                if not parent:continue
                if parent['status']not in {'NO_DATA','NO_PAIR'}:continue
            eligible.append((k,t))
        if not eligible:
            checkpoint();return dict(status='NO_COLLECTION',http=0,reason='No eligible unprocessed tasks')
        if state['used_http']>=plan['max_http']:raise PermissionError('HTTP budget exhausted')
        # Must be the real global lease in deployment; local tests use a fake.
        acquire_shared_day(plan['grant_id'],now)
        rid=uuid.uuid4().hex;runrow=dict(id=rid,day=now.isoformat(),http=0,status='STARTED');state['runs'].append(runrow);checkpoint()
        start=clock()
        for k,t in pending:
            if clock()-start>=seconds-30:runrow['status']='CHECKPOINT_TIME';break
            if runrow['http']>=max_http or state['used_http']>=plan['max_http']:runrow['status']='CHECKPOINT_HTTP';break
            if t.get('depends_on') and state['tasks'].get(t['depends_on'],{}).get('status')not in {'NO_DATA','NO_PAIR'}:continue
            if not page_ready(t):continue
            state['tasks'][k]=dict(status='SENDING',run_id=rid);state['used_http']+=1;runrow['http']+=1;checkpoint()
            try:
                # Single attempt. No tokens/URLs/auth headers in persisted errors.
                result=transport(t)
                if result['status']not in {'STORED','NO_DATA','NO_PAIR'}:raise ValueError('Rejected source response')
                body=result['body'];name=hashlib.sha256(k.encode()).hexdigest()+'.bin'
                raw=d/'responses'/name;raw.parent.mkdir(exist_ok=True);tmp=raw.with_suffix('.tmp');tmp.write_bytes(body);os.chmod(tmp,0o600);os.replace(tmp,raw)
                if preserve is not None:preserve(body)
                state['tasks'][k]=dict(status=result['status'],run_id=rid,response_file='responses/'+name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),metadata=result.get('metadata',{}))
            except Exception as exc:
                state['tasks'][k]=dict(status='FAILED',run_id=rid,error_class=type(exc).__name__)
                if isinstance(getattr(exc,'code',None),int):state['tasks'][k]['http_status']=exc.code
                runrow['status']='STOP_FAILURE';checkpoint();break
            checkpoint()
        else:runrow['status']='NORMAL_EXIT'
        runrow['remaining_unrequested']=sum(k not in state['tasks']for k in tasks);checkpoint()
        return dict(status=runrow['status'],http=runrow['http'],total_http=state['used_http'],remaining_unrequested=runrow['remaining_unrequested'])

def classify_response(task,body):
    """HTTP200 alone is never data success; raw bytes stay in private storage."""
    if task['endpoint']=='document.xml':
        import zipfile,io
        with zipfile.ZipFile(io.BytesIO(body))as archive:
            if archive.testzip()or not any(n.lower().endswith(('.xml','.html'))for n in archive.namelist()):raise ValueError('Invalid document ZIP')
        return dict(status='STORED',body=body)
    import pandas as pd
    from ncav_coverage import financial_pairs
    obj=json.loads(body)
    if obj.get('status')=='013':return dict(status='NO_DATA',body=body)
    if obj.get('status')!='000' or not obj.get('list'):raise ValueError('DART API error or empty success')
    rows=obj['list']
    if any(str(r.get('corp_code'))!=task['corp_code']or str(r.get('bsns_year'))!=task['bsns_year']or str(r.get('reprt_code'))!=task['reprt_code']for r in rows):raise ValueError('Wrong issuer/period response')
    data=pd.DataFrame(rows);data['_fs_div_requested']=task['fs_div']
    pairs=financial_pairs(data)
    return dict(status='STORED'if any(r['status']=='paired'for r in pairs)else'NO_PAIR',body=body)
