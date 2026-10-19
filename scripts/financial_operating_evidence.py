"""Independent source-literal audit of a bounded operating publication.

No production parser/account/period functions are imported. A source-only PASS
never establishes historical identity, correction chain or investment PIT.
"""
import base64,csv,gzip,hashlib,io,json,re,sys,zipfile
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_source_grid import Grid
HOME=Path('docs/audits/financial-deployment-20261018')
BASE=Path('data/financials/legacy_2000_2014/quality_v9')
def amount(raw):
    s=raw.strip().replace(',','')
    return -Decimal(s[1:-1]) if s.startswith('(') and s.endswith(')') else Decimal(s)
def check(root):
    root=Path(root);summary=json.loads((root/HOME/'operating_summary.json').read_text())
    packed=base64.b64decode((root/HOME/'operating_originals.json.gz.b64').read_bytes())
    assert hashlib.sha256(packed).hexdigest()==summary['source_transfer_sha256'],'source transfer SHA'
    raw=json.loads(gzip.decompress(packed));files={n:base64.b64decode(v)for n,v in raw['files'].items()}
    selection=json.loads(files['selection.json'])['samples'];receipts={x['rcept_no']for x in selection}
    assert len(selection)==len(receipts)==summary['completed_documents']<=100
    with (root/'data/status/dart_legacy_backfill_state.csv').open(encoding='utf-8-sig')as f:old={r['rcept_no']for r in csv.DictReader(f)}
    assert not receipts&old,'historical receipt requeued'
    run=json.loads(files['run_status.json']);assert run['stop_reason']=='BATCH_COMPLETE' and run['completed']==len(receipts)
    originals=[json.loads(v) for n,v in files.items() if n.startswith('results/') and n.endswith('.json')]
    assert sum(len(r['rows'])for r in originals)==summary['structural_candidates']==51
    assert json.loads((root/'config/financial_backfill_rollout.json').read_text())['mode']=='HOLD'
    controls=json.loads((root/HOME/'operating_controls.json').read_text())['controls'];grids={};verified=0;actual_stored=set()
    for receipt in receipts:
        collection=json.loads((root/BASE/'collection'/f'{receipt}.json').read_text());quality=json.loads((root/BASE/'quality'/f'{receipt}.json').read_text())
        assert collection['rcept_no']==receipt and collection['source_status']=='DURABLE'
        assert quality['backtest_eligible']is False and quality['availability_status']=='UNVERIFIED'
        for archive in collection['archives']:
            b=files[archive['path']];assert len(b)==archive['bytes'];assert hashlib.sha256(b).hexdigest()==archive['sha256'],'archive SHA'
            with zipfile.ZipFile(io.BytesIO(b))as z:
                assert z.testzip()is None
                for c in [x for x in controls if x['receipt']==receipt and x['publication_policy']=='CORE4_ONLY_AFTER_EXACT_SOURCE_CHECK']:
                    if c['member']not in z.namelist():continue
                    member=z.read(c['member']);assert hashlib.sha256(member).hexdigest()==c['member_sha256']
                    if(receipt,c['member'])not in grids:
                        for enc in ['utf-8','cp949','euc-kr']:
                            try:text=member.decode(enc);assert text.encode(enc)==member;break
                            except UnicodeError:pass
                        else:raise AssertionError('source encoding')
                        g=Grid();g.feed(text);grids[receipt,c['member']]=g
        metric_file=root/BASE/'metrics'/f'{receipt}.json'
        if not metric_file.exists():
            assert quality['published_field_count']==0
            continue
        records=json.loads(metric_file.read_text())['rows'];assert len(records)==quality['published_field_count']
        for row in records:
            matches=[c for c in controls if(c['receipt'],c['metric'],c['scope'],c['member'])==(receipt,row['metric'],row['scope'],row['source_member'])]
            assert len(matches)==1;c=matches[0];assert c['publication_policy']=='CORE4_ONLY_AFTER_EXACT_SOURCE_CHECK','held source published'
            g=grids[receipt,c['member']];literal=g.tables[c['table']]['rows'][c['row']][c['column']]
            assert literal==c['literal'];assert Decimal(row['amount_krw'])==amount(literal)*c['multiplier'],'amount mismatch'
            assert(row['period_start'],row['period_end'],row['measurement_basis'],row['period'])==(c['period_start'],c['period_end'],c['basis'],c['report_period'])
            assert row['fiscal_year']==int(c['period_end'][:4]) and c['report_period']=='FY'
            assert(row['unit'],Decimal(str(row['unit_multiplier'])))==(c['unit'],Decimal(c['multiplier']))
            assert(row['table_index'],row['row_index'],row['value_col'],row['source_member_sha256'])==(c['table'],c['row'],c['column'],c['member_sha256'])
            assert row['document_sha256']==c['archive_sha256'];assert row['backtest_eligible']is False
            assert row['official_publication_verdict']==row['historical_identity_verdict']==row['correction_chain_verdict']=='UNVERIFIED'
            key=(receipt,row['metric'],row['scope']);assert key not in actual_stored;actual_stored.add(key);verified+=1
    assert verified==summary['published_fields']==8
    # This immutable regression certifies only the original10. Later batches
    # have their own independent source/control ledger and must not replace it.
    assert receipts.issubset({p.stem for p in (root/BASE/'collection').glob('*.json')})
    conflicts=json.loads((root/HOME/'operating_source_conflicts.json').read_text())
    for conflict in conflicts:
        observed=[]
        for source_key,literal_key in [('main_source','main_literal'),('attachment_source','attachment_literal')]:
            match=re.fullmatch(r'(.+)#table(\d+),row(\d+),col(\d+)',conflict[source_key]);assert match
            member,table,row,column=match.groups();raw_member=None
            for path,b in files.items():
                if path.startswith('native/'+conflict['receipt']+'-'):
                    with zipfile.ZipFile(io.BytesIO(b))as z:
                        if member in z.namelist():raw_member=z.read(member)
            assert raw_member is not None
            for enc in ['utf-8','cp949','euc-kr']:
                try:text=raw_member.decode(enc);assert text.encode(enc)==raw_member;break
                except UnicodeError:pass
            else:raise AssertionError('conflict source encoding')
            g=Grid();g.feed(text);literal=g.tables[int(table)]['rows'][int(row)][int(column)]
            assert literal==conflict[literal_key];observed.append(amount(literal))
        assert observed[0]!=observed[1]
        assert not(root/BASE/'metrics'/f"{conflict['receipt']}.json").exists(),'conflicting issuer published'
    return dict(status='PASS_BOUNDED_SOURCE_PUBLICATION',documents=len(receipts),source_verified_published_fields=verified,source_conflict_documents_held=summary['source_conflict_documents'],investment_PIT='0/6',financial_population_certification='UNVERIFIED',automatic_collection='HOLD',automatic_publication='HOLD')
if __name__=='__main__':
    root=Path(sys.argv[1])if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
    print(json.dumps(check(root)))
