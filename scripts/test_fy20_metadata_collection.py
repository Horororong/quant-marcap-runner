"""Synthetic boundary tests only: zero live API calls or credential use."""
import copy,json,tempfile,time,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from bounded_official_evidence import Stop,Deadline,raw,sha,atomic,request_id
from bounded_official_github import PUBLIC,PRIVATE,PREFIX,BRANCH
from fy20_metadata_collection import (
    APPROVAL,FYCollector,list_spec,metadata_spec,correction_spec,review_inventory,
    collect_metadata,validate_grant,PAIRS)
from fy20_metadata_github import FYJournal,complete_shared_history

ROOT=Path(__file__).resolve().parents[1]
GRANT=json.loads((ROOT/'config/research/fy20_metadata_approval_20261030.json').read_bytes())
NOW=datetime(2026,10,30,1,tzinfo=timezone.utc)
def history(now=NOW):
    return dict(contract='fixed-three-shared-source-history-v1',observed_at=now.isoformat(),
        day_kst=now.astimezone(timezone(timedelta(hours=9))).date().isoformat(),main_sha='SYNTHETIC_MAIN',
        state_sha256={str(i):'synthetic'for i in range(3)},executions=[],active_source_runs=[],old_authorized_channels_exhausted=True)
def listing(m,**extra):
    return raw(dict(status='000',page_no=1,total_page=1,total_count=1,
        list=[dict(corp_code=m['corp'],rcept_no=m['receipt'],rcept_dt='20100331',report_nm='사업보고서 (2009.12)')],**extra))

