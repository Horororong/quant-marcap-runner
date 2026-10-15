"""Offline transport safety and conservative policy tests (no primary proof)."""
import importlib.util, io, json, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
HOME = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('documents', HOME/'collect_documents.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
spec = importlib.util.spec_from_file_location('audit_versions', HOME/'audit_versions.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
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
    def test_encoded_primary_evidence_identity(self):
        entries=json.loads((HOME/'source_manifest.json').read_text())
        self.assertEqual(len(entries),12)
        for entry in entries:
            raw=A.source_bytes(entry)
            with zipfile.ZipFile(io.BytesIO(raw))as z:self.assertIsNone(z.testzip())
    def test_preserved_documents_never_redownloaded(self):
        with tempfile.TemporaryDirectory()as d:
            result=subprocess.run([sys.executable,'-I',str(HOME/'collect_documents.py'),'--output',str(Path(d)/'new')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['requests'],0)
            self.assertFalse((Path(d)/'new').exists())
class PolicyTests(unittest.TestCase):
    # Synthetic adversarial policy tests; these do not certify an exchange calendar.
    sessions=['2007-08-14','2007-08-16','2007-08-17','2007-08-23','2007-08-24','2007-09-28','2007-10-01']
    root={'rcept_no':'original','receipt_date':'2007-08-14','is_correction':False,'root_receipt':'original',
          'relationship_grade':'CERTIFIED','source_member_sha256':'old-payload'}
    correction={**root,'rcept_no':'same-day-correction','is_correction':True,'source_member_sha256':'amended-payload'}
    later={**correction,'rcept_no':'later-correction','receipt_date':'2007-08-23','source_member_sha256':'future-payload'}
    def test_receipt_day_never_usable(self):
        self.assertEqual(A.select_version([self.root,self.correction],'2007-08-14',self.sessions)['receipt'],'')
    def test_explicit_same_day_reference_beats_root(self):
        self.assertEqual(A.select_version([self.root,self.correction],'2007-08-16',self.sessions)['receipt'],'same-day-correction')
    def test_later_correction_excluded_before_and_on_receipt_day(self):
        for day in ['2007-08-16','2007-08-23']:
            self.assertNotEqual(A.select_version([self.root,self.correction,self.later],day,self.sessions).get('source_member_sha256'),'future-payload')
    def test_later_correction_only_next_session(self):
        self.assertEqual(A.select_version([self.root,self.correction,self.later],'2007-08-24',self.sessions)['receipt'],'later-correction')
    def test_two_same_day_corrections_never_order_by_receipt_number(self):
        ambiguous={**self.correction,'rcept_no':'99999999999999'}
        self.assertEqual(A.select_version([self.root,self.correction,ambiguous],'2007-08-16',self.sessions)['reason'],'SAME_DAY_ORDER_UNPROVEN')
    def test_unknown_new_version_blocks_stale_fallback(self):
        unknown={**self.later,'relationship_grade':'CANDIDATE'}
        self.assertEqual(A.select_version([self.root,unknown],'2007-08-24',self.sessions)['reason'],'UNPROVEN_VERSION')
    def test_no_calendar_no_weekday_fallback(self):
        self.assertEqual(A.available_date('2007-08-14',[]),'')
    def test_missing_mapping_or_calendar_blocks_investment(self):
        choice={'receipt':'original'}
        for facts in [(False,True,True),(True,False,True),(True,True,False)]:
            self.assertFalse(A.investment_gate(choice,*facts))
    def test_current_name_cannot_certify_past_security(self):
        choice={'receipt':'original','current_company_name':'different-name','stock_code':'006210'}
        self.assertFalse(A.investment_gate(choice,True,False,True))
    def test_delisted_fixture_not_excluded_by_current_survival(self):
        old={**self.root,'currently_listed':False}
        self.assertEqual(A.select_version([old],'2007-08-16',self.sessions)['receipt'],'original')
    def test_malformed_first_submission_not_repaired(self):
        self.assertEqual(A.strict_date('2007년 05년 15일'),'')
    def test_candidate_root_not_certified_by_matching_title(self):
        doc={**self.correction,'corp_code':'12345678','period_end':'2007-06-30','document_name':'반기보고서','initial_date':''}
        self.assertEqual(A.certify_root(doc,[]),('CANDIDATE',''))
    def test_actual_N12_N14_receipt_boundaries(self):
        chains={s['sample_id']:s for s in json.loads((HOME/'stage6_version_chains.json').read_text())['samples']}
        calendar=json.loads((HOME/'calendar_research.json').read_text())['observed_sessions']
        for control in json.loads((HOME/'policy_controls.json').read_text())['controls']:
            family=chains[control['sample_id']]['documents']
            result=A.select_version(family,control['signal_day'],calendar)
            self.assertEqual(result['receipt'],control['receipt'],control)
            self.assertFalse(A.investment_gate(result,False,False,True))
if __name__=='__main__':unittest.main(verbosity=2)
