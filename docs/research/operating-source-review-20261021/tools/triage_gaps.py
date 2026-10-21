"""Source-gap triage only; malformed/member evidence never certifies absence."""
import collections,hashlib,html,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as etree
P=Path(__file__).parent;S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded');rows=[]
for p in sorted(S.rglob('results/*.json')):
 d=json.loads(p.read_text())
 if d['state']['status']!='SOURCE_GAP':continue
 rec=d['meta']['rcept_no'];diagnostics=json.loads(d['state']['error']);archive=next((p.parent.parent/'native').glob(rec+'-*.zip'));members=[]
 with zipfile.ZipFile(archive)as z:
  for name in z.namelist():
   b=z.read(name);encoding=None;text=None
   for enc in ['utf-8','cp949','euc-kr']:
    try:text=b.decode(enc);encoding=enc;break
    except UnicodeDecodeError:continue
   wellformed=False;error=None
   try:etree.fromstring(b);wellformed=True
   except (etree.ParseError, LookupError, ValueError) as e:error=str(e).splitlines()[0][:250]
   markers={k:len(re.findall(pattern,text or''))for k,pattern in {'equity':'자본총계|자본합계','revenue':'매출액|영업수익','net_income':'당기순이익|당기순손실','ocf':'영업활동.{0,20}현금흐름'}.items()};contexts=[]
   if text:
    for m in list(re.finditer(r'재무상태표|대차대조표|손익계산서|현금흐름표',text))[:3]:contexts.append(re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]*>',' ',text[max(0,m.start()-70):m.end()+180]))))
   members.append(dict(name=name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),independent_decode=encoding,stdlib_XML_no_external_resolution='WELL_FORMED'if wellformed else'UNVERIFIED_OR_INVALID_XML',XML_error=error,raw_financial_label_mentions=markers,heading_context_samples=contexts))
 rows.append(dict(receipt=rec,company=d['meta']['corp_name'],report_name=d['meta']['report_nm'],original_extraction_state='SOURCE_GAP',original_candidate_count=0,original_diagnostic_summary=[{k:m.get(k) for k in ['member','issues','warnings','resolved_encoding','xml_error']}for m in diagnostics],original_structural_issues=d['state'].get('structural_issues'),source_archive=str(archive.relative_to(S)),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),members=members,triage='COMPLETED_EVIDENCE_INVENTORY_NOT_FINANCIAL_REVIEW',source_absence='UNVERIFIED',extraction_completeness='UNVERIFIED_SOURCE_GAP',PIT='UNVERIFIED',action='Retain gate and original bytes. Strict XML errors may reflect custom DART entities/encoding, not absent financial data. Review exact service/member diagnostics and independent original viewer evidence before any parser migration or recollection.'))
(P/'source-gap-9-triage.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['receipt'],r['company'],'members',[(m['name'],m['stdlib_XML_no_external_resolution'],m['raw_financial_label_mentions'])for m in r['members']])
