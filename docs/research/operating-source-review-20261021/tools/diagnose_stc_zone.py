"""Targeted source-control diagnosis, NOT an independent amount/semantic oracle."""
import json,re,sys,zipfile
from pathlib import Path
P=Path(__file__).parent;S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded');sys.path.insert(0,'/workspace/quant-project-full-20261020/code')
from scripts.legacy_native_financials import NativeTables,source_contract,cell_text
rec='20100331001972';p=next(S.rglob('results/'+rec+'.json'));archive=next((p.parent.parent/'native').glob(rec+'-*.zip'))
with zipfile.ZipFile(archive)as z:b=z.read(rec+'.xml')
for enc in ['utf-8','cp949','euc-kr']:
 try:text=b.decode(enc);break
 except UnicodeDecodeError:continue
r=NativeTables(text);r.feed(text);zone=False;trace=[]
for t in r.tables:
 prefix=re.sub(r'\s+','',t['prefix']);events=list(re.finditer(r'4[.]재무제표|가[.]재무제표|다[.]연결재무제표|(?:XI|Ⅺ|ⅩⅠ)[.](?:부속명세서|재무제표등)|부문별재무현황|사업부문별재무|합병전[ㆍ·]?후|외화자산과부채|주석',prefix))
 for e in events:zone=e.group()in{'4.재무제표','가.재무제표','다.연결재무제표'}or bool(re.fullmatch(r'(?:XI|Ⅺ|ⅩⅠ)[.](?:부속명세서|재무제표등)',e.group()))
 if 58<=t['index']<=64:trace.append(dict(table=t['index'],zone=zone,prefix=prefix[-500:],matched_zone_tokens=[e.group()for e in events],prefix_contract=source_contract(t['prefix']),fresh_header_contract=source_contract(t['prefix']+' '+' '.join(cell_text(c)for row in t['rows']for c in row))if t['index']in{59,63}else None))
assert any(t['table']==59 and not t['zone']and t['fresh_header_contract']['statement']=='IS'for t in trace)
assert any(t['table']==63 and not t['zone']and t['fresh_header_contract']['statement']=='CF'for t in trace)
result=dict(receipt=rec,diagnosis='A primary CFS statement header is parsed, but preceding 연결재무제표에대한주석참조 closes the zone; subsequent primary CFS IS/CF heading does not reopen it. Original output has no such candidates. Financial absence is NOT established.',trace=trace,classification='PARSER_CONTROL_FLOW_GAP_DIAGNOSTIC_ONLY',production_code_changed=False,approved_source_owner_hashes_changed=False,financial_values_published=0,next_fix='Separate an ordinary see-notes sentence from entry into a note/business segment; retain statement date/current-column/unit/scope gates and regression-test original source before any reviewed parser migration.')
(P/'stc-source-zone-diagnosis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
