"""Multi-issuer source-reviewed staging and independent, strict PIT admission.

Typed candidates are NOT engine inputs. No metadata status can auto-create
publication/version/security attestations. Every candidate keeps its original
source binding and all period partitions; no latest-version preview selection.
"""
import copy,hashlib,json
from collections import defaultdict
from datetime import date
from decimal import Decimal
import pandas as pd
from financial_record_readiness import binding
from legacy_reviewed_provider_bridge import CONCEPTS,COLUMNS,to_account_row,bridge
from dart_value_factor_adapter import report_snapshots

def normalise_reviewed(row,review,filing_index_date):
 if review.get('verdict')!='PASS' or not review.get('evidence') or review.get('binding')!=binding(row):raise ValueError('INDEPENDENT_SOURCE_REVIEW_BINDING_REQUIRED')
 if not all(review.get(k)is True for k in ['current_period_proved','scope_proved','unit_sign_proved','account_definition_proved']):raise ValueError('SOURCE_MEANING_NOT_COMPLETE')
 original=copy.deepcopy(row);normal=copy.deepcopy(row);metric=row.get('metric')
 if metric not in CONCEPTS:raise ValueError('UNSUPPORTED_CORE_FIELD')
 end=date.fromisoformat(row['period_end']);period='FY'if(end.month,end.day)==(12,31)else'Q3'if(end.month,end.day)==(9,30)else None
 if period is None:raise ValueError('EXACT_CALENDAR_PERIOD_REQUIRED')
 if metric!='equity':
  start=date.fromisoformat(row['period_start'])
  if start.year!=end.year or(start.month,start.day)!=(1,1):raise ValueError('EXPLICIT_YTD_OR_ANNUAL_RANGE_REQUIRED')
  if row.get('measurement_basis')not in {'duration','cumulative'}:raise ValueError('EXPLICIT_FLOW_BASIS_REQUIRED')
  # Only after bound independent source proof: annual/YTD IS cumulative is a
  # measured duration, not a new quarter. Original source row remains intact.
  if row['statement']=='IS'and row['measurement_basis']=='cumulative':normal['measurement_basis']='duration'
 account=to_account_row(normal,{'publication':{'date':filing_index_date}})
 return dict(original=original,row=normal,canonical_candidate=account,period=(end.year,period),index_date_is_publication_certification=False,normalization_changed_binding=binding(normal)!=binding(original),original_binding=binding(original),normalized_binding=binding(normal),normalization='Explicit source-period IS duration taxonomy only; no value/date/unit/issuer changes')

def compile_reviewed_batch(records,signal_date,calendar):
 partitions=defaultdict(list);audit=[];held=[]
 for item in records:
  try:
   prepared=normalise_reviewed(item['row'],item['review'],item['filing_index_date'])
  except(ValueError,KeyError,TypeError)as exc:
   held.append(dict(receipt=item.get('row',{}).get('rcept_no'),stock_hint=item.get('row',{}).get('stock_code'),metric=item.get('row',{}).get('metric'),reason=str(exc)));continue
  # A full attestation is never rebound by normalization. Its exact original
  # binding must match the normalized row or the unchanged readiness owner refuses.
  att=copy.deepcopy(item.get('attestation')or{})
  if not att:
   att=dict(binding=binding(prepared['row']),financial_accuracy=dict(verdict='PASS',evidence=item['review']['evidence']))
  prepared['attestation']=att;partitions[prepared['period']].append(prepared)
  audit.append(dict(receipt=prepared['row']['rcept_no'],stock_hint=prepared['row']['stock_code'],corp=prepared['row']['corp_code'],metric=prepared['row']['metric'],period=prepared['period'],original_binding=prepared['original_binding'],normalized_binding=prepared['normalized_binding'],normalization_changed_binding=prepared['normalization_changed_binding'],source_review='PASS_ONLY_THIS_BOUND_FIELD',PIT='REQUIRES_SEPARATE_ATTESTATIONS'))
 # The canonical snapshot owner has a stable alias priority. That is not a
 # source adjudication rule: keep conflicting reviewed definitions out of it.
 conflicts=[]
 for period,items in list(partitions.items()):
  groups=defaultdict(list)
  for i in items:
   r=i['row'];groups[(r['stock_code'],r['corp_code'],r['rcept_no'],r['scope'],r['metric'])].append(i)
  isolated=set()
  for identity,versions in groups.items():
   values={Decimal(str(i['row']['amount_krw']))for i in versions}
   if len(values)>1:
    isolated.update(id(i)for i in versions)
    conflicts.append(dict(period=period,identity=identity,values=[str(v)for v in sorted(values)],reason='SAME_RECEIPT_FIELD_VALUE_CONFLICT_NO_ALIAS_PRIORITY_ADJUDICATION'))
    for i in versions:held.append(dict(receipt=i['row']['rcept_no'],stock_hint=i['row']['stock_code'],metric=i['row']['metric'],reason='SAME_RECEIPT_FIELD_VALUE_CONFLICT_NO_ALIAS_PRIORITY_ADJUDICATION'))
  partitions[period]=[i for i in items if id(i)not in isolated]
 outputs={};all_ready=0;ready_codes=set();candidate_rows=0;candidate_codes=set()
 for period,items in sorted(partitions.items()):
  if not items:continue
  frame=pd.DataFrame([i['canonical_candidate']for i in items],columns=COLUMNS);candidate_rows+=len(frame);candidate_codes.update(frame.stock_code)
  # Structural roundtrip preserves ALL receipts. No as-of/latest selection here.
  snapshots=report_snapshots(frame)
  ready=bridge([dict(row=i['row'],attestation=i['attestation'])for i in items],signal_date,calendar);all_ready+=ready['source_ready_rows'];ready_codes.update(ready['raw'].stock_code if len(ready['raw'])else[])
  outputs[period]=dict(candidate_rows=frame,candidate_snapshots=snapshots,ready=ready)
 return dict(partitions=outputs,audit=audit,held=held,conflicts=conflicts,candidate_rows=candidate_rows,candidate_stock_hints=len(candidate_codes),source_ready_rows=all_ready,source_ready_stocks=len(ready_codes),classification='RESEARCH_ONLY',candidate_rows_engine_eligible=False,whole_population_ready=False,investment_approved=False,source_HTTP=0,canonical_ledger_edited=False)
