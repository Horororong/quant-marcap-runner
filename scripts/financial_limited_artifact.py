"""Verify completed first-run artifact against git-preserved source manifests.
No HTTP collector, financial parser or new source request. Transport logs prove
attempt/deadline accounting, independently of source-literal financial review.
"""
import argparse,hashlib,json,sys,zipfile
from collections import Counter
from pathlib import Path
def main(root,artifact,out):
    plans=list(artifact.glob('**/batch_plan.json'))
    if len(plans)!=1:raise ValueError('FIRST_ARTIFACT_PLAN_IDENTITY')
    home=plans[0].parent;batch=home/'batch';plan=json.loads(plans[0].read_text());status=json.loads((batch/'run_status.json').read_text())
    prior=root/'data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39248507369'
    recorded=json.loads((prior/'selection.json').read_text());manifest=json.loads((prior/'manifest.json').read_text())
    if plan!=recorded or status!=manifest['summary']['run_status']:raise ValueError('FIRST_ARTIFACT_ORIGINAL_RECORD_DIFF')
    if status['stop_reason']!='BATCH_COMPLETE'or status['completed']!=100 or status['elapsed_seconds']>600:raise ValueError('FIRST_COLLECTION_LIMIT_OR_FAILURE')
    final=json.loads((home/'final_commit.json').read_text())
    if final['sha']!='f391dc01355b4eeb26ee0f209fa97e5f5ef43900'or final['financial_fields_published']!=0:raise ValueError('FIRST_ACTUAL_COMMIT_OR_PUBLICATION_DIFF')
    events=Counter();http=Counter();max_attempt=0;max_doc=0;archives=0
    for c in manifest['summary']['collection']:
        receipt=c['rcept_no'];progress=batch/'workers'/receipt/'progress.jsonl'
        logs=[json.loads(l)for l in progress.read_text().splitlines()]
        if not logs or any(x.get('receipt',receipt)!=receipt for x in logs):raise ValueError('FIRST_RECEIPT_PROGRESS_MISSING_OR_MIXED')
        for x in logs:
            events[x['stage']]+=1
            if 'http_status'in x:http[str(x['http_status'])]+=1
            max_attempt=max(max_attempt,int(x.get('attempt',0)))
        starts=[x['monotonic']for x in logs if x['stage']=='document_start'];ends=[x['monotonic']for x in logs if x['stage']=='document_end']
        if len(starts)!=1 or len(ends)!=1 or ends[0]-starts[0]>90:raise ValueError('DOCUMENT_PROGRESS_OR_LIMIT')
        max_doc=max(max_doc,ends[0]-starts[0])
        for a in c['archives']:
            b=(batch/a['path']).read_bytes()
            if hashlib.sha256(b).hexdigest()!=a['sha256']or len(b)!=a['bytes']:raise ValueError('ARTIFACT_SOURCE_HASH')
            with zipfile.ZipFile(batch/a['path'])as z:
                if z.testzip()is not None:raise ValueError('ARTIFACT_SOURCE_CRC')
            archives+=1
    if archives!=100 or not 100<=events['http_start']<=200 or max_attempt>2:raise ValueError('ATTEMPT_OR_SOURCE_COUNT_LIMIT')
    result=dict(status='PASS_SOURCE_DURABILITY_AND_LIMITS_NOT_FINANCIAL_OR_PIT',run_id=39248507369,source_commit=final['sha'],archives=archives,http_requests=events['http_start'],http_retries=events['http_retry'],http_status=dict(http),maximum_recorded_attempt=max_attempt,maximum_recorded_document_seconds=max_doc,collection_elapsed_seconds=status['elapsed_seconds'],new_collection_requests_in_verification=0,new_financial_fields_published=0,investment_approved=False)
    out.mkdir(parents=True,exist_ok=False);(out/'artifact_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--artifact',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.artifact,a.output)
