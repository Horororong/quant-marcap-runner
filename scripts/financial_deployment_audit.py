"""Manual primary-source literals/coordinates versus external subject output.

This module never imports production accounts/period/numeric parser functions.
Missing extraction is UNVERIFIED, never an exactness PASS.
"""
import argparse,base64,csv,gzip,hashlib,io,json,sys,zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_source_grid import Grid
def number(raw):
    s=raw.strip().replace(',','')
    if s.startswith('(-)'):return -Decimal(s[3:])
    if s.startswith('(') and s.endswith(')'):return -Decimal(s[1:-1])
    return Decimal(s)
def main(source,controls,replay,out):
    out.mkdir(parents=True,exist_ok=False);data=json.loads(gzip.decompress(base64.b64decode(source.read_bytes())))
    observed={r['receipt']:r for r in json.loads((replay/'replay.json').read_text())};grids={};rows=[]
    for rec in data['manifest']:
        for a in rec['archives']:
            b=base64.b64decode(data['files'][a['path']]);assert hashlib.sha256(b).hexdigest()==a['sha256']
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                assert z.testzip() is None
                for member in z.namelist():
                    if not member.endswith('.xml'):continue
                    raw=z.read(member)
                    for enc in ['utf-8','cp949','euc-kr']:
                        try:text=raw.decode(enc);assert text.encode(enc)==raw;break
                        except UnicodeError:pass
                    else:raise ValueError('Unverified encoding')
                    g=Grid();g.feed(text);grids[rec['receipt'],member]=(g,hashlib.sha256(raw).hexdigest(),a['sha256'])
    for c in json.loads(controls.read_text())['controls']:
        g,digest,archive=grids[c['receipt'],c['member']];literal=g.tables[c['table']]['rows'][c['row']][c['column']];assert literal==c['literal']
        expected=number(literal)*Decimal(c['multiplier'])
        matched=[r for r in observed[c['receipt']]['rows']if (r['metric'],r['scope'])==(c['metric'],c['scope'])]
        # Duplicate extractions must be unambiguous in both amount and period.
        verdict='UNVERIFIED' if not matched else 'PASS' if all(Decimal(r['amount_krw'])==expected for r in matched) else 'FAIL'
        period='UNVERIFIED' if not matched else 'PASS' if all((r.get('period_start'),r.get('period_end'),r.get('measurement_basis'),r.get('period'))==(c['period_start'],c['period_end'],c['basis'],c['report_period'])for r in matched) else 'FAIL'
        exact_source=[r for r in matched if (r['source_member'],r['table_index'],r['row_index'],r['value_col'])==(c['member'],c['table'],c['row'],c['column']) and r['source_member_sha256']==digest]
        source_status='PASS' if exact_source else 'UNVERIFIED'
        rows.append(dict(sample=c['sample'],receipt=c['receipt'],metric=c['metric'],scope=c['scope'],source_literal=literal,unit=c['unit'],expected_normalized=str(expected),extracted='|'.join(r['amount_krw']for r in matched),amount_verdict=verdict,period_verdict=period,source_verdict=source_status,expected_start=c['period_start'],expected_end=c['period_end'],actual_periods='|'.join(str((r.get('period_start'),r.get('period_end'),r.get('measurement_basis')))for r in matched),source_location=f"{c['member']}#table={c['table']},row={c['row']},col={c['column']}",source_member_sha256=digest,archive_sha256=archive,filing_date_index=c['filing_date_index'],official_publication_verdict='UNVERIFIED',correction_chain_verdict=c['correction_chain_verdict'],historical_identity_verdict='UNVERIFIED',investment_approved=False,rejection_reason='|'.join(s['status'] for s in observed[c['receipt']]['states'])if not matched else 'PIT_UNVERIFIED'))
    with (out/'details.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(documents=len({r['receipt']for r in rows}),fields=len(rows),counts={k:dict(Counter(r[k]for r in rows))for k in ['amount_verdict','period_verdict','source_verdict']},samples={sid:{k:dict(Counter(r[k]for r in rows if r['sample']==sid))for k in ['amount_verdict','period_verdict','source_verdict']}for sid in sorted({r['sample']for r in rows})},financial_population_certification='UNVERIFIED',investment_PIT='0/6')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
    return int(any(r['amount_verdict']=='FAIL' or r['period_verdict']=='FAIL'for r in rows))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(main(a.source,a.controls,a.replay,a.output))
