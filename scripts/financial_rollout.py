"""Bounded shadow/operational candidate collection, with NO automatic publication.

Historical v5 files are immutable here. Source collection durability and parser
quality are separate checkpoints. A new parser cannot requeue old classifications.
Each document is processed by the common collector in a killable subprocess.
"""
import argparse
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import ctypes
import fcntl
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
QUALITY_VERSION='financial-quality-v1-source-linked-not-PIT'
TERMINAL={'PARSED_4F','PARSED_PARTIAL','NO_METRICS','NO_DOCUMENT','SOURCE_GAP','EXTRACTION_FAILED','UNVERIFIED_FINANCIALS'}
def now(): return datetime.now(timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.pending')
    with tmp.open('w') as f:
        f.write(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read_csv(path):
    import gzip
    if not path.exists(): return []
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def select_new(index,old_states,collection,limit):
    if not 1<=limit<=100: raise ValueError('MAX100_REQUIRED')
    # ALL older classifications, including ERROR800 quarantine, stay untouched.
    old={r['rcept_no'] for r in old_states}
    durable={r['rcept_no'] for r in collection if r.get('source_status') in {'DURABLE','API014'}}
    blocked=old|durable
    unique={r['rcept_no']:r for r in index if r.get('rcept_no') and r.get('rcept_no') not in blocked and len(r.get('stock_code',''))==6}
    return sorted(unique.values(),key=lambda r:(r.get('rcept_dt',''),r['rcept_no']))[:limit]
def complete_checkpoint(out,meta,result):
    receipt=meta['rcept_no'];state=result['state'];raw=[]
    for p in sorted((out/'native').glob(receipt+'-*.zip')):
        raw.append(dict(path=str(p.relative_to(out)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
    source_status='DURABLE' if raw else 'API014' if state['status']=='NO_DOCUMENT' else 'DEFERRED'
    if state['status'] in TERMINAL-{'NO_DOCUMENT'} and not raw: raise ValueError('Cannot checkpoint source success without original')
    if raw and state.get('document_sha256') not in {r['sha256'] for r in raw}:raise ValueError('Source SHA differs from quality result')
    collection=dict(rcept_no=receipt,source_status=source_status,source_version='opendart-document-v1',archives=raw,run_id=os.getenv('GITHUB_RUN_ID','LOCAL'),updated_at_utc=now())
    quality=dict(rcept_no=receipt,parser_version=result['parser_version'],quality_version=QUALITY_VERSION,extraction_state=state['status'],field_count=len(result['rows']),financial_accuracy='UNVERIFIED_UNAUDITED',availability_status='UNVERIFIED',backtest_eligible=False,document_sha256=state.get('document_sha256',''),rejection_reason=state.get('error',''),updated_at_utc=now())
    # Result/source bytes must be durable before either completion checkpoint.
    atomic(out/'results'/f'{receipt}.json',result)
    atomic(out/'collection'/f'{receipt}.json',collection)
    atomic(out/'quality'/f'{receipt}.json',quality)
    return collection,quality
def worker(meta_path,result_path):
    from scripts import backfill_dart_legacy_2000_2014 as collector
    from scripts.dart_http import progress
    meta=json.loads(meta_path.read_text())
    cache=os.getenv('FINANCIAL_VALIDATION_SOURCE_CACHE')
    if cache:
        # Explicit immutable-source replay. Missing/wrong cache NEVER falls
        # through to the HTTP collector or increments a collection checkpoint.
        collector.fetch_document=cached_document(Path(cache),meta['rcept_no'],meta['_source_cache_sha256'])
    collector.RUN_CONTROL=collector.CollectionControl(max_requests=2,max_seconds=75,min_interval=0.5)
    progress('document_start',receipt=meta['rcept_no'])
    rows,state=collector.process_filing(meta)
    progress('document_end',receipt=meta['rcept_no'],stop_reason=collector.RUN_CONTROL.stop_reason)
    atomic(result_path,dict(meta=meta,rows=rows,state=state,parser_version=collector.PARSER_VERSION,stop_reason=collector.RUN_CONTROL.stop_reason))
def cached_document(cache,receipt,expected_sha):
    paths=list(cache.glob(receipt+'-*.zip'))
    if len(paths)!=1:raise ValueError('READONLY_CACHE_MISSING_OR_AMBIGUOUS')
    blob=paths[0].read_bytes()
    if sha(blob)!=expected_sha:raise ValueError('READONLY_CACHE_SOURCE_HASH')
    def fetch(requested):
        if requested!=receipt:raise ValueError('READONLY_CACHE_RECEIPT_MISMATCH')
        return blob,expected_sha
    return fetch
def _parent_death_signal():
    """The Linux fixed-kit worker must not outlive a SIGKILLed coordinator."""
    parent=os.getppid()
    if ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGTERM)!=0:
        raise OSError(ctypes.get_errno(),'PR_SET_PDEATHSIG')
    if parent==1 or os.getppid()!=parent:os._exit(125)

def _worker_stage_durations(folder,began,ended):
    """Attribute observed progress intervals; uninstrumented time stays explicit."""
    buckets={k:0.0 for k in ['download','parsing','validation','storage','waiting','startup_and_unattributed']}
    classes={'http_start':'download','connect_start':'download','read_start':'download','http_received':'validation','api_response':'validation','source_preserved':'storage','parse_member':'parsing','http_retry':'waiting'}
    last=began;stage='startup_and_unattributed';p=folder/'progress.jsonl'
    if p.exists():
        for line in p.read_text().splitlines():
            try:r=json.loads(line);point=r['monotonic']
            except(ValueError,KeyError):continue
            if not began<=point<=ended:continue
            buckets[stage]+=max(0,point-last);last=point
            stage=classes.get(r['stage'],'startup_and_unattributed')
    buckets[stage]+=max(0,ended-last)
    return {k:round(v,6)for k,v in buckets.items()}

def _recover_completed(out,meta,result_validator):
    receipt=meta['rcept_no'];result_path=out/'results'/f'{receipt}.json'
    worker_result=out/'workers'/receipt/'result.json'
    if not result_path.exists()and not worker_result.exists():
        if (out/'collection'/f'{receipt}.json').exists()or(out/'quality'/f'{receipt}.json').exists():
            raise ValueError('CHECKPOINT_WITHOUT_RESULT:'+receipt)
        return None
    result=json.loads((result_path if result_path.exists()else worker_result).read_text())
    if result['state']['rcept_no']!=receipt or result['meta']['rcept_no']!=receipt:
        raise ValueError('RECOVERY_IDENTITY:'+receipt)
    if result['state']['status']not in TERMINAL:raise ValueError('RECOVERY_NONTERMINAL_REQUIRES_REVIEW:'+receipt)
    if result_validator is not None:result_validator(meta,result,out)
    paths=[out/'collection'/f'{receipt}.json',out/'quality'/f'{receipt}.json']
    if all(p.exists()for p in paths)and result_path.exists():
        c,q=(json.loads(p.read_text())for p in paths)
        if c['rcept_no']!=receipt or q['rcept_no']!=receipt or q['field_count']!=len(result['rows']):raise ValueError('RECOVERY_CHECKPOINT_CONFLICT:'+receipt)
        if(q['extraction_state']!=result['state']['status']or q['parser_version']!=result['parser_version']or q.get('document_sha256','')!=result['state'].get('document_sha256','')or q['backtest_eligible']is not False or q['availability_status']!='UNVERIFIED'):raise ValueError('RECOVERY_QUALITY_CONFLICT:'+receipt)
        if c['source_status']not in {'DURABLE','API014'}:raise ValueError('RECOVERY_SOURCE_NOT_DURABLE:'+receipt)
        for a in c['archives']:
            if Path(a['path']).is_absolute()or'..'in Path(a['path']).parts:raise ValueError('RECOVERY_SOURCE_PATH:'+receipt)
            p=out/a['path']
            if not p.is_file()or p.stat().st_size!=a['bytes']or sha(p.read_bytes())!=a['sha256']:raise ValueError('RECOVERY_SOURCE_HASH:'+receipt)
    else:complete_checkpoint(out,meta,result)
    return dict(receipt=receipt,status=result['state']['status'],rows=len(result['rows']))

def run_batch(metas,out,*,document_seconds=90,total_seconds=600,worker_script=None,result_validator=None,status_callback=None,resume=False,max_documents=None,shutdown_reserve_seconds=None):
    """A fixed selection, durable per-receipt recovery and bounded admission.

    Graceful yields return0 while retaining a pending queue; they never grant a
    new global reservation or clear an operating HOLD. Only the caller owns that
    authorization. Resume never refetches a complete original source.
    """
    out=Path(out)
    out.mkdir(parents=True,exist_ok=resume)
    with(out/'.coordinator.lock').open('a')as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('BATCH_ALREADY_RUNNING')from None
        return _run_batch_locked(metas,out,document_seconds=document_seconds,total_seconds=total_seconds,worker_script=worker_script,result_validator=result_validator,status_callback=status_callback,resume=resume,max_documents=max_documents,shutdown_reserve_seconds=shutdown_reserve_seconds)

def _run_batch_locked(metas,out,*,document_seconds,total_seconds,worker_script,result_validator,status_callback,resume,max_documents,shutdown_reserve_seconds):
    if not metas or len(metas)>100: raise ValueError('Expected1..100 frozen receipts')
    if not (0<document_seconds<=90 and document_seconds<=total_seconds<=600): raise ValueError('Invalid bounded budgets')
    receipts=[m['rcept_no']for m in metas]
    if len(receipts)!=len(set(receipts)):raise ValueError('DUPLICATE_FROZEN_RECEIPTS')
    cap=len(metas)if max_documents is None else max_documents
    if not 1<=cap<=100:raise ValueError('INVALID_BATCH_DOCUMENT_CAP')
    reserve=min(15,total_seconds*.1)if shutdown_reserve_seconds is None else shutdown_reserve_seconds
    if not 0<=reserve<total_seconds:raise ValueError('INVALID_SHUTDOWN_RESERVE')
    started=time.monotonic();stop={'reason':''};results=[]
    status=dict(run_id=os.getenv('GITHUB_RUN_ID','LOCAL'),commit=os.getenv('GITHUB_SHA','LOCAL'),started_at_utc=now(),status='RUNNING',current_receipt=None,current_stage='INITIALIZING',completed=0,last_checkpoint=None,automatic_publication='HELD',financial_population_certification='UNVERIFIED',investment_PIT='0/6')
    selection=out/'selection.json'
    if selection.exists():
        if not resume or json.loads(selection.read_text())['samples']!=metas:raise ValueError('RESUME_SELECTION_CHANGED')
    elif resume:raise ValueError('RESUME_SELECTION_MISSING')
    else:atomic(selection,dict(samples=metas,frozen_at_utc=now(),before_HTTP=True))
    prior=json.loads((out/'run_status.json').read_text())if resume and(out/'run_status.json').exists()else None
    status.update(resumed=resume,prior_stop_reason=(prior or{}).get('stop_reason'),document_states={r:'PENDING'for r in receipts},document_timings=[],resume_history=(prior or{}).get('resume_history',[])+([dict(previous_status=prior.get('status'),previous_stop_reason=prior.get('stop_reason'),resumed_at_utc=now())]if prior else[]))
    def save(**kw):
        status.update(kw,elapsed_seconds=round(time.monotonic()-started,3),updated_at_utc=now());atomic(out/'run_status.json',status)
        if status_callback is not None:status_callback(dict(status))
    def signal_stop(signum,frame): stop['reason']='SIGNAL_'+str(signum)
    previous={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
    for s in previous: signal.signal(s,signal_stop)
    child=None
    admitted=0;yield_reason=''
    try:
        for meta in metas:
            receipt=meta['rcept_no']
            if resume:
                recovered=_recover_completed(out,meta,result_validator)
                if recovered is not None:
                    results.append(recovered);status['document_states'][receipt]='CHECKPOINT_DURABLE'
                    save(completed=len(results),last_checkpoint=receipt,current_stage='RECOVERED_DURABLE');continue
            if stop['reason']:break
            if admitted>=cap:yield_reason='BATCH_DOCUMENT_LIMIT';break
            if total_seconds-(time.monotonic()-started)<document_seconds+reserve:
                yield_reason='YIELD_BEFORE_RUN_BUDGET';break
            folder=out/'workers'/receipt;folder.mkdir(parents=True,exist_ok=resume)
            work_meta=dict(meta)
            cache_env={}
            archives=list((out/'native').glob(receipt+'-*.zip'))
            if archives:
                if len(archives)!=1:raise ValueError('RECOVERY_AMBIGUOUS_SOURCE:'+receipt)
                with zipfile.ZipFile(archives[0])as z:
                    if z.testzip()is not None:raise ValueError('RECOVERY_SOURCE_CRC:'+receipt)
                work_meta['_source_cache_sha256']=sha(archives[0].read_bytes())
                cache_env['FINANCIAL_VALIDATION_SOURCE_CACHE']=str((out/'native').resolve())
                status['document_states'][receipt]='SOURCE_DURABLE'
            atomic(folder/'meta.json',work_meta);admitted+=1;status['document_states'][receipt]='IN_FLIGHT'
            save(current_receipt=receipt,current_stage='WORKER_START')
            env=dict(os.environ,LEGACY_DART_SOURCE_DIR=str(out/'native'),LEGACY_DART_PROGRESS_FILE=str(folder/'progress.jsonl'),LEGACY_DART_RESPONSE_DIR=str(out/'service-responses'))
            env.update(cache_env)
            command=[sys.executable,'-I',str(worker_script or Path(__file__).resolve()),'--worker',str(folder/'meta.json'),'--result',str(folder/'result.json')]
            began=time.monotonic();last_heartbeat=began
            with (folder/'worker.log').open('wb') as log:
                child=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,preexec_fn=_parent_death_signal)
                while child.poll() is None:
                    elapsed=time.monotonic()-began
                    if stop['reason'] or elapsed>=document_seconds or time.monotonic()-started>=total_seconds:
                        stop['reason']=stop['reason'] or ('DOCUMENT_WALL_BUDGET' if elapsed>=document_seconds else 'RUN_WALL_BUDGET')
                        child.terminate()
                        try: child.wait(timeout=2)
                        except subprocess.TimeoutExpired: child.kill();child.wait(timeout=5)
                        break
                    if time.monotonic()-last_heartbeat>=15:
                        progress=folder/'progress.jsonl';last={}
                        if progress.exists():
                            lines=progress.read_text().splitlines()
                            if lines:
                                try:last=json.loads(lines[-1])
                                except ValueError:pass
                        save(current_stage=last.get('stage','WORKER_RUNNING'))
                        print(json.dumps(dict(receipt=receipt,stage=status['current_stage'],elapsed_seconds=round(elapsed,2),last_checkpoint=status['last_checkpoint'])),flush=True)
                        last_heartbeat=time.monotonic()
                    time.sleep(0.1)
            code=child.returncode;child=None
            if stop['reason']:
                status['document_states'][receipt]='DEFERRED'
                save(current_stage='DEFERRED',worker_exit_code=code);break
            if code!=0 or not (folder/'result.json').exists():
                stop['reason']='WORKER_FAILURE';save(worker_exit_code=code);break
            result=json.loads((folder/'result.json').read_text())
            worker_done=time.monotonic()
            status['document_states'][receipt]='RESULT_DURABLE'
            save(current_stage='RESULT_DURABLE')
            if result_validator is not None:
                result_validator(meta,result,out)
            validation_done=time.monotonic()
            collection,quality=complete_checkpoint(out,meta,result)
            timing=dict(receipt=receipt,worker_seconds=round(worker_done-began,6),validation_seconds=round(validation_done-worker_done,6),checkpoint_seconds=round(time.monotonic()-validation_done,6),replayed_source=bool(cache_env))
            timing['worker_progress_intervals']=_worker_stage_durations(folder,began,worker_done)
            atomic(out/'timings'/f'{receipt}.json',timing)
            status['document_timings'].append(timing)
            results.append(dict(receipt=receipt,status=result['state']['status'],rows=len(result['rows'])))
            status['document_states'][receipt]='CHECKPOINT_DURABLE'
            save(completed=len(results),last_checkpoint=receipt,current_stage='CHECKPOINT_DURABLE')
            if result['state']['status'] in {'DEFERRED','RATE_LIMIT','ERROR'}:
                stop['reason']=result.get('stop_reason') or result['state']['status'];break
        save(status='STOPPED_CANDIDATES_HELD'if stop['reason']else'PAUSED_CANDIDATES_HELD'if yield_reason else'COMPLETE_CANDIDATES_HELD',stop_reason=stop['reason']or yield_reason or'BATCH_COMPLETE',results=results,remaining_receipts=[r for r in receipts if r not in {x['receipt']for x in results}],admitted_documents=admitted,finished_at_utc=now())
        return 0 if not stop['reason'] else 1
    except BaseException:
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        save(status='FAILED_CANDIDATES_HELD',stop_reason='EXCEPTION',finished_at_utc=now());raise
    finally:
        for s,h in previous.items(): signal.signal(s,h)

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path);p.add_argument('--result',type=Path);p.add_argument('--mode',choices=['shadow-http','operational']);p.add_argument('--selection',type=Path);p.add_argument('--output',type=Path);p.add_argument('--max-docs',type=int,default=2);a=p.parse_args()
    if a.worker: return worker(a.worker,a.result)
    from scripts.legacy_native_financials import PARSER_VERSION
    if a.mode=='operational':
        if os.getenv('GITHUB_REF')!='refs/heads/main': raise ValueError('Operational mode requires main')
        config=json.loads((ROOT/'config/financial_backfill_rollout.json').read_text())
        if config['mode']!='CANARY_ONCE' or a.max_docs>config['maximum_documents'] or config['parser_version']!=PARSER_VERSION: raise ValueError('Rollout gate closed')
        if a.selection: raise ValueError('Operational receipts must come from untouched automatic pending queue')
        index=read_csv(ROOT/'data/financials/legacy_2000_2014/legacy_filings.csv.gz')
        historical=read_csv(ROOT/'data/status/dart_legacy_backfill_state.csv')
        existing=[]
        for f in (ROOT/'data/financials/legacy_2000_2014/quality_v9/collection').glob('*.json'):existing.append(json.loads(f.read_text()))
        if (ROOT/'data/status/dart_legacy_rollout_status.json').exists(): raise ValueError('First operating canary already consumed; explicit new approval required')
        metas=select_new(index,historical,existing,a.max_docs)
    else:
        if a.max_docs>2: raise ValueError('Predeployment live transport at most2 documents')
        obj=json.loads(a.selection.read_text());metas=obj.get('samples',obj) if isinstance(obj,dict) else obj
        if len(metas)>a.max_docs: raise ValueError('Frozen HTTP limit exceeded')
    return run_batch(metas,a.output.resolve())
if __name__=='__main__':sys.exit(main())
