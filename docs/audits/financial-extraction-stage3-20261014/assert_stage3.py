"""Actual-source assertions for Stage3. Sample IDs belong to test oracles only."""
import argparse,json
from decimal import Decimal
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args()
home=Path(__file__).resolve().parent;oldhome=home.parent/'financial-repair-20261014'
oracle=json.loads((oldhome/'holdout_controls.json').read_text())
records=[]
for sid in ['N10','N11','N12','N15','N16']:
 sample=json.loads((a.replay/(sid+'.json')).read_text())
 controls=next(x for x in oracle['fields']if x['sample_id']==sid and x['metric']=='net_income')
 row=next(x for x in sample['rows']if x['metric']=='net_income'and x['scope']=='OFS')
 expected={'N10':'3495352209','N11':'11818493861','N12':'13043736477','N15':'429181546','N16':'1137232375'}[sid]
 assert row['amount_krw']==expected and row['unit']==controls['unit'] and row['scope']==controls['scope']
 assert row['period_start']==controls['period_start'] and row['period_end']==controls['period_end']and row['measurement_basis']==controls['basis']
 assert not row['backtest_eligible']
 records.append({'sample_id':sid,'verdict':'PASS','value':row['amount_krw'],'scope':row['scope'],'start':row['period_start'],'end':row['period_end'],'unit':row['unit'],'statement':row['statement'],'source_table':row['table_index'],'source_row':row['row_index'],'source_column':row['value_col'],'source_member_sha256':row['source_member_sha256'],'combined_IS_boundary':'UNVERIFIED'if sid=='N10'else'not used as ambiguous money'})
ppe=next(x for x in json.loads((a.replay/'S12.json').read_text())['rows']if x['metric']=='ppe')
assert ppe['amount_krw']=='1196468805'and len(ppe['net_components'])==3
assert Decimal(ppe['net_components'][0]['raw'].replace(',',''))==Decimal(ppe['net_components'][1]['raw'].replace(',',''))-Decimal(ppe['net_components'][2]['raw'].strip('()').replace(',',''))
forensic=json.loads((a.results/'forensic_summary.json').read_text())
assert forensic['protected518']=={'PASS':518}
assert sum(forensic['old135_categories'].values())==135
assert sum(forensic['old123_categories'].values())==123
assert forensic['old135_categories']['PARSING_REGRESSION']==1
validation=json.loads((a.results/'validation_summary.json').read_text())
assert validation['holdout64_targets']=={'PASS':64,'FAIL':0,'UNVERIFIED':0}
assert validation['backtest_eligible_samples']==0 and validation['all_original_sha_crc_verified']
out={'stage3_required5':records,'all5_source_values_recovered':True,'S12_net_PPE':'PASS','protected518':'PASS','classification135_and123':'complete','original60_source_identity':'PASS','backtest_eligible':False}
(a.results/'stage3_assertions.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'required5':'PASS','net_PPE':'PASS','protected518':'PASS','classification135_and123':'complete','backtest_eligible':False}))
