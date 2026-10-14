"""Offline transport/provenance/credential boundaries; no real key or network."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('bounded_dart_history',Path(__file__).with_name('collect_history.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
KEY='Z'*40
def targets():
    return [{'sample_id':f'T{i:02d}','corp_code':f'{i:08d}','rcept_no':f'20070814{i:06d}',
        'index_receipt_date':'2007-08-14','report_nm':'반기보고서 (2007.06)',
        'begin_date':'20070101','declared_original_submission_date':''}for i in range(1,21)]
def good(params,key):
    i=int(params['corp_code']);r={'corp_code':params['corp_code'],'rcept_no':f'20070814{i:06d}',
        'rcept_dt':'20070814','report_nm':'반기보고서 (2007.06)','rm':''}
    return 200,json.dumps({'status':'000','page_no':1,'page_count':100,'total_count':1,'total_page':1,'list':[r]}).encode()
class AcquisitionTests(unittest.TestCase):
    def run_case(self,key=KEY,transport=good):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name)
        return m.acquire(targets(),key,self.output,transport=transport,pause=lambda _:None)
    def test_missing_secret_no_calls(self):
        def forbidden(*a):self.fail('Network attempted with missing key')
        s=self.run_case('',forbidden);self.assertEqual(s['requests'],0);self.assertEqual(s['error']['kind'],'AUTH_ENV_MISSING')
    def test_auth_rejected_stops_before_second(self):
        s=self.run_case(transport=lambda *a:(200,b'{"status":"010","message":"invalid key"}'))
        self.assertEqual(s['requests'],1);self.assertFalse(s['pilot_complete']);self.assertEqual(s['error']['dart_status'],'010')
    def test_second_pilot_failure_blocks_expansion(self):
        calls=[]
        def transport(p,k):
            calls.append(p['corp_code'])
            return good(p,k)if len(calls)==1 else(200,b'{"status":"020"}')
        s=self.run_case(transport=transport);self.assertEqual(len(calls),2);self.assertEqual(len(s['completed_samples']),1);self.assertFalse(s['pilot_complete'])
    def test_key_echo_never_written(self):
        s=self.run_case(transport=lambda *a:(200,json.dumps({'status':'010','message':KEY}).encode()))
        self.assertEqual(s['error']['kind'],'CREDENTIAL_ECHO_BLOCKED');self.assertEqual(list((self.output/'raw').iterdir()),[])
        self.assertTrue(all(KEY not in p.read_text()for p in self.output.rglob('*')if p.is_file()))
    def test_escaped_key_echo_never_accepted(self):
        with self.assertRaises(m.Stop):m.reply(('{"status":"010","message":"'+'\\u005a'*40+'"}').encode(),KEY)
    def test_full_success_keeps_certification_gaps(self):
        s=self.run_case();self.assertEqual(len(s['completed_samples']),20);self.assertTrue(s['pilot_complete'])
        rows=json.loads((self.output/'assessments.json').read_text());self.assertEqual(rows[0]['receipt_date_comparison'],'PASS')
        self.assertTrue(all(r['correction_chain_verdict']=='UNVERIFIED'and not r['backtest_eligible']for r in rows))
        self.assertTrue(all(KEY not in p.read_text()for p in self.output.rglob('*')if p.is_file()))
    def test_wrong_corp_not_authenticated(self):
        def wrong(p,k):
            http,b=good(p,k);d=json.loads(b);d['list'][0]['corp_code']='99999999';return http,json.dumps(d).encode()
        s=self.run_case(transport=wrong);self.assertEqual(s['error']['kind'],'PAGE_OR_IDENTITY_VALIDATION_FAILURE');self.assertEqual(s['requests'],1)
    def test_target_missing_not_success(self):
        def wrong(p,k):
            http,b=good(p,k);d=json.loads(b);d['list'][0]['rcept_no']='20070814000000';return http,json.dumps(d).encode()
        s=self.run_case(transport=wrong);self.assertEqual(s['error']['kind'],'TARGET_RECEIPT_NOT_FOUND')
    def test_bad_page_count_stops(self):
        def wrong(p,k):
            http,b=good(p,k);d=json.loads(b);d['total_count']=2;return http,json.dumps(d).encode()
        s=self.run_case(transport=wrong);self.assertEqual(s['error']['kind'],'PAGE_OR_IDENTITY_VALIDATION_FAILURE')
    def test_existing_checkpoint_never_recollected(self):
        self.run_case()
        with self.assertRaises(m.Stop):m.acquire(targets(),KEY,self.output,transport=lambda *a:self.fail('Duplicate call'))
    def test_exception_url_not_exposed(self):
        from unittest.mock import patch
        from urllib.error import URLError
        with patch.object(m.request,'build_opener',side_effect=URLError('request-url-containing-'+KEY)):
            with self.assertRaises(m.Stop)as caught:m.fetch({},KEY)
        self.assertEqual(str(caught.exception),'TRANSPORT_FAILURE');self.assertNotIn(KEY,str(caught.exception))
    def test_two_pages_checked_before_pilot_advance(self):
        calls=[]
        def multi(p,k):
            calls.append((p['corp_code'],p['page_no']));i=int(p['corp_code']);first=(int(p['page_no'])-1)*100
            part=[{'corp_code':p['corp_code'],'rcept_no':f'20070814{i*1000+j:06d}','rcept_dt':'20070814','report_nm':'반기보고서 (2007.06)','rm':''}for j in range(first,min(first+100,101))]
            if first==0:part[0]['rcept_no']=f'20070814{i:06d}'
            return 200,json.dumps({'status':'000','page_no':int(p['page_no']),'page_count':100,'total_count':101,'total_page':2,'list':part}).encode()
        s=self.run_case(transport=multi);self.assertEqual(s['requests'],40);self.assertTrue(s['pilot_complete'])
        self.assertEqual(calls[:4],[('00000001','1'),('00000001','2'),('00000002','1'),('00000002','2')])
if __name__=='__main__':unittest.main(verbosity=2)
