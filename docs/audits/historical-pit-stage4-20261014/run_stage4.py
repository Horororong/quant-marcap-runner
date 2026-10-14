"""Bounded independent primary-document audit; no production financial parsing.

Stored index dates and corporate-name intervals are leads, never publication or
historical-security attestations. Source bytes are checked before XML inspection.
Production gate probes are containment checks, separately from certification.
"""
import argparse, collections, csv, hashlib, importlib.util, json, re, zipfile
from datetime import date, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

HOME = Path(__file__).resolve().parent
REPO = HOME.parents[2]
def digest(b): return hashlib.sha256(b).hexdigest()
def text(e): return ' '.join(''.join(e.itertext()).split())
def normalize_legal_name(s):
    # Only legal-form typography; never historical aliases or fuzzy matching.
    return re.sub(r'주식회사|\(주\)|㈜|\s+', '', s).strip()
def strict_date(s):
    m = re.fullmatch(r'\s*(\d{4})\s*(?:년|[./-])\s*(\d{1,2})\s*(?:월|[./-])\s*(\d{1,2})\s*일?\s*[.]?\s*', s)
    if not m: return ''
    try: return date(*map(int, m.groups())).isoformat()
    except ValueError: return ''
def load_source(folder, s):
    manifest = {x['sample_id']: x for x in json.loads((folder/'source_manifest.json').read_text())}
    entry = manifest[s['sample_id']]
    filename = Path(entry['artifact_member']).name
    path = folder/'originals'/filename
    assert digest(path.read_bytes()) == entry['sha256'] == s['document_sha256']
    docs = []
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert z.namelist() == [m['name'] for m in entry['members']]
        for member in entry['members']:
            raw = z.read(member['name']); assert digest(raw) == member['sha256']
            for encoding in ['utf-8', 'cp949', 'euc-kr']:
                try:
                    decoded = raw.decode(encoding)
                    assert decoded.encode(encoding) == raw
                    break
                except UnicodeError: continue
            else: raise ValueError('No lossless source encoding: '+member['name'])
            # Bare ampersands are an XML transport defect. Original bytes stay intact.
            structural = re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)', '&amp;', decoded)
            docs.append((member['name'], ET.fromstring(structural), member['sha256'], encoding))
    return entry, docs
def inspect(s, entry, docs):
    member, root, member_sha, encoding = docs[0]
    nodes = list(root.iter()); company = root.find('COMPANY-NAME')
    assert company is not None
    prefix = ' '.join(text(n) for n in nodes if n.tag in ['P', 'P-SMALL', 'P-MEDIUM', 'TITLE', 'COVER-TITLE'])[:1800]
    correction = '정정신고' in re.sub(r'\s+', '', prefix)
    dates = []; original = ''; original_raw = ''; original_loc = ''
    amendment = ''; amendment_loc = ''
    snippets = []
    for i, node in enumerate(nodes):
        if node.tag not in ['P', 'P-SMALL', 'P-MEDIUM', 'TITLE', 'SUBTITLE', 'COVER-TITLE']: continue
        value = text(node); d = strict_date(value)
        if d and i < 180: dates.append({'value':d, 'location':f'ELEMENT[{i}]/{node.tag}'})
        if '최초제출일' in re.sub(r'\s+', '', value) and not original_raw:
            original_raw = value.split(':', 1)[-1].strip()
            original = strict_date(original_raw); original_loc = f'ELEMENT[{i}]/{node.tag}'
        if re.search('상호의 변경|사명변경|상장되어 거래|합 병 일 자', value):
            snippets.append({'location':f'ELEMENT[{i}]/{node.tag}', 'text':value[:700], 'truncated':len(value)>700})
    if correction:
        # The amendment date is in a header TABLE, not the reused original COVER.
        # Stop at the first amendment-item label; never substitute a body date.
        marker=next((i for i,n in enumerate(nodes) if n.tag=='TITLE' and '정정신고' in re.sub(r'\s+','',text(n))),None)
        if marker is not None:
            for i in range(marker+1,len(nodes)):
                n=nodes[i];v=text(n)
                if n.tag in ['P','P-SMALL'] and '정정대상' in v:break
                if n.tag in ['TD','TE','TU','P','P-SMALL'] and strict_date(v):
                    amendment,amendment_loc=strict_date(v),f'ELEMENT[{i}]/{n.tag}';break
    covers = [{'location':f'COVER[{i}]', 'text':text(n)} for i,n in enumerate(root.iter('COVER'))]
    return {'sample_id':s['sample_id'], 'rcept_no':s['rcept_no'],
        'document_company_name':text(company), 'document_dart_corp_code':company.attrib.get('AREGCIK',''),
        'company_location':f'{member}#COMPANY-NAME/@AREGCIK', 'source_member':member,
        'source_member_sha256':member_sha, 'document_sha256':entry['sha256'], 'encoding':encoding,
        'corrective_document':correction, 'declared_document_date':amendment if correction else dates[0]['value'] if dates else '',
        'declared_original_submission_date':original, 'original_date_raw':original_raw,
        'original_date_location':original_loc, 'declared_correction_date':amendment,
        'correction_date_location':amendment_loc, 'covers':covers, 'history_snippets':snippets,
        'source_date_is_publication_attestation':False}
