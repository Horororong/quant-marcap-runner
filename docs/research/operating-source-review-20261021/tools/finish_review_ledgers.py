import collections,hashlib,json
from pathlib import Path
P=Path(__file__).parent;S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded');review={r['receipt']:r for r in json.loads((P/'document-review-ledger.json').read_text())};gap={r['receipt']:r for r in json.loads((P/'source-gap-9-triage.json').read_text())};all_docs=[];remaining=[]
for p in sorted(S.rglob('results/*.json')):
 d=json.loads(p.read_text());rec=d['meta']['rcept_no'];base=dict(receipt=rec,company=d['meta']['corp_name'],report_name=d['meta']['report_nm'],source_result_path=str(p.relative_to(S)),original_extraction_state=d['state']['status'],original_candidate_count=len(d['rows']))
 if rec in review:base.update(review_state='EXISTING_CANDIDATE_DECISIONS_COMPLETE',semantic_PASS=review[rec]['semantic_PASS'],semantic_UNVERIFIED=review[rec]['semantic_UNVERIFIED'],detail='All original candidate rows reviewed; open account definitions and document-wide/PIT issues remain separate')
 elif rec in gap:base.update(review_state='SOURCE_GAP_TRIAGED_NOT_FINANCIAL_CERTIFIED',semantic_PASS=0,semantic_UNVERIFIED=0,detail='No original candidates. Original offending member/format and original financial-label evidence inventoried; financial absence and extraction completeness unverified')
 else:base.update(review_state='NOT_REVIEWED',semantic_PASS=0,semantic_UNVERIFIED=0,detail='Retain original candidates without semantic/PIT promotion');remaining.append(base)
 all_docs.append(base)
assert len(all_docs)==57 and sum(d['original_candidate_count']for d in all_docs)==871;assert len(remaining)==29 and sum(d['original_candidate_count']for d in remaining)==523
(P/'all-57-document-status.json').write_text(json.dumps(all_docs,ensure_ascii=False,indent=2)+'\n');(P/'remaining-29-documents.json').write_text(json.dumps(remaining,ensure_ascii=False,indent=2)+'\n')
r=json.loads((P/'candidate-review-348.json').read_text());keys=[(x['receipt'],x['scope'],x['metric'],x['period_start'],x['period_end'],x['measurement_basis'])for x in r];assert len(keys)==len(set(keys))==348;assert sum(x['prior_reviewed_UNVERIFIED']for x in r)==1
# Independent raw-source anchors transcribed from original current columns.
anchors=[('20100331001950','OFS','net_income','-2931447730'),('20100331001961','OFS','net_income','669854871797'),('20100331001961','CFS','net_income','701738387534'),('20100331001972','CFS','current_assets','12493159822'),('20100331001972','CFS','cash_and_equivalents','2045499835'),('20100331001977','OFS','ocf','2113903000000'),('20100331001982','CFS','net_income','276956779000'),('20100331001982','OFS','net_income','272139112000'),('20100331002038','OFS','ocf','-1230259033')]
for rec,scope,metric,value in anchors:
 item=next(x for x in r if(x['receipt'],x['scope'],x['metric'])==(rec,scope,metric));assert item['candidate_amount_krw']==value
old=next(x for x in r if x['prior_reviewed_UNVERIFIED']);assert old['semantic_verdict']=='UNVERIFIED'and old['receipt']=='20100331001980'
summary=json.loads((P/'semantic-summary.json').read_text());summary.update(document_existing_candidate_sets_all_PASS=9,document_existing_candidate_sets_with_open_definitions=10,source_gap_triage_completed=9,source_gap_semantics_or_completeness_certified=0,numeric_sign_unit_previously_PASS=871,new_numeric_full_reaudit=False)
(P/'semantic-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
checks=dict(status='PASS_AUDIT_EVIDENCE_CONSISTENCY',unique_reviewed_candidate_keys=348,all_57_statuses_present=True,manual_source_anchor_checks=len(anchors),previous_UNVERIFIED_preserved=True,counts_partition='336PASS+12reviewedUNVERIFIED+523NOT_REVIEWED=871',document_partition='19candidate decisions complete+9source-gap triaged+29not reviewed=57',source_TABLE_inventory_count=66,old_runtime_or_integration_CI_repeated=False,PIT_or_publication_promoted=False)
(P/'review-consistency-check.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
