"""Independent Stage3 forensic comparison; production financial parser not imported.
Subjects are before/after output; originals, frozen controls and explicit keys are references.
"""
import argparse,csv,hashlib,json,re,zipfile,collections
import xml.etree.ElementTree as ET
from decimal import Decimal,localcontext
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('original40','holdout20','before_replay','before_audit','after_replay','after_audit','output'):
 p.add_argument('--'+n.replace('_','-'),dest=n,type=Path,required=True)
a=p.parse_args();home=Path(__file__).resolve().parent;basehome=home.parent/'financial-repair-20261014'
a.output.mkdir(parents=True,exist_ok=True)
ctl=json.loads((basehome/'baseline-controls.json').read_text())
supp=json.loads((home/'source_controls.json').read_text())
old=[x for x in csv.DictReader((basehome/'baseline-details.csv').open(encoding='utf-8-sig'))if x['row_type']=='FIELD']
stage2=json.loads((a.before_audit/'validation_summary.json').read_text())
oldU=[x for x in stage2['original565_details']if x['after']=='UNVERIFIED']
assert len(old)==565 and len(oldU)==135 and sum(x['before_amount']=='PASS'for x in oldU)==123
after_details=list(csv.DictReader((a.after_audit/'audit_details.csv').open(encoding='utf-8-sig')))
before_details=list(csv.DictReader((a.before_audit/'audit_details.csv').open(encoding='utf-8-sig')))
units={'원':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000),'억원':Decimal(100000000)}
def num(raw,label=''):
 if re.search(r'\d\s+\d',raw):return None
 token=re.sub(r'\s+','',raw).replace('−','-').replace('－','-')
 neg=token.startswith(('(','△','▲','Δ'))
 if token.startswith('(-)'):token=token[3:]
 elif token.startswith('(')and token.endswith(')'):token=token[1:-1]
 if token.startswith(('△','▲','Δ')):token=token[1:]
 if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:[.][0-9]+)?',token):return None
 d=Decimal(token.replace(',',''))
 label=re.sub(r'\s+','',label)
 if neg:d=-abs(d)
 if '손실'in label and '이익'not in label:d=-abs(d)
 return d
def cells(t,ri):return [x for x in list(t.iter('TR'))[ri]if x.tag in {'TD','TH','TE','TU'}]
def txt(c):return ' '.join(''.join(c.itertext()).split())
def key(row):return (row['rcept_no'],row['metric'],row['period_start'],row['period_end'],row['scope'],row['measurement_basis'])
def keyjson(k):return json.dumps(k,ensure_ascii=False,separators=(',',':'))
subjects_before={};subjects_after={};samples={};references={}
for root in (a.original40,a.holdout20):
 for s in json.loads((root/'selection.json').read_text())['samples']:
  sid=s['sample_id'];samples[sid]=s
  subjects_before[sid]=json.loads((a.before_replay/(sid+'.json')).read_text())
  subjects_after[sid]=json.loads((a.after_replay/(sid+'.json')).read_text())
  assert subjects_before[sid]['sample']['document_sha256']==subjects_after[sid]['sample']['document_sha256']==s['document_sha256']
  path=next((root/'originals').glob(s['rcept_no']+'-*.zip'));blob=path.read_bytes()
  assert hashlib.sha256(blob).hexdigest()==s['document_sha256']
  with zipfile.ZipFile(path)as z:
   assert z.testzip()is None
   for member in subjects_after[sid]['source']['members']:
    assert hashlib.sha256(z.read(member['name'])).hexdigest()==member['sha256']
   b=z.read(subjects_after[sid]['source']['members'][0]['name'])
  text=None
  for enc in ('utf-8','cp949','euc-kr'):
   try:
    decoded=b.decode(enc);assert decoded.encode(enc)==b;text=decoded;break
   except UnicodeError:continue
  assert text is not None
  doc=ET.fromstring(re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)','&amp;',text))
  references[sid]={'tables':list(doc.iter('TABLE')),'member_sha256':hashlib.sha256(b).hexdigest()}
def verified_field(sid,row,details):
 return next((x for x in details if x['row_type']=='FIELD'and x['sample_id']==sid and x['rcept_no']==row['rcept_no']and x['field']==row['metric']and x['scope']==row['scope']and x['period_start']==row['period_start']and x['period_end']==row['period_end']and x['measurement_basis']==row['measurement_basis']),None)
def region(table,ri):
 phase=''
 for r in list(table.iter('TR'))[:ri+1]:
  cs=[x for x in r if x.tag in {'TD','TH','TE','TU'}]
  label=re.sub(r'\s+','',txt(cs[0]))if cs else''
  if label in {'자산','부채','자본'}:phase=label
 return phase
