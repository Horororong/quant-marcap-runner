"""Fixed old controls, exact receipt/metric/date/scope/basis joins; no rebasing."""
import argparse,csv,json
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OLD=ROOT/'docs/audits/financial-extraction-stage3-20261014/results'
def main(replay,audit,out):
 rows={}
 for path in replay.glob('[SN]*.json'):
  for r in json.loads(path.read_text())['rows']:
   key=tuple(str(r[k])for k in ['rcept_no','metric','period_start','period_end','scope','measurement_basis']);assert key not in rows;rows[key]=r
 fixed=list(csv.DictReader((OLD/'protected518.csv').open(encoding='utf-8-sig')));assert len(fixed)==518
 for c in fixed:
  key=tuple(json.loads(c['exact_key']));r=rows[key]
  assert Decimal(c['after_value'])==Decimal(r['amount_krw'])and c['unit']==r['unit'],('protected financial conflict',key)
 summary=json.loads((audit/'validation_summary.json').read_text());assert summary['holdout64_targets']=={'PASS':64,'FAIL':0,'UNVERIFIED':0};assert summary['all_original_sha_crc_verified'];assert summary['backtest_eligible_samples']==0
 result=dict(protected518={'PASS':518,'FAIL':0,'UNVERIFIED':0},core64=summary['holdout64_targets'],old_originals60='PASS_SHA_CRC_MEMBERS',new_full60_field_counts=summary['field_counts'],scope='Fixed original controls preserved, no new PIT/financial population certification',investment_approved=False)
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.replay,a.audit,a.output)
