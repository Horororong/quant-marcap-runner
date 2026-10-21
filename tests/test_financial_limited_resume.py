import copy,hashlib,json,sys,tempfile,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_limited_resume as m
from scripts.financial_rollout import run_batch

class Limited(unittest.TestCase):
    def setUp(self):
        self.c=json.loads((ROOT/m.CONFIG).read_text());self.s=m.initial();self.now=datetime(2026,10,19,8,tzinfo=timezone.utc)
    def test_first_schedule_review_daily_total_and_failure_gates(self):
        m.check_gate(self.c,self.s,self.now,'first-approved-push')
        with self.assertRaisesRegex(ValueError,'APPROVED_PUSH'):m.check_gate(self.c,self.s,self.now,'schedule')
        self.s['runs']=[dict(day_kst='2026-10-19',reserved_documents=100)];self.s['phase']='READY_NEXT'
        with self.assertRaisesRegex(ValueError,'ONCE_PER'):m.check_gate(self.c,self.s,self.now,'schedule')
        later=datetime(2026,10,20,8,tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError,'REVIEW_REQUIRED'):m.check_gate(self.c,self.s,later,'schedule')
        self.s['first_review']=dict(status='PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION')
        m.check_gate(self.c,self.s,later,'schedule')
        self.s['runs']*=3
        with self.assertRaisesRegex(ValueError,'EXHAUSTED'):m.check_gate(self.c,self.s,later,'schedule')
        for phase in ['RUNNING','WAIT_FIRST_REVIEW','HOLD_FAILURE','OBSERVATION_COMPLETE']:
            self.s['phase']=phase
            with self.assertRaises(ValueError):m.check_gate(self.c,self.s,later,'schedule')
    def test_kst_midnight_not_utc_midnight(self):
        self.assertEqual(m.local_day(datetime(2026,10,19,15,tzinfo=timezone.utc)),'2026-10-20')
        for name,value in [('max_documents_per_run',101),('max_runs',4),('max_total_documents',301),('run_seconds',601),('document_seconds',91),('automatic_financial_publication','ON'),('backtest_eligible',True)]:
            c=copy.deepcopy(self.c);c[name]=value
            with self.assertRaises(ValueError):m.check_gate(c,self.s,self.now,'first-approved-push')
    def test_document_reject_then_next_document_complete_without_values(self):
        worker='''import hashlib,json,os,sys
from pathlib import Path
meta=json.loads(Path(sys.argv[sys.argv.index('--worker')+1]).read_text());r=meta['rcept_no']
p=Path(os.environ['LEGACY_DART_SOURCE_DIR']);p.mkdir(exist_ok=True);b=b'isolated synthetic source';(p/(r+'-synthetic.zip')).write_bytes(b)
result={'parser_version':'synthetic','rows':[],'state':{'rcept_no':r,'status':'SOURCE_GAP' if r=='1'else'NO_METRICS','document_sha256':hashlib.sha256(b).hexdigest(),'error':'synthetic unsupported document'}}
Path(sys.argv[sys.argv.index('--result')+1]).write_text(json.dumps(result))
'''
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);p=root/'worker.py';p.write_text(worker)
            self.assertEqual(run_batch([dict(rcept_no='1'),dict(rcept_no='2')],root/'batch',worker_script=p),0)
            status=json.loads((root/'batch/run_status.json').read_text())
            self.assertEqual(status['completed'],2);self.assertEqual(status['last_checkpoint'],'2')
            self.assertEqual(json.loads((root/'batch/quality/1.json').read_text())['field_count'],0)
    def test_common_guard_failure_stops_before_checkpoint_or_next_worker(self):
        worker='''import json,sys
from pathlib import Path
p=Path(sys.argv[sys.argv.index('--result')+1]);p.write_text(json.dumps({'rows':[],'state':{'status':'SOURCE_GAP'}}))
'''
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);p=root/'worker.py';p.write_text(worker)
            def bad(*args):raise ValueError('COMMON_SOURCE_HASH_FAILURE')
            with self.assertRaisesRegex(ValueError,'COMMON_SOURCE_HASH_FAILURE'):
                run_batch([dict(rcept_no='1'),dict(rcept_no='2')],root/'batch',worker_script=p,result_validator=bad)
            self.assertFalse((root/'batch/collection').exists());self.assertFalse((root/'batch/workers/2').exists())
            self.assertEqual(json.loads((root/'batch/run_status.json').read_text())['status'],'FAILED_CANDIDATES_HELD')
    def test_publication_schema_never_certifies_a_source_gap(self):
        from scripts.legacy_native_financials import PARSER_VERSION
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);(root/'native').mkdir();p=root/'native/1-test.zip'
            with zipfile.ZipFile(p,'w')as z:z.writestr('1.xml','<DOCUMENT/>')
            result=dict(parser_version=PARSER_VERSION,rows=[],state=dict(rcept_no='1',status='SOURCE_GAP',document_sha256=m.sha(p.read_bytes())))
            m.validate_result(dict(rcept_no='1'),result,root)
            result['rows']=[{}]
            with self.assertRaisesRegex(ValueError,'ISOLATED_SOURCE_HAS_VALUES'):m.validate_result(dict(rcept_no='1'),result,root)
            result['rows']=[];result['state']['document_sha256']='changed'
            with self.assertRaisesRegex(ValueError,'SOURCE_HASH_FAILURE'):m.validate_result(dict(rcept_no='1'),result,root)
if __name__=='__main__':unittest.main(verbosity=2)
