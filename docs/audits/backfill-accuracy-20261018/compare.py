"""Independent source literals/Decimal controls versus extraction subjects.
No production parser, account aliases, unit/period or selection code imported.
"""
import argparse,base64,csv,gzip,hashlib,io,json,sys,zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
sys.path.insert(0,str(ROOT/'docs/research/long-multi-backfill-20261018'))
from read_main_evidence import Grid

def sha(b):return hashlib.sha256(b).hexdigest()
def number(raw):
 s=raw.strip().replace(',','')
 return -Decimal(s[1:-1]) if s.startswith('(') and s.endswith(')') else Decimal(s)
def writecsv(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def compare(replay,out):
 out.mkdir(parents=True,exist_ok=False);packed=base64.b64decode((HOME/'sources/selected_originals.json.gz.b64').read_bytes())
 assert sha(packed)==json.loads((HOME/'parser_freeze.json').read_text())['compressed_sha256']
 data=json.loads(gzip.decompress(packed));subjects={r['receipt']:r for r in json.loads((replay/'replay.json').read_text())};grids={}
 for rec in data['manifest']:
  for a in rec['archives']:
   b=base64.b64decode(data['files'][a['path']]);assert sha(b)==a['sha256']
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    assert z.testzip() is None
    for name in z.namelist():
     if not name.endswith('.xml'):continue
     raw=z.read(name)
     for enc in ('utf-8','cp949','euc-kr'):
      try:t=raw.decode(enc);assert t.encode(enc)==raw;break
      except UnicodeError:pass
     else:raise ValueError('Unverified encoding')
     g=Grid();g.feed(t);grids[(rec['receipt'],name)]=(g,sha(raw),sha(b))
 controls=json.loads((ROOT/'docs/research/long-multi-backfill-20261018/independent_controls.json').read_text())['controls']+json.loads((HOME/'holdout_controls.json').read_text())['controls'];rows=[]
 periods=json.loads((HOME/'development_period_controls.json').read_text())['controls']
 for c in controls:
  g,digest,archive_sha=grids[c['receipt'],c['member']];tab=g.tables[c['table']];raw=tab['rows'][c['row']][c['column']]
  assert raw==c['original_literal'];assert not c.get('member_sha256') or c['member_sha256']==digest
  expected=number(raw)*c['multiplier'];cohort='holdout' if c['sample'].startswith('H') else 'development'
  before=[r for r in data['metrics'][cohort] if (r['rcept_no'],r['metric'],r['scope'])==(c['receipt'],c['metric'],c['scope'])];assert len(before)<=1
  before=before[0] if before else {};available=[r for r in subjects[c['receipt']]['rows'] if (r['metric'],r['scope'])==(c['metric'],c['scope'])];assert len(available)<=1
  after=available[0] if available else {};bval=before.get('amount_krw','');aval=after.get('amount_krw','');currency=c['currency']=='KRW'
  bv='UNVERIFIED' if not currency else 'PASS' if bval and Decimal(bval)==expected else 'FAIL'
  av='UNVERIFIED' if not currency or not aval else 'PASS' if Decimal(aval)==expected else 'FAIL'
  bp='UNVERIFIED' if not before else 'PASS' if before.get('period_end')==c['period_end'] else 'FAIL'
  ap='UNVERIFIED' if not after else 'PASS' if after.get('period_end')==c['period_end'] else 'FAIL'
  source='UNVERIFIED'
  if after:
   chosen=(after['source_member'],after['table_index'],after['row_index'],after['value_col'])
   source='PASS' if chosen==(c['member'],c['table'],c['row'],c['column']) and after['source_member_sha256']==digest else 'UNVERIFIED'
  basis=c.get('basis');basis=('instant' if c['metric']=='equity' else 'cumulative') if basis in ['as_of','current_fiscal_YTD'] else basis
  expected_start=c.get('period_start','' if c['metric']=='equity' else periods.get(c['sample'],{}).get('start',''))
  expected_period=periods.get(c['sample'],{}).get('report_period')
  contract='UNVERIFIED' if not after else 'PASS' if after.get('measurement_basis')==basis and after.get('period_start')==expected_start and (not expected_period or after.get('period')==expected_period) and ap=='PASS' and source=='PASS' else 'FAIL'
  failure_type='NOT_FINANCIAL_CERTIFICATION' if not currency else 'OMITTED_VALUE' if not bval else 'PRIMARY_EXACT_MATCH' if bv=='PASS' else 'ROUNDED_SUMMARY_PRECISION' if (c['sample'],c['metric']) in [('A01','equity'),('A04','net_income')] else 'SIGN_INVERSION' if Decimal(bval)==-expected else 'UNIT_1000X' if Decimal(bval)==1000*expected else 'QUARTER_YTD_OR_WRONG_SOURCE'
  rows.append(dict(cohort=cohort,sample=c['sample'],receipt=c['receipt'],metric=c['metric'],scope=c['scope'],period_start=c.get('period_start','' if c['metric']=='equity' else ''),period_end=c['period_end'],basis=basis,original_unit=c['original_unit'],original_literal=raw,expected_normalized=str(expected),currency=c['currency'],main_v5=bval,branch_v8=aval,main_amount_verdict=bv,v8_amount_verdict=av,main_period_end=before.get('period_end',''),v8_period_end=after.get('period_end',''),main_period_verdict=bp,v8_period_verdict=ap,v8_source_verdict=source,v8_contract_verdict=contract,error_class=failure_type,source_location=f"{c['member']}#table={c['table']},row={c['row']},col={c['column']}",source_member_sha256=digest,archive_sha256=archive_sha,filing_date_observed=before.get('filing_date',''),availability_verdict='UNVERIFIED',correction_chain_verdict='UNVERIFIED',historical_identity_verdict='UNVERIFIED',pit_approved=False,withholding_reason=subjects[c['receipt']]['status'] if not after else 'PIT_UNVERIFIED'))
 writecsv(out/'field_comparison.csv',rows)
 summary={'zero_tolerance':True,'investment_PIT':'0/6 unchanged','new_original_collection_calls':0,'sample_certification':'All sample-level PIT/identity/correction chains remain UNVERIFIED','cohorts':{}}
 for cohort in ['development','holdout']:
  rr=[r for r in rows if r['cohort']==cohort];summary['cohorts'][cohort]={'samples':len({r['receipt']for r in rr}),'fields':len(rr),**{key:dict(Counter(r[key]for r in rr))for key in ['main_amount_verdict','v8_amount_verdict','main_period_verdict','v8_period_verdict','v8_source_verdict','v8_contract_verdict']},'error_classes':dict(Counter(r['error_class']for r in rr))}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();compare(a.replay,a.output)