class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'private';self.calls=[];self.states=[]
    def tearDown(self):self.tmp.cleanup()
    def transport(self,spec,timeout):
        state=json.loads((self.root/'budget.json').read_bytes())
        self.assertEqual(state['requests'][-1]['status'],'ATTEMPT_STARTED')
        self.assertTrue(state['requests'][-1]['transport_started'])
        self.calls.append(spec)
        if spec['group']=='metadata':return ('<html><script>'+spec['params']['rcpNo']+'</script></html>').encode()
        m=next(m for m in GRANT['targets']if m['corp']==spec['params']['corp_code'])
        return listing(m)
    def collector(self,**kw):
        return FYCollector(self.root,GRANT,history(),transport=self.transport,now=lambda:NOW,source_ready=True,
            mirror=lambda state,deadline:self.states.append(copy.deepcopy(state)),**kw)
    def test_immutable_grant_and_full_cohort(self):
        validate_grant(GRANT)
        for changed in [dict(GRANT,max_HTTP=71),dict(GRANT,targets=GRANT['targets'][:-1]),dict(GRANT,max_retries=1)]:
            with self.assertRaises(Stop):validate_grant(changed)
    def test_nonapproved_target_period_and_original_zip_rejected_no_lease(self):
        with self.collector()as c:
            specs=[dict(list_spec(GRANT['targets'][0]),params=dict(list_spec(GRANT['targets'][0])['params'],end_de='20100501')),
                correction_spec(PAIRS[0][0],PAIRS[0][1]),metadata_spec({'receipt':'20100331009999'})]
            for spec in specs:
                with self.assertRaises(Stop):c.get(spec)
            self.assertEqual(c.remaining()['executions'],2)
        self.assertEqual(self.calls,[])
    def test_two_finite_runs_resume_cache_and_no_duplicate_requests(self):
        with self.assertRaisesRegex(Deadline,'RUN_HTTP_CAP'):
            with self.collector()as c:collect_metadata(c)
        first=c.state;self.assertEqual(len(first['requests']),35);self.assertEqual(len(first['executions']),1)
        self.assertEqual(first['executions'][0]['status'],'STOPPED_TIME')
        tomorrow=NOW+timedelta(days=1)
        with FYCollector(self.root,GRANT,history(tomorrow),transport=self.transport,now=lambda:tomorrow,source_ready=True)as c:
            out=collect_metadata(c)
        self.assertEqual(len(self.calls),40);self.assertEqual(len({request_id(s)for s in self.calls}),40)
        self.assertEqual(c.remaining()['executions'],0);self.assertEqual(c.remaining()['HTTP'],30)
        self.assertEqual(out['new_provider_values'],0)
        with FYCollector(self.root,GRANT,history(tomorrow),transport=self.transport,now=lambda:tomorrow,source_ready=True)as c:
            collect_metadata(c)
        self.assertEqual(len(self.calls),40) # zero pending work does not consume a third lease
    def test_same_day_and_expiry_do_not_charge_http_or_lease(self):
        h=history();h['executions']=[dict(day_kst=h['day_kst'],run_id='old')]
        with FYCollector(self.root,GRANT,h,transport=self.transport,now=lambda:NOW,source_ready=True)as c:
            with self.assertRaisesRegex(Stop,'ONCE_PER_KST_DAY'):c.get(list_spec(GRANT['targets'][0]))
        self.assertEqual(c.remaining()['executions'],2);self.assertEqual(c.remaining()['HTTP'],70)
        with FYCollector(self.root,GRANT,history(),transport=self.transport,
                now=lambda:datetime(2026,11,5,tzinfo=timezone.utc),source_ready=True)as c:
            with self.assertRaisesRegex(Stop,'EXPIRED'):c.get(list_spec(GRANT['targets'][0]))
        self.assertEqual(self.calls,[])
    def test_source_failure_is_charged_once_and_never_retried(self):
        def fail(spec,timeout):self.calls.append(spec);raise Stop('SOURCE_HTTP_401_NO_RETRY')
        with self.assertRaisesRegex(Stop,'401'):
            with FYCollector(self.root,GRANT,history(),transport=fail,now=lambda:NOW,source_ready=True)as c:
                c.get(list_spec(GRANT['targets'][0]))
        self.assertEqual(c.state['status'],'HOLD_FAILURE');self.assertEqual(c.remaining()['HTTP'],69)
        with self.assertRaisesRegex(Stop,'ACTUAL_SOURCE_FAILURE_HELD'):self.collector()
        self.assertEqual(len(self.calls),1)
    def test_interrupted_running_lease_not_reused_or_reset(self):
        c=self.collector();c.start();c.close()
        with self.assertRaisesRegex(Stop,'INTERRUPTED_LEASE_HELD'):self.collector()
        self.assertEqual(len(json.loads((self.root/'budget.json').read_bytes())['executions']),1)
    def test_deadline_before_http_preserves_budget(self):
        with self.collector()as c:
            c.deadline=c.monotonic()+89
            with self.assertRaises(Deadline):c.get(list_spec(GRANT['targets'][0]))
        self.assertEqual(c.remaining()['HTTP'],70)
    def test_page_limit_empty_and_missing_original_remain_held(self):
        m=GRANT['targets'][0];s=list_spec(m)
        self.assertFalse(review_inventory(m,[(s,raw(dict(status='013',list=[])))])['complete'])
        o=json.loads(listing(m));o.update(total_count=201,total_page=3)
        self.assertEqual(review_inventory(m,[(s,raw(o))])['status'],'PAGE_CAP_EXCEEDED')
        o=json.loads(listing(m));o['list'][0]['rcept_no']='20100331009999'
        self.assertEqual(review_inventory(m,[(s,raw(o))])['status'],'KNOWN_ORIGINAL_ABSENT')
    def test_duplicate_pagination_never_closes_chain(self):
        m=GRANT['targets'][0];o=json.loads(listing(m));o.update(total_count=2)
        o['list']*=2
        with self.assertRaisesRegex(Stop,'COUNT_MISMATCH'):review_inventory(m,[(list_spec(m),raw(o))])
    def test_correction_requires_bound_menu_complete_inventory_and_material_review(self):
        m=GRANT['targets'][0];corrected='20100401000001'
        o=json.loads(listing(m));o['list'].append(dict(corp_code=m['corp'],rcept_no=corrected,rcept_dt='20100401',report_nm='[기재정정]사업보고서 (2009.12)'));o['total_count']=2
        with self.collector()as c:
            c.state['inventory'][m['corp']]=review_inventory(m,[(list_spec(m),raw(o))])
            c.get(metadata_spec(m));meta=c.state['requests'][0]
            target=dict(corp=m['corp'],receipt=corrected,inventory_sha256=sha(raw(c.state['inventory'][m['corp']])),
                original_menu_sha256=meta['sha256'],material_fields=['ocf'],relation_review='SYNTHETIC explicit linked version')
            with self.assertRaisesRegex(Stop,'INVENTORY'):c.freeze_corrections([dict(target,inventory_sha256='changed')])
            with self.assertRaisesRegex(Stop,'MATERIAL'):c.freeze_corrections([dict(target,receipt=m['receipt'])])
            c.freeze_corrections([target]);c.validate_spec(correction_spec(m['corp'],corrected))
            with self.assertRaisesRegex(Stop,'IMMUTABLE'):c.freeze_corrections([])

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'private';self.api=FakeAPI()
        self.old=dict(contract='existing-B',executions=[dict(id='old',day_kst='2026-10-29')],requests=[dict(status='FAILED_NO_RETRY')],status='HOLD_FAILURE')
        self.api.files[PREFIX+'budget.json']=(raw(self.old),'old-blob')
    def tearDown(self):self.tmp.cleanup()
    def test_separate_grant_cas_preserves_old_failures_and_counts(self):
        j=FYJournal(self.api,self.root);state=dict(executions=[],requests=[],status='READY')
        j.mirror(state,time.monotonic()+5)
        remote=json.loads(self.api.files[PREFIX+'budget.json'][0]);sub=remote.pop('additional_finite_grants')
        self.assertEqual(remote,self.old);self.assertEqual(sub[APPROVAL],state)
        self.api.files[PREFIX+'budget.json']=(b'changed','new-blob')
        with self.assertRaises(Stop)as held:j.mirror(state,time.monotonic()+5)
        self.assertEqual(held.exception.control_diagnostic['http_status'],409)
        self.assertEqual(held.exception.control_diagnostic['stage'],'JOURNAL_CAS_WRITE')
    def test_unchanged_private_raw_reuse_and_readback_no_public_write(self):
        j=FYJournal(self.api,self.root);body=b'SYNTHETIC PRIVATE';name='raw/'+sha(body)+'.bin'
        j.preserve(name,body,time.monotonic()+5);j.preserve(name,body,time.monotonic()+5)
        puts=[c for c in self.api.calls if c[0]=='PUT'];self.assertEqual(len(puts),1)
        self.assertTrue(all('/repos/'+PRIVATE+'/'in c[1]for c in puts))
    def test_public_destination_and_missing_remote_history_rejected(self):
        self.api.private=False
        with self.assertRaisesRegex(Stop,'DESTINATION'):FYJournal(self.api,self.root)
        self.assertFalse(any(c[0]=='PUT'for c in self.api.calls))
        self.api.private=True;self.root.mkdir(mode=0o700,exist_ok=True);atomic(self.root/'budget.json',{})
        with self.assertRaisesRegex(Stop,'NO_RESET'):FYJournal(self.api,self.root)
    def test_old_B_day_and_other_new_grant_day_block_new_fy(self):
        j=FYJournal(self.api,self.root)
        for extra in (False,True):
            j.outer['executions']=[]if extra else[dict(id='old',day_kst='2026-10-30')]
            j.outer['additional_finite_grants']={'other':dict(executions=[dict(id='other',day_kst='2026-10-30',status='FINISHED')])}if extra else{}
            def public(method,path):return dict(total_count=0,workflow_runs=[])
            with patch('fy20_metadata_github.shared_history',return_value=history()):
                with self.assertRaisesRegex(Stop,'ONCE_PER_KST_DAY'):complete_shared_history(public,self.api,NOW,'self',j)
    def test_shared_running_lease_never_assumed_available(self):
        j=FYJournal(self.api,self.root);j.outer['additional_finite_grants']={APPROVAL:dict(executions=[dict(status='RUNNING',day_kst='2026-10-29')])}
        with patch('fy20_metadata_github.shared_history',return_value=history()):
            with self.assertRaisesRegex(Stop,'RUNNING_LEASE'):complete_shared_history(None,self.api,NOW,'self',j)
    def test_raw_create_and_readback_errors_have_distinct_safe_stages(self):
        for failing_stage in ['RAW_CREATE','RAW_READBACK']:
            j=FYJournal(self.api,self.root);original=self.api;created=[]
            def failing(method,path,body=None):
                from bounded_official_github import Missing
                if method=='PUT'and path.endswith('.bin.gz'):
                    if failing_stage=='RAW_CREATE':raise Stop('CONTROL_HTTP_403_NO_RETRY')
                    created.append(path)
                if method=='GET'and created and path.split('?')[0]in created:raise Missing('synthetic no readback')
                return original(method,path,body)
            j.api=failing;body=('SYNTHETIC '+failing_stage).encode()
            with self.assertRaises(Stop)as held:j.preserve('raw/'+sha(body)+'.bin',body,time.monotonic()+5)
            self.assertEqual(held.exception.control_diagnostic['stage'],failing_stage)
            self.assertNotIn(PREFIX,str(held.exception))
    def test_remote_failure_preserves_local_response_and_stops_without_retry(self):
        j=FYJournal(self.api,self.root)
        def fail(location,body,deadline):raise Stop('SYNTHETIC_READBACK_FAIL')
        with self.assertRaisesRegex(Stop,'READBACK_FAIL'):
            with FYCollector(self.root,GRANT,history(),now=lambda:NOW,source_ready=True,
                    transport=lambda spec,t:listing(GRANT['targets'][0]),mirror=j.mirror,preserve=fail)as c:
                c.get(list_spec(GRANT['targets'][0]))
        row=c.state['requests'][0]
        self.assertTrue((self.root/row['body_path']).is_file());self.assertEqual(row['status'],'FAILED_NO_RETRY')
        self.assertEqual(c.remaining()['HTTP'],69);self.assertEqual(c.remaining()['executions'],1)

