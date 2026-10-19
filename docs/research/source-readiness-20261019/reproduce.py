"""Actual-source arithmetic + full-universe refusal and preserved issue grouping.

No NAV execution, source recollection, factor-provider injection or PIT waiver.
The partial control ordering is explicitly not a strategy population or rank.
"""
import argparse,base64,gzip,hashlib,io,json,re,sys,zipfile
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from dart_value_factor_adapter import calculate_value_factors,DartValueFactorAdapter
from financial_record_readiness import assess,binding,select_asof
from financial_publication_evidence import viewer_evidence
from financial_source_grid import Grid
from research_incident_groups import summarize
HERE=Path(__file__).resolve().parent
def pack(name,expected):
    compressed=base64.b64decode((HERE/name).read_bytes());assert hashlib.sha256(compressed).hexdigest()==expected
    return json.loads(gzip.decompress(compressed))
def main(check=False):
    manifest=json.loads((HERE/'planned_symptoms_manifest.json').read_text());saved=pack('planned_symptoms.json.gz.b64',manifest['compressed_sha256'])
    incidents=summarize(saved['preflights']);assert(incidents['records'],incidents['unique_cross_strategy_symptoms'])==(10136,9926)
    source=pack('preserved10.json.gz.b64','b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68')
    source={k:base64.b64decode(v)for k,v in source['files'].items()}
    pub=pack('publication-proof.json.gz.b64','bfc38f9a76596339233b229fbe9eba730cf255df790a326cf48768df7f5698f8')
    pub={k:base64.b64decode(v)for k,v in pub['files'].items()}
    official=pack('official-market-proof.json.gz.b64','52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23')
    official={k:base64.b64decode(v)for k,v in official['files'].items()};market_state=json.loads(official['state.json'])
    body=pack('official-primary-section.json.gz.b64','293c8377088421b39d8a41bf816e188a4ebd833c36a6badae3bb29ae2ae48a19')
    body={k:base64.b64decode(v)for k,v in body['files'].items()};body_state=json.loads(body['state.json']);assert body_state['requests']==1 and body_state['status']=='COMPLETE_OFFICIAL_SECTION_ONLY'
    attestations=json.loads((HERE/'record_attestations.json').read_text())['records']
    assert market_state['requests']==4 and market_state['status']=='COMPLETE_OFFICIAL_PRICE_ROWS_ONLY'
    for response in market_state['responses']:assert hashlib.sha256(official[response['file']]).hexdigest()==response['sha256']
    request=json.loads((HERE/'actual_signal_inputs.json').read_text());signal=pd.Timestamp(request['signal_date'])
    p=ROOT/'data/krx_equities/yearly/marcap-2010.parquet';raw=p.read_bytes();panel=pd.read_parquet(io.BytesIO(raw),columns=['Date','Code','Market','Name','Close','Volume','Marcap'])
    cs=panel.loc[pd.to_datetime(panel.Date).eq(signal)&panel.Market.isin(['KOSPI','KOSDAQ'])].copy();cs['Code']=cs.Code.astype(str).str.zfill(6)
    cs=cs.loc[cs.Close.gt(0)&cs.Volume.gt(0)&cs.Marcap.gt(0)].copy();assert not cs.Code.duplicated().any()
    amounts=[];audit=[];boundary_checks=[]
    for item in request['records']:
        row=item['row'];control=item['control'];receipt=row['rcept_no']
        blobs=[b for k,b in source.items()if k.startswith('native/'+receipt+'-')];assert len(blobs)==1
        assert hashlib.sha256(blobs[0]).hexdigest()==row['document_sha256']
        with zipfile.ZipFile(io.BytesIO(blobs[0]))as z:
            assert z.testzip()is None;member=z.read(control['member']);assert hashlib.sha256(member).hexdigest()==control['member_sha256']
        for enc in ['utf-8','cp949','euc-kr']:
            try:text=member.decode(enc);assert text.encode(enc)==member;break
            except(UnicodeError,AssertionError):pass
        g=Grid();g.feed(text);literal=g.tables[control['table']]['rows'][control['row']][control['column']];assert literal==control['literal']
        header=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)</COMPANY-NAME>',text[:3000]);assert header and header[1]==row['corp_code']
        expected=Decimal(literal.replace(',',''))*Decimal(control['multiplier']);assert expected==Decimal(row['amount_krw'])
        dart_list=json.loads(pub[row['corp_code']+'-list1.json']);hit=[x for x in dart_list['list']if x['rcept_no']==receipt];assert len(hit)==1 and hit[0]['corp_code']==row['corp_code']
        viewer=viewer_evidence(pub[receipt+'-viewer.html']);main=[o for o in viewer['options']if o['section']=='family'and o['receipt']==receipt];assert len(main)==1 and main[0]['date']=='2010-03-31'
        # Official contemporary numeric issuer code is verified; current API
        # stock/name fields do NOT independently prove historical KRX mapping.
        a=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=[f'{receipt} primary equity table{control["table"]}/row{control["row"]}/column{control["column"]}']),publication=dict(verdict='PASS',date=main[0]['date'],evidence=[viewer['sha256'],row['corp_code']+'-list1.json']),version_relationship=dict(verdict='UNVERIFIED',evidence=['Bounded Mar1-May1 metadata and current viewer; no complete certified source-member version graph.']),historical_security_mapping=dict(verdict='UNVERIFIED',evidence=['Current API code + historical marcap/name observation are supporting evidence, not legal historical mapping certification.']))
        calendar=dict(verdict='UNVERIFIED',evidence=['Historical panel sessions are observations; no separately certified complete official 2010 calendar.'])
        ready=assess(row,str(signal.date()),a,calendar)
        observed=cs.loc[cs.Code.eq(row['stock_code'])];assert len(observed)==1
        quotes=[q for q in market_state['target_rows']if q['security']==row['stock_code']]
        earlier=next(q for q in quotes if q['date']=='20100401');current=next(q for q in quotes if q['date']=='20100430')
        for q in quotes:
            raw_market=json.loads(official[q['source_file']])['OutBlock_1'];assert raw_market[q['source_row_index']]==q['raw_api_row'];assert int(q['raw_api_row']['ACC_TRDVOL'])>0
        assert Decimal(current['raw_api_row']['MKTCAP'])==Decimal(str(observed.iloc[0].Marcap))
        assert Decimal(current['raw_api_row']['TDD_CLSPRC'])==Decimal(str(observed.iloc[0].Close))
        # March31 -> April1 are adjacent civil days. An actual official trade
        # on April1 establishes the first possible next session without any
        # weekday/holiday inference or whole-April calendar certification.
        calendar=dict(verdict='PASS',evidence=[earlier['source_file'],str(earlier['source_row_index'])],coverage_start='2010-03-31',coverage_end='2010-04-01',sessions=['2010-04-01'],additional_verified_sessions={'2010-04-30':dict(verdict='PASS',evidence=[current['source_file'],str(current['source_row_index'])])})
        canonical_name=lambda name:re.sub(r'\s+','',name.replace('주식회사','').replace('(주)','').replace('㈜',''))
        if canonical_name(header[2])==canonical_name(current['raw_api_row']['ISU_NM']):
            a['historical_security_mapping']=dict(verdict='PASS',stock_code=row['stock_code'],**{'from':'2010-04-30','through':'2010-04-30'},evidence=[f'Original DART header AREGCIK={header[1]} / issuer={header[2]}',current['source_file'],str(current['source_row_index'])],scope='Exact normalized legal-form name + official historical code on this signal only; not whole-history lineage.')
        att=[x for x in attestations if(x['receipt'],x['metric'],x['scope'],x['signal_date'])==(receipt,row['metric'],row['scope'],str(signal.date()))]
        if att:
            assert len(att)==1;proof=att[0]['version_relationship'];section=proof['primary_section'];html=body['sajo-primary-XI.html']
            assert body_state['url']==section['url'] and body_state['sha256']==section['sha256']==hashlib.sha256(html).hexdigest()
            literal_viewer=pub[receipt+'-viewer.html'].decode();node=re.search(r"node1\['text'\]\s*=\s*\"XI[.] 재무제표 등\";([\s\S]+?)treeData.push",literal_viewer);assert node
            for field,value in [('rcpNo',receipt),('dcmNo','2591068'),('eleId','25'),('offset','592088'),('length','125209')]:assert re.search(r"node1\['"+field+r"'\]\s*=\s*\""+value+r'"',node[1])
            vg=Grid();vg.feed(html.decode());table=vg.tables[section['table']];cells=table['rows'][section['row']]
            assert cells[0]==section['account'] and cells[section['column']]==section['literal']==literal
            context=' '.join(table['context'].split());assert '2009년 12월 31일'in context and'(단위 : 원)'in context and'제39기'in context
            # The official family provides explicit receipt identity; no chain
            # is synthesized merely from report titles or receipt sorting.
            assert len([o for o in viewer['options']if o['section']=='family'])==1
            candidates=[x for x in dart_list['list']if'사업보고서'in x['report_nm']and'2009.12'in x['report_nm']and x['rcept_dt']<='20100430']
            assert len(candidates)==1 and candidates[0]['rcept_no']==receipt
            a['version_relationship']=proof
        ready=assess(row,str(signal.date()),a,calendar)
        asof=select_asof([dict(row=row,attestation=a)],str(signal.date()),calendar)
        if att:
            same_day=assess(row,'2010-03-31',a,calendar)
            beyond=select_asof([dict(row=row,attestation=a)],'2010-05-03',calendar)
            assert same_day['dimensions']['signal_availability']=='FAIL' and beyond['status']=='UNVERIFIED'
            attachment=next(o for o in viewer['options']if o['section']=='att'and o['document_id']=='2651030')
            assert attachment['date']=='2010-04-30'
            # A real late-attachment candidate is never promoted: no extracted
            # amount, unsupported CFS cover and unbound dcm/member bytes remain U.
            late_member=receipt+'_00761.xml'
            with zipfile.ZipFile(io.BytesIO(blobs[0]))as archive:late_sha=hashlib.sha256(archive.read(late_member)).hexdigest()
            late={**row,'scope':'CFS','source_member':late_member,'source_member_sha256':late_sha,'amount_krw':None,'structural_status':'UNVERIFIED'}
            late_att=dict(binding=binding(late),publication=dict(verdict='PASS',date=attachment['date'],evidence=[viewer['sha256'],'att option dcm2651030 unique CFS audit type/date; exact ZIP-member linkage remains separate']))
            late_before=assess(late,'2010-04-29',late_att,calendar);late_day=assess(late,'2010-04-30',late_att,calendar)
            assert late_before['dimensions']['signal_availability']==late_day['dimensions']['signal_availability']=='FAIL'
            boundary_checks.append(dict(receipt=receipt,primary_same_day=same_day['dimensions']['signal_availability'],primary_signal_asof=asof['status'],beyond_attested_horizon=beyond['status'],late_CFS_not_before=attachment['date'],late_CFS_before=late_before['dimensions']['signal_availability'],late_CFS_same_day=late_day['dimensions']['signal_availability'],late_CFS_financial_and_member_version='UNVERIFIED',exact_publication_clock='UNVERIFIED',investment_approved=False))
        mc=Decimal(str(observed.iloc[0].Marcap));ratio=expected/mc
        amounts.append(dict(Code=row['stock_code'],equity=float(expected),revenue_q=np.nan,net_income_q=np.nan,ocf_q=np.nan,available_date=pd.NaT,fs_div=row['scope']))
        audit.append(dict(receipt=receipt,stock_code=row['stock_code'],original_issuer_name=header[2],official_historical_market_name=current['raw_api_row']['ISU_NM'],official_signal_quote=current,official_first_next_session=earlier,source_issuer_corp_code=header[1],raw_source_literal=literal,normalized_equity=str(expected),market_cap=str(mc),independent_book_to_price=str(ratio),readiness=ready,asof_query_status=asof['status'],asof_query_reason=asof['reason'],source_table=control['table'],source_row=control['row'],source_column=control['column']))
    factors=calculate_value_factors(pd.DataFrame(amounts),cs,signal,'legacy_april_october')
    # Independent rational comparison. These two rows are controls, never an
    # eligible substitute for the full historical requested universe.
    for row in audit:
        actual=float(factors.loc[factors.Code.eq(row['stock_code']),'book_to_price'].iloc[0]);assert abs(Decimal(str(actual))-Decimal(row['independent_book_to_price']))<Decimal('1e-14');row['common_factor_owner_value']=actual
    ordered=sorted(audit,key=lambda x:(-Decimal(x['independent_book_to_price']),x['stock_code']))
    for n,row in enumerate(ordered,1):row['arithmetic_order_among_controls_ONLY']=n
    try:
        provider=DartValueFactorAdapter(ROOT);provider.coverage_report(signal);provider_gate=dict(status='PASS_LEGACY_EXISTING_PROVIDER_COVERAGE_ONLY',warning='This does not admit the source-only records or certify them.')
    except(OSError,ValueError,RuntimeError,KeyError,AssertionError)as e:provider_gate=dict(status='data_gap',error_type=type(e).__name__,message=str(e))
    ready_count=sum(x['readiness']['research_record_ready']for x in audit)
    result=dict(signal_date=str(signal.date()),source_panel_sha256=hashlib.sha256(raw).hexdigest(),historical_observed_tradable_population=len(cs),raw_control_documents=len(audit),arithmetically_matched_factors=len(audit),research_ready_source_records=ready_count,missing_certified_population=len(cs)-ready_count,records=ordered,actual_boundaries=boundary_checks,provider_gate=provider_gate,ready_for_strategy_ranking=False,approved_strategy_rank_rows=[],source_only_provider_injection=False,backtest_eligible=False,investment_PIT='0/6',new_NAV_completed=False,scope='One named primary OFS equity field at one signal satisfies bounded research-record readiness. Other source-member version/abbreviation links remain incomplete. Two-control arithmetic ordering is NOT full-population strategy rank. No whole-calendar/global-correction/investment certification or operating-provider admission.')
    for name,obj in [('incident_groups.json',incidents),('actual_signal_result.json',result)]:
        data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();p=HERE/name
        if name=='incident_groups.json':
            p=HERE/'incident_groups.json.gz.b64';data=base64.b64encode(gzip.compress(data,mtime=0))+b'\n'
        if check:assert p.read_bytes()==data,('REPRODUCTION_DIFF',name)
        else:p.write_bytes(data)
    print(json.dumps(dict(symptom_records=incidents['records'],unique_symptoms=incidents['unique_cross_strategy_symptoms'],diagnostic_groups=incidents['diagnostic_groups'],families=incidents['groups_by_family'],signal=result['signal_date'],population=len(cs),factor_arithmetic_matches=len(audit),research_ready_source_records=result['research_ready_source_records'],strategy_rank_ready=False,new_multi_completions=0)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');main(p.parse_args().check)
