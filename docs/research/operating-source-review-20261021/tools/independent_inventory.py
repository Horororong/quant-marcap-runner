"""Read-only evidence inventory from original XML, separate from native collector."""
import ast,collections,hashlib,html,json,re,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
P=Path(__file__).parent;S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded')
# Manually reviewed source headings/period columns, not candidate-derived defaults.
CONTROL={
'20100331001943':(18,'원',{'OFS':(67,69,75)}),'20100331001944':(50,'원',{'OFS':(87,89,95)}),'20100331001949':(6,'원',{'OFS':(61,63,69)}),'20100331001950':(13,'원',{'OFS':(102,104,110)}),'20100331001951':(33,'원',{'OFS':(149,151,157)}),'20100331001953':(15,'원',{'OFS':(102,104,110)}),'20100331001954':(16,'원',{'OFS':(82,84,90)}),'20100331001955':(9,'원',{'OFS':(163,165,171)}),'20100331001960':(11,'원',{'OFS':(95,97,103)}),'20100331001961':(36,'원',{'OFS':(171,173,179),'CFS':(181,183,187)}),'20100331001962':(13,'원',{'OFS':(67,69,75)}),'20100331001963':(10,'원',{'OFS':(74,76,82)}),'20100331001966':(10,'원',{'OFS':(106,108,114)}),'20100331001972':(22,'원',{'OFS':(127,129,135),'CFS':(58,60,64)}),'20100331001977':(27,'백만원',{'OFS':(183,185,191)}),'20100331001980':(48,'천원',{'CFS':(125,127,131)}),'20100331001981':(13,'원',{'OFS':(74,76,82)}),'20100331001982':(3,'천원',{'OFS':(125,127,133),'CFS':(135,137,141)}),'20100331002038':(29,'원',{'OFS':(167,169,175)})}
# Registry only declares the inventory's requested concepts. No production parser,
# choose_metric, decimal_amount, table selector or scope inference is imported.
tree=ast.parse(Path('/workspace/quant-project-full-20261020/code/scripts/legacy_financial_fields.py').read_text());registry={}
for n in tree.body:
 if isinstance(n,ast.Assign):
  for target in n.targets:
   if isinstance(target,ast.Name)and target.id in {'ALIASES','METRIC_STATEMENTS'}:registry[target.id]=ast.literal_eval(n.value)
def plain(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s))).strip()
def norm(label):
 label=re.sub(r'\((?:주석|주)[\s\d,~과및등-]*\)\s*$','',label);label=re.sub(r'\s+','',label).strip('= _');return re.sub(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVXLC0-9.()\-]+','',label)
def literal(text):
 text=text.strip().replace(',','').replace('−','-').replace('－','-');negative=(text.startswith('(')and text.endswith(')'))or text.startswith(('▲','△','Δ'));text=text.strip('()▲△Δ')
 if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',text):return None
 d=Decimal(text);return -abs(d)if negative else d
def row_cells(table):
 rows=[]
 for m in re.finditer(r'<TR(?=[\s>])[^>]*>(.*?)</TR\s*>',table,re.I|re.S):
  cs=[dict(text=plain(c.group(2)),attrs=c.group(1))for c in re.finditer(r'<(?:TD|TH|TE|TU)(?=[\s>])([^>]*)>(.*?)</(?:TD|TH|TE|TU)\s*>',m.group(1),re.I|re.S)]
  if cs:rows.append(cs)
 return rows
expected=[];sources=[];missing=[];ambiguous=[]
for p in sorted(S.rglob('results/*.json')):
 doc=json.loads(p.read_text());rec=doc['meta']['rcept_no']
 if rec not in CONTROL:continue
 term,unit,scopes=CONTROL[rec];archive=next((p.parent.parent/'native').glob(rec+'-*.zip'))
 with zipfile.ZipFile(archive)as z:
  member=rec+'.xml';raw=z.read(member)
  for enc in ['utf-8','cp949','euc-kr']:
   try:t=raw.decode(enc);break
   except UnicodeDecodeError:continue
 starts=list(re.finditer(r'<TABLE(?=[\s>])',t,re.I))
 for scope,tables in scopes.items():
  present={r['metric']for r in doc['rows']if r['scope']==scope}
  for family,ix in zip(['BS','IS','CF'],tables):
   start=starts[ix].start();end=t.find('</TABLE>',start);rs=row_cells(t[start:end+8]);header=plain(t[max(0,start-2000):start]);cols=[1,2]if rec in {'20100331001972','20100331001982'}and scope=='CFS'else[1]
   sources.append(dict(receipt=rec,scope=scope,family=family,member=member,member_sha256=hashlib.sha256(raw).hexdigest(),table=ix,header=header,header_cells=rs[0],rows=rs,term=term,unit=unit,current_physical_columns=cols))
   for i,cells in enumerate(rs):
    if len(cells)<2:continue
    label=cells[0]['text'];metric=[m for m,aliases in registry['ALIASES'].items()if family in registry['METRIC_STATEMENTS'].get(m,set())and norm(label)in{norm(a)for a in aliases}]
    if not metric:continue
    # Scope-specific primary statement and its proved current-column group.
    numbers=[(col,literal(cells[col]['text']))for col in cols if col<len(cells)and literal(cells[col]['text'])is not None]
    base=dict(receipt=rec,scope=scope,family=family,table=ix,row=i,label=label,cells=[c['text']for c in cells],metrics=metric,current_physical_columns=cols)
    if len(numbers)!=1:
     if any(c['text']not in {'','-','—'}for c in cells[1:]):ambiguous.append(dict(**base,reason='CURRENT_CELL_PRESENTATION_OR_GROUP_UNVERIFIED'))
     continue
    col,value=numbers[0]
    if '손실'in label and'이익'not in label:value=-abs(value)
    for met in metric:
     item=dict(**base,metric=met,current_column=col,source_amount=str(value),unit=unit,term=term)
     expected.append(item)
     if met not in present:missing.append(dict(**item,verdict='SOURCE_PRESENT_CANDIDATE_ABSENT',PIT='UNVERIFIED',publication='HOLD'))
record=dict(scope='Manual primary BS/IS/CF table families and source-proved current-column groups, registered monetary account aliases only. Not whole-filing/notes/attachments/unsupported aliases/PIT completeness certification.',controls=CONTROL,source_tables=sources,expected_current_source_rows=expected,missing=missing,source_cell_groups_needing_review=ambiguous)
(P/'primary-table-inventory.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print('primary source tables',len(sources),'declared monetary rows',len(expected),'source present/candidate absent',len(missing),'presentation groups',len(ambiguous))
for r in missing:print('MISSING',r['receipt'],r['scope'],r['family'],r['metric'],r['source_amount'],r['label'])
for r in ambiguous:print('PRESENTATION',r['receipt'],r['scope'],r['family'],r['table'],r['row'],r['label'],r['cells'][:5])
