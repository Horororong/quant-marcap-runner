"""Preserve legacy version alternatives; classify clues without choosing values.

An indexed amendment label is a clue, not a source-attested correction graph.
Units are retained as source representations, never separate economic concepts.
"""
from decimal import Decimal
from itertools import combinations
import hashlib,json
BASE=('corp_code','stock_code','fiscal_year','period','metric','scope','statement')
def version_key(row):
 """No rounded/latest/averaged collapsing; missing member/duration stays unknown."""
 names=BASE+('period_end','period_start','measurement_basis','rcept_no','document_sha256','source_member','source_member_sha256','unit','unit_multiplier','value_col','table_index','row_index','amount_krw')
 return hashlib.sha256(json.dumps({k:row.get(k,'UNVERIFIED')for k in names},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def classify(rows):
 if not rows or len({tuple(r[k]for k in BASE)for r in rows})!=1:raise ValueError('MIXED_OR_EMPTY_CONFLICT_IDENTITY')
 reasons=[];values=[Decimal(r['amount_krw'])for r in rows]
 if not all(v.is_finite()for v in values):raise ValueError('NONFINITE_LEGACY_VALUE')
 if len(set(values))<2:raise ValueError('NOT_A_VALUE_CONFLICT')
 if any('정정'in r.get('report_nm','')for r in rows):reasons.append('INDEXED_AMENDMENT_SOURCE_GRAPH_UNVERIFIED')
 months={r.get('period_end','')[5:7]for r in rows}
 wanted='12'if rows[0]['period']=='FY'else'09'
 relevant=wanted in months
 if not relevant:reasons.append('OUTSIDE_TARGET_CALENDAR_PERIOD_HINT')
 unit_change=len({(r.get('unit'),r.get('unit_multiplier'))for r in rows})>1
 if unit_change:reasons.append('DIFFERENT_SOURCE_UNIT_REPRESENTATION')
 factor1000=False;opposite=False;rounding=False
 for a,b in combinations(rows,2):
  av,bv=Decimal(a['amount_krw']),Decimal(b['amount_krw']);am=Decimal(a.get('unit_multiplier','1'));bm=Decimal(b.get('unit_multiplier','1'))
  # A mathematical signature identifies what to audit, never the correct operand.
  if av and bv and max(abs(av),abs(bv))==min(abs(av),abs(bv))*1000 and av*bv>0:factor1000=True
  if av*bv<0:opposite=True
  if am!=bm and av*bv>0 and abs(av-bv)<max(am,bm):rounding=True
 if factor1000:reasons.append('EXACT_1000X_SCALE_SIGNATURE')
 if opposite:reasons.append('SIGN_OR_ACCOUNT_DEFINITION_AMBIGUITY')
 if rounding:reasons.append('WITHIN_SOURCE_DISPLAY_PRECISION_NOT_EQUAL')
 if not(factor1000 or opposite or rounding):reasons.append('VALUE_OR_CURRENT_COMPARATIVE_VERSION_UNRESOLVED')
 return dict(reasons=reasons,source_adjudication='UNVERIFIED',economic_values_resolved=0,target_calendar_period_relevant=relevant,version_keys=[version_key(r)for r in rows],selected=None,source_required=True,comparative_vs_current='UNVERIFIED_NO_ORIGINAL_HEADER',cumulative_vs_standalone='UNVERIFIED_NO_ORIGINAL_HEADER',unit_change_is_not_new_economic_key=True)
