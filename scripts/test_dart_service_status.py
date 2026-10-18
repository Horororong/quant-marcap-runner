import ast,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dart_service_status import service_status,defer_maintenance,defer_http_transient
from legacy_backfill_runtime import CollectionControl,CollectionPaused,collect_bounded

class Maintenance(unittest.TestCase):
    def test_explicit_xml_only(self):
        for source in [b'<html>800</html>',b'<broken>',b'PK800',b'<result><status>014</status></result>']:
            defer_maintenance(source,None,CollectionPaused)
        self.assertEqual(service_status(b'<?xml version="1.0"?><result><status> 800 </status></result>'),'800')

    def test_actual_fetch_function_stops_before_retry(self):
        # Execute the actual function AST with a deterministic transport double.
        # This is not a claim that the full requests-dependent collector imports.
        source=Path('scripts/backfill_dart_legacy_2000_2014.py').read_text()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_document')
        class Response:
            status_code=200
            content=b'<result><status>800</status><message>maintenance</message></result>'
            text=content.decode()
            def raise_for_status(self):pass
        class Transport:
            calls=0
            def progress(self,*a,**k):pass
            def preserve_error_response(self,*a,**k):pass
            Timeout=type('Timeout',(Exception,),{})
            ConnectionError=type('ConnectionError',(Exception,),{})
            def get(self,*a,**k):self.calls+=1;return Response()
        transport=Transport();control=CollectionControl(min_interval=0)
        env=dict(requests=transport,RUN_CONTROL=control,BASE='https://synthetic.invalid',API_KEY='synthetic',defer_maintenance=defer_maintenance,defer_http_transient=defer_http_transient,CollectionPaused=CollectionPaused,RateLimitExceeded=type('RateLimitExceeded',(Exception,),{}))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-fetch-AST>','exec'),env)
        with self.assertRaises(CollectionPaused):env['fetch_document']('synthetic')
        self.assertEqual(transport.calls,1);self.assertEqual(control.stop_reason,'SERVICE_MAINTENANCE_800')

    def test_http_service_outage_is_deferred_and_other_statuses_not_relabelled(self):
        for code in [408,500,502,503,504]:
            c=CollectionControl(min_interval=0)
            with self.assertRaisesRegex(CollectionPaused,'TRANSIENT_HTTP_'+str(code)):
                defer_http_transient(code,c,CollectionPaused)
            self.assertEqual(c.stop_reason,'TRANSIENT_HTTP_'+str(code))
        for code in [None,200,400,401,403,404,429]:
            c=CollectionControl(min_interval=0);defer_http_transient(code,c,CollectionPaused)
            self.assertEqual(c.stop_reason,'')

    def test_actual_fetch_exhaustion_is_deferred_with_no_secret_or_document_error(self):
        import types
        source=Path('scripts/backfill_dart_legacy_2000_2014.py').read_text()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_document')
        class Transport:
            calls=0
            def progress(self,*a,**k):pass
            Timeout=type('Timeout',(Exception,),{})
            ConnectionError=type('ConnectionError',(Exception,),{})
            def get(self,*a,**k):self.calls+=1;raise self.Timeout('https://synthetic.invalid/?crtfc_key=DO_NOT_LOG')
        c=CollectionControl(min_interval=0);t=Transport();sleeps=[]
        env=dict(requests=t,RUN_CONTROL=c,BASE='https://synthetic.invalid',API_KEY='DO_NOT_LOG',defer_maintenance=defer_maintenance,defer_http_transient=defer_http_transient,CollectionPaused=CollectionPaused,RateLimitExceeded=type('RateLimitExceeded',(Exception,),{}),time=types.SimpleNamespace(sleep=sleeps.append))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-fetch-AST>','exec'),env)
        with self.assertRaises(CollectionPaused) as caught:env['fetch_document']('synthetic')
        self.assertEqual(t.calls,2);self.assertEqual(sleeps,[2]);self.assertEqual(c.stop_reason,'TRANSIENT_TRANSPORT_EXHAUSTED')
        self.assertNotIn('DO_NOT_LOG',str(caught.exception));self.assertNotIn('https://',str(caught.exception))

    def test_bounded_resume_preserves_other_finished_work(self):
        control=CollectionControl(min_interval=0);saved=[]
        def process(meta):
            if meta['id']==2:
                try:defer_maintenance(b'<result><status>800</status></result>',control,CollectionPaused)
                except CollectionPaused:return [],dict(id=2,status='DEFERRED',attempt_count=0)
            return [dict(id=meta['id'],amount=10)],dict(id=meta['id'],status='PARSED_PARTIAL',attempt_count=0)
        def save(rows,states):saved.extend((list(rows),list(states)))
        result=collect_bounded([dict(id=i) for i in range(1,20)],process,save,control,workers=1,checkpoint_size=25)
        self.assertEqual(result['stop_reason'],'SERVICE_MAINTENANCE_800')
        states=[s for group in saved for s in group if 'status' in s]
        self.assertEqual([s['status'] for s in states],['PARSED_PARTIAL','DEFERRED'])
        self.assertTrue(all(s['attempt_count']==0 for s in states))

if __name__=='__main__':unittest.main(verbosity=2)