def write_json(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
def main():
    p=argparse.ArgumentParser()
    for k in ['original40','holdout20','replay','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    controls=json.loads((HOME/'selection20.json').read_text())
    preservation=json.loads((HOME/'preservation_controls.json').read_text())
    for name, expected in preservation['repo_files'].items():
        assert digest((REPO/name).read_bytes())==expected, ('Protected baseline changed',name)
    assert len(preservation['replay_files'])==60
    for name, expected in preservation['replay_files'].items():
        assert digest((a.replay/name).read_bytes())==expected, ('Existing replay changed',name)
    with (REPO/'docs/audits/financial-extraction-stage3-20261014/results/protected518.csv').open(newline='') as f:
        protected=list(csv.DictReader(f))
    assert len(protected)==518
    financial=json.loads((REPO/'docs/audits/financial-extraction-stage3-20261014/results/validation_summary.json').read_text())
    assert financial['holdout64_targets']=={'PASS':64,'FAIL':0,'UNVERIFIED':0}
    allsamples={}; folders={}
    for folder in [a.original40,a.holdout20]:
        for s in json.loads((folder/'selection.json').read_text())['samples']:
            assert s['sample_id'] not in allsamples
            allsamples[s['sample_id']]=s;folders[s['sample_id']]=folder
    assert len(allsamples)==60
    # Check all sixty original files, not only the selected twenty.
    for sid,s in allsamples.items():load_source(folders[sid],s)
    spec=importlib.util.spec_from_file_location('stage4_gate_probe',REPO/'scripts/legacy_native_financials.py')
    import sys
    sys.path.insert(0,str(REPO/'scripts'))
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    facts=[];details=[];signals=[]
    for selected in controls['samples']:
        sid=selected['sample_id'];s=allsamples[sid]
        entry,docs=load_source(folders[sid],s);f=inspect(s,entry,docs);facts.append(f)
        manual=json.loads((HOME/'document_identity_controls.json').read_text())[sid]
        for k,v in manual.items():assert f[k]==v, ('Independent document control disagrees',sid,k,f[k],v)
        corp='PASS' if f['document_dart_corp_code']==s['corp_code'] else 'FAIL'
        name_match=normalize_legal_name(s['corp_name'])==normalize_legal_name(f['document_company_name'])
        # Cover/header identity is not an effective-dated security mapping.
        mapping='FAIL' if corp=='FAIL' else 'UNVERIFIED'
        doc_date=date.fromisoformat(s['rcept_dt'])
        scenarios=[('before_index_date',doc_date-timedelta(days=1)),('on_index_date',doc_date),('after_index_date',doc_date+timedelta(days=1))]
        if f['declared_original_submission_date'] and f['declared_correction_date']:
            before=date.fromisoformat(f['declared_original_submission_date']);after=date.fromisoformat(f['declared_correction_date'])
            if before<after:scenarios.append(('declared_original_to_correction_gap',before))
        replay=json.loads((a.replay/(sid+'.json')).read_text())
        for scenario,day in scenarios:
            evidence={'identity_verified':False,'correction_chain_verified':False,'publication_verified':False,
                'rcept_no':s['rcept_no'],'document_sha256':s['document_sha256']}
            opened=any(gate.backtest_usable(row,day.isoformat(),evidence) for row in replay['rows']) if replay['rows'] else None
            assert opened is not True, ('Unverified source opened native gate',sid,scenario)
            signals.append({'sample_id':sid,'rcept_no':s['rcept_no'],'scenario':scenario,'signal_date':day.isoformat(),
                'date_basis':'Index or original declared date; official public boundary UNVERIFIED',
                'independent_availability':'UNVERIFIED','audit_usable':False,'native_gate_usable':opened,
                'containment_test':'PASS' if replay['rows'] else 'UNVERIFIED',
                'probe_reason':'Actual emitted rows tested' if replay['rows'] else 'No emitted financial row; no vacuous PASS',
                'historical_availability_certified':False})
        details.append({'sample_id':sid,'risk_category':selected['risk_category'],'stored_corp_name':s['corp_name'],
            'document_corp_name':f['document_company_name'],'dart_corp_code':s['corp_code'],
            'source_dart_corp_code':f['document_dart_corp_code'],'corp_code_verdict':corp,
            'stored_stock_code':s['stock_code'],'historical_stock_code_verified':'',
            'document_name_matches_stored_name':name_match,'name_difference_is_wrong_security_proof':False,
            'name_effective_at_corrected_filing':'UNVERIFIED', 'mapping_verdict':mapping,
            'historical_listing_verdict':'UNVERIFIED','listing_status_at_signal':'UNKNOWN',
            'delisting_effective_date_verified':'','name_merger_history_verdict':'UNVERIFIED',
            'rcept_no':s['rcept_no'],'index_receipt_date':s['rcept_dt'],
            'declared_original_submission_date':f['declared_original_submission_date'],
            'original_date_raw':f['original_date_raw'],'original_date_format_verdict':
                ('PASS' if f['declared_original_submission_date'] else 'FAIL') if f['original_date_raw'] else 'UNVERIFIED',
            'original_rcept_no_verified':'','corrective_document':f['corrective_document'],
            'correction_rcept_no':s['rcept_no'] if f['corrective_document'] else '',
            'declared_correction_date':f['declared_correction_date'],'correction_chain_verdict':'UNVERIFIED',
            'official_public_date_verified':'','official_public_datetime_verified':'',
            'publication_verdict':'UNVERIFIED','calendar_verified':False,'next_trading_day_available':'',
            'backtest_eligible':False,'overall_verdict':mapping,
            'checked_at':controls['checked_at'],'evidence_location':f['company_location'],
            'document_sha256':s['document_sha256'],
            'official_url':f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={s["rcept_no"]}',
            'official_url_attempted':sid in ['S01','S02'],
            'official_url_status':'Tool access unavailable; preserved original used' if sid in ['S01','S02'] else 'NOT_ATTEMPTED after same-host failures; preserved original used',
            'official_secondary_evidence_ids':';'.join(selected.get('official_evidence_ids',[])),
            'reason':'Source identity observed; effective-dated ticker/tradability, exhaustive amendment chain and actual publication not attested. No same-day or next-session release inferred.'})
    assert len(details)==20 and len({r['rcept_no'] for r in details})==20
    for name, rows in [('stage4_details.csv',details),('signal_tests.csv',signals)]:
        with (a.output/name).open('w',newline='',encoding='utf-8-sig') as out:
            writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(a.output/'source_facts.json',facts)
    count=lambda k:{v:sum(r[k]==v for r in details)for v in ['PASS','FAIL','UNVERIFIED']}
    result={'baseline_sha':controls['baseline_sha'],'samples':20,'mapping':count('mapping_verdict'),
        'correction_chain':count('correction_chain_verdict'),'publication':count('publication_verdict'),
        'overall':count('overall_verdict'),'corp_code_source_comparison':count('corp_code_verdict'),
        'name_differences':sum(not r['document_name_matches_stored_name']for r in details),
        'corrective_documents':sum(r['corrective_document']for r in details),
        'original_date_format':count('original_date_format_verdict'),
        'native_containment_scenarios':len(signals),
        'native_containment_pass':sum(r['containment_test']=='PASS' for r in signals),
        'native_containment_unverified':sum(r['containment_test']=='UNVERIFIED' for r in signals),
        'actual_public_boundary_tests':'UNVERIFIED; provisional-date probes are not publication certification',
        'delisted_retention':'All selected receipts retained; actual universe/official delisting certification UNVERIFIED',
        'financial_protection':{'protected518_bytes':'PASS','holdout64_control_and_results_bytes':'PASS',
            'financial_production_files_unchanged':'PASS','all60_original_zip_and_member_sha_crc':'PASS',
            'replay60_result_bytes':'PASS'},'backtest_eligible_samples':0,'certification_rate':0.0}
    write_json(a.output/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
