"""Independent XML DOM/source-control audit. Production parser is never imported.
Physical references locate originals only; human table controls establish semantics.
Unknown table contracts and ambiguous source tokens cannot PASS.
"""
import argparse,csv,hashlib,json,re,zipfile,collections
import xml.etree.ElementTree as ET
from decimal import Decimal,localcontext
from pathlib import Path
from datetime import date
p=argparse.ArgumentParser()
for k in ('original40','holdout20','replay','output'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();home=Path(__file__).resolve().parent.parent/"financial-repair-20261014";a.output.mkdir(parents=True,exist_ok=True)
base=json.loads((home/'baseline-controls.json').read_text());hold=json.loads((home/'holdout_controls.json').read_text())
supplement=json.loads((Path(__file__).resolve().parent/'source_controls.json').read_text())
base['tables'].update(supplement['tables'])
old=list(csv.DictReader((home/'baseline-details.csv').open(encoding='utf-8-sig')))
units={'원':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000),'억원':Decimal(100000000)}
def money(token,label='',decoration=False):
 if re.search(r'\d\s+\d',token):return None
 s=re.sub(r'\s+','',token).replace('−','-').replace('－','-')
 if decoration:s=s.rstrip('=')
 negative=s.startswith(('(','△','▲','Δ'))
 if s.startswith('(-)'):s=s[3:]
 elif s.startswith('(')and s.endswith(')'):s=s[1:-1]
 if s.startswith(('△','▲','Δ')):s=s[1:]
 if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:[.][0-9]+)?',s):return None
 v=Decimal(s.replace(',',''))
 if negative:v=-abs(v)
 account=re.sub(r'\s+','',label)
 if '손실'in account and '이익'not in account:v=-abs(v)
 return v
def source(root,s):
 f=next((root/'originals').glob(s['rcept_no']+'-*.zip'));b=f.read_bytes()
 assert hashlib.sha256(b).hexdigest()==s['document_sha256']
 out=[]
 with zipfile.ZipFile(f)as z:
  assert z.testzip()is None
  for name in z.namelist():
   raw=z.read(name);text=None
   for enc in ('utf-8','cp949','euc-kr'):
    try:
     t=raw.decode(enc);assert t.encode(enc)==raw;text=t;break
    except UnicodeError:continue
   assert text is not None
   structural=re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)','&amp;',text)
   doc=ET.fromstring(structural)
   tables=[]
   for table in doc.iter('TABLE'):
    rows=[]
    for row in table.iter('TR'):
     cells=[c for c in row if c.tag in {'TD','TH','TE','TU'}]
     rows.append(cells)
    tables.append(rows)
   out.append({'name':name,'doc':doc,'tables':tables,'text':text,'sha256':hashlib.sha256(raw).hexdigest()})
 return out
assert money('7,205,734,7733') is None
assert money('1,234','당 기 순 이 익 (손실)') == Decimal(1234)
assert money('1,234','당 기 순 손 실') == Decimal(-1234)
def text(c):return ' '.join(''.join(c.itertext()).split())
def lines(c):
 result=['']
 def visit(e):
  if e.tag=='BR':result.append('')
  elif e.text:result[-1]+=e.text
  for child in e:
   visit(child)
   if child.tail:result[-1]+=child.tail
 visit(c)
 return [s.strip()for s in result]
def tally(values):return {k:values.count(k)for k in ('PASS','FAIL','UNVERIFIED')}
def source_window(rows,ri,ci,controlled):
 # Independent DOM header span expansion. Financial semantics come from the
 # human contract; only the original 3-month/cumulative headings set the basis.
 if not controlled.get('has_three_month_and_cumulative_header'):return 'cumulative'
 layout=[];occupied={}
 for rn,rs in enumerate(rows[:max(ri+1,4)]):
  cells={col:cell for col,(until,cell)in occupied.items()if until>=rn}
  occupied={col:(until,cell)for col,(until,cell)in occupied.items()if until>=rn}
  col=0
  for cn,cell in enumerate(rs):
   while col in cells:col+=1
   width=int(cell.attrib.get('COLSPAN','1'));height=int(cell.attrib.get('ROWSPAN','1'))
   for x in range(col,col+width):
    cells[x]=(rn,cn,cell)
    if height>1:occupied[x]=(rn+height-1,(rn,cn,cell))
   col+=width
  layout.append(cells)
 logical=[c for c,v in layout[ri].items()if v[:2]==(ri,ci)]
 for hr in layout[:4]:
  for col in logical:
   if col in hr:
    caption=re.sub(r'\s+','',text(hr[col][2]))
    if caption in {'3개월','누적'}:return 'three_month'if caption=='3개월'else'cumulative'
 return ''
