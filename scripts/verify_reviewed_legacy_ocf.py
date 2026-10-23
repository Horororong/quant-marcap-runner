"""New named OFS annual OCF audit from already preserved original + official body.
No external HTTP, production financial parser, canonical ledger or global PIT edit.
"""
import argparse,base64,copy,gzip,hashlib,html,io,json,re,sys,zipfile
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_source_grid import Grid
from financial_record_readiness import binding
from legacy_reviewed_provider_bridge import bridge
ROOT=Path(__file__).resolve().parents[1];HOME=ROOT/'docs/research/source-readiness-20261019'
def main(output):
 output.mkdir(parents=True,exist_ok=False)
 def pack(name,sha):
  b=base64.b64decode((HOME/name).read_bytes());assert hashlib.sha256(b).hexdigest()==sha
  return {k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(b))['files'].items()}
 source=pack('preserved10.json.gz.b64','b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68')
 official=pack('official-primary-section.json.gz.b64','293c8377088421b39d8a41bf816e188a4ebd833c36a6badae3bb29ae2ae48a19')
 prior=json.loads((ROOT/'docs/research/pit-period-20261021/evidence/PIT_CASE.json').read_text());annual=json.loads((ROOT/'docs/research/finite-source-linkage-20261021/evidence/ANNUAL_PIT_CASES.json').read_text());old=prior['original_record'];raw=next(v for k,v in source.items()if k.startswith('native/'+old['rcept_no']+'-'));assert hashlib.sha256(raw).hexdigest()==old['document_sha256']
 with zipfile.ZipFile(io.BytesIO(raw))as z:assert z.testzip()is None;member=z.read(old['source_member'])
 assert hashlib.sha256(member).hexdigest()==old['source_member_sha256'];text=member.decode('cp949');assert text.encode('cp949')==member
 body=official['sajo-primary-XI.html'];bodysha=hashlib.sha256(body).hexdigest();assert bodysha=='cb78f57965c2d1beae36121088ef1f591df08e334ca23f2229f03e00f3c224da'
 g=Grid();g.feed(text);h=Grid();h.feed(body.decode());native=g.tables[174];page=h.tables[9]
 for table in [native,page]:
  context=' '.join(table['context'].split());assert '현금흐름표'in context and'2009년 01월 01일'in context and'2009년 12월 31일'in context and'(단위 : 원)'in context
  assert table['rows'][0]==['과 목','제39기','제38기','제37기']
 scope=text[text.index('XI. 재무제표 등',550000):text.index('<TITLE ATOC="N">현금흐름표</TITLE>',550000)];assert 'XBRL 개별재무제표'in scope and'XBRL 연결재무제표'not in scope
 # Independent literal markup corroborates five top-level CF rows. Nested
 # components are deliberately not summed into their parent twice.
 clean=lambda s:html.unescape(re.sub('<[^>]*>','',s)).replace('&cr;','').strip()
 rawrows=[[clean(c)for c in re.findall(r'<(?:TD|TH)\b[^>]*>(.*?)</(?:TD|TH)>',tr,re.S|re.I)]for tr in re.findall(r'<TR\b[^>]*>.*?</TR>',text,re.S|re.I)]
 controls=[(1,'영업활동으로인한현금흐름','15,922,637,039'),(2,'당기순이익(손실)','34,326,086,558'),(3,'현금의유출이없는비용등의가산','14,580,298,231'),(17,'현금의유입이없는수익등의차감','(28,544,031,412)'),(25,'영업활동으로인한자산·부채의변동','(4,439,716,338)')]
 def number(s):return Decimal(s.replace(',','').strip('()'))*(-1 if s.startswith('(')and s.endswith(')')else 1)
 references=[]
 for index,label,literal in controls:
  row=native['rows'][index];assert row==page['rows'][index]and row[0]==label and row[1]==literal
  raw_index=1632+index;assert rawrows[raw_index]==row;references.append(dict(native_table=174,official_table=9,row=index,current_column=1,raw_TR=raw_index,label=label,literal=literal,comparative=row[2:]))
 assert sum(number(v)for _,_,v in controls[1:])==number(controls[0][2])
 row={**old,'metric':'ocf','statement':'CF','period_start':'2009-01-01','period_end':'2009-12-31','measurement_basis':'cumulative','amount_krw':'15922637039','unit':'원','unit_multiplier':'1','structural_status':'PASS','backtest_eligible':False}
 cases=[]
 for signal in ['2010-04-01','2010-04-30']:
  previous=annual['cases'][0]['source_attestations'][signal];a=copy.deepcopy(previous['attestation']);a['binding']=binding(row);a['financial_accuracy']=dict(verdict='PASS',evidence=[old['document_sha256'],old['source_member_sha256'],bodysha,'Primary OFS CF table174/official9 currentrow1/col1; source-header annual Jan1-Dec31 and 4top-level-components exact sum']);version=a['version_relationship'];version['scope']='New independently source-reviewed named primary OFS annual CF/OCF, same already proved publication/node family through2010-04-30 only';version['primary_section']=dict(version['primary_section'],table=9,row=1,column=1,literal='15,922,637,039',account=controls[0][1],period_start='2009-01-01',period_end='2009-12-31',unit='원');version['evidence'].append('Named CF field is independently corroborated against original XML and same official node; late CFS attachment not imported.')
  selected=bridge([dict(row=row,attestation=a)],signal,previous['calendar']);assert selected['source_ready_rows']==1 and selected['snapshots'].iloc[0].ocf_cum==15922637039 and selected['snapshots'].iloc[0].rcept_no==row['rcept_no'];assert not selected['engine_population_ready']
  checks={}
  for day in ['2010-03-30','2010-03-31','2010-05-03']:
   blocked=bridge([dict(row=row,attestation=a)],day,previous['calendar']);assert blocked['source_ready_rows']==0;checks[day]=blocked['decisions']
  changed={**row,'amount_krw':'15922637040'};assert bridge([dict(row=changed,attestation=a)],signal,previous['calendar'])['source_ready_rows']==0
  cases.append(dict(signal=signal,row=row,attestation=a,calendar=previous['calendar'],provider_rows=selected['raw'].to_dict('records'),provider_snapshots=selected['snapshots'].to_dict('records'),boundary_checks=checks,amount_change_rejected=True,classification='RESEARCH_ONLY',population_ready=False))
 # Exact legacy cumulative marker is retained; no rewrite of the original row.
 existing=[dict(row=prior['original_record'],attestation=prior['attestation'])]+[dict(row=c['row'],attestation=c['source_attestations']['2010-04-01']['attestation'])for c in annual['cases']]
 ready=bridge(existing+[dict(row=row,attestation=cases[0]['attestation'])],'2010-04-01',prior['calendar']);assert ready['source_ready_rows']==4 and ready['source_ready_stocks']==1
 # Compare the three old fields to the immutable pre-change provider evidence.
 import pandas as pd
 previous=ROOT/'docs/research/legacy-provider-link-20261023/evidence'
 old_rows=pd.read_csv(previous/'EXISTING_ATTESTED_ACCOUNT_ROWS.csv',dtype=str).fillna('');new_old=ready['raw'][ready['raw'].sj_div!='CF'].fillna('').astype(str)
 pd.testing.assert_frame_equal(old_rows.reset_index(drop=True),new_old.reset_index(drop=True))
 old_snapshot=pd.read_csv(previous/'EXISTING_PROVIDER_SNAPSHOT.csv',dtype=str).fillna('');new_snapshot=ready['snapshots']
 for name in ['equity_current','revenue_current','net_income_current']:
  assert Decimal(old_snapshot.iloc[0][name])==Decimal(str(new_snapshot.iloc[0][name]))
 ready['raw'].to_csv(output/'CANONICAL_FY4_ACCOUNT_ROWS.csv',index=False);ready['snapshots'].to_csv(output/'CANONICAL_FY4_SNAPSHOT.csv',index=False)
 report=dict(status='PASS_NEW_SOURCE_ATTESTED_ANNUAL_CUMULATIVE_OCF',classification='RESEARCH_ONLY',new_unique_provider_fields=1,new_issuers=0,new_periods=0,new_field_signal_pairs=2,stock='007160',corp='00124799',receipt=old['rcept_no'],annual_OCF_krw='15922637039',measurement_basis='cumulative',current_provider_owner='dart_value_factor_adapter.report_snapshots/latest_snapshot',raw_controls=references,top_level_OCF_identity='34326086558+14580298231-28544031412-4439716338=15922637039',cases=cases,prior_three_source_rows='EXACT_UNCHANGED',prior_three_provider_values='EXACT_UNCHANGED',total_previously_reviewed_plus_new_FY_core_fields=4,old_bulk_newly_admitted=0,current914_changed=False,current914_PIT_promoted=0,new_rank_strategy_periods=0,source_HTTP=0,operating_values_changed=0,financial_publication='HOLD',investment_PIT='0/6',scope_limit='Outside914 existing canary; bounded named primary OFS field at4/1 and4/30 only. Annual notQ4. No actual two-version correction, whole-document extraction or full-universe certification.')
 (output/'OCF_CASE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in {'cases','raw_controls'}},ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
