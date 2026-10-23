"""Named primary source controls transcribed BEFORE candidate amount comparison.
No production parser import. Whole filing completeness/PIT remain separate.
"""
import hashlib,io,json,re,sys,zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
import argparse
a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--workdir',type=Path,required=True);args=a.parse_args();R=args.root;P=args.workdir;sys.path.insert(0,str(R/'scripts'));from financial_source_grid import Grid
# term, BS table/equity row/value, IS table/revenue row/value, NI row/value,
# CF table/OCF row/value. Current physical column1, exact OFS FY2009, KRW1.
CONTROLS={
'20100331001761':[38,109,116,'267164561466',111,1,'803174786065',83,'10182466223',117,1,'109869545005'],
'20100331001769':[37,49,101,'17403479511',51,1,'50125849731',79,'765191041',57,1,'22252523901'],
'20100331001771':[44,134,125,'30458591369',136,1,'25765057888',73,'351420446',142,1,'1205723502'],
'20100331001778':[28,116,98,'81487763621',118,1,'571821264398',63,'6790259439',124,1,'-21787711407'],
'20100331001779':[2,95,84,'34274895149',97,1,'74916538296',55,'3013683040',103,1,'2321848125'],
'20100331001780':[21,54,79,'105687074334',56,1,'64748407097',73,'5521470916',62,1,'68301540403'],
'20100331001781':[42,107,76,'77177985784',109,1,'257079909995',60,'7452348986',115,1,'18439373054'],
'20100331001783':[21,107,80,'127160786541',109,1,'9631327008',55,'-11200439241',115,1,'-2358451137'],
'20100331001788':[14,235,92,'26323946348',237,1,'207217582967',62,'6551322530',243,1,'1375154632'],
'20100331001811':[15,103,70,'221582517054',105,1,'191841842440',57,'36519338829',111,1,'49729618154'],
'20100331001823':[12,96,109,'21297188765',98,1,'15006835551',74,'-8962262830',104,1,'-1493428329'],
'20100331001830':[20,164,106,'68553447290',166,1,'127457053649',90,'889899712',172,1,'-976932330'],
'20100331001840':[9,58,92,'36126924110',60,1,'86009899002',77,'-15326315973',66,1,'19861984024'],
'20100331001853':[11,99,81,'70171558614',101,1,'6854420166',83,'-7459012958',107,1,'-1996263242'],
'20100331001861':[2,92,86,'30499137789',94,1,'74514553314',58,'-1179952979',100,1,'811368549'],
'20100331001862':[62,169,77,'30177328172',171,1,'48595592085',48,'2888948848',177,1,'4406658439'],
'20100331001866':[37,75,138,'100417983784',77,1,'10830190881',50,'-37132383552',83,1,'4432977059'],
'20100331001878':[49,67,76,'72733421020',69,1,'221030682513',62,'31325990110',75,1,'32059271678'],
'20100331001888':[14,78,91,'214933638464',80,1,'200095504250',80,'2359444272',86,1,'30735693662'],
'20100331001893':[10,114,115,'23766662854',116,1,'33400784023',80,'192946419',122,1,'2611619596']}
controls_sha=hashlib.sha256(json.dumps(CONTROLS,sort_keys=True).encode()).hexdigest();out=P/'new20-review';out.mkdir(exist_ok=False);scope=json.loads((P/'FROZEN_NEW_REVIEW_SCOPE.json').read_text());assert {d['receipt']for d in scope['documents']}==set(CONTROLS);reviews=[];docs=[];exclusions=[]
for d in scope['documents']:
 receipt=d['receipt'];f=P/'first100-chunks'/d['result'];part=f.parents[1];archive=next((part/'native').glob(receipt+'-*.zip'));rawzip=archive.read_bytes()
 assert hashlib.sha256(rawzip).hexdigest()==archive.stem.split('-')[1]
 with zipfile.ZipFile(io.BytesIO(rawzip))as z:assert z.testzip()is None;member=receipt+'.xml';raw=z.read(member)
 for enc in ['utf-8','cp949','euc-kr']:
  try:text=raw.decode(enc);assert text.encode(enc)==raw;break
  except(UnicodeError,AssertionError):continue
 else:raise ValueError('ENCODING_NOT_PROVED')
 g=Grid();g.feed(text);term,bs,eqr,eq,ist,rr,rev,nr,ni,cf,cr,ocf=CONTROLS[receipt];assert '개별재무제표'in re.sub(r'\s+','',g.tables[bs]['context']);golden=[('equity','BS',bs,eqr,eq),('revenue','IS',ist,rr,rev),('net_income','IS',ist,nr,ni),('ocf','CF',cf,cr,ocf)];candidates=json.loads(f.read_text())['rows'];reviewed_candidate_ids=set()
 for metric,statement,table_index,row_index,expected in golden:
  table=g.tables[table_index];row=table['rows'][row_index];header=table['rows'][0];context=re.sub(r'\s+','',table['context']);assert re.search(r'第|제',header[1])and str(term)in header[1];assert '2009년12월31일'in context and'(단위:원)'in context
  if metric!='equity':assert '2009년01월01일'in context or'2009년1월1일'in context
  literal=row[1].strip();assert re.fullmatch(r'\(?[\d,]+\)?',literal);reference=Decimal(literal.replace(',','').strip('()'))*(-1 if literal.startswith('(')else 1);assert reference==Decimal(expected),(receipt,metric,'GOLDEN_SOURCE_MISMATCH')
  matching=[(n,r)for n,r in enumerate(candidates)if r['metric']==metric and r['scope']=='OFS'and r['statement']==statement and r['source_member']==member and r['table_index']==table_index and r['row_index']==row_index and r['value_col']==1]
  if len(matching)!=1:exclusions.append(dict(receipt=receipt,metric=metric,reason='NO_UNIQUE_CANDIDATE_AT_REVIEWED_SOURCE_COORDINATE',matches=len(matching)));continue
  n,candidate=matching[0];reviewed_candidate_ids.add(n);checks=dict(amount=Decimal(str(candidate['amount_krw']))==reference,unit=candidate['unit']=='원'and Decimal(str(candidate['unit_multiplier']))==1,period=candidate['period_end']=='2009-12-31'and candidate['period_start']==(''if metric=='equity'else'2009-01-01'),member=hashlib.sha256(raw).hexdigest()==candidate['source_member_sha256'],archive=hashlib.sha256(rawzip).hexdigest()==candidate['document_sha256'])
  verdict='PASS'if all(checks.values())else'FAIL';reviews.append(dict(receipt=receipt,stock_code_hint=d['stock_hint'],corp_code=d['corp'],original_issuer=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)',text[:3000])[2],scope='OFS',statement=statement,metric=metric,period_start=''if metric=='equity'else'2009-01-01',period_end='2009-12-31',measurement_basis=candidate['measurement_basis'],source_archive_sha256=hashlib.sha256(rawzip).hexdigest(),source_member=member,source_member_sha256=hashlib.sha256(raw).hexdigest(),table=table_index,row=row_index,current_physical_column=1,source_row_label=row[0],literal=literal,independent_amount_krw=str(reference),candidate_amount_krw=str(candidate['amount_krw']),reference_unit='원',reference_unit_multiplier='1',source_term=term,current_header=header,source_context=table['context'],period_current_comparative='PASS',scope_heading='PASS',unit_sign='PASS',account_definition='PASS',semantic_verdict=verdict,checks=checks,candidate_fingerprint=hashlib.sha256(json.dumps(candidate,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),definition='Reported equity at year-end or named annual IS/CF line; operating-revenue aliases are not certified as economically comparable across industries',PIT='UNVERIFIED_PUBLICATION_AND_VERSION_CHAIN',engine_eligible=False,whole_filing_extraction_completeness='UNVERIFIED',review_method='Independent manual primary-source table/current-year/column/unit/scope controls frozen before candidate amount comparison; no production parser replay'))
 docs.append(dict(receipt=receipt,stock_hint=d['stock_hint'],candidate_count=len(candidates),reviewed_core_candidate_count=len(reviewed_candidate_ids),remaining_candidate_count=len(candidates)-len(reviewed_candidate_ids),core_presence='FOUR_NAMED_PRIMARY_OFS_LINES_ONLY',whole_document_review_complete=False,unreviewed_candidate_indices=[n for n in range(len(candidates))if n not in reviewed_candidate_ids]))
summary=dict(classification='RESEARCH_ONLY',new_documents_with_core_field_review=len(docs),new_source_meaning_PASS=sum(r['semantic_verdict']=='PASS'for r in reviews),new_source_meaning_FAIL=sum(r['semantic_verdict']=='FAIL'for r in reviews),reviewed_fields=len(reviews),source_candidate_binding_exclusions=len(exclusions),first100_total=1363,first100_new_reviewed=len(reviews),first100_remaining_unreviewed=1363-len(reviews),selected20_other_candidates_unreviewed=sum(d['remaining_candidate_count']for d in docs),prior914=dict(PASS=891,UNVERIFIED=23,changed=0),combined_research2277=dict(PASS=891+sum(r['semantic_verdict']=='PASS'for r in reviews),FAIL=sum(r['semantic_verdict']=='FAIL'for r in reviews),reviewed_UNVERIFIED=23,unreviewed=1363-len(reviews)),new_source_HTTP=0,new_candidates=0,new_PIT_eligible=0,new_live_engine_eligible=0,whole_documents_completed=0,independent_controls_sha256=controls_sha)
(out/'NEW20_CORE_SOURCE_REVIEW.json').write_text(json.dumps(dict(summary=summary,rows=reviews,documents=docs,exclusions=exclusions),ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));assert len(reviews)==80 and not exclusions and summary['new_source_meaning_FAIL']==0
