"""Independent literal-control gate; never imports production account/period code.

Human semantic controls are explicit inputs, not inferred from parser output.
The gate verifies their source locations and arithmetic, and publishes only the
reviewed subset. Source-literal accuracy does not authenticate document PIT.
"""
import argparse,base64,csv,gzip,hashlib,io,json,re,sys,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_source_grid import Grid
VERSION='independent-source-review-v1'
UNITS={'원':1,'천원':1000,'백만원':1000000,'억원':100000000}
def sha(data):return hashlib.sha256(data).hexdigest()
def normalize(literal,unit,negative_account=False):
    if unit not in UNITS:raise ValueError('UNSUPPORTED_UNIT')
    text=literal.strip();negative=False
    # A native explicit line-break entity followed solely by total-rule marks
    # cannot contain a second amount/EPS. Keep every other suffix unsupported.
    decoration=re.fullmatch(r'(.+)&cr;([=_]{2,})',text)
    if decoration:text=decoration.group(1).strip()
    if text.startswith(('△','▲','Δ')):negative=True;text=text[1:].strip()
    if text.startswith('(')and text.endswith(')'):negative=True;text=text[1:-1].strip()
    text=text.replace('−','-').replace('－','-')
    if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',text):raise ValueError('AMBIGUOUS_SCALAR')
    number=Decimal(text.replace(',',''))
    if negative or negative_account:number=-abs(number)
    return number*UNITS[unit]
def unpack(pack,expected_sha):
    compressed=base64.b64decode(pack.read_bytes(),validate=False)
    if sha(compressed)!=expected_sha:raise ValueError('SOURCE_PACK_HASH')
    data=json.loads(gzip.decompress(compressed))
    return {n:base64.b64decode(v)for n,v in data['files'].items()}
def grids(files,receipt):
    result={}
    for name,data in files.items():
        if not name.startswith('native/'+receipt+'-'):continue
        with zipfile.ZipFile(io.BytesIO(data))as z:
            if z.testzip()is not None:raise ValueError('SOURCE_ZIP_CRC')
            for member in z.namelist():
                if not member.endswith('.xml'):continue
                raw=z.read(member)
                for enc in ['utf-8','cp949','euc-kr']:
                    try:text=raw.decode(enc);assert text.encode(enc)==raw;break
                    except(UnicodeError,AssertionError):pass
                else:raise ValueError('SOURCE_ENCODING_UNVERIFIED')
                g=Grid();g.feed(text);result[member]=(g,sha(raw),sha(data))
    return result
