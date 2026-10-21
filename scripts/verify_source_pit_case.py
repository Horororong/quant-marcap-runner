"""New first-usable-close query on preserved official sources. No source HTTP."""
import argparse,base64,copy,gzip,hashlib,io,json,re,sys,zipfile
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_record_readiness import assess,binding
from financial_publication_evidence import viewer_evidence
from financial_source_grid import Grid
from reviewed_financial_query import inspect_equity_asof
from dart_value_factor_adapter import DartValueFactorAdapter,calculate_value_factors
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'docs/research/source-readiness-20261019'

def main(output):
 output.mkdir(parents=True,exist_ok=False)
 def pack(name,expected):
  b=base64.b64decode((HOME/name).read_bytes());assert hashlib.sha256(b).hexdigest()==expected
  return {k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(b))['files'].items()}
 sources=pack('preserved10.json.gz.b64','b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68')
 pub=pack('publication-proof.json.gz.b64','bfc38f9a76596339233b229fbe9eba730cf255df790a326cf48768df7f5698f8')
 market=pack('official-market-proof.json.gz.b64','52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23')
 body=pack('official-primary-section.json.gz.b64','293c8377088421b39d8a41bf816e188a4ebd833c36a6badae3bb29ae2ae48a19')
 item=next(x for x in json.loads((HOME/'actual_signal_inputs.json').read_text())['records']if x['row']['rcept_no']=='20100331001582')
 row=item['row'];control=item['control'];blob=next(v for k,v in sources.items()if k.startswith('native/'+row['rcept_no']+'-'))
 assert hashlib.sha256(blob).hexdigest()==row['document_sha256']
 with zipfile.ZipFile(io.BytesIO(blob))as z:
  member=z.read(control['member']);assert hashlib.sha256(member).hexdigest()==control['member_sha256']
 for encoding in ['utf-8','cp949','euc-kr']:
  try:
   text=member.decode(encoding);assert text.encode(encoding)==member;break
  except(UnicodeError,AssertionError):continue
 else:raise ValueError('ORIGINAL_ENCODING_NOT_PROVED')
 g=Grid();g.feed(text)
 literal=g.tables[control['table']]['rows'][control['row']][control['column']]
 assert literal==control['literal'] and Decimal(literal.replace(',',''))*Decimal(control['multiplier'])==Decimal(row['amount_krw'])
 issuer=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)</COMPANY-NAME>',text[:3000]);assert issuer and issuer[1]==row['corp_code']
 viewer=viewer_evidence(pub[row['rcept_no']+'-viewer.html']);family=[x for x in viewer['options']if x['section']=='family'];assert len(family)==1 and family[0]['receipt']==row['rcept_no'] and family[0]['date']=='2010-03-31'
 listing=json.loads(pub[row['corp_code']+'-list1.json']);assert int(listing['total_page'])==1
 candidates=[x for x in listing['list']if'사업보고서'in x['report_nm']and'2009.12'in x['report_nm']and x['rcept_dt']<='20100430']
 assert len(candidates)==1 and candidates[0]['rcept_no']==row['rcept_no']
 proof=next(x for x in json.loads((HOME/'record_attestations.json').read_text())['records']if x['receipt']==row['rcept_no'])['version_relationship'];section=proof['primary_section']
 primary=body['sajo-primary-XI.html'];assert hashlib.sha256(primary).hexdigest()==section['sha256']
 vg=Grid();vg.feed(primary.decode());table=vg.tables[section['table']];assert table['rows'][section['row']][section['column']]==literal
 context=' '.join(table['context'].split());assert '2009년 12월 31일'in context and'(단위 : 원)'in context
 ms=json.loads(market['state.json']);quote=next(x for x in ms['target_rows']if x['security']=='007160'and x['date']=='20100401')
 raw=json.loads(market[quote['source_file']])['OutBlock_1'][quote['source_row_index']];assert raw==quote['raw_api_row'] and int(raw['ACC_TRDVOL'])>0
 normalize=lambda s:re.sub(r'\s+','',s.replace('주식회사','').replace('(주)','').replace('㈜',''))
 assert normalize(issuer[2])==normalize(raw['ISU_NM']) and raw['ISU_CD']==row['stock_code'] and raw['BAS_DD']=='20100401'
 a=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=[row['document_sha256'],section['sha256'],'Exact original OFS equity and official primary viewer cell/period/unit']),
  publication=dict(verdict='PASS',date='2010-03-31',evidence=[viewer['sha256'],row['corp_code']+'-list1.json']),
  version_relationship=proof,
  historical_security_mapping=dict(verdict='PASS',stock_code=row['stock_code'],**{'from':'2010-04-01','through':'2010-04-01'},
   evidence=[f'Original issuer AREGCIK={issuer[1]} name={issuer[2]}',quote['source_file'],str(quote['source_row_index']),raw['ISU_NM']],
   scope='NEW exact signal-date mapping; not a continuous legal lineage certificate'))
 calendar=dict(verdict='PASS',evidence=[quote['source_file'],str(quote['source_row_index'])],coverage_start='2010-03-31',coverage_end='2010-04-01',sessions=['2010-04-01'])
 records=[dict(row=row,attestation=a)]
 queries={d:inspect_equity_asof(records,d,calendar)for d in ['2010-03-30','2010-03-31','2010-04-01','2010-05-03']}
 assert queries['2010-03-30']['value']is None and queries['2010-03-31']['value']is None
 assert queries['2010-04-01']['status']=='PASS'and queries['2010-04-01']['value']['source_amount_krw']=='131053210651'
 assert queries['2010-05-03']['status']=='UNVERIFIED'
 inputs=pd.DataFrame([dict(Code='007160',fs_div='OFS',equity=float(row['amount_krw']),revenue_q=float('nan'),net_income_q=float('nan'),ocf_q=float('nan'),available_date=pd.Timestamp('2010-04-01'))])
 cs=pd.DataFrame([dict(Code='007160',Marcap=float(raw['MKTCAP']))]);factors=calculate_value_factors(inputs,cs,pd.Timestamp('2010-04-01'),'legacy_april_october')
 ratio=Decimal(row['amount_krw'])/Decimal(raw['MKTCAP']);actual=float(factors.iloc[0]['book_to_price']);assert abs(Decimal(str(actual))-ratio)<Decimal('1e-14')
 try:DartValueFactorAdapter(ROOT).factor_frame(pd.Timestamp('2010-04-01'),cs);raise AssertionError('Unexpected full population admission')
 except (RuntimeError,FileNotFoundError)as e:population_gate=str(e)
 result=dict(status='PASS_BOUNDED_FIELD_AT_NEW_SIGNAL',new_research_field_signal_pairs=1,new_unique_financial_fields=0,
  new_signal='2010-04-01',previous_verified_signal='2010-04-30',cohort='Prior canary original; outside finite157 and current880',
  source_HTTP=0,source_receipt=row['rcept_no'],stock_code=row['stock_code'],corp_code=row['corp_code'],fiscal_period_end=row['period_end'],
  field='OFS equity',publication_date='2010-03-31',publication_clock='UNVERIFIED',availability_rule='Exclude disclosure day; first attested next trading session close2010-04-01; any trade still requires normal t+lag and population gates',
  correction_scope='Bounded original primary chain closed through2010-04-30; no actual correction in this attested interval. No global correction certification.',
  queries=queries,original_record=row,attestation=a,calendar=calendar,book_to_price_common_owner=actual,independent_decimal_ratio=str(ratio),
  full_population_gate=population_gate,whole_population_rank_ready=False,operating_store_changed=False,financial_publication='HOLD',investment_PIT='0/6',
  current880_PIT_promoted=0,classification='RESEARCH_ONLY')
 (output/'PIT_CASE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k not in ['queries','original_record','attestation','calendar']},ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
