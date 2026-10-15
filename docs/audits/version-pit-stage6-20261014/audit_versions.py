"""Independent primary XML identities/references and fail-closed daily policy.

No production financial parser/gate is imported. Root-reference certification
does not assert an immediate predecessor, intraday time, or legal ticker link.
"""
import argparse, base64, collections, csv, hashlib, io, json, re, zipfile
from datetime import date, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET
HOME = Path(__file__).resolve().parent
REPO = HOME.parents[2]
FOCUS = ['S01','S05','N12','N14','S39','S19']
def sha(raw): return hashlib.sha256(raw).hexdigest()
def txt(node): return ' '.join(''.join(node.itertext()).split())
def source_bytes(entry):
    stored=(HOME/entry['file']).read_bytes()
    if entry.get('transport_sha256'):assert sha(stored)==entry['transport_sha256']
    if entry.get('transport_encoding')=='base64':
        stored=base64.b64decode(b''.join(stored.splitlines()),validate=True)
    assert sha(stored)==entry['sha256']
    return stored
def strict_date(value):
    m = re.fullmatch(r'\s*(\d{4})\s*(?:년|[./-])\s*(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?\s*[.]?\s*', value)
    if not m: return ''
    try: return date(*map(int,m.groups())).isoformat()
    except ValueError: return ''
def read_document(entry):
    with zipfile.ZipFile(io.BytesIO(source_bytes(entry))) as z:
        assert z.testzip() is None
        docs=[]
        for member in entry['members']:
            raw=z.read(member['name']);assert sha(raw)==member['sha256']
            for encoding in ('utf-8','cp949','euc-kr'):
                try:
                    source=raw.decode(encoding);assert source.encode(encoding)==raw;break
                except UnicodeError:continue
            else:raise ValueError('lossless decoding unavailable')
            root=ET.fromstring(re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)','&amp;',source))
            docs.append((member,root,encoding))
    assert len(docs)==1, 'multiple members require manual primary-document identification'
    member,root,encoding=docs[0];nodes=list(root.iter());positions={id(n):i for i,n in enumerate(nodes)}
    company=root.find('COMPANY-NAME');assert company is not None and company.get('AREGCIK')==entry['corp_code']
    correction=root.find('.//CORRECTION');header=[];initial='';initial_raw='';initial_location='';target='';reason=''
    if correction is not None:
        for n in correction.iter():
            if n.tag not in ['P-SMALL','P','TITLE']:continue
            value=txt(n)
            if not value:continue
            if n.tag=='P-SMALL' and ('정정대상' in value or '정정사유' in value):
                header.append({'location':f'{member["name"]}#ELEMENT[{positions[id(n)]}]/{n.tag}','text':value})
                if '최초제출일' in value:
                    initial_raw=value.split(':',1)[-1].strip();initial=strict_date(initial_raw);initial_location=header[-1]['location']
                elif '정정대상' in value:target=value.split(':',1)[-1].strip()
                elif '정정사유' in value:reason=value.split(':',1)[-1].strip()
    cover=root.find('.//COVER');assert cover is not None
    periods={n.get('AUNIT'):n.get('AUNITVALUE','')for n in cover.iter() if n.get('AUNIT') in ['PERIODFROM','PERIODTO']}
    assert re.fullmatch(r'\d{8}',periods.get('PERIODTO',''))
    period_start=date.fromisoformat(periods['PERIODFROM'][:4]+'-'+periods['PERIODFROM'][4:6]+'-'+periods['PERIODFROM'][6:]).isoformat()
    period_end=date.fromisoformat(periods['PERIODTO'][:4]+'-'+periods['PERIODTO'][4:6]+'-'+periods['PERIODTO'][6:]).isoformat()
    witnesses=[]
    if correction is not None:
        for table in correction.iter('TABLE'):
            for row in table.findall('./THEAD/TR')+table.findall('./TBODY/TR'):
                cells=[txt(n)for n in row if n.tag in ['TD','TE','TU','TH']]
                witnesses.append({'location':f'{member["name"]}#ELEMENT[{positions[id(row)]}]/TR','cells':cells})
    history=[]
    for i,n in enumerate(nodes):
        value=txt(n)
        if n.tag in ['P','P-SMALL','TD','TE'] and re.search(r'상호의 변경|사명변경|상장되어|시장에 상장|상장폐지|상장일|합병일',value):
            history.append({'location':f'{member["name"]}#ELEMENT[{i}]/{n.tag}','text':value[:1200],'truncated':len(value)>1200})
    return {**entry,'company_name':txt(company),'document_corp_code':company.get('AREGCIK'),
            'document_name':txt(root.find('DOCUMENT-NAME')),'period_start':period_start,'period_end':period_end,
            'source_member':member['name'],'source_member_sha256':member['sha256'],'encoding':encoding,
            'is_correction':correction is not None,'initial_date':initial,'initial_date_raw':initial_raw,
            'initial_date_location':initial_location,'correction_target':target,'correction_reason':reason,
            'header_references':header,'correction_table_witnesses':witnesses,'history_mentions':history,
            'explicit_receipt_references':sorted(set(re.findall(r'20\d{12}',source))),
            'public_timestamp':'','historical_ticker_certified':False}
