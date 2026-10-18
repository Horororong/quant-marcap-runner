"""Rollout failure boundaries and append-only source/quality contracts."""
import contextlib,hashlib,io,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import dart_http as http
from scripts.financial_rollout import select_new,complete_checkpoint,run_batch,read_csv

class Queue(unittest.TestCase):
    def test_upgrade_never_requeues_old_parser_or_service_quarantine(self):
        index=[dict(rcept_no=str(i),stock_code='000001',rcept_dt='2007-01-01')for i in range(5)]
        states=[dict(rcept_no='0',parser_version='v5',status='PARSED_4F'),dict(rcept_no='1',parser_version='v5',status='ERROR',error='800')]
        before=json.dumps(states)
        selected=select_new(index+index,states,[dict(rcept_no='2',source_status='DURABLE')],2)
        self.assertEqual([r['rcept_no'] for r in selected],['3','4']);self.assertEqual(json.dumps(states),before)
    def test_no_over100_or_silent_negative_limit(self):
        for n in [0,-1,101]:
            with self.assertRaises(ValueError):select_new([],[],[],n)
    def test_source_and_quality_versions_are_separate(self):
        with tempfile.TemporaryDirectory()as t:
            out=Path(t);(out/'native').mkdir();(out/'native/0001-synthetic.zip').write_bytes(b'synthetic source')
            result=dict(parser_version='synthetic-v9',rows=[dict(amount_krw='123',backtest_eligible=False)],state=dict(status='PARSED_PARTIAL',error='',document_sha256=hashlib.sha256(b'synthetic source').hexdigest()))
            source,quality=complete_checkpoint(out,dict(rcept_no='0001'),result)
            self.assertEqual(source['source_status'],'DURABLE');self.assertNotIn('parser_version',source)
            self.assertEqual(quality['parser_version'],'synthetic-v9');self.assertFalse(quality['backtest_eligible']);self.assertEqual(quality['financial_accuracy'],'UNVERIFIED_UNAUDITED')
            self.assertTrue((out/'results/0001.json').exists())
    def test_cannot_checkpoint_financial_success_without_original(self):
        with tempfile.TemporaryDirectory()as t:
            with self.assertRaises(ValueError):complete_checkpoint(Path(t),dict(rcept_no='1'),dict(parser_version='x',rows=[],state=dict(status='PARSED_PARTIAL')))
            self.assertFalse((Path(t)/'collection').exists())
    def test_api014_is_transport_absence_not_numeric_certification(self):
        with tempfile.TemporaryDirectory()as t:
            c,q=complete_checkpoint(Path(t),dict(rcept_no='1'),dict(parser_version='x',rows=[],state=dict(status='NO_DOCUMENT')))
            self.assertEqual(c['source_status'],'API014');self.assertEqual(q['financial_accuracy'],'UNVERIFIED_UNAUDITED')
    def test_source_sha_conflict_cannot_mark_receipt_complete(self):
        with tempfile.TemporaryDirectory()as t:
            out=Path(t);(out/'native').mkdir();(out/'native/1-synthetic.zip').write_bytes(b'synthetic')
            with self.assertRaisesRegex(ValueError,'Source SHA'):
                complete_checkpoint(out,dict(rcept_no='1'),dict(parser_version='x',rows=[],state=dict(status='PARSED_PARTIAL',document_sha256='wrong')))
            self.assertFalse((out/'collection').exists())

class WallBudgets(unittest.TestCase):
    def test_hung_document_killed_with_pending_receipt_and_no_false_completion(self):
        with tempfile.TemporaryDirectory()as t:
            folder=Path(t);worker=folder/'hung.py';worker.write_text('import time\ntime.sleep(20)\n')
            begin=time.monotonic();code=run_batch([dict(rcept_no='synthetic')],folder/'run',document_seconds=.2,total_seconds=1,worker_script=worker)
            self.assertEqual(code,1);self.assertLess(time.monotonic()-begin,4)
            state=json.loads((folder/'run/run_status.json').read_text())
            self.assertEqual(state['stop_reason'],'DOCUMENT_WALL_BUDGET');self.assertEqual(state['completed'],0)
            self.assertEqual(state['automatic_publication'],'HELD');self.assertFalse((folder/'run/collection').exists())
    def test_crashing_worker_is_not_a_document_missing_success(self):
        with tempfile.TemporaryDirectory()as t:
            folder=Path(t);worker=folder/'crash.py';worker.write_text('raise SystemExit(7)\n')
            self.assertEqual(run_batch([dict(rcept_no='synthetic')],folder/'run',document_seconds=1,total_seconds=2,worker_script=worker),1)
            state=json.loads((folder/'run/run_status.json').read_text());self.assertEqual(state['worker_exit_code'],7);self.assertEqual(state['stop_reason'],'WORKER_FAILURE')

class Transport(unittest.TestCase):
    def test_real_opener_dispatch_uses_ssl_context_without_private_hostname_attribute(self):
        class Stream(io.BytesIO):
            code=200;msg='OK';headers={'Content-Type':'application/xml'}
            def info(self):return self.headers
        captured=[]
        def do_open(handler,connection,req,**kw):
            captured.append(kw);return Stream(b'<result><status>014</status></result>')
        with patch.object(http.request.HTTPSHandler,'do_open',do_open):
            response=http.get('https://opendart.fss.or.kr/api/document.xml')
        self.assertEqual(response.status_code,200);self.assertTrue(captured[0]['context'].check_hostname)
        self.assertNotIn('check_hostname',captured[0])
    def test_endpoint_redirect_or_plain_http_never_leaks_key(self):
        for url in ['http://opendart.fss.or.kr/api/document.xml','https://evil.invalid/api/document.xml','https://opendart.fss.or.kr/other']:
            with self.assertRaises(ValueError):http.get(url,params={'crtfc_key':'DO_NOT_LOG'})
    def test_progress_whitelist_excludes_secrets_urls_and_response_body(self):
        with tempfile.TemporaryDirectory()as t,contextlib.redirect_stdout(io.StringIO())as output:
            dest=Path(t)/'progress.jsonl'
            with patch.dict(os.environ,{'LEGACY_DART_PROGRESS_FILE':str(dest)}):http.progress('http_start',receipt='synthetic',url='SECRET_URL',crtfc_key='DO_NOT_LOG',body='SENSITIVE')
            for text in [dest.read_text(),output.getvalue()]:
                self.assertNotIn('DO_NOT_LOG',text);self.assertNotIn('SECRET_URL',text);self.assertNotIn('SENSITIVE',text)
    def test_actual_stdlib_http_path_has_bounded_body_and_status(self):
        class Stream(io.BytesIO):
            code=503;headers={'Content-Type':'application/xml'}
        class Opener:
            def open(self,req,timeout):
                self.timeout=timeout;return Stream(b'<result><status>800</status></result>')
        opener=Opener();r=http.get('https://opendart.fss.or.kr/api/document.xml',params={'rcept_no':'synthetic'},_opener=opener)
        self.assertEqual(r.status_code,503);self.assertEqual(opener.timeout,10);self.assertIn(b'800',r.content)
        with self.assertRaisesRegex(http.HTTPError,'HTTP_STATUS_503'):r.raise_for_status()
if __name__=='__main__':unittest.main(verbosity=2)
