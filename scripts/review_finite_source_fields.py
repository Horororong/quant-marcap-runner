import base64,csv,gzip,hashlib,io,json,re,sys,zipfile
from decimal import Decimal
from pathlib import Path
import argparse
a=argparse.ArgumentParser();a.add_argument('--source-root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();P=args.output;P.mkdir(parents=True,exist_ok=False);SOURCE=args.source_root;R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));from financial_source_grid import Grid
H=R/'docs/research/source-readiness-20261019';packed=base64.b64decode((H/'official-market-proof.json.gz.b64').read_bytes());assert hashlib.sha256(packed).hexdigest()=='52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23';market={k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(packed))['files'].items()}
normalize=lambda s:re.sub(r'\s+','',s.replace('주식회사','').replace('(주)','').replace('㈜',''))
reviews=[];documents=[]
for f in sorted(SOURCE.rglob('results/*.json')):
 result=json.loads(f.read_text());receipt=result['meta']['rcept_no'];archive=next(f.parents[1].glob('native/'+receipt+'-*.zip'));raw=archive.read_bytes();assert hashlib.sha256(raw).hexdigest()==result['state']['document_sha256']
 with zipfile.ZipFile(io.BytesIO(raw))as z:
  assert z.testzip()is None;members={name:z.read(name)for name in {r['source_member']for r in result['rows']}}
 for row in result['rows']:
  assert hashlib.sha256(members[row['source_member']]).hexdigest()==row['source_member_sha256']
 grids={};texts={}
 for name,b in members.items():
  for encoding in ['utf-8','cp949','euc-kr']:
   try:t=b.decode(encoding);assert t.encode(encoding)==b;break
   except(UnicodeError,AssertionError):continue
  else:raise ValueError('ORIGINAL_ENCODING_UNPROVED')
  g=Grid();g.feed(t);grids[name]=g;texts[name]=t
 header=next(iter(texts.values()))[:2000];issuer=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)</COMPANY-NAME>',header);assert issuer[1]==result['meta']['corp_code']
 identities=[]
 for day in ['20100401','20100430']:
  candidates=[]
  for name in [f'stk_bydd_trd_{day}.json',f'ksq_bydd_trd_{day}.json']:
   for n,row in enumerate(json.loads(market[name])['OutBlock_1']):
    if row['ISU_CD']==result['meta']['stock_code']:candidates.append((name,n,row))
  assert len(candidates)==1;name,n,row=candidates[0];identity_match=normalize(issuer[2])==normalize(row['ISU_NM'])and int(row['ACC_TRDVOL'])>0
  identities.append(dict(date=day,stock_code=row['ISU_CD'],issuer_name_original=issuer[2],official_KRX_name=row['ISU_NM'],source=name,row=n,verdict='PASS_EXACT_SIGNAL_MAPPING_ONLY'if identity_match else'UNVERIFIED_NAME_CHANGE_LINK_REQUIRED'))
 for r in result['rows']:
  g=grids[r['source_member']];table=g.tables[r['table_index']];row=table['rows'][r['row_index']];literal=row[r['value_col']].strip();label=row[0];assert label==r['account_name']
  amount=Decimal(literal.replace(',','').strip('()'))*(-1 if literal.startswith('(')and literal.endswith(')')else 1);assert amount*Decimal(str(r['unit_multiplier']))==Decimal(str(r['amount_krw']))
  context=' '.join(table['context'].split());dates=re.findall(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일',context);assert ('2009','12','31')in dates;assert '(단위 : 원)'in context and r['unit']=='원'and Decimal(str(r['unit_multiplier']))==1
  assert r['scope']=='OFS'and r['period_end']=='2009-12-31'and(r['statement']=='BS'and r['period_start']==''or r['statement']in {'IS','CF'}and r['period_start']=='2009-01-01')
  # Explicit source semantics, not equivalence to every issuer's ratio input.
  meaning=dict(amortization='Annual IS amortization expense as reported; not a CF addback assertion',depreciation='Annual IS depreciation expense as reported; not EBITDA',capex_intangibles='CF intangible-acquisition amount as reported; preserve statement sign, no inferred net-cash formula',current_portion_long_term_debt='Explicit aggregate current portion of long-term debt row, not an inferred subset').get(r['metric'],'Named primary statement account and measurement period as reported')
  reviews.append(dict(receipt=receipt,corp_code=issuer[1],stock_code_hint=r['stock_code'],original_issuer=issuer[2],metric=r['metric'],scope=r['scope'],statement=r['statement'],period_start=r['period_start'],period_end=r['period_end'],measurement_basis=r['measurement_basis'],amount_krw=str(r['amount_krw']),source_member=r['source_member'],source_member_sha256=r['source_member_sha256'],document_sha256=r['document_sha256'],table=r['table_index'],row=r['row_index'],column=r['value_col'],source_label=label,literal=literal,unit='원',unit_multiplier='1',numeric_sign_unit='PASS',semantic='PASS_NAMED_SOURCE_FIELD',definition=meaning,PIT='UNVERIFIED_PUBLICATION_MEMBER_VERSION_CHAIN',engine_input='BLOCKED',whole_document_extraction='UNVERIFIED',context=context,header=table['rows'][0]))
 documents.append(dict(receipt=receipt,issuer=issuer[2],corp_code=issuer[1],candidate_count=len(result['rows']),core_fields_found=sorted({r['metric']for r in result['rows']} & {'equity','revenue','net_income','ocf'}),targeted_core_presence='4/4 in selected primary statements; not whole-filing completeness',historical_identity=identities,publication='Filing-index date2010-03-31 only; exact member availability unverified',corrections='Primary member/attachment/correction graph not yet proved; not inferred from receipt date',PIT='UNVERIFIED'))
assert len(reviews)==34
report=dict(status='PASS_SOURCE_FIELD_REVIEW_NOT_PIT',classification='RESEARCH_ONLY',new_originals=2,candidates_reviewed=34,numeric_sign_unit_PASS=34,source_semantic_PASS=34,source_semantic_FAIL=0,source_semantic_UNVERIFIED=0,new_PIT_eligible=0,new_engine_eligible=0,new_source_HTTP=0,documents=documents,rows=reviews,counts=dict(prior_proposed=880,proposed_now=914,semantic_PASS=891,reviewed_UNVERIFIED=23,unreviewed=0,operating_candidates=905,held_parser_proposals=9),limits='No whole-filing completeness, field/factor interchangeability, version-graph/PIT or population certification. Old880decisions unchanged.')
(P/'NEW34_SOURCE_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in {'rows','documents'}},ensure_ascii=False))
