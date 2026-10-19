"""Finite source-review batch. HOLD stays closed; no data/ref publication.

Collection, extraction, independent review and publication are different ledgers.
The production collector is reused; its results are NEVER independent controls.
"""
import argparse, hashlib, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.financial_rollout import atomic, read_csv, run_batch, select_new
CONTRACT='financial-validation-batch-v1'
SEED='financial-validation-100-20261019-v1'
CHECKPOINT='20100331001585'
HOME=Path('docs/audits/financial-validation-100-20261019')
BASE=Path('data/financials/legacy_2000_2014/quality_v9')
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def freeze(root,out):
    if (root/'data/status/dart_legacy_validation100_status.json').exists():
        raise ValueError('AUTHORIZED100_ALREADY_CONSUMED_NO_AUTOMATIC_EXPANSION')
    config=json.loads((root/'config/financial_backfill_rollout.json').read_text())
    if config['mode']!='HOLD' or config['automatic_publication_enabled'] or config['automatic_schedule_enabled']:
        raise ValueError('GLOBAL_HOLD_REQUIRED')
    prior=json.loads((root/'data/status/dart_legacy_rollout_status.json').read_text())
    if prior['last_checkpoint']!=CHECKPOINT or prior['published_fields']!=8:
        raise ValueError('CANARY_BASELINE_CHANGED_REVIEW_REQUIRED')
    index_path=root/'data/financials/legacy_2000_2014/legacy_filings.csv.gz'
    state_path=root/'data/status/dart_legacy_backfill_state.csv'
    index=read_csv(index_path);old=read_csv(state_path)
    collected=[json.loads(p.read_text())for p in sorted((root/BASE/'collection').glob('*.json'))]
    if len(collected)!=10:raise ValueError('EXACT_PRIOR10_REQUIRED_NO_AUTOMATIC_EXPANSION')
    samples=select_new(index,old,collected,100)
    if len(samples)!=100 or any(s['rcept_no']<=CHECKPOINT for s in samples):
        raise ValueError('EXPECTED_NEXT100_AFTER_CHECKPOINT')
    plan=dict(contract=CONTRACT,seed=SEED,base_sha='98a5f706b56ba23c4d10731050c14be0405c4da2',checkpoint=CHECKPOINT,
        input_sha256={str(p.relative_to(root)):digest(p.read_bytes())for p in [index_path,state_path]},
        samples=samples,selection_sha256=digest(canonical(samples)),order='rcept_dt,rcept_no; no replacement',
        independent_review_rule={'primary':'lowest SHA256(seed|receipt)20 receipts, fixed before HTTP',
          'augment':'All extracted documents if total extracted<=20; otherwise at least10 extracted, plus first2 of every observed extraction state, ordered by same seed',
          'conflicts':'All discovered source conflicts held regardless of sample',
          'expected_values':'Human literal controls frozen from independent raw grids before opening production row amounts; no parser-derived expectations',
          'after_fix':'A sample used to change parser becomes regression, fresh unused holdout required'},
        primary_review=sorted([s['rcept_no']for s in samples],key=rank)[:20],
        limits={'total_documents':100,'chunk_documents':20,'document_seconds':90,'chunk_seconds':600},
        automatic_collection='HOLD',automatic_publication='HOLD',backtest_eligible=False)
    if out.exists():
        if json.loads(out.read_text())!=plan:raise ValueError('FROZEN_SELECTION_IMMUTABLE')
    else:atomic(out,plan)
    return plan
def rank(receipt):return digest((SEED+'|'+receipt).encode())
def review_selection(plan,statuses):
    receipts=[s['rcept_no']for s in plan['samples']];chosen=set(plan['primary_review'])
    extracted=sorted([r for r in receipts if statuses.get(r,{}).get('field_count',0)>0],key=rank)
    chosen.update(extracted if len(extracted)<=20 else extracted[:10])
    for state in sorted({s.get('extraction_state')for s in statuses.values()}):
        chosen.update(sorted([r for r in receipts if statuses.get(r,{}).get('extraction_state')==state],key=rank)[:2])
    return [r for r in receipts if r in chosen]
def collect(plan_path,out,chunk):
    plan=json.loads(plan_path.read_text())
    if plan['contract']!=CONTRACT or len(plan['samples'])!=100 or digest(canonical(plan['samples']))!=plan['selection_sha256']:
        raise ValueError('FROZEN_SELECTION_INTEGRITY')
    if not 0<=chunk<5:raise ValueError('ONLY_FIVE_FIXED_CHUNKS')
    if os.getenv('GITHUB_RUN_ATTEMPT','1')!='1':raise ValueError('NO_AUTOMATIC_RUN_RETRY')
    folder=out/f'chunk{chunk:02d}'
    # Prior chunks must be durably complete; no jumping past failures.
    for i in range(chunk):
        prior=json.loads((out/f'chunk{i:02d}'/'run_status.json').read_text())
        if prior['completed']!=20 or prior['stop_reason']!='BATCH_COMPLETE':raise ValueError('PRIOR_CHUNK_INCOMPLETE')
    if folder.exists():raise ValueError('EXISTING_SOURCE_CHECKPOINT_PRESERVED_NO_RECOLLECTION')
    return run_batch(plan['samples'][chunk*20:(chunk+1)*20],folder)
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','collect','review-selection']);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--chunk',type=int);a=p.parse_args()
    if a.mode=='freeze':
        obj=freeze(ROOT,a.plan);print(json.dumps(dict(selection_sha256=obj['selection_sha256'],count=100,primary_review=obj['primary_review'])));return 0
    if a.mode=='collect':return collect(a.plan,a.output,a.chunk)
    plan=json.loads(a.plan.read_text());statuses={p.stem:json.loads(p.read_text())for p in a.output.glob('chunk*/quality/*.json')}
    atomic(a.output/'review_selection.json',dict(seed=SEED,selection_sha256=plan['selection_sha256'],receipts=review_selection(plan,statuses),before_opening_production_amounts=True))
    return 0
if __name__=='__main__':sys.exit(main())
