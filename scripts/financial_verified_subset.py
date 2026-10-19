"""Append independently reviewed source-only observations; never revise old data."""
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_review_gate import audit

HOME=Path('docs/audits/financial-limited-resume-20261019')
AUDIT=Path('docs/audits/financial-source-readiness-20261019')
BASE=Path('data/financials/legacy_2000_2014/quality_v9/reviewed_batches/source_readiness_20261019')
QUALITY='financial-quality-v1-source-linked-not-PIT'
def sha(b): return hashlib.sha256(b).hexdigest()
def encoded(o): return (json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode()
def key(r):return tuple(r[k]for k in ('rcept_no','metric','scope','period_start','period_end'))
def plan(root):
    summary,details,rows=audit(root/AUDIT)
    if summary['counts']!={'PASS':199,'FAIL':0,'UNVERIFIED':28}:raise ValueError('FROZEN_REVIEW_COUNTS_CHANGED')
    if rows!=json.loads((root/AUDIT/'reviewed_rows.json').read_text()):raise ValueError('FROZEN_SOURCE_REVIEW_CHANGED')
    previous=[];old_hashes={}
    legacy=root/'data/financials/legacy_2000_2014/quality_v9'
    for suffix in ['metrics','reviewed_batches/validation100_20261019/metrics']:
        for p in sorted((legacy/suffix).glob('*.json')):
            previous.extend(json.loads(p.read_text())['rows']);old_hashes[str(p.relative_to(root))]=sha(p.read_bytes())
    if len(previous)!=93:raise ValueError('PREVIOUS93_BASELINE_CHANGED')
    old={key(r):r for r in previous};new={key(r):r for r in rows}
    if len(new)!=len(rows):raise ValueError('DUPLICATE_REVIEWED_KEY')
    overlap=set(old)&set(new);conflicts=[]
    for k in overlap:
        if any(old[k].get(n)!=new[k].get(n)for n in ['amount_krw','unit','unit_multiplier','measurement_basis','source_member_sha256','document_sha256']):conflicts.append(k)
    # Even a conflicting old observation is immutable: new values live under
    # a distinct, review-versioned namespace and are never a replacement.
    outputs={};by_receipt={}
    for row in rows:
        if any(row.get(k)!='PASS'for k in ['financial_source_literal_verdict','semantic_selection_verdict'])or row.get('backtest_eligible')is not False:
            raise ValueError('UNREVIEWED_OR_INVESTMENT_PROMOTION')
        by_receipt.setdefault(row['rcept_no'],[]).append(row)
    for receipt,rs in sorted(by_receipt.items()):
        outputs[str(BASE/'metrics'/f'{receipt}.json')]=encoded(dict(rcept_no=receipt,quality_version=QUALITY,publication_contract='reviewed-subset-v1',financial_accuracy_scope='Only listed source-linked fields; not whole-document PIT',backtest_eligible=False,rows=rs))
    held=[d for d in details if d['record_type']=='financial_field'and d['verdict']!='PASS']
    outputs[str(HOME/'held_fields.json')]=encoded(held)
    ledger=dict(contract='reviewed-subset-v1',audit_root=str(AUDIT),quality_version=QUALITY,parser_version='legacy-v9.2-statement-boundary-guard',source_diagnostic_version='legacy-document-quality-v3-literal-labels',published_fields=len(rows),published_documents=len(by_receipt),previous_fields=93,duplicate_keys=len(overlap),conflicting_old_observations=conflicts,new_distinct_fields=len(set(new)-set(old)),new_distinct_documents=len(set(by_receipt)-{r['rcept_no']for r in previous}),held_fields=len(held),coverage=summary['extraction_coverage_counts'],old_file_hashes=old_hashes,metric_directory=str(BASE/'metrics'),files=[dict(path=p,bytes=len(b),sha256=sha(b))for p,b in sorted(outputs.items())],backtest_eligible=False,investment_PIT='0/6',automatic_financial_publication='HOLD')
    outputs[str(HOME/'publication_manifest.json')]=encoded(ledger)
    return ledger,outputs
def main(root,check=False):
    ledger,outputs=plan(root)
    for name,raw in outputs.items():
        p=root/name
        if check:
            if not p.exists()or p.read_bytes()!=raw:raise ValueError('SUBSET_PUBLICATION_DIFF:'+name)
        else:
            if p.exists()and p.read_bytes()!=raw:raise ValueError('IMMUTABLE_PUBLICATION_COLLISION:'+name)
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    found={str(p.relative_to(root))for p in (root/BASE/'metrics').glob('*.json')}
    if found!={p for p in outputs if '/metrics/'in p}:raise ValueError('UNLISTED_SUBSET_FILE')
    print(json.dumps({k:ledger[k]for k in ['published_fields','published_documents','new_distinct_fields','new_distinct_documents','duplicate_keys','conflicting_old_observations','held_fields','coverage','backtest_eligible']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--check',action='store_true');a=p.parse_args();main(a.root,a.check)
