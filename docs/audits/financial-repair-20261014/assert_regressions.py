"""Named source-backed regression assertions. Fixtures are replay60 results subject
to the separate independent DOM audit; constants are test oracles, not parser rules.
"""
import argparse,json
from pathlib import Path
from decimal import Decimal
p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def result(s):return json.loads((a.replay/(s+'.json')).read_text())
def amount(s,metric):
 rows=[x for x in result(s)['rows']if x['metric']==metric and x['scope']=='OFS'];assert len(rows)==1,(s,metric)
 return Decimal(rows[0]['amount_krw'])
records=[]
def check(name,condition,evidence):
 assert condition,name
 records.append({'test':name,'status':'PASS','evidence':evidence})
check('S01 original exact period end',all(x['period_end']=='2007-06-30'for x in result('S01')['rows']),'S01 original COVER and primary statement date headers')
for sid,expected in [('S05',1705325070),('S09',22702024384),('S38',3728783406)]:
 check(sid+' positive profit sign and explicit cumulative basis',amount(sid,'net_income')==expected,'Stage1 independent primary IS table controls; revalidation DOM arithmetic')
check('S24 corrected PPE',amount('S24','ppe')==4776788895,'corrected original body table92')
check('S24 malformed current liability withheld',not any(x['metric']=='current_liabilities'for x in result('S24')['rows']),'corrected source 7,205,734,7733 is malformed')
check('S39 corrected full body revenue',amount('S39','revenue')==1721725595,'corrected full body table142; rounded summary is not the oracle')
check('S40 corrected KRW revenue and loss',amount('S40','revenue')==5361076009 and amount('S40','net_income')==-6848255870,'corrected full body table51; source unit 원')
check('S11 prior dividends absent',not any(x['metric']=='dividends_paid'for x in result('S11')['rows']),'current dash cannot become prior 360,000,000')
check('S17 comparative annual CFS excluded',not any(x['scope']=='CFS'for x in result('S17')['rows']),'current June period vs prior December connected statements')
check('S36 comparative borrowings and bonds excluded',not any(x['scope']=='CFS'or x['metric']in {'short_term_borrowings','bond_liabilities'}for x in result('S36')['rows']),'current OFS dash vs prior 34,277,560,000/50,000,000,000')
check('S21 whole company revenue',amount('S21','revenue')==350592000000 and all(x['scope']=='OFS'for x in result('S21')['rows']),'primary OFS whole company amount; segment excluded')
check('S37 whole company cumulative net revenue',amount('S37','revenue')==171879491773,'primary OFS table91 row2 col2; former segment revenue1,342million excluded')
for i in range(26,36):
 sid=f'S{i:02}';s=result(sid)['state']
 check(sid+' data-present extraction gap',s['financial_data_present']and s['status']!='NO_METRICS','Stage1 independent financial_absence_evidence and preserved source cells')
check('60 unique exact preserved ZIPs',len({x['sha256']for x in json.loads((a.replay/'replay_summary.json').read_text())})==60,'source_manifest ZIP SHA, member SHA and CRC')
check('60 publication gates remain closed',all(not result(f'{prefix}{i:02}')['state']['backtest_eligible']for prefix,total in [('S',40),('N',20)]for i in range(1,total+1)),'no identity/correction/publication attestation')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'assertions':len(records),'status':'PASS','results':records},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'assertions':len(records),'status':'PASS'}))