def certify_root(document, originals):
    # Explicit valid first-submission reference is required, never title-only.
    candidates=[x for x in originals if x['corp_code']==document['corp_code'] and
                document.get('period_start') and x.get('period_start')==document['period_start'] and
                x['period_end']==document['period_end'] and x['document_name']==document['document_name'] and
                x['receipt_date']==document['initial_date'] and not x['is_correction'] and
                not x['official_title'].startswith('[')]
    if document['is_correction'] and document['initial_date'] and len(candidates)==1:
        return 'CERTIFIED',candidates[0]['rcept_no']
    return 'CANDIDATE',''
def version_scope(family):
    # A first-submission reference proves a root relationship, not adjacency.
    # Sorting receipt numbers is display only; the preserved corpus does not
    # contain independently certified immediate-predecessor or completeness proof.
    ordered=sorted(family,key=lambda d:(d['receipt_date'],d['rcept_no']))
    adjacency=[{'from_receipt':prev['rcept_no'],'to_receipt':nxt['rcept_no'],
                'grade':'CANDIDATE',
                'reason':'immediate predecessor not explicitly identified; root reference does not prove adjacency'}
               for prev,nxt in zip(ordered,ordered[1:])]
    return adjacency,'UNVERIFIED'
def available_date(receipt_day, sessions):
    # No weekday arithmetic or default package calendar in the certified path.
    later=[d for d in sessions if d>receipt_day]
    return min(later) if later else ''
def select_version(documents,signal_day,sessions):
    # Filter disclosure date before ranking, including all later corrections.
    eligible=[d for d in documents if d['receipt_date']<signal_day and
              available_date(d['receipt_date'],sessions) and available_date(d['receipt_date'],sessions)<=signal_day]
    if not eligible:return {'receipt':'','reason':'NO_PUBLIC_PRIOR_DOCUMENT'}
    latest=max(d['receipt_date']for d in eligible);same_day=[d for d in eligible if d['receipt_date']==latest]
    if any(d['relationship_grade']!='CERTIFIED'for d in same_day):return {'receipt':'','reason':'UNPROVEN_VERSION'}
    if len(same_day)>1:
        amendments=[d for d in same_day if d['is_correction']]
        if len(amendments)!=1 or not all(d['rcept_no']==amendments[0]['root_receipt']for d in same_day if not d['is_correction']):
            return {'receipt':'','reason':'SAME_DAY_ORDER_UNPROVEN'}
        winner=amendments[0]
    else:winner=same_day[0]
    return {'receipt':winner['rcept_no'],'source_member_sha256':winner['source_member_sha256'],'reason':'RETROSPECTIVE_POLICY_ONLY'}
