"""Independent source-table inventory; never imports or reruns production extractor."""
import collections,hashlib,html,json,re,zipfile
from pathlib import Path
from decimal import Decimal
P=Path(__file__).parent;S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded')
CHOSEN={'20100331001943','20100331001944','20100331001949','20100331001950','20100331001951','20100331001953','20100331001954','20100331001955','20100331001960','20100331001961','20100331001962','20100331001963','20100331001966','20100331001972','20100331001977','20100331001980','20100331001981','20100331001982','20100331002038'}
plain=lambda s:re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s))).strip()
def cells(table):
 out=[]
 for match in re.finditer(r'<TR(?=[\s>])[^>]*>(.*?)</TR\s*>',table,re.I|re.S):
  cs=[dict(text=plain(m.group(2)),attrs=m.group(1))for m in re.finditer(r'<(?:TD|TH|TE|TU)(?=[\s>])([^>]*)>(.*?)</(?:TD|TH|TE|TU)\s*>',match.group(1),re.I|re.S)]
  if cs:out.append(cs)
 return out
records=[]
for file in sorted(S.rglob('results/*.json')):
 result=json.loads(file.read_text());receipt=result['meta']['rcept_no']
 if receipt not in CHOSEN:continue
 archive=next((file.parent.parent/'native').glob(receipt+'-*.zip'));members={};table_evidence=[];inventory=[]
 with zipfile.ZipFile(archive)as z:
  for member in z.namelist():
   if not member.lower().endswith(('.xml','.html','.htm')):continue
   raw=z.read(member)
   for enc in ['utf-8','cp949','euc-kr']:
    try:text=raw.decode(enc);break
    except UnicodeDecodeError:text=None
   if text is None:members[member]=dict(bytes=len(raw),decode='UNVERIFIED');continue
   starts=list(re.finditer(r'<TABLE(?=[\s>])',text,re.I));members[member]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),tables=len(starts),encoding=enc,correction_markers=[plain(text[max(0,m.start()-80):m.end()+200])for m in list(re.finditer(r'정정신고|정정사항|기재정정|정정대상',text))[:5]])
   wanted={r['table_index']for r in result['rows']if r['source_member']==member}
   for index,start in enumerate(starts):
    end=text.find('</TABLE>',start.start());table=text[start.start():end+8];rs=cells(table);labels=[c[0]['text']for c in rs if c]
    # Broad discovery deliberately includes summaries/notes; manual review must classify.
    core=[(i,label)for i,label in enumerate(labels)if re.search(r'자본총계|매출액|영업수익|당기순이익|당기순손실|영업활동.*현금흐름',label)]
    if core:inventory.append(dict(member=member,index=index,context=plain(text[max(0,start.start()-850):start.start()])[-850:],core_rows=[dict(row=i,cells=[c['text']for c in rs[i]][:6])for i,_ in core]))
    if index not in wanted:continue
    attached=[r for r in result['rows']if r['source_member']==member and r['table_index']==index]
    # Raw header before source table; never source-supplied candidate header.
    header=plain(text[max(0,start.start()-2400):start.start()]);numeric_rows=[]
    for i,rr in enumerate(rs):
     if any(re.search(r'\d',c['text'])for c in rr[1:]):numeric_rows.append(dict(row=i,cells=[c['text']for c in rr],cell_attrs=[c['attrs']for c in rr]))
    table_evidence.append(dict(member=member,index=index,header=header,first_rows=[[c['text']for c in rr]for rr in rs[:3]],source_rows=numeric_rows,candidates=attached))
 records.append(dict(receipt=receipt,meta=result['meta'],source_archive=str(archive.relative_to(S)),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),members=members,candidate_count=len(result['rows']),tables=table_evidence,full_source_core_inventory=inventory))
(P/'document-source-evidence.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
for d in records:
 out=['# '+d['receipt']+' '+d['meta'].get('corp_name','')+' '+d['meta']['report_nm']+' candidates='+str(d['candidate_count'])]
 for t in d['tables']:
  out+=['TABLE '+str(t['index'])+' / '+t['member'],'HEADER '+t['header'],'COLUMN '+json.dumps(t['first_rows'],ensure_ascii=False)]
  for c in t['candidates']:
   pos=c['row_index'];rr=next((r for r in t['source_rows']if r['row']==pos),None)
   out.append('ROW '+str(pos)+' '+json.dumps(rr['cells']if rr else'NOT_RESOLVED',ensure_ascii=False)+' -> '+c['metric']+' '+c['scope']+' '+c['statement']+' '+c['period_start']+'..'+c['period_end']+' unit'+c['unit']+' value_col'+str(c['value_col']))
 out+=['OTHER CORE TABLES '+json.dumps([dict(index=t['index'],member=t['member'],context=t['context'][-400:],core=t['core_rows'])for t in d['full_source_core_inventory']if t['index']not in {x['index']for x in d['tables']}],ensure_ascii=False)]
 (P/(d['receipt']+'.txt')).write_text('\n'.join(out)+'\n')
print('Document packs:',len(records),'candidate rows:',sum(d['candidate_count']for d in records))
