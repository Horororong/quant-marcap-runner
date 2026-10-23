import base64,csv,gzip,hashlib,json,zipfile
from collections import Counter
from pathlib import Path
import argparse
a=argparse.ArgumentParser();a.add_argument('--source-dir',type=Path,required=True);a.add_argument('--before-json',type=Path,required=True);a.add_argument('--approval-json',type=Path,required=True);a.add_argument('--base-membership',type=Path,required=True);a.add_argument('--repair-membership',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();args.output.mkdir(parents=True,exist_ok=False)
P=args.output;D=args.source_dir;O=P/'decoded';O.mkdir(exist_ok=False)
def load(f):return json.loads(f.read_text())
m=load(D/'manifest.json');plan=load(D/'selection.json');before=load(args.before_json);after=load(D/'ORIGINAL_AFTER.json');budget=load(D/'SUPPLEMENTAL_AFTER.json');cfg=load(args.approval_json)
assert m['code_sha']=='3b505b5fb299e4d162a9676d9f4e757d4415fc69'
assert before['runs']==after['runs'] and before['first_review']==after['first_review']
assert before['last_checkpoint']=='20100331002063'and after['last_checkpoint']=='20100331002116'
assert cfg['receipts'][:21]==[x['rcept_no']for x in plan['samples']]==budget['completed_receipts']
assert after['completed_receipts']==before['completed_receipts']+cfg['receipts'][:21]
assert len(after['completed_receipts'])==len(set(after['completed_receipts']))==180
assert budget['phase']=='PAUSED'and len(budget['attempts'])==1
attempt=budget['attempts'][0];assert attempt['HTTP_requests_observed']==m['HTTP_requests_observed']==21
assert attempt['retries_observed']==0 and attempt['http_reserved']==m['http_reserved']==42
assert attempt['source_elapsed_seconds']==251.381 and attempt['stop_reason']=='BATCH_COMPLETE'
assert budget['remaining_receipts']==cfg['receipts'][21:]and len(budget['remaining_receipts'])==20
assert len(m['transfers'])==2
for i,pin in enumerate(m['transfers']):
 source=D/f'sources{i:02d}.json.gz.b64'
 if i==0 and (D/'sources00.gitblob.json.gz.b64').is_file():source=D/'sources00.gitblob.json.gz.b64'
 packed=base64.b64decode(source.read_bytes());assert len(packed)==pin['bytes']and hashlib.sha256(packed).hexdigest()==pin['compressed_sha256']
 for name,b64 in json.loads(gzip.decompress(packed))['files'].items():
  rel=Path(name);assert not rel.is_absolute()and'..'not in rel.parts
  out=O/f'part{i:02d}'/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(base64.b64decode(b64))
baseids={r['candidate_id']for r in csv.DictReader(args.base_membership.open())}
repairids={r['candidate_id']for r in csv.DictReader(args.repair_membership.open())}
records=[];docs=[]
for f in sorted(O.rglob('results/*.json')):
 d=load(f);receipt=d['meta']['rcept_no'];native=list((f.parent.parent/'native').glob(receipt+'-*.zip'));assert len(native)==1
 archive=native[0];blob=archive.read_bytes();archive_sha=hashlib.sha256(blob).hexdigest();assert archive_sha==d['state']['document_sha256']
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for r in d['rows']:
   assert hashlib.sha256(z.read(r['source_member'])).hexdigest()==r['source_member_sha256']
   assert r['document_sha256']==archive_sha and r['rcept_no']==receipt and r['corp_code']==d['meta']['corp_code']
   assert r['backtest_eligible']is False and r['availability_status']=='UNVERIFIED'
   assert r['parser_version']=='legacy-v9.2-statement-boundary-guard'
   binding=dict(receipt=receipt,**{k:r.get(k)for k in ['scope','statement','metric','period_start','period_end','measurement_basis','source_member','source_member_sha256','table_index','row_index','value_col']})
   id='source-candidate-v1:'+hashlib.sha256(json.dumps(binding,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   assert id not in baseids|repairids
   records.append(dict(candidate_id=id,**binding,amount_krw=r['amount_krw'],semantic_status='UNREVIEWED',PIT='UNVERIFIED',engine_eligible=False))
 core={scope:sorted({r['metric']for r in d['rows']if r['scope']==scope and r['metric']in {'equity','revenue','net_income','ocf'}})for scope in ['OFS','CFS']}
 docs.append(dict(receipt=receipt,stock_hint=d['meta']['stock_code'],corp_code=d['meta']['corp_code'],company=d['meta']['corp_name'],source_archive_sha256=archive_sha,source_CRC='PASS',candidate_count=len(d['rows']),extraction_status=d['state']['status'],core_field_hints=core,semantic='UNREVIEWED',PIT='UNVERIFIED',whole_filing_completeness='UNVERIFIED'))
assert len(docs)==21 and len(records)==273 and len({r['candidate_id']for r in records})==273
with(P/'NEW273_CANDIDATE_IDS.csv').open('w')as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
report=dict(status='PASS_NEW_SOURCE_HASH_CRC_ROW_BINDING_FROZEN_ORDER_NO_DUPLICATE_NORMAL_EXIT',classification='RESEARCH_ONLY',run_id='40024818567',run_url='https://github.com/Horororong/quant-marcap-runner/actions/runs/40024818567',code_sha=m['code_sha'],source_result_commit=load(D/'HEAD.json')['head'],source_HTTP=21,retries=0,new_originals=21,new_candidates=273,duplicate_receipts=0,duplicate_candidates=0,elapsed_seconds=251.381,normal_exit=True,stop_reason='BATCH_COMPLETE',checkpoint_before=before['last_checkpoint'],checkpoint_after=after['last_checkpoint'],next_receipt=budget['remaining_receipts'][0],budget=dict(executions_used=1,executions_remaining=1,documents_remaining=20,HTTP_actual=21,HTTP_reserved=42,HTTP_additional_reservable=40,total_approved_HTTP=82),source_states=dict(Counter(d['extraction_status']for d in docs)),new_source_semantic_PASS=0,new_PIT=0,new_engine_eligible=0,original3history_preserved=True,sourcepack_remote_persistent=True,automatic_supplemental_resume=False,financial_publication='HOLD',research_population=dict(total=2565,PASS=986,reviewed_UNVERIFIED=23,unreviewed=1556),documents=docs,HTTP_evidence='Deployed pinned collector instrumented progress counts persisted in both remote manifest and supplemental ledger; worker artifact independently checked only if download succeeds')
(P/'FINITE21_VERIFIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='documents'},ensure_ascii=False,indent=2))
