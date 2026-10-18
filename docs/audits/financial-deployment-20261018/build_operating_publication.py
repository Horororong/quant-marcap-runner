"""Independent source review and finite publication overlay; no network or parser."""
import csv,hashlib,json,sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
ROOT=Path('/workspace/financial-operating-canary');OUT=Path('/workspace/financial-operating-publication');OUT.mkdir(exist_ok=False)
controls=json.loads((ROOT/'operating_controls.json').read_text());grids={(x['receipt'],x['member']):x for x in json.loads((ROOT/'independent_grids.json').read_text())};results={p.stem:json.loads(p.read_text())for p in(ROOT/'results').glob('*.json')};audits=[];published={};counts=Counter();rejections=[]
def number(t):
 s=t.strip().replace(',','')
 if s.startswith('(')and s.endswith(')'):return -Decimal(s[1:-1])
 if s.startswith('(-)'):return -Decimal(s[3:])
 return Decimal(s)
def save(path,obj):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
for c in controls['controls']:
 g=grids[c['receipt'],c['member']];literal=g['tables'][c['table']]['rows'][c['row']][c['column']];assert literal==c['literal'];assert g['member_sha256']==c['member_sha256'];wanted=number(literal)*c['multiplier'];rows=[r for r in results[c['receipt']]['rows']if(r['metric'],r['scope'])==(c['metric'],c['scope'])];assert len(rows)<=1
 verdict='UNVERIFIED'if not rows else'PASS'if Decimal(rows[0]['amount_krw'])==wanted else'FAIL';period='UNVERIFIED';source='UNVERIFIED';unit='UNVERIFIED'
 if rows:
  r=rows[0];period='PASS'if(r['period_start'],r['period_end'],r['measurement_basis'],r['period'],r['fiscal_year'])==(c['period_start'],c['period_end'],c['basis'],c['report_period'],2009)else'FAIL';source='PASS'if(r['source_member'],r['table_index'],r['row_index'],r['value_col'],r['source_member_sha256'])==(c['member'],c['table'],c['row'],c['column'],c['member_sha256'])else'FAIL';unit='PASS'if r['unit']==c['unit']and Decimal(str(r['unit_multiplier']))==c['multiplier']else'FAIL'
 assert 'FAIL'not in [verdict,period,source,unit],(c['receipt'],c['metric'],verdict,period,source,unit)
 allow=c['publication_policy']=='CORE4_ONLY_AFTER_EXACT_SOURCE_CHECK'and all(x=='PASS'for x in [verdict,period,source,unit])
 if allow:
  row=dict(rows[0]);assert row['backtest_eligible']is False and row['availability_status']=='UNVERIFIED';row.update(financial_source_literal_verdict='PASS',financial_period_unit_scope_verdict='PASS',historical_identity_verdict='UNVERIFIED',correction_chain_verdict='UNVERIFIED',official_publication_verdict='UNVERIFIED',quality_version='financial-quality-v1-source-linked-not-PIT',source_archive_artifact=12153773795,source_run_id=39174955546,source_control_sha256=hashlib.sha256((ROOT/'operating_controls.json').read_bytes()).hexdigest(),corp_name_semantics='index label, not historical-identity certification',original_issuer_name='고려반도체시스템'if c['receipt']=='20100331001578'else'사조산업',source_viewer_url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+c['receipt']);published.setdefault(c['receipt'],[]).append(row)
 audits.append(dict(receipt=c['receipt'],metric=c['metric'],scope=c['scope'],literal=literal,unit=c['unit'],normalized_expected=str(wanted),extracted=rows[0]['amount_krw']if rows else'',amount_verdict=verdict,period_verdict=period,source_verdict=source,unit_verdict=unit,publication_verdict='PASS_SOURCE_ONLY'if allow else'UNVERIFIED_HELD',period_start=c['period_start'],period_end=c['period_end'],source_location=f"{c['member']}#table={c['table']},row={c['row']},col={c['column']}",member_sha256=c['member_sha256'],archive_sha256=c['archive_sha256'],availability='UNVERIFIED',correction_chain='UNVERIFIED',historical_identity='UNVERIFIED',backtest_eligible=False,hold_reason=''if allow else c['publication_policy']))
