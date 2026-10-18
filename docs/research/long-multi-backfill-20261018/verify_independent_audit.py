"""Compare manually reviewed primary cells, NOT a financial parser re-run."""
import argparse,base64,csv,gzip,hashlib,io,json
from collections import Counter
from decimal import Decimal
from pathlib import Path
HOME=Path(__file__).resolve().parent
def unpack(name):
    return gzip.decompress(base64.b64decode((HOME/'sources'/name).read_bytes()))
def original(name):return unpack('main_evidence-recovered__'+name+'.gz.b64')
def decimal(literal):
    s=literal.strip().replace(',','')
    if not s or s=='-':return None
    return -Decimal(s[1:-1]) if s.startswith('(') and s.endswith(')') else Decimal(s)
def verify(output):
    output.mkdir(parents=True,exist_ok=False)
    grids=json.loads(gzip.decompress(base64.b64decode(original('source_grids.json.gz.b64'))))
    metrics=list(csv.DictReader(io.StringIO(original('selected_metrics.csv').decode())))
    states={r['rcept_no']:r for r in csv.DictReader(io.StringIO(original('selected_state.csv').decode()))}
    plan=json.loads(original('selection.json'));controls=json.loads((HOME/'independent_controls.json').read_bytes())['controls']
    details=[];checks=[]
    for c in controls:
        g=next(x for x in grids if x['receipt']==c['receipt'] and x['member']==c['member'])
        t=next(x for x in g['tables'] if x['index']==c['table'])
        literal=t['rows'][c['row']][c['column']]
        assert literal==c['original_literal'],('Control/source changed',c)
        found=[r for r in metrics if (r['rcept_no'],r['scope'],r['metric'])==(c['receipt'],c['scope'],c['metric'])]
        assert len(found)<=1,'duplicate metric key'
        r=found[0] if found else {};expected=decimal(literal)*c['multiplier'];raw=r.get('amount_krw','')
        actual=Decimal(raw) if raw else None
        verdict=('UNVERIFIED' if c['currency']!='KRW' else 'FAIL' if actual is None or actual!=expected else 'PASS')
        literal_verdict='UNVERIFIED';selected_literal='';selected_context=''
        if r:
            # Identify exact chosen raw cell; independently normalize its LOCAL
            # unit. Do not inherit the parser's multiplier or sign handling.
            rt=next(x for x in g['tables'] if x['index']==int(r['table_index']))
            selected_literal=rt['rows'][int(r['row_index'])][int(r['value_col'])]
            selected_context=rt['context'][-1200:]
            local=1 if '단위 : 원' in selected_context or '단위:원' in selected_context else None
            if local is None and ('백만원' in selected_context):local=1000000
            if local is None and ('천원' in selected_context):local=1000
            d=decimal(selected_literal)
            if local is not None and d is not None and actual is not None:literal_verdict='PASS' if d*local==actual else 'FAIL'
        details.append(dict(**c,original_amount=str(expected),extracted_amount=raw,verdict=verdict,source_literal_verdict=literal_verdict,selected_literal=selected_literal,extracted_period_end=r.get('period_end',''),period_verdict='PASS' if r and r.get('period_end')==c['period_end'] else 'FAIL' if r else 'UNVERIFIED',source_archive_sha256=g['archive_sha256'],source_member_sha256=g['member_sha256'],source_location=f"{c['member']}#table={c['table']},row={c['row']},col={c['column']}",source_url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+c['receipt'],source_header_context=t['context'][-1200:]))
    for s in plan['selected']:
        rid=s['receipt'];ss=states[rid];gg=[x for x in grids if x['receipt']==rid]
        own=[x for x in details if x['receipt']==rid]
        # Aggregate sample completeness includes mapping/correction/PIT, never
        # upgrades monetary matches to complete investment certification.
        for item in ['historical_identity','filing_and_correction_chain','availability_PIT']:
            checks.append(dict(sample=s['sample'],receipt=rid,item=item,verdict='UNVERIFIED',reason='Original company text retained; historical legal code links/full chain/actual available time not independently established'))
        if ss['audit_stratum']=='QUARANTINED_ERROR':
            checks.append(dict(sample=s['sample'],receipt=rid,item='failure_classification',verdict='FAIL' if '<status>800</status>' in ss['error'] else 'UNVERIFIED',reason='Service maintenance must not count as per-filing permanent parser/document failure'))
        elif ss['audit_stratum']=='SOURCE_GAP':
            checks.append(dict(sample=s['sample'],receipt=rid,item='source_presence',verdict='PASS' if gg else 'UNVERIFIED',reason='Preserved members include financial tables; strict XML rejection is not proof of missing finances; extraction accuracy remains UNVERIFIED'))
        elif ss['audit_stratum']=='NO_DOCUMENT':
            checks.append(dict(sample=s['sample'],receipt=rid,item='source_presence',verdict='UNVERIFIED',reason='OpenDART014 observed, original unavailable in archive; not global proof of absent public document'))
        if s['sample']=='A04':
            for metric in ['revenue','net_income']:
                r=next(x for x in metrics if x['rcept_no']==rid and x['scope']=='CFS' and x['metric']==metric)
                assert r['table_index']=='56'
                checks.append(dict(sample=s['sample'],receipt=rid,item='CFS_'+metric+'_scope',verdict='FAIL',reason='Selected table56 is current ordinary summary matching OFS; separate connection summary table70 is prior year, not current CFS. Current ordinary figures cannot be authenticated as current CFS.'))
    for name,rows in [('audit_details.csv',details),('audit_checks.csv',checks)]:
        with (output/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    samples=[]
    for s in plan['selected']:
        ds=[x for x in details if x['receipt']==s['receipt']];cs=[x for x in checks if x['receipt']==s['receipt']]
        allv=[x['verdict'] for x in ds+cs]+[x['period_verdict'] for x in ds]
        samples.append(dict(**s,verdict='FAIL' if 'FAIL' in allv else 'UNVERIFIED' if 'UNVERIFIED' in allv else 'PASS'))
    result=dict(samples=len(samples),sample_verdicts=dict(Counter(x['verdict'] for x in samples)),financial_controls=len(details),financial_primary_exact=dict(Counter(x['verdict'] for x in details)),literal_normalization=dict(Counter(x['source_literal_verdict'] for x in details)),period_checks=dict(Counter(x['period_verdict'] for x in details)),nonmonetary_checks=dict(Counter(x['verdict'] for x in checks)),cohorts=dict(Counter(x['cohort'] for x in samples)),no_metrics_latest_batch=0,no_metrics_stratum_shortfall=4,parser='legacy-v5-single-amount',main_snapshot=plan['plan']['main_sha'],research_parser_certified_by_this_audit=False,investment_approved=False,limits='Only32 reviewed core fields, not remaining fields/CFS candidates or full population. Full source ZIP identities retained; literal grids do not replace original archives. Source-date/currency/mapping/version ambiguity never passed.')
    (output/'audit_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (output/'audit_samples.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);verify(p.parse_args().output)
