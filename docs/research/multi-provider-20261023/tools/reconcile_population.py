import json,sys
from pathlib import Path
import pandas as pd
import argparse
a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();R=args.root;sys.path.insert(0,str(R/'scripts'));from dart_value_factor_adapter import load_historical_code_map,expected_codes_for_period
out=args.output;out.mkdir(exist_ok=False);date=pd.Timestamp('2010-04-30');mapping=load_historical_code_map(R);valid=mapping.corp_code.str.fullmatch(r'\d{8}',na=False)&mapping.first_date.notna()&mapping.last_date.notna();B=expected_codes_for_period(mapping,2009);atdate=mapping[valid&mapping.first_date.le(date)&mapping.last_date.ge(date)];Bdate=set(atdate.stock_code)
panel=pd.read_parquet(R/'data/krx_equities/yearly/marcap-2010.parquet',columns=['Date','Code','Name','Market','Close','Volume','Marcap'],filters=[('Date','=',date)]);panel.Code=panel.Code.astype(str).str.zfill(6);signal=panel[panel.Market.isin(['KOSPI','KOSDAQ'])&panel.Marcap.gt(0)];assert not signal.Code.duplicated().any();A=set(signal.Code);I=A&B;ao=A-B;bo=B-A;assert(len(A),len(B),len(I),len(ao),len(bo))==(1946,1495,1490,456,5);assert len(I)+len(ao)==len(A)and len(I)+len(bo)==len(B)
rows=[]
for code in sorted(A|B):
 m=mapping[mapping.stock_code.eq(code)];q=panel[panel.Code.eq(code)];active=m[m.first_date.le(date)&m.last_date.ge(date)];corp=sorted(set(c for c in m.corp_code if len(c)==8 and c.isdigit()));reasons=[]
 if code in ao:
  if m.empty:reasons.append('NO_CODE_ROW_IN_SOURCE_MAP')
  elif not corp:reasons.append('NO_VALID_CORPORATE_IDENTIFIER')
  elif any((r.first_date.year==2010 and r.last_date>=date)for r in m.itertuples()):reasons.append('SOURCE_YEAR2009_EXCLUDES_OBSERVED_START2010')
  elif active.empty:reasons.append('OUTSIDE_OBSERVED_MAPPING_INTERVAL_AT_SIGNAL')
  else:reasons.append('REQUIRES_YEAR_SCOPE_RECONCILIATION')
 if code in bo:
  if q.empty:reasons.append('NO_OBSERVATION_ON_SIGNAL')
  elif not q.Market.isin(['KOSPI','KOSDAQ']).any():reasons.append('OUTSIDE_REQUESTED_MARKETS')
  elif not q.Marcap.gt(0).any():reasons.append('NO_POSITIVE_MARCAP')
  else:raise AssertionError('SET_MEMBERSHIP_DRIFT')
 rows.append(dict(stock_code=code,in_strategy=code in A,in_source_year2009=code in B,in_mapping_on_signal=code in Bdate,group='INTERSECTION'if code in I else'STRATEGY_ONLY'if code in ao else'LEDGER_ONLY',signal_date='2010-04-30',signal_name='|'.join(sorted(set(q.Name.astype(str)))),signal_market='|'.join(sorted(set(q.Market))),mapping_corp_codes='|'.join(corp),map_rows=len(m),active_map_rows=len(active),mapping_first='|'.join(sorted({str(d.date())for d in m.first_date if pd.notna(d)})),mapping_last='|'.join(sorted({str(d.date())for d in m.last_date if pd.notna(d)})),code_to_company_certification='UNVERIFIED_UNLESS_SEPARATELY_ATTESTED',name_preferred_hint=bool(len(q)and any('우'in str(n)for n in q.Name)),reasons='|'.join(reasons)))
