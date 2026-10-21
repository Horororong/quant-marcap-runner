"""Frozen first-observation source review; approval permits SOURCES, not metrics.

Uses the independent literal/semantic review gate, never production normalization.
Unsupported documents and unavailable fields remain held rather than converted
to zero/PASS. The exact reviewed scope and its immutable inputs bind approval.
"""
import argparse,base64,gzip,hashlib,io,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_review_gate import audit,unpack
HOME=Path('docs/audits/financial-limited-resume-20261019/first_observation')
STATE=Path('data/status/dart_legacy_limited_resume_v1.json')
BASE=Path('data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39248507369')
NAMES=['controls.json','source_manifest.json','review_plan.json','review_summary.json','reviewed_rows.json']
STATUS='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION'
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(o):return (json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def check_hashes(root,approval):
    if approval.get('status')!=STATUS or approval.get('backtest_eligible')is not False or approval.get('automatic_financial_publication')!='HOLD':raise ValueError('FIRST_REVIEW_SCOPE_OR_PROMOTION')
    if set(approval['files'])!=set(NAMES):raise ValueError('FIRST_REVIEW_INPUT_SET')
    for name in NAMES:
        if sha((root/HOME/name).read_bytes())!=approval['files'][name]:raise ValueError('FIRST_REVIEW_INPUT_HASH:'+name)
def check(root):
    home=root/HOME;plan=json.loads((home/'review_plan.json').read_text());summary,details,rows=audit(home)
    if summary!=json.loads((home/'review_summary.json').read_text())or rows!=json.loads((home/'reviewed_rows.json').read_text()):raise ValueError('FIRST_REVIEW_REPRODUCTION_DIFF')
    if summary['counts']['FAIL']or summary['reviewed_documents']<20:raise ValueError('JUDGED_FINANCIAL_ERROR_OR_REVIEW_SHORTFALL')
    controls=json.loads((home/'controls.json').read_text())['controls'];receipts={c['receipt']for c in controls}
    if receipts!=set(plan['augmented_review'])or not set(plan['primary_review'])<=receipts or len(plan['primary_review'])!=20:raise ValueError('FROZEN_SAMPLE_REPLACED')
    if not json.loads((home/'controls.json').read_text())['frozen_before_candidate_comparison']:raise ValueError('INDEPENDENT_CONTROLS_REQUIRED')
    official_plan=json.loads((root/BASE/'selection.json').read_text());manifest=json.loads((root/BASE/'manifest.json').read_text());s=manifest['summary']
    if plan['selection_sha256']!=official_plan['selection_sha256']or set(plan['primary_review'])!=set(official_plan['primary_review']):raise ValueError('PRE_HTTP_PLAN_CHANGED')
    selected={r['rcept_no']for r in official_plan['samples']}
    if len(selected)!=100 or set(s['completed_receipts'])!=selected or s['durable_terminal_documents']!=100 or s['run_status']['stop_reason']!='BATCH_COMPLETE':raise ValueError('FIRST_SOURCE_OBSERVATION_INCOMPLETE')
    if s['published_financial_fields']!=0 or s['automatic_financial_publication']!='HOLD'or s['backtest_eligible']is not False:raise ValueError('FIRST_CANDIDATES_PUBLISHED_OR_PROMOTED')
    # Independent byte/ZIP accounting, not a rerun of the financial parser.
    files={}
    for p in json.loads((home/'source_manifest.json').read_text())['packs']:
        for n,b in unpack(home/p['path'],p['compressed_sha256']).items():
            if n.startswith(('native/','results/','collection/','quality/')):
                if n in files and files[n]!=b:raise ValueError('FIRST_SOURCE_PACK_COLLISION')
                files[n]=b
    crc=0
    for c in s['collection']:
        if c['rcept_no']not in selected or c['source_status']!='DURABLE':raise ValueError('SOURCE_RECEIPT_OR_DURABILITY')
        for a in c['archives']:
            b=files[a['path']]
            if sha(b)!=a['sha256']or len(b)!=a['bytes']:raise ValueError('FIRST_SOURCE_ARCHIVE_HASH')
            with zipfile.ZipFile(io.BytesIO(b))as z:
                if z.testzip()is not None:raise ValueError('FIRST_SOURCE_ARCHIVE_CRC')
            crc+=1
    if crc!=100:raise ValueError('FIRST_SOURCE_ARCHIVE_COUNT')
    result=dict(status=STATUS,scope='Source-only finite continuation; only frozen23x2 financial controls reviewed; not all1363 candidates or investment/PIT',run_id='39248507369',code_sha=manifest['code_sha'],source_commit='f391dc01355b4eeb26ee0f209fa97e5f5ef43900',selected_documents=100,source_archives_crc=crc,reviewed_documents=summary['reviewed_documents'],financial_fields=summary['counts'],coverage=summary['extraction_coverage_counts'],all_unreviewed_candidates_held=True,new_batch_financial_fields_published=0,automatic_financial_publication='HOLD',backtest_eligible=False,investment_PIT='0/6',files={n:sha((home/n).read_bytes())for n in NAMES})
    return result
def verify_approval(root,state):
    approval=state.get('first_review')or{};check_hashes(root,approval)
    actual=check(root)
    if actual!=approval:raise ValueError('FIRST_REVIEW_APPROVAL_REPRODUCTION')
def main(root,approve=False):
    result=check(root)
    if approve:
        state=json.loads((root/STATE).read_text())
        if state['phase']!='WAIT_FIRST_REVIEW'or len(state['runs'])!=1 or state['runs'][0]['status']!='COMPLETE':raise ValueError('EXACT_FIRST_REVIEW_STATE_REQUIRED')
        state.update(phase='READY_NEXT',first_review=result)
        (root/STATE).write_bytes(encoded(state))
    else:
        state=json.loads((root/STATE).read_text())
        if state.get('first_review'):verify_approval(root,state)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--approve',action='store_true');a=p.parse_args();main(a.root,a.approve)
