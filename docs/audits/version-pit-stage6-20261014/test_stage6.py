"""Offline transport safety and conservative policy tests (no primary proof)."""
import importlib.util, io, json, tempfile, unittest, zipfile
from pathlib import Path
HOME = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('documents', HOME/'collect_documents.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
KEY = 'a'*40
ROW = {'sample_id':'TEST','corp_code':'12345678','rcept_no':'20070814000001'}
def archive(corp='12345678', extra=''):
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('receipt.xml',f'<DOCUMENT><COMPANY-NAME AREGCIK="{corp}">Company</COMPANY-NAME><P>{extra}</P></DOCUMENT>')
    return out.getvalue()
class CollectionTests(unittest.TestCase):
    def run_case(self, key=KEY, payload=None, rows=None, transport=None):
        calls=[]
        def fake(receipt,key):
            calls.append(receipt); return 200,payload if payload is not None else archive()
        with tempfile.TemporaryDirectory() as d:
            state=C.acquire(rows or [ROW],key,Path(d)/'new',transport or fake)
            files=[p.name for p in (Path(d)/'new/raw').iterdir()]
        return state,calls,files
    def test_exact_success(self):
        s,c,f=self.run_case();self.assertEqual(s['status'],'COMPLETE');self.assertEqual(c,[ROW['rcept_no']]);self.assertEqual(len(f),1)
    def test_missing_auth_no_request(self):
        s,c,f=self.run_case(key='');self.assertEqual(c,[]);self.assertEqual(s['error']['kind'],'AUTH_ENV_MISSING_OR_INVALID')
    def test_rate_error_preserved_no_retry(self):
        s,c,f=self.run_case(payload=b'<result><status>020</status><message>limit</message></result>')
        self.assertEqual(s['error']['dart_status'],'020');self.assertEqual(len(c),1);self.assertEqual(len(f),1)
    def test_wrong_corp_not_saved(self):
        s,c,f=self.run_case(payload=archive('87654321'));self.assertEqual(s['error']['kind'],'DOCUMENT_CORP_MISMATCH');self.assertEqual(f,[])
    def test_literal_credential_inside_compressed_zip(self):
        s,c,f=self.run_case(payload=archive(extra=KEY));self.assertEqual(s['error']['kind'],'CREDENTIAL_ECHO_BLOCKED');self.assertEqual(f,[])
    def test_xml_escaped_credential(self):
        s,c,f=self.run_case(payload=archive(extra='&#97;'*40));self.assertEqual(s['error']['kind'],'CREDENTIAL_ECHO_BLOCKED');self.assertEqual(f,[])
    def test_exception_url_never_emitted(self):
        def broken(*args):raise C.Stop('TRANSPORT_FAILURE')
        s,c,f=self.run_case(transport=broken);self.assertNotIn(KEY,json.dumps(s));self.assertEqual(s['status'],'STOPPED')
    def test_duplicate_plan_no_calls(self):
        s,c,f=self.run_case(rows=[ROW,ROW]);self.assertEqual(c,[]);self.assertEqual(s['error']['kind'],'INVALID_PLAN')
    def test_budget_no_calls(self):
        rows=[{**ROW,'rcept_no':f'20070814{i:06d}'}for i in range(21)]
        s,c,f=self.run_case(rows=rows);self.assertEqual(c,[]);self.assertEqual(s['status'],'STOPPED')
    def test_existing_checkpoint_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(C.Stop):C.acquire([ROW],KEY,Path(d),lambda *a:self.fail('network'))
    def test_corrupt_xml_held(self):
        s,c,f=self.run_case(payload=b'broken');self.assertEqual(s['status'],'STOPPED');self.assertEqual(f,[])
    def test_real_plan_from_preserved_metadata(self):
        self.assertEqual(len(C.load_plan(HOME/'document_plan.json')),6)
if __name__=='__main__':unittest.main(verbosity=2)
