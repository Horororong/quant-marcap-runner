"""Independent official-reply verification; never imports the collector/parser.

Source API fields prove receipt identity/day only. Version chronology and names
alone do not attest predecessor links, public clock, or KRX tradability.
"""
import csv,hashlib,json,re,zipfile
from pathlib import Path
HOME=Path(__file__).resolve().parent
REPO=HOME.parents[2]
root=HOME/'results'
state=json.loads((root/'run_state.json').read_text())
assert state['code_sha']=='651e6a48a9b0b75822ab244a2ab9e8266d026d9c'
assert state['status']=='COMPLETE_WITH_CERTIFICATION_GAPS' and state['pilot_complete'] is True
manifest=json.loads((root/'response_manifest.json').read_text())
assert len(manifest)==state['requests']==22
selection=json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/selection20.json').read_text())['samples']
facts={s['sample_id']:s for s in json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/results/source_facts.json').read_text())}
assert set(state['completed_samples'])=={s['sample_id']for s in selection}
by_sample={s['sample_id']:[]for s in selection}
for entry in manifest:
    path=root/entry['file'];assert path.resolve().is_relative_to(root.resolve())
    raw=path.read_bytes();assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
    assert b'crtfc_key' not in raw
    d=json.loads(raw);q=entry['parameters']
    assert set(q)=={'corp_code','bgn_de','end_de','last_reprt_at','pblntf_ty','sort','sort_mth','page_count','page_no'}
    assert q['last_reprt_at']=='N' and q['pblntf_ty']=='A' and q['end_de']==state['end_date']
    assert entry['http_status']==200 and entry['dart_status']==d['status']=='000'
    assert int(d['page_no'])==int(q['page_no']) and int(d['page_count'])==100
    assert all(r['corp_code']==q['corp_code']==facts[entry['sample_id']]['document_dart_corp_code']for r in d['list'])
    by_sample[entry['sample_id']].append(d)
details=list(csv.DictReader((root/'stage5_details.csv').open(encoding='utf-8-sig')))
assert len(details)==20
total=0
for row in details:
    sid=row['sample_id'];pages=sorted(by_sample[sid],key=lambda d:int(d['page_no']))
    count=int(pages[0]['total_count']);pagecount=int(pages[0]['total_page'])
    assert [int(p['page_no'])for p in pages]==list(range(1,pagecount+1))
    assert all(int(p['total_count'])==count and int(p['total_page'])==pagecount for p in pages)
    filings=[r for p in pages for r in p['list']]
    assert len(filings)==len({r['rcept_no']for r in filings})==count
    target=[r for r in filings if r['rcept_no']==row['rcept_no']]
    assert len(target)==1 and target[0]['corp_code']==row['corp_code']
    assert row['rcept_no']==facts[sid]['rcept_no']
    assert target[0]['rcept_dt']==row['official_receipt_date'].replace('-','')
    assert row['api_response']==row['receipt_corp_match']==row['receipt_date']=='PASS'
    assert all(row[k]=='UNVERIFIED'for k in ['correction_chain','exact_public_time','daily_availability','historical_krx_mapping'])
    assert row['daily_available_date']=='' and row['backtest_eligible']=='False'
    total+=count
assert total==1240
# Original Stage4 evidence remains immutable, including source-date typo/gaps.
old=REPO/'docs/audits/historical-pit-stage4-20261014'
preserve=json.loads((old/'preservation_controls.json').read_text())
for name,h in preserve['repo_files'].items():assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==h,name
evidence=json.loads((old/'stage4_evidence_manifest.json').read_text())
for name,h in evidence['outputs'].items():assert hashlib.sha256((old/name).read_bytes()).hexdigest()==h['sha256'],name
print(json.dumps({'status':'PASS','official_reply_pages':22,'verified_samples':20,'listed_filings':1240,
    'receipt_corp_date_pass':20,'exact_clock_version_chain_daily_krx':'UNVERIFIED',
    'financial518_core64_and_stage4_preserved':True,'backtest_eligible':False}))