detail=[];summary=[];targets=[];regressions=[]
def add(s,field,oracle,extracted,unit,verdict,where,reason,row_type='FIELD',before='',**extra):
 detail.append({'row_type':row_type,'sample_id':s['sample_id'],'category':s['category'],'corp_name':s['corp_name'],'stock_code':s['stock_code'],'corp_code':s['corp_code'],'rcept_no':s['rcept_no'],'accounting_period':s['period'],'field':field,'original_value':oracle,'extracted_value':extracted,'unit':unit,'verdict':verdict,'before_verdict':before,'evidence_location':where,'reason':reason,'document_sha256':s['document_sha256'],**extra})
for root in (a.original40,a.holdout20):
 selection=json.loads((root/'selection.json').read_text())['samples']
 for s in selection:
  sid=s['sample_id'];isold=sid.startswith('S');r=json.loads((a.replay/(sid+'.json')).read_text());docs=source(root,s)
  controls=base['samples'][sid]if isold else hold['samples'][sid]
  expected_end=controls.get('original_period_end',controls.get('period_end'))
  alltxt=' '.join(text(c) for d in docs for c in d['doc'].iter('COVER'))
  validcover=expected_end.replace('-','.')in alltxt.replace(' ','') # fall back explicit Korean date below
  ed=expected_end.split('-')
  pattern=rf'{ed[0]}\s*[.년/-]\s*0?{int(ed[1])}\s*[.월/-]\s*0?{int(ed[2])}(?:\s*[.일])?'
  validcover=bool(re.search(pattern,alltxt))
  field_results=[];per_unit=[];per_scope=[];per_current=[];per_window=[]
  for row in r['rows']:
   d=next(x for x in docs if x['name']==row['source_member']);ti,ri,ci=(row[k]for k in ('table_index','row_index','value_col'));rows=d['tables'][ti]
   rawlines=lines(rows[ri][ci]);li=row.get('source_line_index',0)
   raw=rawlines[li]if len(rawlines)>1 else text(rows[ri][ci])
   label_lines=lines(rows[ri][0]);label=label_lines[li]if len(label_lines)>1 else text(rows[ri][0])
   t=base['tables'].get(f'{sid}:{ti}')if isold else None
   h=next((x for x in hold['fields']if x['sample_id']==sid and x['table']==ti and x['row']==ri and x['metric']==row['metric']),None)if not isold else None
   if h is None:h=next((x for x in supplement['fields']if x['sample_id']==sid and x['table']==ti and x['row']==ri and x['metric']==row['metric']),None)
   if h and (not isold or not t):t={'unit':h['unit'],'scope':h['scope'],'period_end':h['period_end'],'kind':'primary','current_group_cols':[h['column']],'has_three_month_and_cumulative_header':h['basis']=='cumulative'}
   loc=f'{s["rcept_no"]}/{d["name"]}#TABLE[{ti}]/TR[{ri}]/CELL[{ci}]/line[{li}]'
   scope_ok=bool(t and t['scope']==row['scope']and t['kind']=='primary'and t['period_end']==expected_end)
   col_ok=bool(t and ci in t['current_group_cols'])
   amount=money(raw,label,decoration=bool(h and h.get('decoration')))
   with localcontext()as ctx:
    ctx.prec=50
    expected=amount*units[t['unit']]if amount is not None and t and t['unit']in units else None
   unit_ok=bool(t and row['unit']==t['unit'])
   period_ok=validcover and row['period_end']==expected_end
   window=h['basis']if h else source_window(rows,ri,ci,t)if t else ''
   window_ok=bool(t and (row['statement']=='BS' and row['measurement_basis']=='instant' or row['period_start']and row['measurement_basis']==window))
   if h:window_ok=window_ok and row['period_start']==h['period_start']
   if window_ok and row['measurement_basis']=='three_month':
    end=date.fromisoformat(expected_end);ordinal=end.year*12+end.month-3
    window_ok=row['period_start']==date(ordinal//12,ordinal%12+1,1).isoformat()
   verdict='UNVERIFIED'
   reason='Independent human table/account contract unavailable'
   if t and amount is None:reason='Source token ambiguous or malformed; no invented normalization'
   elif t and expected is not None:
    verdict='PASS'if str(expected)==str(Decimal(row['amount_krw']))and unit_ok and scope_ok and col_ok and period_ok and window_ok else'FAIL'
    reason='Exact original-unit DOM arithmetic and human current primary statement controls; zero tolerance'
   field_results.append(verdict);per_unit.append('PASS'if unit_ok else'UNVERIFIED');per_scope.append('PASS'if scope_ok else'UNVERIFIED');per_current.append('PASS'if col_ok else'UNVERIFIED');per_window.append('PASS'if window_ok else'UNVERIFIED')
   add(s,row['metric'],str(expected)if expected is not None else raw,row['amount_krw'],row['unit'],verdict,loc,reason,source_member_sha256=d['sha256'],scope=row['scope'],period_end=row['period_end'],measurement_basis=row['measurement_basis'],period_start=row['period_start'])
  # A fixed denominator also records original fields that are now withheld.
  if isold:
   prior=[x for x in old if x['row_type']=='FIELD'and x['sample_id']==sid]
   for before in prior:
    matches=[x for x in detail if x['row_type']=='FIELD'and x['sample_id']==sid and x['field']==before['financial_field']and x['scope']==before['scope_extracted']and x['rcept_no']==before['rcept_no']and x['period_end']==expected_end]
    after=matches[0]['verdict']if matches else'UNVERIFIED'
    targets.append({'sample_id':sid,'metric':before['financial_field'],'scope':before['scope_extracted'],'before':'FAIL','before_amount':before['amount_verdict'],'after':after,'after_action':'EMITTED'if matches else'WITHHELD'})
    add(s,before['financial_field'],matches[0]['original_value']if matches else before['original_value'],matches[0]['extracted_value']if matches else'',matches[0]['unit']if matches else before['unit'],after,matches[0]['evidence_location']if matches else before['evidence_location'],'Fixed original565 denominator; source-backed current emitted value or explicit withholding. No substituted value.','BASELINE_TARGET',before['verdict'],before_extracted_value=before['extracted_value'],before_amount_verdict=before['amount_verdict'],scope=before['scope_extracted'])
    if before['amount_verdict']=='PASS'and after!='PASS':regressions.append(targets[-1])
  else:
   for oracle in [x for x in hold['fields']if x['sample_id']==sid]:
    # Frozen exact current-cumulative source target. Missing is an extraction FAIL.
    d=docs[0];actual=text(d['tables'][oracle['table']][oracle['row']][oracle['column']]);assert actual==oracle['raw']
    amount=money(actual,oracle['source_account'],oracle['decoration']);assert amount is not None
    expected=amount*units[oracle['unit']]
    found=next((x for x in r['rows']if x['metric']==oracle['metric']and x['scope']==oracle['scope']),None)
    verdict='FAIL'if found is None else'PASS'if Decimal(found['amount_krw'])==expected and found['period_end']==oracle['period_end']and found['measurement_basis']==oracle['basis']and found['unit']==oracle['unit']else'FAIL'
    targets.append({'sample_id':sid,'metric':oracle['metric'],'scope':'OFS','after':verdict,'after_action':'EMITTED'if found else'MISSING'})
    add(s,oracle['metric'],str(expected),found['amount_krw']if found else'',oracle['unit'],verdict,f'{s["rcept_no"]}/{docs[0]["name"]}#TABLE[{oracle["table"]}]/TR[{oracle["row"]}]/CELL[{oracle["column"]}]','Frozen holdout oracle; missing current source value is an extraction defect','HOLDOUT_TARGET')
  def aggregate(v):return 'FAIL'if'FAIL'in v else'UNVERIFIED'if not v or'UNVERIFIED'in v else'PASS'
  period_verdict='PASS'if validcover and all(x['period_end']==expected_end for x in r['rows'])else'FAIL'
  checks={'1_identity':'UNVERIFIED','2_receipt_report_period':'UNVERIFIED'if period_verdict=='PASS'else'FAIL','3_amounts':aggregate(field_results),'4_units':aggregate(per_unit),'5_scope':aggregate(per_scope),'6_corrections':'UNVERIFIED','8_point_in_time':'UNVERIFIED'}
  if isold:
   checks['3_amounts']=aggregate(field_results+[x['after']for x in targets if x['sample_id']==sid])
  if not isold:
   core=[x['after']for x in targets if x['sample_id']==sid]
   if core:checks['3_amounts']=aggregate(core+field_results)
  if s['category']=='no_metrics' or s['status']=='NO_METRICS':
   present=(sid in base['financial_absence_evidence'])if isold else True
   checks['7_no_metrics']='PASS'if present and r['state']['status']!='NO_METRICS'and r['state']['financial_data_present']else'FAIL'
  for k,v in checks.items():
   before=next((x['verdict']for x in old if x['row_type']=='CHECK'and x['sample_id']==sid and x['check']==k),'')if isold else''
   add(s,k,'','', '',v,'original document faces and controlled tables',{'1_identity':'CIK matches alone do not establish historical ticker/name chain','2_receipt_report_period':'Exact source period separately checked; receipt filename/manifest agree but live receipt/report authentication is not independently obtained','6_corrections':'Internal corrected body is checked; full linked original/correction publication chain unavailable','8_point_in_time':'Publication timestamp and historical mapping unavailable; all observations quarantined'}.get(k,'Conservative aggregate; missing contracts remain unverified'),'CHECK',before)
  summary.append({'sample_id':sid,'checks':checks,'source_period_verdict':period_verdict,'field_counts':tally(field_results),'status':r['state']['status'],'rows':len(r['rows']),'backtest_eligible':False,'verdict':aggregate(list(checks.values()))})
header=sorted(set().union(*(x.keys()for x in detail)))
with (a.output/'audit_details.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=header);w.writeheader();w.writerows(detail)
comparison={}
for k in ['1_identity','2_receipt_report_period','3_amounts','4_units','5_scope','6_corrections','7_no_metrics','8_point_in_time']:
 comparison[k]={'before':tally([x['verdict']for x in old if x['row_type']=='CHECK'and x['check']==k and x['applicable']=='True']),'after':tally([x['checks'][k]for x in summary if x['sample_id'].startswith('S')and k in x['checks']])}
result={'samples':60,'original40':40,'holdout20':20,'all_original_sha_crc_verified':True,'field_rows':len([x for x in detail if x['row_type']=='FIELD']),'field_counts':tally([x['verdict']for x in detail if x['row_type']=='FIELD']),'original565_fixed_denominator':tally([x['after']for x in targets if x['sample_id'].startswith('S')]),'holdout64_targets':tally([x['after']for x in targets if x['sample_id'].startswith('N')]),'holdout_target_details':[x for x in targets if x['sample_id'].startswith('N')],'original565_details':[x for x in targets if x['sample_id'].startswith('S')],'baseline_amount_pass_not_revalidated_count':len(regressions),'baseline_amount_pass_not_revalidated':regressions,'comparison40':comparison,'sample_details':summary,'backtest_eligible_samples':0,'auditor_changes':'Stage3 supplementary source controls and exact receipt/metric/current-period/scope linking. Original Stage1 retained. Strict grouping rejects malformed 7,205,734,7733. New cumulative publication basis is explicit; old 3-month literal verdicts remain unchanged. No oracle import from production parser. Withheld original targets remain UNVERIFIED; missing known holdout targets FAIL.'}
(a.output/'validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in {'sample_details','baseline_amount_pass_not_revalidated','original565_details','holdout_target_details'}},ensure_ascii=False,indent=2))
