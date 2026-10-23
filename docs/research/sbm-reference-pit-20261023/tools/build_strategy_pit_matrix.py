"""Field/issuer/signal evidence inventory; never turn catalog hints into PIT."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();R=a.root;sys.path.insert(0,str(R/'scripts'))
from financial_record_readiness import assess,binding,select_asof
from reviewed_financial_batch_bridge import normalise_reviewed
def load(f):return json.loads(f.read_text())
base=R/'docs/research/source-core-batch3-20261023/evidence'
identities=load(base/'identity-final/IDENTITY_AT_SIGNALS.json')
source=load(base/'new20-review/NEW20_CORE_SOURCE_REVIEW.json')
records=load(base/'provider-new80/BOUND_SOURCE_REVIEW_RECORDS.json')
assert len(identities)==40 and len(records)==80
reqfile=R/'docs/research/legacy-provider-link-20261023/evidence/VALUE_STRATEGY_1495_REQUIREMENTS.csv'
with reqfile.open()as f:requirements={r['stock_code_hint']:r for r in csv.DictReader(f)}
# Existing bounded official session proof is a market-level fact, reusable
# independently of issuer publication/version proofs. It cannot supply either.
case=load(R/'docs/research/pit-period-20261021/evidence/PIT_CASE.json')
calendar=case['calendar']
calendar=dict(calendar,additional_verified_sessions={'2010-04-30':dict(verdict='PASS',evidence=[
 dict(path='docs/research/source-readiness-20261019/official-market-proof.json.gz.b64',
      evidence='Existing exact official KRX2010-04-30 snapshot; no continuous listing inferred')])})
matrix=[];fields=[];reasons=[]
for ident in identities:
 receipt=ident['receipt'];code=ident['stock_code'];signal=ident['signal_date']
 group=[x for x in records if x['row']['rcept_no']==receipt]
 assert len(group)==4
 q3=requirements.get(code,{}).get('Q3_core_fields','').split('|')
 missing_q3=[m for m in ['revenue','net_income','ocf']if m not in q3]
 for item in group:
  prepared=normalise_reviewed(item['row'],item['review'],item['filing_index_date']);row=prepared['row']
  att=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=item['review']['evidence']))
  if ident['verdict']=='PASS':att['historical_security_mapping']=ident['historical_security_mapping']
  # No fabricated publication or chain attestation. A single ORIGINAL version
  # is allowed by select_asof once a bounded official no-correction chain is
  # actually proved; a second version is NOT required merely for validation.
  check=assess(row,signal,att,calendar)
  query=select_asof([dict(row=row,attestation=att)],signal,calendar)
  assert not check['research_record_ready'] and query['selected']is None
  fields.append(dict(receipt=receipt,metric=row['metric'],signal_date=signal,
                     source_binding=binding(row),readiness=check,provider_asof=query))
 matrix.append(dict(receipt=receipt,stock_code_hint=code,corp_code=ident['corp_code'],
  signal_date=signal,identity=ident['verdict'],identity_reason=ident['reason'],
  filing_index_date_claim='2010-03-31',public_date_independently_attested=False,
  exact_publication_clock='UNKNOWN_NEXT_OFFICIAL_SESSION_CLOSE_RULE',
  version_chain_closed_at_signal=False,actual_correction_presence='UNVERIFIED',
  actual_two_version_comparison='NOT_REQUIRED_IF_OFFICIAL_ASOF_CHAIN_PROVES_NO_CORRECTION',
  required_FY_semantic_fields='equity|revenue|net_income|ocf',FY_meaning_PASS=4,
  required_Q3_semantic_fields='revenue|net_income|ocf',Q3_meaning_PASS=0,
  Q3_catalog_field_hints='|'.join(m for m in ['revenue','net_income','ocf']if m in q3),
  Q3_missing_raw_hint='|'.join(missing_q3),Q3_exact_JanSep_period_source_proved=False,
  CFS_first_or_OFS_fallback_evidence='UNVERIFIED_NO_COMPLETION_LEDGER_PROMOTION',
  required_field_semantics='4/7',PIT_ready_required_fields=0,engine_ready=False,
  price_and_corporate_action_status='Existing gates retained; no new certification'))
 reasons.append(dict(receipt=receipt,signal_date=signal,needed=[
  'Official publication/viewer plus exact member original-version association',
  'Official filing/attachment/correction list bounded through signal date, all versions preserved; no invented second version',
  'Three independently reviewed Q3Jan1..Sep30 source flows in compatible scope and period',
  'CFS query outcome/explicit allowed OFS fallback for canonical population completion']+
  ([]if ident['verdict']=='PASS'else['Exact historical issuer/security alias/change evidence']),
  receipt_scope='Existing preserved FY receipt only; no new source requests authorized by this report'))
summary=dict(classification='RESEARCH_ONLY',strategy='super_value_dart_dsl',
 strategy_signal='2010-04-30 close, execution under existing next-close contract',
 population=1946,full_population_required_slots=13622,slots_per_stock=7,
 required_slots=['FY2009 equity Dec31','FY2009 annual revenue','FY2009 annual net_income','FY2009 annual OCF',
                 'Q3Jan1Sep30 cumulative revenue','Q3Jan1Sep30 cumulative net_income','Q3Jan1Sep30 cumulative OCF'],
 strategy_definition='EP/BP/CFP/SP; annual-minus-Q3 for the three Q4flows. No Q3equity requirement added',
 companies=20,issuer_signals=40,identity=dict(Counter(x['identity']for x in matrix)),
 field_signal_queries=len(fields),FY_independent_semantics=80,required_semantic_slots_selected20=140,
 selected20_source_semantics_ratio='80/140; all FY only, Q3 source-period and semantics unverified',
 selected20_full_ready_stocks=0,selected20_PIT_ready_fields=0,actual_correction_pairs_newly_compared=0,
 new_identity_PASS=0,new_PIT_fields=0,new_live_engine_fields=0,
 no_correction_rule='A verified closed as-of single-version chain is sufficient; never require a hypothetical second version',
 existing33_identity_proofs_preserved=True,whole_population_ranking_still_blocked=True,
 calendar_shared=True,source_HTTP=0,publication='HOLD',
 priority=['Actual original/version publication proof for20 source-bound FY documents',
           'Resolve7 remaining identity signal pairs with official alias/change evidence',
           'Retrieve existing Q3 raw/version evidence before proposing any re-collection; validate only3needed flows',
           'Full1946 universe and CFS/OFS/corporate-action/source-coverage gates before ranking'])
a.output.mkdir(parents=True,exist_ok=False)
with(a.output/'STRATEGY_PIT_40_CASES.csv').open('w')as f:
 w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
for name,value in [('FIELD_ASOF_160.json',fields),('REQUIRED_EVIDENCE.json',reasons),('SUMMARY.json',summary)]:
 (a.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
