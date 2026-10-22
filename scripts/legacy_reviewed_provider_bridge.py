"""Explicit source-attested legacy -> canonical DART account-row bridge.

Never consumes v5 confidence/source_quality as a financial/PIT approval. It
returns only source-ready records, retains flow duration, and does not change
coverage_report or register a partial-universe ranking capability.
"""
import math
from collections import defaultdict
from datetime import date
from decimal import Decimal
import pandas as pd
from financial_record_readiness import key,select_asof
from dart_value_factor_adapter import report_snapshots,latest_snapshot
CONCEPTS={'equity':('BS','자본총계'),'revenue':('IS','매출액'),'net_income':('IS','당기순이익(손실)'),'ocf':('CF','영업활동으로인한현금흐름')}
UNITS={'원':Decimal(1),'KRW':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000),'억원':Decimal(100000000)}
COLUMNS=['stock_code','fs_div_requested','rcept_no','filing_date','sj_div','account_id','account_nm','thstrm_amount','thstrm_add_amount']
def to_account_row(row,attestation):
 metric=row.get('metric');scope=row.get('scope')
 if metric not in CONCEPTS or scope not in {'CFS','OFS'}or row.get('statement')!=CONCEPTS[metric][0]:raise ValueError('LEGACY_UNSUPPORTED_CONCEPT_OR_STATEMENT')
 if len(str(row.get('stock_code','')))!=6 or not str(row['stock_code']).isdigit()or len(str(row.get('corp_code','')))!=8 or not str(row['corp_code']).isdigit():raise ValueError('LEGACY_UNVERIFIED_IDENTIFIER')
 amount=Decimal(str(row['amount_krw']));unit=row.get('unit');multiplier=Decimal(str(row.get('unit_multiplier')))
 if not amount.is_finite()or unit not in UNITS or multiplier!=UNITS[unit]:raise ValueError('LEGACY_UNKNOWN_UNIT_OR_NONFINITE')
 # amount_krw is already independently attested normalizedKRW; never scale twice.
 end=date.fromisoformat(row['period_end']);publication=attestation['publication']['date']
 if end>date.fromisoformat(publication):raise ValueError('LEGACY_FUTURE_ACCOUNTING_PERIOD')
 if(end.month,end.day)not in {(9,30),(12,31)}:raise ValueError('LEGACY_CALENDAR_Q3_FY_ONLY')
 current=cumulative=''
 if metric=='equity':
  if row.get('measurement_basis')!='instant'or row.get('period_start'):raise ValueError('LEGACY_BALANCE_NOT_INSTANT')
  current=str(amount)
 else:
  if row.get('measurement_basis')!='duration':raise ValueError('LEGACY_FLOW_DURATION_UNVERIFIED')
  start=date.fromisoformat(row['period_start'])
  if start.year!=end.year or(end.month,end.day)not in {(9,30),(12,31)}:raise ValueError('LEGACY_CALENDAR_Q3_FY_ONLY')
  if(start.month,start.day)==(1,1):
   if(end.month,end.day)==(12,31):current=str(amount) # actual annual total
   else:cumulative=str(amount) # actual Jan..Sep YTD, never a standalone Q3
  elif(start.month,start.day)==(7,1)and(end.month,end.day)==(9,30):current=str(amount)
  else:raise ValueError('LEGACY_FLOW_WINDOW_UNSUPPORTED')
 return dict(stock_code=row['stock_code'],fs_div_requested=scope,rcept_no=row['rcept_no'],filing_date=publication,sj_div=row['statement'],account_id='',account_nm=CONCEPTS[metric][1],thstrm_amount=current,thstrm_add_amount=cumulative)

def bridge(records,signal_date,calendar):
 groups=defaultdict(list)
 for record in records:groups[(record['row'].get('stock_code'),)+key(record['row'])].append(record)
 raw=[];decisions=[]
 for identity,versions in groups.items():
  chosen=select_asof(versions,signal_date,calendar);decision=dict(stock_code_hint=identity[0],corp_code=identity[1],metric=identity[2],status=chosen['status'],reason=chosen['reason'])
  if chosen['status']=='PASS':
   row=chosen['selected'];att=next(v['attestation']for v in versions if v['row']==row);raw.append(to_account_row(row,att));decision.update(receipt=row['rcept_no'],source_binding=chosen['readiness']['binding'],usable_from_close=chosen['readiness']['usable_from_close'])
  decisions.append(decision)
 frame=pd.DataFrame(raw,columns=COLUMNS)
 snapshots=latest_snapshot(report_snapshots(frame),pd.Timestamp(signal_date))if len(frame)else pd.DataFrame()
 return dict(raw=frame,snapshots=snapshots,decisions=decisions,source_ready_rows=len(frame),source_ready_stocks=frame.stock_code.nunique()if len(frame)else 0,engine_population_ready=False,coverage_owner='Unchanged DartValueFactorAdapter.coverage_report; no status ledger edited',classification='RESEARCH_ONLY',investment_approved=False)