def verify(control,subject,source):
    outcome=dict(receipt=control['receipt'],cohort=control.get('cohort','new100'),record_type=control.get('record_type','financial_field'),metric=control['metric'],scope=control['scope'],source_location=f"{control['member']}#table{control['table']},row{control['row']},col{control['column']}",amount='UNVERIFIED',selection='UNVERIFIED',metadata='UNVERIFIED',verdict='UNVERIFIED',reason='')
    outcome.update(raw_literal=control.get('literal',''),raw_account=control.get('account_literal',''),unit=control.get('unit',''),period_start=control.get('period_start',''),period_end=control.get('period_end',''),basis=control.get('basis',''),statement=control.get('statement',''),source_value='',extracted_value='',extraction_coverage='UNVERIFIED')
    if control.get('semantic_verdict')!='PASS':outcome['reason']=control.get('reason','SEMANTIC_REVIEW_MISSING');return outcome,None
    if not control.get('header_proofs')or not control.get('semantic_rationale'):
        outcome['reason']='SEMANTIC_HEADER_OR_RATIONALE_MISSING';return outcome,None
    try:
        g,member_sha,archive_sha=source[control['member']]
        if(member_sha,archive_sha)!=(control['member_sha256'],control['archive_sha256']):raise ValueError('SOURCE_IDENTITY')
        table=g.tables[control['table']];row=table['rows'][control['row']]
        if row[control['column']]!=control['literal'] or row[0]!=control['account_literal']:raise ValueError('LITERAL_OR_ACCOUNT_LOCATION')
        # Explicit human-reviewed raw header snippets, with no inferred dates.
        for proof in control['header_proofs']:
            raw_table=g.tables[proof['table']];text=raw_table['context']+' '+' '.join(' '.join(r)for r in raw_table['rows'])
            if proof['literal']not in text:raise ValueError('HEADER_PROOF_NOT_AT_SOURCE')
        expected=normalize(control['literal'],control['unit'],control.get('negative_account',False))
        outcome['source_value']=str(expected)
        outcome['selection']='PASS'
        preview=[r for r in subject if(r['metric'],r['scope'],r['source_member'])==(control['metric'],control['scope'],control['member'])]
        if len(preview)==1:outcome['extracted_value']=str(preview[0]['amount_krw'])
        for corroboration in control.get('corroborating_sources',[]):
            other,other_sha,_=source[corroboration['member']]
            other_row=other.tables[corroboration['table']]['rows'][corroboration['row']]
            if other_sha!=corroboration['member_sha256'] or other_row[corroboration['column']]!=corroboration['literal'] or other_row[0]!=corroboration['account_literal']:raise ValueError('CORROBORATING_SOURCE_LOCATION')
            if(corroboration['scope'],corroboration['period_start'],corroboration['period_end'])!=(control['scope'],control['period_start'],control['period_end']):raise ValueError('CORROBORATION_PERIOD_OR_SCOPE')
            other_amount=normalize(corroboration['literal'],corroboration['unit'],corroboration.get('negative_account',False))
            if other_amount!=expected:
                outcome['reason']='INDEPENDENT_CROSS_MEMBER_CONFLICT';return outcome,None
        if control.get('hold_reason'):
            outcome['reason']=control['hold_reason'];return outcome,None
        matches=[r for r in subject if(r['metric'],r['scope'],r['source_member'])==(control['metric'],control['scope'],control['member'])]
        if len(matches)!=1:
            outcome['extraction_coverage']='FAIL'if not matches else'UNVERIFIED'
            outcome['reason']='PROVED_SOURCE_VALUE_NOT_EXTRACTED'if not matches else'SUBJECT_AMBIGUOUS'
            return outcome,None
        outcome['extraction_coverage']='PASS'
        row=matches[0];outcome['source_value']=str(expected);outcome['extracted_value']=str(row['amount_krw'])
        if row.get('structural_status')!='PASS' or row.get('amendment_region')not in {'FILED_BODY','AFTER','ORIGINAL_FILED'}:
            outcome['reason']='STRUCTURE_OR_FILED_REGION_UNVERIFIED';return outcome,None
        if control['report_period']=='FY' and row.get('fiscal_year')!=int(control['period_end'][:4]):raise ValueError('FISCAL_IDENTITY_MISMATCH')
        if Decimal(str(row['amount_krw']))!=expected:outcome.update(amount='FAIL',verdict='FAIL',reason='AMOUNT_MISMATCH');return outcome,None
        outcome['amount']='PASS'
        actual=(row['table_index'],row['row_index'],row['value_col'],row['period_start'],row['period_end'],row['measurement_basis'],row['period'],row['statement'],row['unit'],Decimal(str(row['unit_multiplier'])),row['source_member_sha256'],row['document_sha256'])
        wanted=(control['table'],control['row'],control['column'],control['period_start'],control['period_end'],control['basis'],control['report_period'],control['statement'],control['unit'],Decimal(UNITS[control['unit']]),member_sha,archive_sha)
        if actual!=wanted:outcome.update(metadata='FAIL',verdict='FAIL',reason='METADATA_MISMATCH');return outcome,None
        if row.get('backtest_eligible')is not False:raise ValueError('INVESTMENT_PROMOTION_REFUSED')
        outcome.update(metadata='PASS',verdict='PASS',reason='INDEPENDENT_LITERAL_AND_HUMAN_SEMANTIC_CONTROL')
        published={**row,'financial_source_literal_verdict':'PASS','semantic_selection_verdict':'PASS','review_contract':VERSION,'review_control_id':control['id'],'source_review_evidence':{'raw_cell':control['literal'],'raw_account':control['account_literal'],'unit':control['unit'],'header_proofs':control['header_proofs'],'semantic_rationale':control.get('semantic_rationale',''),'cohort':control.get('cohort','new100')},'official_publication_verdict':'UNVERIFIED','historical_identity_verdict':'UNVERIFIED','correction_chain_verdict':'UNVERIFIED','backtest_eligible':False,'availability_status':'UNVERIFIED'}
        return outcome,published
    except(KeyError,IndexError,ValueError,InvalidOperation)as error:
        outcome.update(verdict='FAIL',reason=str(error));return outcome,None
