"""Q3/FY2009 scope and explicit source-ready bridge; no collection/status writes."""
import argparse,copy,csv,hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from dart_value_factor_adapter import load_historical_code_map,load_backfill_state,expected_codes_for_period,signal_completeness_report,DartValueFactorAdapter
from legacy_reviewed_provider_bridge import bridge
CORE={'equity','revenue','net_income','ocf'}
def main(output,new_source_review,trial_source):
 output.mkdir(parents=True,exist_ok=False)
 original=pd.read_csv(ROOT/'data/financials/legacy_2000_2014/normalized/legacy_metrics_2009.csv.gz',dtype=str).fillna('');x=original[(original.fiscal_year=='2009')&original.period.isin(['Q3','FY'])].copy()
 mapping=load_historical_code_map(ROOT);state=load_backfill_state(ROOT);expected=expected_codes_for_period(mapping,2009)
 reports=[]
 for period,sub in x.groupby('period'):
  identity=['corp_code','stock_code','fiscal_year','period','metric','scope','statement'];source=identity+['parser_version','rcept_no'];groups=sub.groupby(identity,dropna=False).agg(rows=('amount_krw','size'),distinct_values=('amount_krw','nunique'),receipts=('rcept_no','nunique')).reset_index()
  ready=[g for _,g in sub[sub.metric.isin(CORE)].groupby(['corp_code','stock_code','rcept_no','scope'])if set(g.metric)>=CORE]
  reports.append(dict(period=period,rows=len(sub),unique_companies=sub.corp_code.nunique(),unique_stock_hints=sub.stock_code.nunique(),unique_company_stock_pairs=len(sub[['corp_code','stock_code']].drop_duplicates()),unique_receipts=sub.rcept_no.nunique(),unique_fields=sub.metric.nunique(),unique_field_scope_statement_identities=len(groups),unique_source_version_identities=len(sub[source].drop_duplicates()),exact_duplicate_rows=int(sub.duplicated().sum()),repeated_source_version_rows=int(sub.duplicated(source).sum()),multirow_field_identity_groups=int(groups.rows.gt(1).sum()),conflicting_value_identity_groups=int(groups.distinct_values.gt(1).sum()),parser_versions=sub.parser_version.value_counts().to_dict(),scope_counts=sub.scope.value_counts().to_dict(),period_end_hints=sub.period_end.value_counts().to_dict(),source_quality_labels=sub.source_quality.value_counts().to_dict(),raw_four_core_receipt_scope_groups=len(ready),raw_four_core_stock_hints=len(set(pd.concat(ready).stock_code))if ready else 0,canonical_engine_eligible_stocks=0))
  groups[groups.rows.gt(1)].to_csv(output/f'{period}_DUPLICATE_FIELD_GROUPS.csv',index=False,lineterminator='\n')
 # Inventory every expected stock; raw hint coverage is never an admission list.
 matrix=[]
 for stock in sorted(expected):
  own=x[x.stock_code==stock];row=dict(stock_code_hint=stock,expected_year=2009,required_signal='2010-04-30 close, next-close execution',canonical_source_complete=False,engine_eligible=False,missing='canonical source completion; independent semantics; source-member/version/publication and historical identity')
  for period in ['Q3','FY']:
   s=own[own.period==period];row[period+'_raw_rows']=len(s);row[period+'_raw_receipts']=s.rcept_no.nunique();row[period+'_core_fields']='|'.join(sorted(set(s.metric)&CORE));row[period+'_missing_core']='|'.join(sorted(CORE-set(s.metric)))
  matrix.append(row)
 pd.DataFrame(matrix).to_csv(output/'VALUE_STRATEGY_1495_REQUIREMENTS.csv',index=False,lineterminator='\n')
 x.groupby(['period','metric','scope','statement','parser_version']).agg(rows=('amount_krw','size'),companies=('corp_code','nunique'),stock_hints=('stock_code','nunique'),receipts=('rcept_no','nunique')).reset_index().to_csv(output/'FIELDS_PERIODS_VERSIONS.csv',index=False,lineterminator='\n')
 # Existing actual-source attestations, not newly invented v5 approvals.
 equity=json.loads((ROOT/'docs/research/pit-period-20261021/evidence/PIT_CASE.json').read_text());annual=json.loads((ROOT/'docs/research/finite-source-linkage-20261021/evidence/ANNUAL_PIT_CASES.json').read_text());records=[dict(row=equity['original_record'],attestation=equity['attestation'])]
 for c in annual['cases']:records.append(dict(row=c['row'],attestation=c['source_attestations']['2010-04-01']['attestation']))
 passed=bridge(records,'2010-04-01',equity['calendar']);assert passed['source_ready_rows']==3 and passed['source_ready_stocks']==1
 passed['raw'].to_csv(output/'EXISTING_ATTESTED_ACCOUNT_ROWS.csv',index=False,lineterminator='\n');passed['snapshots'].to_csv(output/'EXISTING_PROVIDER_SNAPSHOT.csv',index=False,lineterminator='\n')
 rejected=[]
 # The new independent source review supplies meaning, not a fabricated version chain.
 review=json.loads(new_source_review.read_text());source_by={r['receipt']:[]for r in review['rows']}
 for p in trial_source.rglob('results/*.json'):
  result=json.loads(p.read_text())
  for r in result['rows']:
   if r['metric']in CORE:
    source_by[r['rcept_no']].append(dict(row=r,attestation={}))
 for receipt,items in source_by.items():
  got=bridge(items,'2010-04-01',equity['calendar']);assert got['source_ready_rows']==0;rejected.extend(got['decisions'])
 try:DartValueFactorAdapter(ROOT).factor_frame(pd.Timestamp('2010-04-30'),pd.DataFrame([dict(Code=s,Marcap=1)for s in sorted(expected)]));raise AssertionError('PARTIAL_UNIVERSE_ADMITTED')
 except RuntimeError as e:population_block=str(e)
 same_source_matches=sum(any(x.rcept_no.eq(r['row']['rcept_no']))for r in records)
 summary=dict(classification='RESEARCH_ONLY',periods=reports,rows_total=len(x),raw_total_companies=x.corp_code.nunique(),raw_total_stock_hints=x.stock_code.nunique(),source_member_columns_present=any(c.startswith('source_member')for c in x.columns),canonical_coverage=signal_completeness_report(ROOT,pd.Timestamp('2010-04-30'),mapping,state),eligible_stocks_of_expected=0,expected_population=len(expected),bulk_legacy_rows_newly_admitted=0,existing_verified_bridge=dict(account_rows=3,stocks=1,period='2009FY',signal='2010-04-01',net_new_PIT_fields=0,matching_rows_from_old_v5_dataset=same_source_matches,source='Already attested canary records, separate from oldv5bulk and880; no double-count of prior verification'),new_issuer_core_provider_queries=rejected,full_population_refusal=population_block,status_ledger_changed=False,source_HTTP=0,causes=dict(schema='v5 metric/amount columns differ from canonical account-row schema; new bridge maps only source-attested concepts',identifiers='Stock/corp hints need exact historical identity, not padding/current-name guesses',period='Month-first v5 period_end is a hint; only original-header duration can populate current vs YTD',unit='NormalizedKRW must not be multiplied twice; source unit/multiplier must be attested',source='Document SHA exists but source-member/version binding is absent from v5 schema',meaning='Confidence/source_qualityPASS is not independent financial verification; conflicting source versions remain unresolved',PIT='No population-complete publication/correction/identity attestations; new two-issuer values return no provider input'),strategy_contract=dict(strategy='Existing equity universe book_to_price rank, KOSPI/KOSDAQ observed population, April2010 signal',population=1495,period_dependencies=['2009Q3','2009FY'],required_fields=['equity_FY_instant','revenue_FY_minus_same_scope_Q3_cumulative','net_income_FY_minus_same_scope_Q3_cumulative','ocf_FY_minus_same_scope_Q3_cumulative'],eligibility='All required source/semantic/PIT/issuer conditions; original universe, no easy-stock subset',costs_execution='Existing DSL fixedcost and next-close; not run because input gate remains blocked'))
 (output/'LEGACY_PROVIDER_SCOPE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in summary.items()if k in {'periods','rows_total','eligible_stocks_of_expected','expected_population','bulk_legacy_rows_newly_admitted','existing_verified_bridge'}},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--new-source-review',type=Path,required=True);p.add_argument('--trial-source',type=Path,required=True);a=p.parse_args();main(a.output,a.new_source_review,a.trial_source)
