import collections,hashlib,json
from pathlib import Path
P=Path(__file__).parent
OLD=Path('/workspace/quant-source-review-20261021')
def read(p):return json.loads(p.read_text())
def save(n,obj):(P/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
old=read(OLD/'candidate-review-348.json');new=read(P/'candidate-review-523.json')
old_docs=read(OLD/'document-review-ledger.json');new_docs=read(P/'document-review-ledger.json')
all_rows=old+new;all_docs=old_docs+new_docs
keys=[(r['receipt'],r['scope'],r['metric'],r['period_start'],r['period_end'],r['measurement_basis'])for r in all_rows]
assert len(keys)==len(set(keys))==871
assert len({r['receipt']for r in all_docs})==48
assert all(r['PIT']=='UNVERIFIED' for r in all_rows)
# Exact old decisions preserved; newly read documents do not reinterpret old gaps.
assert all_rows[:348]==old
anchors=[('20100331001983','OFS','cash_and_equivalents','227670517'),('20100331001983','OFS','net_income','-12164392917'),('20100331001983','OFS','ocf','-3883067262'),('20100331001990','OFS','net_income','414155700'),('20100331001998','OFS','revenue','294520529000'),('20100331002001','OFS','capex_ppe','2142012377'),('20100331002017','CFS','total_assets','277294035892'),('20100331002017','CFS','revenue','179574505391'),('20100331002034','OFS','equity','-27627233784'),('20100331002037','OFS','depreciation','22270606786'),('20100331002039','OFS','ocf','-38181907759'),('20100331002046','CFS','net_income','168653115783'),('20100331002046','OFS','net_income','169715728863'),('20100331002053','OFS','gross_profit','-89359191'),('20100331002054','OFS','net_income','-2594128893')]
for rec,scope,metric,value in anchors:
 r=next(x for x in new if (x['receipt'],x['scope'],x['metric'])==(rec,scope,metric));assert r['candidate_amount_krw']==value
uv=[r for r in all_rows if r['semantic_verdict']=='UNVERIFIED']
assert len(uv)==23 and sum(r['semantic_verdict']=='PASS'for r in all_rows)==848
source_status=read(OLD/'all-57-document-status.json')
by={r['receipt']:r for r in all_docs}
for d in source_status:
 if d['receipt'] in by:
  r=by[d['receipt']];d.update(review_state='EXISTING_CANDIDATE_DECISIONS_COMPLETE',semantic_PASS=r['semantic_PASS'],semantic_UNVERIFIED=r['semantic_UNVERIFIED'],detail='All original candidate rows have source-row semantic decisions; whole-document extraction, cross-statement accuracy, correction chain and PIT remain separately unverified')
assert len(source_status)==57 and sum(d['original_candidate_count']for d in source_status)==871
save('all-57-document-status.json',source_status);save('all-871-candidate-decisions.json',all_rows);save('all-48-document-review-ledger.json',all_docs)
save('unverified-23-cause-ledger.json',[dict(receipt=r['receipt'],scope=r['scope'],metric=r['metric'],source_label=r['source_row_label'],source_table=r['table'],source_row=r['row'],findings=r['findings'],previous_reviewed_12=r in old,prior_SK_control=r['prior_reviewed_UNVERIFIED'],reopen_only_with='Explicit account-definition evidence / proved aggregate or approved concept contract; no alias-only promotion',PIT='UNVERIFIED')for r in uv])
invs=[read(OLD/'primary-table-inventory.json'),read(P/'primary-table-inventory.json')]
missing=[x for inv in invs for x in inv['missing']]
groups=collections.defaultdict(list)
for r in missing:groups[(r['receipt'],r['scope'],r['metric'])].append(r)
group_rows=[]
for key,rs in groups.items():
 if key[0]=='20100331001972' and key[1]=='CFS':cause='CONFIRMED_ZONE_CONTROL_FLOW_DEFECT';priority='P1';action='Fix ordinary see-notes sentence vs actual notes entry; source-date/column/unit/scope guards and approved-source migration remain required'
 elif key[2] in {'depreciation','amortization'}:cause='IS_COMPONENT_VS_CF_ADJUSTMENT_CONCEPT_COLLISION_TRACE_REQUIRED';priority='P2';action='Separate statement-specific concept schema; never select an arbitrary amount or sum different accounting meanings'
 elif key[2]=='current_portion_long_term_debt':cause='BOND_OR_BORROWING_COMPONENT_VS_TOTAL_DEFINITION_COLLISION';priority='P2';action='Prove aggregate definition and source composition before changing selection'
 else:cause='BOND_AGGREGATE_VS_COMPONENT_COLLISION';priority='P2';action='Keep conflicting amounts withheld'
 group_rows.append(dict(receipt=key[0],scope=key[1],metric=key[2],source_row_count=len(rs),priority=priority,cause=cause,source_rows=rs,next_action=action,financial_publication='HOLD',PIT='UNVERIFIED'))
save('all-extraction-coverage-priorities.json',dict(primary_tables=sum(len(i['source_tables'])for i in invs),declared_source_rows=sum(len(i['expected_current_source_rows'])for i in invs),source_present_candidate_absent_rows=len(missing),metric_scope_keys=len(groups),groups=group_rows,additional_P1=dict(receipt='20100331001982',scope='CFS',metric='total_assets',table=135,row=73,reason='CURRENT_TOKEN_LINEBREAK_AND_UNDERLINE_REJECTED',raw='4,877,276,061&cr;=============',next_action='Prove line-break/decoration token boundary; never join two numeric tokens. Preserve original bytes and require independent source value plus whole PASS regression before parser migration'),presentation_groups=sum(len(i['source_cell_groups_needing_review'])for i in invs),scope_limit='Registered aliases in manually designated primary BS/IS/CF tables; not full filing/notes/attachments/unsupported account completeness'))
warnings=[dict(receipt='20100331001990',type='COMPARATIVE_PERIOD_NOT_FULL_YEAR',evidence='Term33 comparative is 2008-12-01..2008-12-31; term32 is 2007-12-01..2008-11-30. Current term34 is full 2009.',effect='Do not label comparative as full FY2008'),dict(receipt='20100331001993',type='SOURCE_CROSS_STATEMENT_CONFLICT',evidence='BS table70 equity112274988298 vs preceding capital-change ending equity112274988297; 1KRW. IS profit7435596123 vs preceding capital-change7435596122.',effect='Literal BS/IS row match does not resolve source inconsistency. No tolerance or value replacement'),dict(receipt='20100331002001',type='SOURCE_CAPITAL_CHANGE_PRINT_CONFLICT',evidence='Table113 prefix contains current profit574371236 vs total571371236, ending total0; primary BS equity20378926851 and primary IS profit574371236.',effect='No capital-change reconciliation certification; reported primary candidate not replaced'),dict(receipt='20100331002002',type='SOURCE_PARENTHESES_STALE_TEXT',evidence='BS profit commentary in prefix shows prior negative3911485520; actual current IS109 positive1035190305 agrees CF115 current. Parenthetical commentary is not current-column evidence.',effect='Use source-proved current monetary column; do not relabel prior commentary'),dict(receipt='20100331002003',type='SOURCE_CROSS_STATEMENT_CONFLICT',evidence='BS equity15708393854 vs capital-change ending15708593854 (200000KRW). Prior IS profit-4719654038 vs prior CF-8597485308.',effect='Current literal-row source check only; cross-statement/recast comparability unverified'),dict(receipt='20100331002046',type='SOURCE_COMPARATIVE_DATE_PRINT_CONFLICT',evidence='CFS term34 header prints 2007-01-01..2008-12-31; current term36 is 2009-01-01..2009-12-31.',effect='Do not certify historical comparative dates from this header'),dict(receipt='20100331001983',type='ADDITIONAL_ANNEX_SCOPE_NOT_FULLY_EXTRACTED',evidence='Annex00761 has CFS primaryBS7/IS10/CF16 current2009, including revenue4642600859 and OCF-4951563026; existing17candidates are OFS only.',effect='OFS existing-candidate completion does not certify annex/CFS extraction completeness')]
save('source-conflicts-and-scope-limits.json',warnings)
summary=dict(classification='RESEARCH_ONLY',previous_PASS=336,new_PASS=512,total_PASS=848,previous_reviewed_UNVERIFIED=12,new_reviewed_UNVERIFIED=11,total_reviewed_UNVERIFIED=23,semantic_FAIL=0,unreviewed_existing_candidates=0,total_existing_candidates=871,previous_candidate_documents=19,new_candidate_documents=29,existing_candidate_document_decisions_complete=48,source_gap_documents_unchanged=9,total_source_documents=57,PIT_UNVERIFIED=871,whole_document_completeness_certified=0,financial_values_published=0,numeric_sign_unit_prior_evidence=871,production_parser_changed=False,HTTP_original_source_requests=0,next_review='Resolve23account definitions only with new evidence; P1STCzone8fields/CJtoken1field; annexCFS and completeness follow-up separately',collection_checkpoint='20100331002054',next_source_targets=['20100331002062','20100331002063'],source_absent_rows=len(missing),source_absent_metric_scope_keys=len(groups))
save('combined-summary.json',summary)
checks=dict(status='PASS_EVIDENCE_CONSISTENCY',new_unique_keys=523,combined_unique_keys=871,previous348_decisions_preserved=True,old12_UNVERIFIED_preserved=True,source_gap9_reinterpreted=False,independent_raw_source_anchors=15,partition='848PASS+23reviewedUNVERIFIED+0NOT_REVIEWED=871',PIT_or_publication_promoted=False,operational_checkpoint_unchanged=True)
save('review-consistency-check.json',checks)
print(json.dumps(summary,indent=2))
