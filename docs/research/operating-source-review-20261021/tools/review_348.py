"""Record document-level source decisions after reading the original19document packs.
No production extraction/NAV code or existing data is modified. PASS is scoped to
reported source-row semantics, never an economic aggregate/PIT certification.
"""
import collections,hashlib,json,re
from decimal import Decimal,localcontext
from pathlib import Path
P=Path(__file__).parent
packs=json.loads((P/'document-source-evidence.json').read_text());inventory=json.loads((P/'primary-table-inventory.json').read_text());tables=inventory['source_tables'];by={(x['receipt'],x['scope'],x['family']):x for x in tables}
def norm(s):
 s=re.sub(r'\((?:주석|주)[\s\d,~과및등-]*\)\s*$','',s);s=re.sub(r'\s+','',s);return re.sub(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVXLC0-9.()\-]+','',s)
def number(s):
 s=s.replace(',','').strip().replace('−','-').replace('－','-');neg=s.startswith(('(','▲','△','Δ'));s=s.strip('()▲△Δ');assert re.fullmatch(r'[+-]?\d+(?:\.\d+)?',s),s;d=Decimal(s);return -abs(d)if neg else d
accepted={'cash_and_equivalents':{'현금및현금성자산'},'current_assets':{'유동자산'},'current_liabilities':{'유동부채'},'current_portion_long_term_debt':{'유동성장기부채'},'equity':{'자본총계'},'total_assets':{'자산총계'},'total_liabilities':{'부채총계'},'ppe':{'유형자산'},'short_term_borrowings':{'단기차입금'},'long_term_borrowings':{'장기차입금'},'revenue':{'매출액','영업수익'},'cost_of_sales':{'매출원가'},'gross_profit':{'매출총이익','매출총이익(손실)'},'net_income':{'당기순이익','당기순이익(손실)'},'operating_income':{'영업이익','영업이익(손실)'},'ocf':{'영업활동으로인한현금흐름'},'depreciation':{'감가상각비'},'amortization':{'무형자산상각비'},'dividends_paid':{'배당금의지급'},'capex_ppe':{'유형자산의취득'},'capex_intangibles':{'무형자산의취득'}}
# The old unresolved control is deliberately NOT promoted by discovering aliases.
old_unknown=('20100331001980','CFS','bonds_payable')
results=[];documents=[]
for d in packs:
 rec=d['receipt'];rows=[];observed=collections.Counter()
 for t in d['tables']:
  for candidate in t['candidates']:
   r=candidate;control=by[(rec,r['scope'],r['statement'])];source=next(x for x in t['source_rows']if x['row']==r['row_index']);label=norm(source['cells'][0]);col=r['value_col'];key=(rec,r['scope'],r['metric']);findings=[]
   # Independent source coordinates/columns; summary rows need explicit primary corroboration.
   cols=[1]if rec=='20100331001963'and t['index']in {43,44}else control['current_physical_columns']
   assert col in cols,(rec,t['index'],col,cols)
   assert str(r['term'])==str(control['term']);assert r['unit']==control['unit'];assert r['period_end']=='2009-12-31';assert r['period_start']==(''if r['statement']=='BS'else'2009-01-01')
   raw=source['cells'][col];actual=number(raw)
   if '손실'in label and'이익'not in label:actual=-abs(actual)
   assert actual==Decimal(r['amount_reported']),(key,raw,r['amount_reported'])
   multiplier={'원':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000)}[control['unit']]
   with localcontext()as ctx:ctx.prec=60;assert actual*multiplier==Decimal(r['amount_krw'])
   primary_corroboration=None
   if rec=='20100331001963'and t['index']in {43,44}:
    matches=[x for x in inventory['expected_current_source_rows']if x['receipt']==rec and x['scope']==r['scope']and x['family']==r['statement']and x['metric']==r['metric']]
    assert len(matches)==1 and Decimal(matches[0]['source_amount'])==actual,(key,matches)
    primary_corroboration=dict(table=control['table'],row=matches[0]['row'],amount=matches[0]['source_amount'],reason='Summary YoY% column is not used; exact current money corroborated against source XBRL individual primary statement')
   if r['metric']=='bonds_payable':findings.append('NONCURRENT_BOND_LINE_VS_TOTAL_BOND_DEFINITION_UNRESOLVED')
   elif r['metric']=='current_portion_long_term_debt'and label=='유동성사채':findings.append('CURRENT_BOND_COMPONENT_NOT_PROVED_TOTAL_CURRENT_LONG_TERM_DEBT')
   elif r['metric']=='cost_of_sales'and label=='영업비용':findings.append('OPERATING_EXPENSE_IS_NOT_PROVED_COST_OF_SALES')
   else:assert label in accepted[r['metric']],(key,label)
   verdict='UNVERIFIED'if findings else'PASS'
   row=dict(receipt=rec,scope=r['scope'],statement=r['statement'],metric=r['metric'],period_start=r['period_start'],period_end=r['period_end'],measurement_basis=r['measurement_basis'],source_member=r['source_member'],source_member_sha256=r['source_member_sha256'],source_archive=d['source_archive'],source_archive_sha256=d['archive_sha256'],table=r['table_index'],row=r['row_index'],current_physical_column=col,current_source_cell=raw,source_row_label=source['cells'][0],source_comparison_cells=source['cells'][col+1:],source_header=t['header'],proved_current_columns=cols,reference_term=control['term'],reference_unit=control['unit'],reference_amount=str(actual),reference_unit_multiplier=str(multiplier),candidate_amount_krw=r['amount_krw'],period_current_comparative='PASS',scope_heading='PASS',unit_sign='PASS',account_definition=verdict,semantic_verdict=verdict,findings=findings,prior_reviewed_UNVERIFIED=(key==old_unknown),report_name=d['meta']['report_nm'],report_type='CORRECTED_FILING'if'기재정정'in d['meta']['report_nm']else'ATTACHMENT_ADDED'if'첨부추가'in d['meta']['report_nm']else'BUSINESS_REPORT',candidate_correction_flag=r['correction_file'],candidate_amendment_region=r['amendment_region'],amendment_chain='UNVERIFIED',PIT='UNVERIFIED',primary_corroboration=primary_corroboration,scope_of_PASS='Literal reported accounting line with stated statement/scope/current period/unit/sign; not companywide aggregate equivalence, extraction completeness or investment approval',review_method='Manual reading of all candidate source rows and document-specific original headers/columns; independent reference/current-column assertions; no production extractor as correctness oracle')
   if r['metric']in {'depreciation','amortization'}:row['source_scope_limit']='This declared IS/CF line only; not an inferred companywide depreciation/amortization total'
   if r['metric']=='revenue'and label=='영업수익':row['source_scope_limit']='Reported operating revenue, not certified cross-industry industrial sales equivalence'
   if r['metric']=='net_income'and r['scope']=='CFS':row['source_scope_limit']='Reported consolidated total; not silently converted to owner-attributable income'
   results.append(row);rows.append(row);observed[verdict]+=1
 missing=[x for x in inventory['missing']if x['receipt']==rec];presentation=[x for x in inventory['source_cell_groups_needing_review']if x['receipt']==rec];candidate_source_count=len(rows);assert candidate_source_count==d['candidate_count']
 notes=[]
 if rec=='20100331001963':notes.append('10 summary-derived current monetary fields independently corroborated to primary XBRL tables74/76; YoY% and previous-year columns explicitly excluded')
 if rec=='20100331001972':notes.append('CFS current group spans physical columns1/2; source CFS IS/CF values exist but8declared monetary concept keys are absent from output. Full candidate review is not document extraction completeness')
 if rec=='20100331001982':notes.append('CFS current group spans1/2; third OFS comparative is2007-09-01..2007-12-31, not a full year. CFS assets row73 withDART &cr;/underlines is missing as numeric observation')
 if rec=='20100331002038':notes.append('Corrected filed-body statements checked; prior corrected versions/correction legal timeline/first availability NOT established')
 documents.append(dict(receipt=rec,company=d['meta']['corp_name'],report_name=d['meta']['report_nm'],candidate_review='COMPLETE_EXISTING_CANDIDATE_SCOPE',candidate_count=candidate_source_count,semantic_PASS=observed['PASS'],semantic_FAIL=0,semantic_UNVERIFIED=observed['UNVERIFIED'],primary_source_table_inventory='COMPLETED_REGISTERED_LINE_SCOPE',source_present_absent_lines=len(missing),source_present_absent_metric_scope_keys=len({(x['scope'],x['metric'])for x in missing}),current_cell_presentation_or_missing_cases=len(presentation),extraction_completeness='GAP_OR_WITHHOLDING_FOUND'if missing or presentation else'NO_GAP_FOUND_IN_REVIEWED_PRIMARY_TABLE_ALIAS_SCOPE',whole_document_notes_attachments_completeness='UNVERIFIED',PIT='UNVERIFIED',notes=notes))
