"""Synthetic GitHub journal/control tests; no remote mutation or source HTTP."""
import base64,copy,json,tempfile,time,unittest
import os
from unittest.mock import patch
from pathlib import Path
from bounded_official_evidence import Stop,raw,sha,atomic
from bounded_official_github import API,PrivateJournal,Missing,PRIVATE,PUBLIC,PREFIX,BRANCH,shared_history,OLD_STATES,content
from test_bounded_official_evidence import NOW,GRANT,history

class FakeAPI:
    def __init__(self):self.files={};self.calls=[];self.private=True;self.seq=0
    def __call__(self,method,path,body=None):
        self.calls.append((method,path,copy.deepcopy(body)))
        if path=='/repos/'+PRIVATE:return dict(full_name=PRIVATE,private=self.private,permissions={'push':True},default_branch='main')
        if '/git/ref/'in path:return {'object':{'sha':'base'}}
        prefix='/repos/'+PRIVATE+'/contents/'
        if path.startswith(prefix):
            name=path[len(prefix):].split('?')[0]
            if method=='GET':
                if name not in self.files:raise Missing('not found')
                data,h=self.files[name];return dict(type='file',encoding='base64',content=base64.b64encode(data).decode(),sha=h)
            if method=='PUT':
                old=self.files.get(name)
                if old and body.get('sha')!=old[1]:raise Stop('CONTROL_HTTP_409_NO_RETRY')
                self.seq+=1;data=base64.b64decode(body['content']);h='blob-'+str(self.seq)
                self.files[name]=(data,h);return {'content':{'sha':h}}
        raise AssertionError((method,path))

class PrivateJournalTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'private';self.api=FakeAPI()
    def tearDown(self):self.tmp.cleanup()
    def test_public_destination_rejected_before_write(self):
        self.api.private=False
        with self.assertRaisesRegex(Stop,'PRIVATE_REPOSITORY'):PrivateJournal(self.api,self.root)
        self.assertFalse(any(m!='GET'for m,_,_ in self.api.calls))
    def test_raw_private_write_readback_and_idempotent_reuse(self):
        j=PrivateJournal(self.api,self.root);data=b'SYNTHETIC official body';path='raw/'+sha(data)+'.bin'
        j.preserve(path,data,999999);j.preserve(path,data,999999)
        puts=[c for c in self.api.calls if c[0]=='PUT']
        self.assertEqual(len(puts),1);self.assertIn('/repos/'+PRIVATE+'/',puts[0][1])
        self.assertEqual(puts[0][2]['branch'],BRANCH)
    def test_ledger_update_compare_and_swap_no_force(self):
        j=PrivateJournal(self.api,self.root);state={'executions':[],'requests':[]}
        j.mirror(state,999999);state['executions']=[{'id':'one'}];j.mirror(state,999999)
        puts=[c for c in self.api.calls if c[0]=='PUT'];self.assertNotIn('sha',puts[0][2]);self.assertEqual(puts[1][2]['sha'],'blob-1')
        self.api.files[PREFIX+'budget.json']=(b'changed by another actor','other-sha')
        with self.assertRaisesRegex(Stop,'409'):j.mirror(state,999999)
    def test_restore_private_raw_from_remote_without_source_call(self):
        j=PrivateJournal(self.api,self.root);data=b'SYNTHETIC preserved raw';path='raw/'+sha(data)+'.bin'
        j.preserve(path,data,999999);j.mirror(dict(requests=[dict(body_path=path,sha256=sha(data))],executions=[]),999999)
        restored=Path(self.tmp.name)/'restored';PrivateJournal(self.api,restored)
        self.assertEqual((restored/path).read_bytes(),data)
        self.assertTrue((restored/'budget.json').exists())
    def test_local_remote_ledger_conflict_not_overwritten(self):
        j=PrivateJournal(self.api,self.root);j.mirror(dict(requests=[],executions=[]),999999)
        atomic(self.root/'budget.json',dict(altered=True));before=(self.root/'budget.json').read_bytes()
        with self.assertRaisesRegex(Stop,'DISAGREEMENT'):PrivateJournal(self.api,self.root)
        self.assertEqual((self.root/'budget.json').read_bytes(),before)
    def test_missing_remote_counterpart_never_resets_local_usage(self):
        self.root.mkdir(mode=0o700);atomic(self.root/'budget.json',dict(executions=[1]))
        with self.assertRaisesRegex(Stop,'NO_RESET'):PrivateJournal(self.api,self.root)
    def test_transport_rejects_public_writes_before_network(self):
        api=API('SYNTHETIC',time.monotonic()+10)
        with self.assertRaisesRegex(Stop,'PUBLIC_REPOSITORY_WRITE'):api('PUT','/repos/'+PUBLIC+'/contents/raw.json',{})
    def test_missing_private_secret_reports_only_name_before_any_network_or_lease(self):
        from bounded_official_github import main
        env=dict(GITHUB_REPOSITORY=PUBLIC,GITHUB_REF='refs/heads/main',GITHUB_RUN_ATTEMPT='1',
                 GITHUB_TOKEN='SYNTHETIC_control',DART_API_KEY='SYNTHETIC_dart',KRX_AUTH_KEY='SYNTHETIC_krx')
        with patch.dict(os.environ,env,clear=True),patch('sys.argv',['collector','--private-root',str(self.root),'--grant','unused.json']),patch('bounded_official_github.API')as network:
            with self.assertRaisesRegex(Stop,'^REQUIRED_ACTIONS_SECRET_NOT_INJECTED_NO_LEASE:B_PRIVATE_BACKUP_TOKEN$'):main()
            network.assert_not_called()
    def test_large_private_content_reads_exact_blob_without_source_or_signed_URL(self):
        calls=[];payload=b'SYNTHETIC large private content'
        def api(method,path,body=None):
            calls.append(path)
            if '/contents/'in path:return dict(type='file',encoding='none',sha='bound-blob')
            return dict(encoding='base64',sha='bound-blob',content=base64.b64encode(payload).decode())
        b,h=content(api,PRIVATE,'example.gz',BRANCH)
        self.assertEqual((b,h),(payload,'bound-blob'));self.assertEqual(calls[-1],'/repos/'+PRIVATE+'/git/blobs/bound-blob')
    def test_shared_snapshot_preserves_resumed_day_and_blocks_current_day(self):
        guards=dict(backtest_eligible=False,investment_PIT='0/6',financial_publication='HOLD')
        old=dict(**guards,contract='limited-source-observation-v1',automatic_financial_publication='HOLD',phase='OBSERVATION_COMPLETE',runs=[{'day_kst':'2026-10-21','resume_segments':[{'day_kst':NOW.date().isoformat()}]}])
        states=[old,dict(**guards,contract='supplemental-finite-source-v1',phase='COMPLETE',remaining_receipts=[],attempts=[{'status':'COMPLETE'},{'status':'COMPLETE'}]),
                dict(**guards,contract='q3-fixed-source-v1',phase='RAW_COMPLETE_PENDING_WORKSPACE_REVIEW',remaining_receipts=[],executions_remaining=0)]
        def api(method,path,body=None):
            if path.endswith('/commits/main'):return {'sha':'a'*40}
            if '/actions/runs?'in path:return dict(total_count=0,workflow_runs=[])
            for name,obj in zip(OLD_STATES,states):
                if '/contents/'+name+'?'in path:return dict(type='file',encoding='base64',content=base64.b64encode(raw(obj)).decode(),sha='blob')
            raise AssertionError(path)
        with self.assertRaisesRegex(Stop,'ONCE_PER_KST_DAY'):shared_history(api,NOW,'self')

if __name__=='__main__':unittest.main()
