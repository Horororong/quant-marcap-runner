"""Independent raw-source controls; never imports production extraction code."""
import hashlib,html,json,re,zipfile
from decimal import Decimal
from pathlib import Path
P=Path(__file__).parent/'evidence'
S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded')
# Transcribed from original primary financial tables, prior to reading replay amounts.
controls=[('20100331001972',60,1,2,'IS','revenue','3507674422','원',22),
 ('20100331001972',60,5,2,'IS','cost_of_sales','2192294089','원',22),
 ('20100331001972',60,9,2,'IS','gross_profit','1315380333','원',22),
 ('20100331001972',60,18,1,'IS','depreciation','280329158','원',22),
 ('20100331001972',60,19,1,'IS','amortization','127621339','원',22),
 ('20100331001972',60,37,2,'IS','operating_income','-5134536307','원',22),
 ('20100331001972',60,61,2,'IS','net_income','-9844112035','원',22),
 ('20100331001972',64,1,2,'CF','ocf','-4481694015','원',22),
 ('20100331001982',135,73,2,'BS','total_assets','4877276061000','천원',3)]
def plain(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s))).strip()
records=[]
for rec,table,row,col,statement,metric,expected,unit,term in controls:
 archive=next(S.rglob('native/'+rec+'-*.zip'));member=rec+'.xml'
 with zipfile.ZipFile(archive)as z:raw=z.read(member)
 for encoding in ['utf-8','cp949','euc-kr']:
  try:text=raw.decode(encoding);assert text.encode(encoding)==raw;break
  except UnicodeDecodeError:continue
 start=list(re.finditer(r'<TABLE(?=[\s>])',text,re.I))[table].start();end=text.find('</TABLE>',start)
 rows=[];attrs=[]
 for tr in re.finditer(r'<TR(?=[\s>])[^>]*>(.*?)</TR\s*>',text[start:end+8],re.I|re.S):
  cells=list(re.finditer(r'<(?:TD|TH|TE|TU)(?=[\s>])([^>]*)>(.*?)</(?:TD|TH|TE|TU)\s*>',tr.group(1),re.I|re.S))
  if cells:rows.append([plain(c.group(2))for c in cells]);attrs.append([c.group(1)for c in cells])
 header=plain(text[max(0,start-2000):start]);label=rows[row][0];token=rows[row][col]
 assert {'IS':'연결손익계산서','CF':'연결현금흐름표','BS':'연결재무상태표'}[statement]in re.sub(r'\s+','',header)
 assert re.search(r'제\s*'+str(term)+r'\s*(?:\(당\))?\s*기',rows[0][1]),rows[0]
 assert 'COLSPAN="2"'in attrs[0][1]and col in {1,2}
 assert re.search(r'2009\s*년\s*12\s*월\s*31\s*일',header)
 if statement!='BS':assert re.search(r'2009\s*년\s*0?1\s*월\s*0?1\s*일',header)
 assert re.search(r'단위\s*[:：]\s*'+unit+r'\s*\)',header)
 cleaned=token
 if metric=='total_assets':
  # The literal source cell has one comma-grouped integer, native break,
  # and a decorative rule; no second number is present in the cell.
  match=re.fullmatch(r'(\d{1,3}(?:,\d{3})+)&cr;={2,}',token);assert match,token
  cleaned=match.group(1)
 negative=cleaned.startswith('(')or('손실'in label and'이익'not in label)
 amount=Decimal(cleaned.strip('()').replace(',',''))
 if negative:amount=-abs(amount)
 amount_krw=amount*({'원':Decimal(1),'천원':Decimal(1000)}[unit]);assert amount_krw==Decimal(expected)
 records.append(dict(receipt=rec,scope='CFS',statement=statement,metric=metric,source_archive=str(archive.relative_to(S)),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),source_member=member,source_member_sha256=hashlib.sha256(raw).hexdigest(),table=table,row=row,current_physical_column=col,current_header=rows[0],current_column_header_attrs=attrs[0],period_start=''if statement=='BS'else'2009-01-01',period_end='2009-12-31',header=header,source_row_label=label,source_raw_amount=token,source_comparative_cells=rows[row][3:],reference_term=term,reference_unit=unit,independent_amount_krw=str(amount_krw),source_row_semantics='PASS',scope_limit='Reported original current accounting line only; ISdepreciation/amortization are SG&A components, not inferred company totals',PIT='UNVERIFIED',whole_filing_completeness='UNVERIFIED',publication='HOLD'))
replay=json.loads((P/'original-57-replay.json').read_text());new=replay['additions'];assert len(new)==9
for reference in records:
 item=next(r for r in new if(r['receipt'],r['scope'],r['metric'])==(reference['receipt'],'CFS',reference['metric']))
 assert item['source_member_sha256']==reference['source_member_sha256']
 assert item['amount_krw']==reference['independent_amount_krw']
 assert(item['table_index'],item['row_index'],item['value_col'])==(reference['table'],reference['row'],reference['current_physical_column'])
 assert item['backtest_eligible']is False and item['availability_status']=='UNVERIFIED'
assert Decimal(records[0]['independent_amount_krw'])-Decimal(records[1]['independent_amount_krw'])==Decimal(records[2]['independent_amount_krw'])
old=json.loads(Path('/workspace/quant-source-review-batch2-20261021/all-871-candidate-decisions.json').read_text())
cj={r['metric']:Decimal(r['candidate_amount_krw'])for r in old if r['receipt']=='20100331001982'and r['scope']=='CFS'and r['metric']in {'equity','total_liabilities'}}
assert cj['equity']+cj['total_liabilities']==Decimal('4877276061000')
result=dict(status='PASS_9_NEW_HELD_SOURCE_ROW_CONTROLS',records=records,checks=dict(STC_revenue_minus_cost_equals_gross=True,CJ_assets_equals_previously_audited_liabilities_plus_equity=True,independent_original_source_amounts=9),existing_operating_candidates_871_unchanged=True,original_semantic_PASS=848,original_reviewed_UNVERIFIED=23,proposed_research_additions_source_semantics_PASS=9,all_proposed_880_source_row_semantics=dict(PASS=857,UNVERIFIED=23),operating_candidate_count_remains=871,PIT='UNVERIFIED',financial_publication=0,scope_limit='Offline proposed parser output only; no migration or operational dataset replacement; source-row PASS is not investment or whole-filing certification')
(P/'new-9-independent-source-controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('PASS9independent source rows, STCIS identity, CJBS identity; operating dataset unchanged')