def investment_gate(selection,official_calendar,historical_mapping,version_certified):
    return bool(selection.get('receipt') and official_calendar and historical_mapping and version_certified)
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def verify_preservation():
    pins=HOME/'preservation_inputs.json'
    if pins.exists():
        for name,expected in json.loads(pins.read_text()).items():assert sha((REPO/name).read_bytes())==expected,name
    controls=json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/preservation_controls.json').read_text())
    for name,expected in controls['repo_files'].items():assert sha((REPO/name).read_bytes())==expected,name
    responses=json.loads((REPO/'docs/audits/dart-history-stage5-20261014/results/response_manifest.json').read_text())
    for r in responses:assert sha((REPO/'docs/audits/dart-history-stage5-20261014/results'/r['file']).read_bytes())==r['sha256']
    assert len(responses)==22
    return {'protected_financial_values':518,'core_targets':64,'stage5_raw_responses':22,'operating_parser_changes':False}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    preservation=verify_preservation()
    assessments={x['sample_id']:x for x in json.loads((REPO/'docs/audits/dart-history-stage5-20261014/results/assessments.json').read_text())}
    metadata={}
    for p in (REPO/'docs/audits/dart-history-stage5-20261014/results/raw').glob('*.json'):
        for row in json.loads(p.read_text())['list']:metadata[row['rcept_no']]=row
    docs=[]
    for entry in json.loads((HOME/'source_manifest.json').read_text()):
        d=read_document(entry);official=metadata[d['rcept_no']]
        assert official['corp_code']==d['document_corp_code']
        d['receipt_date']=date.fromisoformat(official['rcept_dt'][:4]+'-'+official['rcept_dt'][4:6]+'-'+official['rcept_dt'][6:]).isoformat()
        d['official_title']=official['report_nm'];d['official_rm']=official.get('rm','')
        d['official_url']='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+d['rcept_no'];docs.append(d)
    for d in docs:
        if d['is_correction']:d['relationship_grade'],d['root_receipt']=certify_root(d,docs)
        elif d['official_title'].startswith('['):d['relationship_grade'],d['root_receipt']='CANDIDATE',''
        else:d['relationship_grade'],d['root_receipt']='CERTIFIED',d['rcept_no']
    # Exchange package and archived panel are corroborating *secondary* sources.
    import pandas as pd, exchange_calendars as xc
    price_path=REPO/'data/krx_equities/yearly/marcap-2007.parquet'
    panel=pd.read_parquet(price_path,columns=['Date','Code','Name','Market','Close','Volume'])
    observed=sorted(set(panel.Date.dt.strftime('%Y-%m-%d')))
    package_sessions=xc.get_calendar('XKRX',start='2007-01-01',end='2007-12-31').sessions.strftime('%Y-%m-%d').tolist()
    calendar={'official_session_calendar_verdict':'UNVERIFIED','observed_sessions':observed,
              'price_source_sha256':sha(price_path.read_bytes()),'price_source_bytes':price_path.stat().st_size,
              'price_rows':len(panel),'date_code_duplicates':int(panel.duplicated(['Date','Code']).sum()),
              'exchange_calendars_version':xc.__version__,'package_sessions':package_sessions,
              'observed_minus_package':sorted(set(observed)-set(package_sessions)),
              'package_minus_observed':sorted(set(package_sessions)-set(observed)),
              'confidence':'corroborated secondary observations; legal listing and official calendar not certified'}
    write_json(a.output/'calendar_research.json',calendar)
    chains=[];details=[];signals=[]
    for sid in FOCUS:
        family=[d for d in docs if d['sample_id']==sid];target=next(d for d in family if d['origin']=='preserved_original60')
        assessment=assessments[sid];candidates=assessment['version_candidates']
        # The source corpus includes every scoped title-family candidate, not an assertion of all history.
        assert {x['rcept_no']for x in family}=={x['rcept_no']for x in candidates}
        edges=[{'from_receipt':d['root_receipt'],'to_receipt':d['rcept_no'],'grade':d['relationship_grade'],
                'relation_kind':'explicit_first_submission_root_reference','basis_location':d['initial_date_location'],
                'initial_date_raw':d['initial_date_raw'],'source_member_sha256':d['source_member_sha256']}for d in family if d['is_correction']]
        adjacency,full_chain=version_scope(family)
        stock=assessment.get('stock_code') or metadata[target['rcept_no']].get('stock_code','')
        observed_security=panel.loc[panel.Code.astype(str)==stock]
        historical={'stock_code_lead':stock,'source':'archived secondary marcap panel',
                    'observed_rows':len(observed_security),'observed_names':observed_security.Name.unique().tolist(),
                    'legal_listing_state':'UNVERIFIED','corp_security_link':'UNVERIFIED',
                    'name_merger_history':'partial issuer disclosures and secondary observed names; not a complete effective-dated registry'}
        claims={'sample_id':sid,'target_receipt':target['rcept_no'],'relationship_grade':target['relationship_grade'],
                'claim_scope':'document identity and explicit first-submission root references only; no universal correction-absence assertion',
                'documents':family,'root_reference_edges':edges,'immediate_predecessor_edges':adjacency,
                'scoped_candidates':candidates,'query_begin':assessment['scope_begin'],'query_end':assessment['scope_end'],
                'query_category':'A','absence_outside_query_or_title_family':'UNVERIFIED','historical_security':historical,
                'full_chain_verdict':full_chain,
                'investment_eligible':False}
        chains.append(claims)
        for d in family:
            next_observed=available_date(d['receipt_date'],observed)
            checks=[('document_identity','PASS',d['company_name'],d['source_member']+'#COMPANY-NAME/@AREGCIK'),
                    ('official_receipt_date','PASS',d['receipt_date'],'Stage5/raw/'+sid+'_page001.json#'+d['rcept_no']),
                    ('version_root_relationship','PASS'if d['is_correction']and d['relationship_grade']=='CERTIFIED'else'UNVERIFIED',d['relationship_grade']if d['is_correction']else'NOT_A_CORRECTION_ROOT_REFERENCE',d['initial_date_location']or d['source_member']+'#COVER'),
                    ('first_submission_date_format','FAIL'if d['is_correction']and not d['initial_date']else'PASS'if d['is_correction']else'UNVERIFIED',d['initial_date_raw'],d['initial_date_location']),
                    ('exact_public_timestamp','UNVERIFIED','','API returns date only'),
                    ('official_historical_sessions','UNVERIFIED','','official 2007 calendar not retrieved'),
                    ('certified_daily_available_date','UNVERIFIED','','official calendar missing; observed candidate '+next_observed),
                    ('historical_security_link','UNVERIFIED',stock,'no effective-dated official ticker/legal-state chain'),
                    ('investment_backtest_approval','UNVERIFIED','BLOCKED','calendar/security/version certification gaps')]
            for check,verdict,value,location in checks:
                details.append({'sample_id':sid,'corp_code':d['corp_code'],'company_name':d['company_name'],'stock_code_lead':stock,
                                'rcept_no':d['rcept_no'],'period_start':d['period_start'],'period_end':d['period_end'],
                                'check':check,'verdict':verdict,'relationship_grade':d['relationship_grade'],'value':value,
                                'official_receipt_date':d['receipt_date'],'observed_policy_candidate_date':next_observed,
                                'evidence_location':location,'source_sha256':d['sha256'],'source_member_sha256':d['source_member_sha256'],
                                'official_url':d['official_url'],'investment_eligible':False})
            boundary=[('before_public_date',(date.fromisoformat(d['receipt_date'])-timedelta(days=1)).isoformat()),
                      ('on_public_date',d['receipt_date']),('first_observed_session_after_public_date',next_observed)]
            for scenario,signal_day in boundary:
                selected=select_version(family,signal_day,observed)
                future=[x['rcept_no']for x in family if x['receipt_date']>=signal_day]
                assert selected['receipt']not in future
                investment=investment_gate(selected,False,False,target['relationship_grade']=='CERTIFIED');assert not investment
                signals.append({'sample_id':sid,'boundary_receipt':d['rcept_no'],'scenario':scenario,'signal_day':signal_day,
                                'selected_receipt':selected['receipt'],'selected_source_member_sha256':selected.get('source_member_sha256',''),
                                'future_or_same_day_receipts_blocked':';'.join(future),'policy_test_verdict':'PASS',
                                'exact_public_time':'UNVERIFIED','official_calendar_verdict':'UNVERIFIED',
                                'daily_certification_verdict':'UNVERIFIED','investment_eligible':investment,
                                'scope':'retrospective secondary-calendar policy simulation', 'selection_reason':selected['reason']})
    write_json(a.output/'stage6_version_chains.json',{'samples':chains,'no_title_only_merging':True,'immediate_predecessor_not_inferred':True})
    for name,rows in [('stage6_details.csv',details),('signal_tests.csv',signals)]:
        with (a.output/name).open('w',newline='')as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'samples':len(chains),'primary_documents':len(docs),'new_downloads':6,
             'target_relationship_grades':dict(collections.Counter(x['relationship_grade']for x in chains)),
             'document_relationship_grades':dict(collections.Counter(d['relationship_grade']for d in docs)),
             'root_reference_edge_grades':dict(collections.Counter(e['grade']for c in chains for e in c['root_reference_edges'])),
             'immediate_predecessor_edge_grades':dict(collections.Counter(e['grade']for c in chains for e in c['immediate_predecessor_edges'])),
             'details_counts':dict(collections.Counter(d['verdict']for d in details)),
             'counts_by_check':{k:dict(collections.Counter(d['verdict']for d in details if d['check']==k))for k in sorted({d['check']for d in details})},
             'policy_boundary_tests':len(signals),'policy_test_failures':0,'official_calendar_certified':0,
             'exact_time_certified':0,'historical_security_certified':0,'daily_available_dates_certified':0,
             'investment_approved':0,'preservation':preservation}
    write_json(a.output/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
