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
def run_batch(metas,out,*,document_seconds=90,total_seconds=600,worker_script=None):
    if not metas or len(metas)>100: raise ValueError('Expected1..100 frozen receipts')
    if not (0<document_seconds<=90 and document_seconds<=total_seconds<=600): raise ValueError('Invalid bounded budgets')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();stop={'reason':''};results=[]
    status=dict(run_id=os.getenv('GITHUB_RUN_ID','LOCAL'),commit=os.getenv('GITHUB_SHA','LOCAL'),started_at_utc=now(),status='RUNNING',current_receipt=None,current_stage='INITIALIZING',completed=0,last_checkpoint=None,automatic_publication='HELD',financial_population_certification='UNVERIFIED',investment_PIT='0/6')
    atomic(out/'selection.json',dict(samples=metas,frozen_at_utc=now(),before_HTTP=True))
    def save(**kw):
        status.update(kw,elapsed_seconds=round(time.monotonic()-started,3),updated_at_utc=now());atomic(out/'run_status.json',status)
    def signal_stop(signum,frame): stop['reason']='SIGNAL_'+str(signum)
    previous={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
    for s in previous: signal.signal(s,signal_stop)
    child=None
    try:
        for meta in metas:
            if stop['reason'] or time.monotonic()-started>=total_seconds:
                stop['reason']=stop['reason'] or 'RUN_WALL_BUDGET';break
            receipt=meta['rcept_no'];folder=out/'workers'/receipt;folder.mkdir(parents=True)
            atomic(folder/'meta.json',meta);save(current_receipt=receipt,current_stage='WORKER_START')
            env=dict(os.environ,LEGACY_DART_SOURCE_DIR=str(out/'native'),LEGACY_DART_PROGRESS_FILE=str(folder/'progress.jsonl'),LEGACY_DART_RESPONSE_DIR=str(out/'service-responses'))
            command=[sys.executable,'-I',str(worker_script or Path(__file__).resolve()),'--worker',str(folder/'meta.json'),'--result',str(folder/'result.json')]
            began=time.monotonic();last_heartbeat=began
            with (folder/'worker.log').open('wb') as log:
                child=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
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
                save(current_stage='DEFERRED',worker_exit_code=code);break
            if code!=0 or not (folder/'result.json').exists():
                stop['reason']='WORKER_FAILURE';save(worker_exit_code=code);break
            result=json.loads((folder/'result.json').read_text())
            collection,quality=complete_checkpoint(out,meta,result)
            results.append(dict(receipt=receipt,status=result['state']['status'],rows=len(result['rows'])))
            save(completed=len(results),last_checkpoint=receipt,current_stage='CHECKPOINT_DURABLE')
            if result['state']['status'] in {'DEFERRED','RATE_LIMIT','ERROR'}:
                stop['reason']=result.get('stop_reason') or result['state']['status'];break
        save(status='COMPLETE_CANDIDATES_HELD' if not stop['reason'] else 'STOPPED_CANDIDATES_HELD',stop_reason=stop['reason'] or 'BATCH_COMPLETE',results=results,finished_at_utc=now())
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