x=pd.DataFrame(rows);x.to_csv(out/'ALL_MEMBERSHIP.csv',index=False)
for group in ['INTERSECTION','STRATEGY_ONLY','LEDGER_ONLY']:x[x.group.eq(group)].to_csv(out/(group+'.csv'),index=False)
# Derive field counts from exact same seven slots, never use row counts as stocks.
legacy=pd.read_csv(R/'data/financials/legacy_2000_2014/normalized/legacy_metrics_2009.csv.gz',dtype=str).fillna('');legacy=legacy[(legacy.fiscal_year=='2009')&legacy.period.isin(['Q3','FY'])];slots={('FY','equity'),('FY','revenue'),('FY','net_income'),('FY','ocf'),('Q3','revenue'),('Q3','net_income'),('Q3','ocf')};hint={}
for r in legacy.itertuples():
 if (r.period,r.metric)in slots and r.period_end.startswith('2009-'+('12'if r.period=='FY'else'09')):hint.setdefault(r.stock_code,set()).add((r.period,r.metric))
# Reuse preserved semantic judgments; no source re-audit. Already reviewed seven
# input identities are deduplicated by security/period/metric, not receipt count.
cat=pd.read_csv(R/'data/financials/legacy_2000_2014/legacy_filings.csv.gz',dtype=str).fillna('');cat=cat.drop_duplicates('rcept_no').set_index('rcept_no');semantic={}
old=json.loads((R/'docs/research/source-review-batch2-20261021/all-871-candidate-decisions.json').read_text());new9=json.loads((R/'docs/research/native-source-boundary-repair-20261021/new-9-independent-source-controls.json').read_text())['records'];new34=json.loads((R/'docs/research/legacy-provider-link-20261023/evidence/NEW34_SOURCE_REVIEW.json').read_text())['rows']
for d in [d for d in old if d['semantic_verdict']=='PASS']+new9+new34:
 code=d.get('stock_code_hint')or str(cat.loc[d['receipt'],'stock_code']);end=d['period_end'];period='FY'if end=='2009-12-31'else'Q3'if end=='2009-09-30'else''
 if(period,d['metric'])in slots:semantic.setdefault(code,set()).add((period,d['metric']))
semantic.setdefault('007160',set()).update({('FY',m)for m in ['equity','revenue','net_income','ocf']})
coverage=[]
for label,codes in [('SOURCE_YEAR2009',B),('ORIGINAL_STRATEGY',A),('MAPPING_AT_SIGNAL',Bdate)]:
 n=len(codes)*7;raw=sum(len(hint.get(c,set()))for c in codes);sem=sum(len(semantic.get(c,set()))for c in codes);coverage.append(dict(population=label,unique_security_codes=len(codes),required_slots=n,candidate_hint_numerator=raw,candidate_hint_rate=raw/n,source_semantic_numerator=sem,source_semantic_rate=sem/n,fully_PIT_ready_stocks=0,unique_valid_corp_hint_count=mapping[mapping.stock_code.isin(codes)&valid].corp_code.nunique()))
summary=dict(status='PASS_SET_ARITHMETIC_WITH_DISTINCT_TIME_BASES',signal='2010-04-30',identifier='six-digit security code; company count kept separate',A_strategy=1946,B_source_year2009=1495,intersection=1490,A_only=456,B_only=5,arithmetic=['1946=1490+456','1495=1490+5'],strategy_duplicate_codes=0,source_map_duplicate_rows=int(mapping.stock_code.duplicated().sum()),source_gate_time_basis='Year2009 observed interval intersects year, not snapshot2010-04-30',mapping_codes_on_same_signal=len(Bdate),same_signal_intersection=len(A&Bdate),same_signal_A_only=len(A-Bdate),same_signal_mapping_only=len(Bdate-A),outside_causes=x[x.group.eq('STRATEGY_ONLY')].reasons.value_counts().to_dict(),ledger_only=x[x.group.eq('LEDGER_ONLY')].to_dict('records'),coverage=coverage,corporate_mapping_hint_not_legal_certification=True,source_HTTP=0,universe_changed=False)
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