classification=[]
for target in oldU:
 sid,metric,scope=target['sample_id'],target['metric'],target['scope']
 matches=[b for b in old if b['sample_id']==sid and b['rcept_no']==samples[sid]['rcept_no']and b['financial_field']==metric and b['scope_extracted']==scope]
 assert len(matches)==1
 b=matches[0];expected_end=ctl['samples'][sid]['original_period_end']
 # Original target and original literal are kept distinct; corrections/previous
 # columns must never be silently joined to a different source or period.
 loc=b['evidence_location'];m=re.search(r'table-(\d+)[.]json#rows\[(\d+)\][.]cells\[(\d+)\]',loc)
 assert m,(sid,loc);ti,ri,ci=map(int,m.groups())
 table=references[sid]['tables'][ti];raw=txt(cells(table,ri)[ci]);label=txt(cells(table,ri)[0])
 tc=ctl['tables'].get(f'{sid}:{ti}',supp['tables'].get(f'{sid}:{ti}',{}))
 unit=tc.get('unit',b['unit']);literal=num(raw,label)
 with localcontext()as c:
  c.prec=50;source_krw=literal*units[unit]if literal is not None and unit in units else None
 stage2_rows=[r for r in subjects_before[sid]['rows']if r['rcept_no']==b['rcept_no']and r['metric']==metric and r['scope']==scope and r['period_end']==expected_end]
 stage3_rows=[r for r in subjects_after[sid]['rows']if r['rcept_no']==b['rcept_no']and r['metric']==metric and r['scope']==scope and r['period_end']==expected_end]
 assert len(stage2_rows)<=1 and len(stage3_rows)<=1
 after=stage3_rows[0]if stage3_rows else None
 grade=verified_field(sid,after,after_details)['verdict']if after is not None else'UNVERIFIED'
 if b['original_period_end']!=expected_end:
  category='SAFE_BLOCK';reason='Confirmed source is a different accounting period; same receipt/metric/scope is not a current-period key.'
 elif b['scope_original']!=scope or tc.get('kind')in {'segment','historical_merger','foreign_currency_subset'}:
  category='SAFE_BLOCK';reason='Source is a segment/merger/subset or different statement scope; original numeric agreement does not prove company-wide financial identity.'
 elif metric=='bonds_payable'and region(table,ri)=='자산':
  category='SAFE_BLOCK';reason='Company-bond holding appears under ASSETS/securities, not debt issued; original financial-field semantics were wrong.'
 elif b['current_column_verdict']=='FAIL'and re.sub(r'\s+','',raw)in {'','-','—','–','―'}:
  category='SAFE_BLOCK';reason='Current original cell is dash/blank; preceding parser selected a previous column. No invented current zero/value.'
 elif source_krw is None:
  category='SOURCE_EVIDENCE_INSUFFICIENT';reason='Malformed/ambiguous original scalar or missing original unit. No guessed repair of the published source.'
 elif metric in {'depreciation','amortization'}:
  category='AUDIT_METHOD_DIFFERENCE';reason='IS SG&A expense and CF total noncash adjustment are separate financial definitions; source scalars are proved, generic unqualified metric is not.'
 elif '요약재무정보'in re.sub(r'\s+','',tc.get('source_title_and_unit','')):
  category='AUDIT_METHOD_DIFFERENCE';reason='Earlier agreement concerns a low-precision summary. New full original statement value has a different precision; old number is not silently declared exact.'
 elif stage2_rows:
  category='AUDIT_METHOD_DIFFERENCE';reason='Stage2 emitted the corrected current value but lacked an independent controlled-table entry; fresh original header/unit/cell evidence supplied.'
 elif metric=='ppe':
  category='PARSING_REGRESSION';reason='Net carrying subtotal and gross component were conflated into one candidate group. Original net=gross+negative accumulated depreciation proves the correct subtotal.'
 else:
  category='SOURCE_EVIDENCE_INSUFFICIENT';reason='No sufficiently proved current financial definition or source boundary; keep unresolved.'
 recert='UNVERIFIED'
 if category=='PARSING_REGRESSION'and after is not None and source_krw is not None:
  recert='PASS'if grade=='PASS'and Decimal(after['amount_krw'])==source_krw else'FAIL'
 elif category=='SAFE_BLOCK':
  # A correct withholding is not successful extraction/reauthentication.
  recert='UNVERIFIED'
 elif category=='AUDIT_METHOD_DIFFERENCE'and stage2_rows and after is not None:
  recert=grade
 summary_source='UNVERIFIED'if source_krw is None else'PASS'if source_krw==Decimal(b['extracted_value'])else'FAIL'
 classification.append({'sample_id':sid,'rcept_no':b['rcept_no'],'metric':metric,'scope_stored':scope,
  'old_original_key':keyjson((b['rcept_no'],metric,b['extracted_period_end'],scope)),
  'proved_source_key':keyjson((b['rcept_no'],metric,b['original_period_end'],b['scope_original'])),
  'current_target_key':keyjson((b['rcept_no'],metric,expected_end,scope)),
  'stage2_exact_key':keyjson(key(stage2_rows[0]))if stage2_rows else'',
  'stage3_exact_key':keyjson(key(after))if after else'',
  'source_member_sha256':references[sid]['member_sha256'],'document_sha256':samples[sid]['document_sha256'],
  'stage1_amount_verdict':b['amount_verdict'],'was_previously_pass123':b['amount_verdict']=='PASS',
  'stage1_value':b['extracted_value'],'source_current_or_original_raw':raw,'source_amount_krw':str(source_krw)if source_krw is not None else'',
  'original_source_arithmetic_verdict':summary_source,'unit':unit,'stage2_verdict':'UNVERIFIED',
  'stage2_value':stage2_rows[0]['amount_krw']if stage2_rows else'',
  'stage3_value':after['amount_krw']if after else'','stage3_field_verdict':grade,
  'old123_current_recertification':recert,'category':category,'reason':reason,'source_evidence':loc})