def audit(root):
    root=Path(root);manifest=json.loads((root/'source_manifest.json').read_text());controls=json.loads((root/'controls.json').read_text())['controls']
    extra_hashes={}
    for extra in manifest.get('additional_controls',[]):
        raw=(root/extra['path']).read_bytes()
        if sha(raw)!=extra['sha256']:raise ValueError('ADDITIONAL_FROZEN_CONTROL_HASH')
        controls.extend(json.loads(raw)['controls']);extra_hashes[extra['path']]=sha(raw)
    files={}
    for pack in manifest['packs']:
        for name,data in unpack(root/pack['path'],pack['compressed_sha256']).items():
            if name.startswith(('results/','native/','collection/','quality/')):
                if name in files and files[name]!=data:raise ValueError('PACK_SOURCE_COLLISION')
                files[name]=data
    replacement={}
    if manifest.get('subject_override'):
        obj=manifest['subject_override'];raw=base64.b64decode((root/obj['path']).read_bytes())
        if sha(raw)!=obj['compressed_sha256']:raise ValueError('CANDIDATE_SUBJECT_HASH')
        payload=json.loads(gzip.decompress(raw))
        if payload['new_HTTP_calls']!=0:raise ValueError('REPLAY_MUST_NOT_RECOLLECT')
        replacement=payload['subjects']
        if set(replacement)!={Path(k).stem for k in files if k.startswith('results/')}:raise ValueError('REPLAY_RECEIPT_POPULATION_CHANGED')
        if any(s['parser_version']!=obj['parser_version']for s in replacement.values()):raise ValueError('REPLAY_PARSER_VERSION')
    details=[];published={};cache={}
    for c in controls:
        receipt=c['receipt']
        if receipt not in cache:cache[receipt]=grids(files,receipt)
        subjects=(replacement[receipt]if replacement else json.loads(files['results/'+receipt+'.json']))['rows']
        result,row=verify(c,subjects,cache[receipt]);details.append(result)
        if row is not None:
            key=(receipt,row['scope'],row['metric'],row['period_start'],row['period_end'])
            if key in published:raise ValueError('DUPLICATE_PUBLICATION_CONTROL')
            published[key]=row
    control_sha=sha((root/'controls.json').read_bytes());code_sha=sha(Path(__file__).read_bytes());manifest_sha=sha((root/'source_manifest.json').read_bytes())
    for row in published.values():row.update(review_controls_sha256=control_sha,additional_review_controls_sha256=extra_hashes,review_code_sha256=code_sha,review_source_manifest_sha256=manifest_sha)
    fields=[d for d in details if d['record_type']=='financial_field']
    counts={v:sum(d['verdict']==v for d in fields)for v in ['PASS','FAIL','UNVERIFIED']}
    documents={}
    for receipt in sorted({c['receipt']for c in controls}):
        ds=[d for d in details if d['receipt']==receipt]
        documents[receipt]='FAIL'if any(d['verdict']=='FAIL'for d in ds)else'UNVERIFIED'if any(d['verdict']=='UNVERIFIED'for d in ds)else'PASS'
    doc_counts={v:sum(d==v for d in documents.values())for v in ['PASS','FAIL','UNVERIFIED']}
    cohorts={}
    for cohort in sorted({d['cohort']for d in details}):
        subset=[d for d in details if d['cohort']==cohort];rs={d['receipt']for d in subset}
        cohorts[cohort]=dict(documents=len(rs),financial_fields={v:sum(d['verdict']==v and d['record_type']=='financial_field'for d in subset)for v in counts},document_counts={v:sum(documents[r]==v for r in rs)for v in counts})
    return dict(contract=VERSION,controls_sha256=control_sha,review_code_sha256=code_sha,source_manifest_sha256=manifest_sha,counts=counts,cohorts=cohorts,extraction_coverage_counts={v:sum(d['extraction_coverage']==v for d in fields)for v in counts},reviewed_documents=len(documents),document_counts=doc_counts,document_verdicts=documents,source_review_scope='Only frozen reviewed items; never entire document PIT or population accuracy',published_eligible_fields=len(published),backtest_eligible=False,investment_PIT='0/6'),details,list(published.values())