class FakeAPI:
    """In-memory control store with CAS; no access to real network or tokens."""
    def __init__(self):self.files={};self.calls=[];self.private=True;self.seq=0
    def __call__(self,method,path,body=None):
        from bounded_official_github import Missing
        import base64
        self.calls.append((method,path,copy.deepcopy(body)))
        if path=='/repos/'+PRIVATE:return dict(full_name=PRIVATE,private=self.private,permissions={'push':True})
        prefix='/repos/'+PRIVATE+'/contents/'
        if not path.startswith(prefix):raise AssertionError('Unexpected synthetic control scope')
        name=path[len(prefix):].split('?')[0]
        if method=='GET':
            if name not in self.files:raise Missing('synthetic missing')
            data,blob=self.files[name]
            return dict(type='file',encoding='base64',content=base64.b64encode(data).decode(),sha=blob)
        if method!='PUT':raise AssertionError('Unexpected synthetic mutation')
        old=self.files.get(name)
        if old and body.get('sha')!=old[1]:raise Stop('CONTROL_HTTP_409_NO_RETRY')
        self.seq+=1;blob='synthetic-'+str(self.seq)
        self.files[name]=(base64.b64decode(body['content']),blob)
        return dict(content=dict(sha=blob))

if __name__=='__main__':unittest.main()