summary=dict(previous_semantic_PASS=13,reviewed_existing_candidates=len(results),semantic_PASS=sum(r['semantic_verdict']=='PASS'for r in results),semantic_FAIL=0,semantic_UNVERIFIED=sum(r['semantic_verdict']=='UNVERIFIED'for r in results),prior_UNVERIFIED_retained=1,new_reviewed_UNVERIFIED=sum(r['semantic_verdict']=='UNVERIFIED'and not r['prior_reviewed_UNVERIFIED']for r in results),detailed_unreviewed_candidates=871-len(results),candidate_documents_reviewed=len(documents),candidate_documents_remaining=48-len(documents),source_gap_documents_separate=9,primary_source_tables=len(tables),source_present_output_absent_lines=len(inventory['missing']),source_present_output_absent_metric_scope_keys=len({(r['receipt'],r['scope'],r['metric'])for r in inventory['missing']}),source_group_cases=len(inventory['source_cell_groups_needing_review']),PIT_UNVERIFIED=871,whole_filing_completeness_certified=0,financial_publication=0,next_candidate_document='20100331001983',next_candidate_count=17,classification='RESEARCH_ONLY')
summary['semantic_PASS_increment']=summary['semantic_PASS']-13;assert summary['semantic_PASS']+summary['semantic_UNVERIFIED']+summary['detailed_unreviewed_candidates']==871
(P/'candidate-review-348.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');(P/'document-review-ledger.json').write_text(json.dumps(documents,ensure_ascii=False,indent=2)+'\n');(P/'semantic-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
