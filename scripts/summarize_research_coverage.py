"""Coverage accounting from preserved manifests/review ledgers, not a hash audit."""
import argparse,csv,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dart_value_factor_adapter import load_historical_code_map,load_backfill_state,period_completeness
ROOT=Path(__file__).resolve().parents[1]
def main(observation_root,output):
 output.mkdir(parents=True,exist_ok=False)
 restored=json.loads((ROOT/'docs/restoration/full-project-20261020/evidence/data-manifest-restored.json').read_text())
 groups=defaultdict(list)
 for f in restored['files']:groups['/'.join(Path(f['path']).parts[:2])].append(f)
 file_groups=[dict(kind=k,files=len(v),bytes=sum(x['bytes']for x in v),presence='Accepted prior751-file audit; no repeated hashes',accuracy='NOT_INFERRED_FROM_FILE_MATCH')for k,v in sorted(groups.items())]
 cohorts={};metadata={};docs={}
 for rid in ['39248507369','39504052321']:
  folder=observation_root/('operating-'+rid);m=json.loads((folder/'manifest.json').read_text());plan=json.loads((folder/'selection.json').read_text())
  completed=m['summary']['completed_receipts'];receipts=[x['rcept_no']if isinstance(x,dict)else x for x in completed]
  samples={x['rcept_no']:x for x in plan['samples']};metadata.update(samples)
  cohorts[rid]=dict(receipts=receipts,documents=len(receipts),candidate_fields=m['summary']['candidate_fields'],counts=m['summary']['counts'],executed_code_commit=m['code_sha'])
 first=set(cohorts['39248507369']['receipts']);second=set(cohorts['39504052321']['receipts']);assert len(first)==100 and len(second)==57 and not first&second
 source_docs=json.loads((ROOT/'docs/research/source-review-batch2-20261021/all-57-document-status.json').read_text())
 gap={d['receipt']for d in source_docs if d['original_extraction_state']=='SOURCE_GAP'};candidate_docs=second-gap
 assert len(gap)==9 and len(candidate_docs)==48
 old=json.loads((ROOT/'docs/research/source-review-batch2-20261021/all-871-candidate-decisions.json').read_text())
 extra=json.loads((ROOT/'docs/research/native-source-boundary-repair-20261021/new-9-independent-source-controls.json').read_text())['records']
 assert len(old)==871 and len(extra)==9
 rows=[];keys=set()
 for row in old+extra:
  key=tuple(row.get(k)for k in ['receipt','scope','statement','metric','period_start','period_end','measurement_basis'])
  # New independent controls omit measurement_basis; source identity still
  # cannot duplicate any old receipt/scope/statement/metric/current period.
  uniq=tuple(row.get(k)for k in ['receipt','scope','statement','metric','period_start','period_end'])
  assert uniq not in keys;keys.add(uniq)
  meta=metadata[row['receipt']];verdict=row.get('semantic_verdict',row.get('source_row_semantics'))
  if verdict not in {'PASS','UNVERIFIED','FAIL'}:raise ValueError('Unknown semantic verdict '+str(verdict))
  rows.append(dict(receipt=row['receipt'],stock_code=meta['stock_code'],corp_code=meta['corp_code'],company=meta['corp_name'],
   period_start=row.get('period_start',''),period_end=row['period_end'],scope=row['scope'],statement=row['statement'],field=row['metric'],
   acquired='YES',extracted='OPERATING'if row in old else'OFFLINE_PROPOSAL',semantic=verdict,PIT='UNVERIFIED',engine_input='HOLD',
   amount_krw=row.get('candidate_amount_krw',row.get('independent_amount_krw')),correction_chain='UNVERIFIED',
   security_mapping='UNVERIFIED; frozen index code/name hints, not historical legal identity proof'))
 counts=Counter(x['semantic']for x in rows);assert counts==Counter(PASS=857,UNVERIFIED=23)
 with(output/'candidate_coverage_by_security_field.csv').open('w',newline='')as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 field_counts=[]
 for key in sorted({(x['period_end'],x['scope'],x['field'])for x in rows}):
  values=[x for x in rows if(x['period_end'],x['scope'],x['field'])==key]
  field_counts.append(dict(period_end=key[0],scope=key[1],field=key[2],stocks=len({x['stock_code']for x in values}),
   candidates=len(values),semantic_PASS=sum(x['semantic']=='PASS'for x in values),semantic_UNVERIFIED=sum(x['semantic']=='UNVERIFIED'for x in values),PIT_eligible=0,engine_admitted=0))
 years=json.loads((ROOT/'docs/restoration/full-project-20261020/evidence/all-year-parquet-schemas.json').read_text())
 loaded={x['year']:x for x in json.loads((ROOT/'docs/restoration/full-project-20261020/evidence/representative-engine-loading.json').read_text())}
 krx=[dict(year=int(Path(x['path']).stem.split('-')[-1]),first=x['first'],last=x['last'],rows=x['rows'],fields=x['columns'],
  observed_stock_count_prior_evidence=loaded.get(int(Path(x['path']).stem.split('-')[-1]),{}).get('codes','NOT_COUNTED_IN_PRIOR_SCHEMA_EVIDENCE'),
  schema='PASS_PRIOR_EVIDENCE',accuracy='Held source/reference/event checks required per exposure; no whole-market certification')for x in years]
 mapping=load_historical_code_map(ROOT);state=load_backfill_state(ROOT);modern=[]
 periods=sorted({(int(m[1]),m[2])for f in restored['files']if(m:=re.search(r'dart_full_(\d{4})_(Q1|H1|Q3|FY)_',f['path']))})
 for year,period in periods:
  c=period_completeness(ROOT,mapping,state,year,period)
  c.update(acquired='Raw shards present',extracted_fields=['equity','revenue','net_income','ocf'],
   semantic='No whole-population certification; prior independent controls remain separate',PIT='Date-based provider contract; exact clocks/version/identity not population-certified',
   engine_input='SOURCE_COVERAGE_PASS_ONLY'if c['ratio']==1 and c['raw_ok']else'BLOCKED_INCOMPLETE_SOURCE_COVERAGE',security_detail_source='data/status/dart_full_backfill_state.csv(stock_code,year,period,fs_div,status)')
  modern.append(c)
 actions=ROOT/'config/kr_corporate_actions.csv'
 with actions.open(newline='')as f:events=list(csv.DictReader(f))
 report=dict(scope='Reused restored manifest/schema evidence and current metadata/review ledgers; no full data rehash/recollection',
  restored_snapshot=dict(files=restored['count'],bytes=restored['bytes'],file_groups=file_groups),
  observations=cohorts,relations=dict(finite_documents=157,first100_second57_overlap=0,reviewed57_subset_of157=True,source_gap9_subset_of57=True,
    total_finite_source_gap_documents=cohorts['39248507369']['counts']['SOURCE_GAP']+len(gap),
    total_finite_candidate_documents=cohorts['39248507369']['counts']['PARSED_4F']+cohorts['39248507369']['counts']['PARSED_PARTIAL']+len(candidate_docs),
    candidate_docs48_subset_of57=True,all_57_published_originals_preserved=True,source_gap9_not_candidates23=True,older_sajo_case_outside157=True),
  candidate_set=dict(operating=871,operating_semantic_PASS=848,operating_semantic_UNVERIFIED=23,proposed_new=9,unique_proposed=880,
   semantic_PASS=counts['PASS'],semantic_FAIL=0,reviewed_UNVERIFIED=23,unreviewed=0,proposed_PIT_eligible=0,
   all_finite_observation_candidates=cohorts['39248507369']['candidate_fields']+cohorts['39504052321']['candidate_fields']),
  legacy_field_coverage=field_counts,krx_by_year=krx,modern_by_year_period=modern,
  corporate_actions=dict(registered_rows=len(events),fields=list(events[0])if events else[],source=str(actions.relative_to(ROOT)),
   accuracy='Registered event terms checked only in their original scoped evidence; unresolved events in config/kr_corporate_action_gaps.json still block exposure'),
  new_PIT_case=dict(stock_code='007160',field='OFS equity',new_signal='2010-04-01',scope='Single bounded source-field/signal inspection; not new operating provider or whole-population ranking'),
  blockers=[dict(strategy='2010 financial ranking',required='2009Q3 and FY complete expected1495 issuers plus source/PIT correctness',current='0/1495 existing provider coverage for both periods; source-only880 held'),
   dict(strategy='2019-2025 multi-security example',required='207940 rights2022-02-28 and other original incident evidence',current='Existing exact planned gap remains; no ticker exclusion'),
   dict(strategy='financial period expansion',required='Correct period/standalone-quarter dependencies, correction graphs and historical mappings for entire selected universe',current='One reviewed field cannot substitute for all candidate issuers')],
  investment_PIT='0/6',financial_publication='HOLD',classification='RESEARCH_ONLY')
 report['official_extensions']=json.loads((ROOT/'config/research/official_source_extensions_v1.json').read_text())
 (output/'DATA_COVERAGE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 (output/'OBSERVATION_COHORTS.json').write_text(json.dumps(dict(cohorts=cohorts,source_gap9=sorted(gap),candidate_docs48=sorted(candidate_docs)),ensure_ascii=False,indent=2)+'\n')
 for name,values in [('legacy_field_scope_summary.csv',field_counts),('modern_year_period_coverage.csv',modern),('krx_year_coverage.csv',krx)]:
  with(output/name).open('w',newline='')as f:
   writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
 print(json.dumps(dict(snapshot_files=restored['count'],snapshot_bytes=restored['bytes'],observed_documents=157,source_gap9=len(gap),candidate_rows=len(rows),
  field_scope_groups=len(field_counts),krx_year_files=len(krx),modern_year_period_groups=len(modern),cohort_counts={k:v['documents']for k,v in cohorts.items()}),indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--observation-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.observation_root,a.output)