def check_publication(audit_root,rows):
    repo=audit_root.parents[2]
    status=json.loads((repo/'data/status/dart_legacy_validation100_status.json').read_text())
    if status['automatic_collection']!='HOLD' or status['automatic_publication']!='HOLD' or status['investment_PIT']!='0/6':raise ValueError('HOLD_AND_PIT_MUST_STAY_CLOSED')
    ledger=json.loads((audit_root/'publication_manifest.json').read_text())
    paths=[item['path']for item in ledger['files']]
    if len(paths)!=len(set(paths)):raise ValueError('DUPLICATE_LEDGER_PATH')
    if any(not(repo/p).resolve().is_relative_to(repo.resolve())for p in paths):raise ValueError('PUBLICATION_PATH_ESCAPE')
    metric_root=repo/ledger['metric_directory']
    if not metric_root.resolve().is_relative_to(repo.resolve()):raise ValueError('METRIC_PATH_ESCAPE')
    metric_paths={str(p.relative_to(repo))for p in metric_root.glob('*.json')}
    if metric_paths!={p for p in paths if '/metrics/'in p}:raise ValueError('UNLISTED_PUBLICATION_FILE')
    expected={}
    for row in rows:expected.setdefault(row['rcept_no'],[]).append(row)
    found={}
    for item in ledger['files']:
        p=repo/item['path']
        if sha(p.read_bytes())!=item['sha256']:raise ValueError('PUBLISHED_FILE_HASH')
        obj=json.loads(p.read_text())
        if '/metrics/'in item['path']:
            if obj['rows']!=expected.get(obj['rcept_no']):raise ValueError('PUBLISHED_UNREVIEWED_OR_DIFFERENT_ROWS')
            found[obj['rcept_no']]=obj['rows']
        if '/quality/'in item['path'] and(obj['backtest_eligible']is not False or obj['availability_status']!='UNVERIFIED'):raise ValueError('QUALITY_PIT_PROMOTION')
    if found!=expected:raise ValueError('PUBLICATION_SUBSET_INCOMPLETE')
    if status['published_fields']!=len(rows) or status['published_documents']!=len(expected):raise ValueError('PUBLICATION_COUNTS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args();summary,details,rows=audit(a.root)
    if a.check:
        if summary!=json.loads((a.root/'review_summary.json').read_text()):raise ValueError('REVIEW_REPRODUCTION_DIFFERS')
        if rows!=json.loads((a.root/'reviewed_rows.json').read_text()):raise ValueError('PUBLICATION_REPRODUCTION_DIFFERS')
        if (a.root/'publication_manifest.json').exists():check_publication(a.root,rows)
    else:
        (a.root/'review_summary.json').write_text(json.dumps(summary,indent=2)+'\n');(a.root/'reviewed_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        (a.root/'field_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary));sys.exit(1 if summary['counts']['FAIL']else 0)
