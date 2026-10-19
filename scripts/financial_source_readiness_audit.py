"""Reconcile frozen110 evidence sets and verify a view-only source diagnostic.

No HTTP, no operational writes and no new publication. The numeric gate's raw
controls are independent inputs; parser replay is only consistency/coverage.
"""
import argparse,base64,csv,gzip,hashlib,io,json,sys,zipfile
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_review_gate import audit,unpack,grids,verify
from legacy_document_quality import inspect_member,DIAGNOSTIC_VERSION
def sha(b):return hashlib.sha256(b).hexdigest()
def read_subjects(path):return json.loads(gzip.decompress(base64.b64decode(path.read_bytes())))['subjects']
def main(root,check=False):
    old=root.parent/'financial-validation-100-20261019';manifest=json.loads((old/'source_manifest.json').read_text());files={}
    for pack in manifest['packs']:files.update(unpack(old/pack['path'],pack['compressed_sha256']))
    before=read_subjects(old/'subjects_v92.json.gz.b64');after=read_subjects(root/'subjects_quality_v3.json.gz.b64')
    assert len(before)==len(after)==110 and set(before)==set(after)
    hundred={s['rcept_no']for s in json.loads((old/'batch_plan.json').read_text())['samples']}
    ten=set(before)-hundred;assert len(hundred)==100 and len(ten)==10
    reviewed=set(json.loads((old/'review_selection.json').read_text())['receipts'])|set(json.loads((old/'postfix_holdout_plan.json').read_text())['receipts'])
    unreviewed=hundred-reviewed;gaps={r for r in hundred if before[r]['state']['status']=='SOURCE_GAP'}
    assert len(unreviewed)==52 and len(gaps)==71 and len(unreviewed&gaps)==44
    summary,details,passed=audit(root)
    assert summary['counts']['FAIL']==0,'Numeric/metadata audit FAIL: do not deploy'
    controls=json.loads((root/'controls.json').read_text())['controls']+json.loads((root/'fresh10_controls.json').read_text())['controls']
    old_details=[];cache={}
    for c in controls:
        receipt=c['receipt']
        if receipt not in cache:cache[receipt]=grids(files,receipt)
        old_details.append(verify(c,before[receipt]['rows'],cache[receipt])[0])
    changed=[];prior_count=0
    for receipt,subject in before.items():
        for row in subject['rows']:
            identity=lambda x:tuple(x.get(k)for k in ('metric','scope','period_start','period_end','measurement_basis','source_member'))
            matches=[x for x in after[receipt]['rows']if identity(x)==identity(row)]
            assert len(matches)==1,(receipt,identity(row),'PRIOR_VALUE_REMOVED_OR_AMBIGUOUS')
            delta=[k for k in set(row)|set(matches[0])if row.get(k)!=matches[0].get(k)]
            assert set(delta)<= {'source_diagnostic_version'},(receipt,delta,'PRIOR_FINANCIAL_OR_SOURCE_CHANGE')
            prior_count+=1
    source=[]
    for receipt in sorted(before):
        archives=[(k,b)for k,b in files.items()if k.startswith('native/'+receipt+'-')and k.endswith('.zip')];assert len(archives)==1
        name,blob=archives[0];members=[]
        with zipfile.ZipFile(io.BytesIO(blob))as z:
            assert z.testzip()is None
            for member in z.namelist():
                if not member.endswith('.xml'):continue
                d=inspect_member(z.read(member),member)
                members.append(dict(member=member,sha256=d['sha256'],issues=d['issues'],warnings=d['warnings'],literal_labels=len(d.get('literal_label_view',[])),xml_error=d.get('xml_error')))
        old_state=before[receipt]['state']['status'];new_state=after[receipt]['state']['status']
        category='UNSUPPORTED_SOURCE_MARKUP_REMAINS'if any(m['issues']for m in members)else'UNSUPPORTED_PRIMARY_TABLE_OR_COVER'if not after[receipt]['rows']else'VALIDATED_STRUCTURAL_VIEW_NOT_FINANCIAL_CERTIFICATION'
        source.append(dict(receipt=receipt,cohort='new100'if receipt in hundred else'prior10',archive_sha256=sha(blob),archive_crc='PASS',before=old_state,after=new_state,category=category,members=members,financial_absence='NOT_CERTIFIED',new_HTTP_calls=0))
    new_gaps={x['receipt']for x in source if x['after']=='SOURCE_GAP'}
    original93={}
    repo=root.parents[2]
    for p in (repo/'data/financials/legacy_2000_2014/quality_v9/metrics').glob('*.json'):original93[str(p.relative_to(repo))]=sha(p.read_bytes())
    for p in (repo/'data/financials/legacy_2000_2014/quality_v9/reviewed_batches/validation100_20261019/metrics').glob('*.json'):original93[str(p.relative_to(repo))]=sha(p.read_bytes())
    result=dict(documents=110,new100=100,prior10=10,overlap=sorted(hundred&ten),previous_candidates_new100=435,previous_candidates_all110=prior_count,
        prior_publication=dict(original8=8,new100=82,prior_bank_released3=3,total=93,previous_held43_release3_remaining40=40,modified=False),
        prior_reviewed_new100=48,prior_unreviewed_new100=52,prior_source_gap_new100=71,overlap_unreviewed_and_gap=44,
        newly_source_reviewed_receipts=sorted(unreviewed),numeric_scope='Selected primary OFS fields only; missing CFS/other metrics are not certified by document review',
        state_counts_before=dict(Counter(before[r]['state']['status']for r in before)),state_counts_after=dict(Counter(after[r]['state']['status']for r in after)),
        resolved_source_gaps_new100=len(gaps-new_gaps),remaining_source_gaps_new100=len(gaps&new_gaps),
        source_gap_prior10_before=sum(before[r]['state']['status']=='SOURCE_GAP'for r in ten),source_gap_prior10_after=sum(after[r]['state']['status']=='SOURCE_GAP'for r in ten),
        candidate_fields_after=sum(len(s['rows'])for s in after.values()),
        numeric_before=dict(Counter(d['verdict']for d in old_details if d['record_type']=='financial_field')),
        numeric_after=summary['counts'],coverage_after=summary['extraction_coverage_counts'],cohorts=summary['cohorts'],
        newly_published_fields=0,old_publication_hashes=original93,diagnostic_version=DIAGNOSTIC_VERSION,
        automatic_collection='HOLD',automatic_publication='HOLD',investment_PIT='0/6',backtest_eligible=False,new_HTTP_calls=0)
    outputs={'reconciliation.json':result,'source_classification.json':source}
    for name,obj in outputs.items():
        data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();p=root/name
        if check:assert p.read_bytes()==data,('REPRODUCTION_DIFF',name)
        else:p.write_bytes(data)
    if not check:
        with(root/'field_details.csv').open('w',newline='',encoding='utf-8')as f:
            w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
    print(json.dumps({k:v for k,v in result.items()if k not in ['old_publication_hashes','newly_source_reviewed_receipts','cohorts']},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args();main(a.root,a.check)
