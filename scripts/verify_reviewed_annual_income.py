"""Review two new annual source fields; no new HTTP or operating-store writes."""
import argparse,base64,copy,gzip,hashlib,html,io,json,re,sys,zipfile
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_source_grid import Grid
from financial_record_readiness import binding
from financial_publication_evidence import viewer_evidence
from reviewed_annual_income_query import inspect_annual_income_asof
ROOT=Path(__file__).resolve().parents[1];HOME=ROOT/'docs/research/source-readiness-20261019'

def main(output):
 output.mkdir(parents=True,exist_ok=False)
 def pack(name,sha):
  b=base64.b64decode((HOME/name).read_bytes());assert hashlib.sha256(b).hexdigest()==sha
  return {k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(b))['files'].items()}
 native=pack('preserved10.json.gz.b64','b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68')
 body=pack('official-primary-section.json.gz.b64','293c8377088421b39d8a41bf816e188a4ebd833c36a6badae3bb29ae2ae48a19')
 market=pack('official-market-proof.json.gz.b64','52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23')
 pub=pack('publication-proof.json.gz.b64','bfc38f9a76596339233b229fbe9eba730cf255df790a326cf48768df7f5698f8')
 prior=json.loads((ROOT/'docs/research/pit-period-20261021/evidence/PIT_CASE.json').read_text());old=prior['original_record'];receipt=old['rcept_no'];raw=next(v for k,v in native.items()if k.startswith('native/'+receipt+'-'))
 assert hashlib.sha256(raw).hexdigest()==old['document_sha256']
 with zipfile.ZipFile(io.BytesIO(raw))as z:member=z.read(old['source_member'])
 assert hashlib.sha256(member).hexdigest()==old['source_member_sha256'];text=member.decode('cp949');assert text.encode('cp949')==member
 primary=body['sajo-primary-XI.html'];assert hashlib.sha256(primary).hexdigest()=='cb78f57965c2d1beae36121088ef1f591df08e334ca23f2229f03e00f3c224da'
 original=Grid();original.feed(text);official=Grid();official.feed(primary.decode())
 scope_start=text.index('XI. 재무제표 등',550000);income_start=text.index('<TITLE ATOC="N">손익계산서</TITLE>',scope_start);scope_span=text[scope_start:income_start]
 assert 'XBRL 개별재무제표'in scope_span and 'XBRL 연결재무제표'not in scope_span
 scope_evidence=dict(original_section_character=scope_start,income_heading_character=income_start,marker='XBRL 개별재무제표',same_primary_body=True,late_CFS_attachment_excluded=True)
 for g,t in [(original,168),(official,3)]:
  context=' '.join(g.tables[t]['context'].split());assert '손익계산서'in context and'2009년 01월 01일'in context and'2009년 12월 31일'in context and'(단위 : 원)'in context
  assert g.tables[t]['rows'][0]==['과 목','제39기','제38기','제37기']
 issuer=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)</COMPANY-NAME>',text[:3000]);assert issuer[1]=='00124799'
 viewer=viewer_evidence(pub[receipt+'-viewer.html']);family=[x for x in viewer['options']if x['section']=='family'];assert len(family)==1 and family[0]['receipt']==receipt and family[0]['date']=='2010-03-31'
 listing=json.loads(pub['00124799-list1.json']);assert int(listing['total_page'])==1
 candidates=[x for x in listing['list']if'사업보고서'in x['report_nm']and'2009.12'in x['report_nm']and x['rcept_dt']<='20100430'];assert len(candidates)==1 and candidates[0]['rcept_no']==receipt
 # Independent raw markup rows, selected with fixed previously reviewed positions;
 # no native financial parser or reported candidate amount is the accuracy oracle.
 clean=lambda s:html.unescape(re.sub('<[^>]*>','',s)).replace('&cr;','').strip()
 raw_rows=[[clean(c)for c in re.findall(r'<(?:TD|TH)\b[^>]*>(.*?)</(?:TD|TH)>',tr,re.S|re.I)]for tr in re.findall(r'<TR\b[^>]*>.*?</TR>',text,re.S|re.I)]
 controls=[dict(metric='revenue',account='매출액',row=1,raw_TR=1518,literal='328,527,137,799'),dict(metric='net_income',account='당기순이익(손실)',row=72,raw_TR=1589,literal='34,326,086,558')]
 cases=[];market_state=json.loads(market['state.json']);normalize=lambda s:re.sub(r'\s+','',s.replace('주식회사','').replace('(주)','').replace('㈜',''))
 for control in controls:
  o=original.tables[168]['rows'][control['row']];v=official.tables[3]['rows'][control['row']];assert o==v==raw_rows[control['raw_TR']]
  assert o[0]==control['account']and o[1]==control['literal'];amount=str(Decimal(o[1].replace(',','')));assert Decimal(amount)>0
  # A second literal note supports profit identity; do not confuse retained earnings.
  if control['metric']=='net_income':assert '당기말:34,326,086,558원'in original.tables[166]['rows'][92][0]
  row=dict(rcept_no=receipt,document_sha256=old['document_sha256'],source_member=old['source_member'],source_member_sha256=old['source_member_sha256'],corp_code='00124799',stock_code='007160',metric=control['metric'],scope='OFS',statement='IS',period_start='2009-01-01',period_end='2009-12-31',measurement_basis='duration',unit='원',unit_multiplier='1',amount_krw=amount,structural_status='PASS',backtest_eligible=False)
  outputs={};attestations={}
  for signal in ['2010-04-01','2010-04-30']:
   quote=next(x for x in market_state['target_rows']if x['security']=='007160'and x['date']==signal.replace('-',''));official_quote=json.loads(market[quote['source_file']])['OutBlock_1'][quote['source_row_index']]
   assert official_quote==quote['raw_api_row']and official_quote['ISU_CD']=='007160'and official_quote['BAS_DD']==signal.replace('-','')and int(official_quote['ACC_TRDVOL'])>0
   assert normalize(issuer[2])==normalize(official_quote['ISU_NM'])
   version=copy.deepcopy(prior['attestation']['version_relationship']);version['scope']='New named primary OFS annual IS field, same official receipt/node family, bounded through2010-04-30; no global correction certification';version['primary_section']=dict(version['primary_section'],table=3,row=control['row'],column=1,literal=control['literal'],account=control['account'],period_start='2009-01-01',period_end='2009-12-31',unit='원');version['evidence'].append('Additional field independently checked against original XML rawTR and official primary IS; equity-specific conclusion is not reused as financial accuracy.')
   att=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=[old['document_sha256'],old['source_member_sha256'],version['primary_section']['sha256'],f"XML table168,row{control['row']},column1/rawTR{control['raw_TR']}; official primary table3 same row; exact39th currentFY2009/원/OFS/positive"]),publication=copy.deepcopy(prior['attestation']['publication']),version_relationship=version,historical_security_mapping=dict(verdict='PASS',stock_code='007160',**{'from':signal,'through':signal},evidence=[f'Original AREGCIK={issuer[1]} name={issuer[2]}',quote['source_file'],str(quote['source_row_index']),official_quote['ISU_NM']],scope='Exact signal date only, not continuous issuer lineage'))
   calendar=copy.deepcopy(prior['calendar']);calendar['additional_verified_sessions']={'2010-04-30':dict(verdict='PASS',evidence=['stk_bydd_trd_20100430.json',str(next(x['source_row_index']for x in market_state['target_rows']if x['security']=='007160'and x['date']=='20100430'))])}
   outputs[signal]=inspect_annual_income_asof([dict(row=row,attestation=att)],signal,calendar);assert outputs[signal]['status']=='PASS'and Decimal(outputs[signal]['value']['source_amount_krw'])==Decimal(amount);attestations[signal]=dict(attestation=att,calendar=calendar)
  selected=attestations['2010-04-01'];records=[dict(row=row,attestation=selected['attestation'])]
  for day in ['2010-03-30','2010-03-31']:
   outputs[day]=inspect_annual_income_asof(records,day,selected['calendar']);assert outputs[day]['value']is None
  outputs['2010-05-03']=inspect_annual_income_asof(records,'2010-05-03',selected['calendar']);assert outputs['2010-05-03']['status']=='UNVERIFIED'and outputs['2010-05-03']['value']is None
  cases.append(dict(control=control,scope_evidence=scope_evidence,row=row,attested_queries=outputs,source_attestations=attestations))
 result=dict(status='PASS_TWO_NEW_BOUNDED_ANNUAL_FIELDS',classification='RESEARCH_ONLY',new_unique_reviewed_fields=2,new_field_signal_pairs=4,unique_issuer=1,period='2009FY',new_source_HTTP=0,cases=cases,source_cohort='Existing preserved canary; OUTSIDE finite157/current880',current880_changed=False,new_operating_values=0,financial_publication='HOLD',investment_PIT='0/6',new_rank_strategy_ready=False,limitations=['Annual totals are notQ4; independently attested same-scopeQ3 and full1495 population still required','Only original primary OFS report chain through2010-04-30; actual two-version correction not certified','Source stock mapping is exactly4/1 and4/30; no continuous legal lineage certification','Publication clock unknown; original disclosure day excluded and next actual session close used'])
 (output/'ANNUAL_PIT_CASES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='cases'},ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