assert sum(len(x)for x in published.values())==8 and len(published)==2
base=Path('data/financials/legacy_2000_2014/quality_v9')
for receipt,result in sorted(results.items()):
 state=result['state'];counts[state['status']]+=1
 source=json.loads((ROOT/'collection'/f'{receipt}.json').read_text());source.update(source_artifact_id=12153773795,artifact_url='https://github.com/Horororong/quant-marcap-runner/actions/runs/39174955546/artifacts/12153773795',source_run_commit='63ad9b8fe26ff619dafd11935619ca7f61be530b');save(base/'collection'/f'{receipt}.json',source)
 quality=json.loads((ROOT/'quality'/f'{receipt}.json').read_text());quality.update(structural_candidate_count=len(result['rows']),published_field_count=len(published.get(receipt,[])),source_audited_field_count=sum(a['amount_verdict']=='PASS'for a in audits if a['receipt']==receipt),financial_accuracy='SOURCE_LITERAL_VERIFIED_SUBSET_PIT_UNVERIFIED'if receipt in published else'UNVERIFIED_SOURCE_CONFLICT'if receipt=='20100331001580'else'UNVERIFIED_SOURCE_GAP',publication_status='SOURCE_VERIFIED_SUBSET_ONLY'if receipt in published else'HELD',unpublished_candidate_count=len(result['rows'])-len(published.get(receipt,[])),source_artifact_id=12153773795)
 if receipt=='20100331001580':quality['source_conflict']=controls['source_conflicts'][0]
 save(base/'quality'/f'{receipt}.json',quality)
 if receipt in published:save(base/'metrics'/f'{receipt}.json',dict(parser_version=result['parser_version'],quality_version=quality['quality_version'],investment_PIT='0/6',financial_population_certification='UNVERIFIED',rows=published[receipt]))
 if state['status']=='SOURCE_GAP':
  diagnostics=json.loads(state['error']);rejections.append(dict(receipt=receipt,status='SOURCE_GAP',financial_data_present=state.get('financial_data_present'),diagnostics=diagnostics,meaning='At least one native XML member failed strict source-integrity checks; financial absence not certified'))
run=json.loads((ROOT/'run_status.json').read_text());summary=dict(merge_sha=run['commit'],operating_run=39174955546,status=run['status'],elapsed_seconds=run['elapsed_seconds'],selected_documents=10,completed_documents=run['completed'],classification_counts=dict(counts),structural_candidates=sum(len(r['rows'])for r in results.values()),audited_controls=16,source_amount_counts=dict(Counter(a['amount_verdict']for a in audits)),publication_counts=dict(Counter(a['publication_verdict']for a in audits)),published_documents=2,published_fields=8,unpublished_structural_candidates=43,unextracted_CFS_controls=4,source_conflict_documents=1,last_checkpoint=run['last_checkpoint'],historical_v5_rewritten=False,old22_reprocessed_in_main=False,historical3998_reset=False,automatic_collection='HOLD',automatic_publication='HOLD',investment_PIT='0/6',financial_population_certification='UNVERIFIED',source_artifact_id=12153773795,source_transfer_blob='aad8c5f8f42afa33fafe14c3bba9dbe0c43b451d',source_transfer_sha256='b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68')
save(Path('data/status/dart_legacy_rollout_status.json'),dict(summary,canary_consumed=True,code_status='DEPLOYED_BOUNDED',quality_version='financial-quality-v1-source-linked-not-PIT',parser_version='legacy-v9.1-primary-source-metadata',updated_at_utc=run['updated_at_utc'],source_states_durable=10,legacy_v5_snapshot=dict(processed=72028,four_fields=14046,partial=9624,NO_METRICS=10203,NO_DOCUMENT=2048,SOURCE_GAP=36107,pending=38971,quarantine=4021,updated_at_utc='2026-10-18T19:37:25.711357+00:00',financial_quality='INDEPENDENT_SOURCE_AUDIT_REQUIRED'),new_untouched_queue_remaining=38961,queue_count_basis='Prior38971 minus10 disjoint never-classified receipts; v5 counts not re-labelled as v9.'))
h=Path('docs/audits/financial-deployment-20261018');save(h/'operating_summary.json',summary);save(h/'operating_source_gaps.json',rejections);save(h/'operating_source_conflicts.json',controls['source_conflicts']);save(h/'operating_controls.json',controls)
p=OUT/h/'operating_details.csv';p.parent.mkdir(parents=True,exist_ok=True)
with p.open('w',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(audits[0]));w.writeheader();w.writerows(audits)
print(json.dumps(summary,ensure_ascii=False))