protected=[]
for item in before_details:
 if item['row_type']!='FIELD'or item['verdict']!='PASS':continue
 sid=item['sample_id'];oldrow=[r for r in subjects_before[sid]['rows']if r['metric']==item['field']and r['scope']==item['scope']and r['period_start']==item['period_start']and r['period_end']==item['period_end']and r['measurement_basis']==item['measurement_basis']]
 assert len(oldrow)==1
 r=oldrow[0];new=[q for q in subjects_after[sid]['rows']if key(q)==key(r)];assert len(new)<=1
 q=new[0]if new else None;ref=verified_field(sid,q,after_details)if q else None
 v='UNVERIFIED'if q is None or ref is None or ref['verdict']=='UNVERIFIED'else'PASS'if Decimal(q['amount_krw'])==Decimal(r['amount_krw'])and q['unit']==r['unit']and ref['verdict']=='PASS'else'FAIL'
 protected.append({'sample_id':sid,'exact_key':keyjson(key(r)),'before_value':r['amount_krw'],'after_value':q['amount_krw']if q else'','unit':r['unit'],'verdict':v,'new_independent_field_verdict':ref['verdict']if ref else'UNVERIFIED','original_evidence':item['evidence_location'],'new_evidence':ref['evidence_location']if ref else''})
assert len(protected)==518
def write(name,records):
 header=sorted(set().union(*(x.keys()for x in records)))
 with (a.output/name).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=header,lineterminator='\n');w.writeheader();w.writerows(records)
write('unverified135_classification.csv',classification);write('protected518.csv',protected)
# All565 are linked by explicit receipt/field/period/scope; changed source or
# measurement window is recorded, never merged into a supposed same-value key.
links=[]
for b in old:
 sid,metric,scope=b['sample_id'],b['financial_field'],b['scope_extracted'];end=ctl['samples'][sid]['original_period_end']
 prior=[x for x in subjects_before[sid]['rows']if x['rcept_no']==b['rcept_no']and x['metric']==metric and x['scope']==scope and x['period_end']==end]
 newer=[x for x in subjects_after[sid]['rows']if x['rcept_no']==b['rcept_no']and x['metric']==metric and x['scope']==scope and x['period_end']==end]
 assert len(prior)<=1 and len(newer)<=1
 q=newer[0]if newer else None;ref=verified_field(sid,q,after_details)if q else None
 c=next((x for x in classification if x['sample_id']==sid and x['metric']==metric and x['scope_stored']==scope),None)
 links.append({'sample_id':sid,'rcept_no':b['rcept_no'],'metric':metric,'scope':scope,'old_recorded_period':b['extracted_period_end'],'proved_original_source_period':b['original_period_end'],'target_current_period':end,'old_original_key':keyjson((b['rcept_no'],metric,b['extracted_period_end'],scope)),'stage2_key':keyjson(key(prior[0]))if prior else'','stage3_key':keyjson(key(q))if q else'','stage1_value':b['extracted_value'],'stage1_amount_verdict':b['amount_verdict'],'stage2_value':prior[0]['amount_krw']if prior else'','stage2_verdict':next(x['after']for x in stage2['original565_details']if x['sample_id']==sid and x['metric']==metric and x['scope']==scope),'stage3_value':q['amount_krw']if q else'','stage3_verdict':ref['verdict']if ref else'UNVERIFIED','category':c['category']if c else'PREVIOUSLY_REVALIDATED','change_reason':c['reason']if c else'Compare the same exact current key; preserve direct original reference.'})
write('before_after565.csv',links)
count=lambda rs,k:dict(collections.Counter(x[k]for x in rs))
summary={'baseline_commit':'3f1ac4fd0709f42dd4400030c98d2666cc001960','all60_original_sha_crc_member_sha_verified':True,'old135_count':135,'previously_pass123_count':123,'old135_categories':count(classification,'category'),'old123_categories':count([x for x in classification if x['was_previously_pass123']],'category'),'old123_current_recertification':count([x for x in classification if x['was_previously_pass123']],'old123_current_recertification'),'old135_stage3_field_verdict':count(classification,'stage3_field_verdict'),'protected518':count(protected,'verdict'),'before_after565_stage3':count(links,'stage3_verdict'),'backtest_eligible':False,'category_interpretation':'SAFE_BLOCK treatment is successful but extracted value is not PASS; historical cell arithmetic is separate from current-period/metric reauthentication. Summary precision changes and missing audit controls are explicit. All source fields remain subject to identity/correction/publication gaps.'}
(a.output/'forensic_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
assert all(x['verdict']=='PASS'for x in protected),'New regression or missing independent proof for a formerly proved source value'
