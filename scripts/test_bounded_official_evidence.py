"""Offline boundary tests; all source responses synthetic, never source HTTP."""
import copy,json,os,tempfile,unittest,multiprocessing
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
from bounded_official_evidence import *

GRANT=json.loads((Path(__file__).resolve().parents[1]/'config/research/fixed_three_evidence_approval_20261028.json').read_text())
NOW=datetime(2026,10,28,1,tzinfo=KST)
def history(now=NOW):
    return dict(contract='fixed-three-shared-source-history-v1',observed_at=stamp(now),day_kst=day(now),
                active_source_runs=[],old_authorized_channels_exhausted=True,executions=[],main_sha='a'*40,
                state_sha256={str(i):'b'*64 for i in range(3)})
def response(spec,timeout):
    if spec['group']=='signal_market':return raw({'OutBlock_1':[{'BAS_DD':'20091230'}]})
    if spec['group']=='dart_inventory':
        stock=spec['security'];receipt='2011033100'+stock[-4:]
        return raw(dict(status='000',page_no=spec['params']['page_no'],total_page=1,total_count=2,
                        list=[dict(corp_code=spec['params']['corp_code'],rcept_no=x)
                              for x in [GRANT['existing_Q3_receipts'][stock],receipt]]))
    if spec['group']=='kind_inventory':return ('official '+spec.get('security','form')+' count=1 linked-row').encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w')as z:z.writestr(spec['receipt']+'.xml','<DOCUMENT>SYNTHETIC</DOCUMENT>')
    return out.getvalue()
def kill_transport(spec,timeout):os._exit(77)
def interrupted(root):
    with Collector(root,GRANT,history(),source_ready=True,transport=kill_transport,now=lambda:NOW)as c:c.get(inventory_requests(GRANT)[0])

class FiniteEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'private';self.requests=[]
    def tearDown(self):self.tmp.cleanup()
    def collect(self,**kw):
        opts=dict(source_ready=True,transport=self.transport,now=lambda:NOW);opts.update(kw)
        return Collector(self.root,GRANT,history(opts['now']()),**opts)
    def transport(self,s,t):self.requests.append(copy.deepcopy(s));return response(s,t)
    def seed_inventory(self,c):
        proofs=[];targets=[]
        for s in inventory_requests(GRANT):c.get(s)
        form=dict(group='kind_inventory',method='GET',url='https://kind.krx.co.kr/disclosure/details.do',params={'method':'searchDetailsMain'},purpose='Exact form')
        form_body=c.get(form)
        for m in GRANT['members']:
            stock=m['stock_code'];d=next(s for s in inventory_requests(GRANT)if s.get('security')==stock)
            proofs.append(dict(security=stock,kind='issuer_all_filings',request_ids=[request_id(d)],total_pages_verified=True))
            k=dict(group='kind_inventory',method='POST',url=form['url'],params=dict(method='searchDetailsSub',code=stock,start='20091101',end='20110430'),
                   purpose='Exact issuer all events',security=stock,kind_binding=dict(stock_code=stock,**{'from':'2009-11-01','through':'2011-04-30'},
                   form_sha256=sha(form_body),all_event_types=True,field_map={'stock_code':'code','from':'start','through':'end'}))
            kb=c.get(k)
            proofs.append(dict(security=stock,kind='exchange_all_events',request_ids=[request_id(k)],total_pages_verified=True,
                               parsed_pages=[dict(request_id=request_id(k),response_sha256=sha(kb),count_literal='count=1',page_no=1,total_pages=1,total_count=1,
                                                  rows=[dict(security=stock,source_literal='linked-row')])]))
            receipt='2011033100'+stock[-4:]
            targets.append(dict(group='annual',method='GET',url='https://opendart.fss.or.kr/api/document.xml',params={'rcept_no':receipt},
                                receipt=receipt,security=stock,evidence_ids=[request_id(d)],purpose='Retrospective share timeline, never signal factor'))
        return dict(complete=True,proofs=proofs),targets
    def test_grant_cannot_raise_budget_or_change_cohort(self):
        for k,v in [('max_HTTP',37),('max_executions',3),('max_retries',1),('expires_at','2026-11-05T00:00:00+09:00')]:
            g=copy.deepcopy(GRANT);g[k]=v
            with self.assertRaises(Stop):validate_grant(g)
    def test_missing_setup_does_not_consume_execution_or_HTTP(self):
        with self.collect(source_ready=False)as c:
            with self.assertRaisesRegex(Stop,'PREFLIGHT'):c.get(inventory_requests(GRANT)[0])
            self.assertEqual((len(c.state['executions']),len(c.state['requests'])),(0,0))
        self.assertEqual(self.requests,[])
    def test_missing_one_real_key_does_not_charge(self):
        with patch.dict(os.environ,{},clear=True),self.collect(transport=fetch)as c:
            with self.assertRaisesRegex(Stop,'AUTH_ENV'):c.get(inventory_requests(GRANT)[0])
            self.assertEqual(len(c.state['requests']),0)
    def test_history_day_active_and_stale_blocks(self):
        for change in [dict(active_source_runs=['123']),dict(observed_at=stamp(NOW-timedelta(seconds=121))),dict(old_authorized_channels_exhausted=False),dict(executions=[{'day_kst':day(NOW)}])]:
            h=history();h.update(change)
            with self.assertRaises(Stop):check_history(h,NOW)
    def test_auth_parameter_or_external_host_rejected(self):
        s=inventory_requests(GRANT)[0]
        for delta in [dict(url='https://example.com/x'),dict(params={'basDd':'20091230','AUTH_KEY':'do-not-log'}),dict(url=s['url']+'?x=1')]:
            with self.assertRaises(Stop):validate_request({**s,**delta},GRANT)
    def test_signal_date_or_issuer_cannot_change(self):
        s=inventory_requests(GRANT)[0]
        with self.assertRaises(Stop):validate_request({**s,'params':{'basDd':'20091229'}},GRANT)
        s=inventory_requests(GRANT)[2];s['security']='999999'
        with self.assertRaises(Stop):validate_request(s,GRANT)
    def test_normal_checkpoint_and_cache_no_redownload(self):
        s=inventory_requests(GRANT)[0]
        with self.collect()as c:
            first=c.get(s);self.assertEqual(c.get(s),first)
            self.assertEqual(len(c.state['requests']),1)
        with self.collect(source_ready=False)as c:self.assertEqual(c.get(s),first);self.assertIsNone(c.execution)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(json.loads((self.root/'budget.json').read_bytes())['executions'][0]['status'],'FINISHED')
    def test_same_day_new_request_blocked_and_prior_history_preserved(self):
        with self.collect()as c:c.get(inventory_requests(GRANT)[0])
        old=(self.root/'budget.json').read_bytes()
        with self.collect()as c:
            with self.assertRaisesRegex(Stop,'ONCE_PER_KST_DAY'):c.get(inventory_requests(GRANT)[1])
        self.assertEqual((self.root/'budget.json').read_bytes(),old)
    def test_second_day_consumes_second_lease_no_third(self):
        for i in range(2):
            with self.collect(now=lambda i=i:NOW+timedelta(days=i))as c:c.get(inventory_requests(GRANT)[i])
        with self.collect(now=lambda:NOW+timedelta(days=2))as c:
            with self.assertRaisesRegex(Stop,'EXECUTION_BUDGET'):c.get(inventory_requests(GRANT)[2])
        self.assertEqual(len(self.requests),2)
    def test_expired_never_calls_source(self):
        with self.collect(now=lambda:datetime(2026,11,5,tzinfo=KST))as c:
            with self.assertRaisesRegex(Stop,'EXPIRED'):c.get(inventory_requests(GRANT)[0])
        self.assertEqual(self.requests,[])
    def test_before_deadline_normal_checkpoint_stop(self):
        ticks=iter([0,511,512])
        with self.assertRaises(Deadline),self.collect(monotonic=lambda:next(ticks))as c:c.get(inventory_requests(GRANT)[0])
        self.assertEqual(self.requests,[])
    def test_partial_run_deadline_saves_and_next_day_reuses_completed_raw(self):
        tick=[0.]
        def transport(s,t):
            self.requests.append(s);tick[0]=520.;return response(s,t)
        first=inventory_requests(GRANT)[0];second=inventory_requests(GRANT)[1]
        with self.assertRaises(Deadline),self.collect(monotonic=lambda:tick[0],transport=transport)as c:
            original=c.get(first);c.get(second)
        state=json.loads((self.root/'budget.json').read_bytes())
        self.assertEqual(state['executions'][0]['status'],'STOPPED_TIME')
        self.assertEqual(state['status'],'PAUSED_TIME')
        with self.collect(now=lambda:NOW+timedelta(days=1))as c:
            self.assertEqual(c.get(first),original);self.assertIsNone(c.execution);c.get(second)
            self.assertEqual(len(c.state['requests']),2)
        self.assertEqual(len(self.requests),2)
    def test_failure_counted_once_and_never_retried(self):
        def fail(s,t):self.requests.append(s);raise Stop('SOURCE_HTTP_401_NO_RETRY')
        with self.assertRaises(Stop),self.collect(transport=fail)as c:c.get(inventory_requests(GRANT)[0])
        with self.assertRaisesRegex(Stop,'ACTUAL_SOURCE_FAILURE'):self.collect()
        state=json.loads((self.root/'budget.json').read_bytes())
        self.assertEqual((len(state['executions']),len(state['requests']),len(self.requests)),(1,1,1))
    def test_source_validation_failure_preserves_private_bytes(self):
        with self.assertRaises(Stop),self.collect(transport=lambda s,t:raw({'status':'020'}))as c:c.get(inventory_requests(GRANT)[2])
        s=json.loads((self.root/'budget.json').read_bytes());r=s['requests'][0]
        self.assertEqual(sha((self.root/r['body_path']).read_bytes()),r['sha256'])
        self.assertEqual(r['status'],'FAILED_NO_RETRY')
    def test_forced_exit_does_not_reset_or_retry(self):
        p=multiprocessing.get_context('fork').Process(target=interrupted,args=(self.root,));p.start();p.join(10)
        self.assertEqual(p.exitcode,77)
        before=(self.root/'budget.json').read_bytes()
        with self.assertRaisesRegex(Stop,'INTERRUPTED_LEASE'):self.collect()
        self.assertEqual((self.root/'budget.json').read_bytes(),before)
        self.assertEqual(len(json.loads(before)['requests']),1)
    def test_private_storage_rejects_git_and_broad_permissions(self):
        repo=Path(self.tmp.name)/'repo';(repo/'.git').mkdir(parents=True);(repo/'.git'/'HEAD').write_text('ref: refs/heads/main')
        with self.assertRaisesRegex(Stop,'INSIDE_GIT'):private_root(repo/'private')
        self.root.mkdir(mode=0o700);self.root.chmod(0o755)
        with self.assertRaisesRegex(Stop,'0700'):private_root(self.root)
    def test_empty_sandbox_git_guard_is_not_a_git_repository(self):
        (Path(self.tmp.name)/'.git').mkdir()
        self.assertEqual(private_root(self.root),self.root)
    def test_request_metadata_and_files_never_store_keys(self):
        with self.collect()as c:c.get(inventory_requests(GRANT)[0])
        for f in self.root.rglob('*'):
            if f.is_file():self.assertEqual(f.stat().st_mode&0o077,0)
        self.assertNotIn(b'AUTH_KEY',(self.root/'budget.json').read_bytes())
    def test_cache_hash_corruption_blocked(self):
        with self.collect()as c:
            c.get(inventory_requests(GRANT)[0]);(self.root/c.state['requests'][0]['body_path']).write_bytes(b'changed')
            with self.assertRaisesRegex(Stop,'HASH_MISMATCH'):c.get(inventory_requests(GRANT)[0])
    def test_unfrozen_original_blocked(self):
        with self.collect()as c:
            with self.assertRaisesRegex(Stop,'FROZEN'):c.get(dict(group='annual',method='GET',url='https://opendart.fss.or.kr/api/document.xml',params={'rcept_no':'20110331007160'},purpose='none'))
        self.assertEqual(self.requests,[])
    def test_closed_inventory_freezes_targets_then_fetches_once(self):
        with self.collect()as c:
            inv,targets=self.seed_inventory(c);f=c.freeze(inv,targets)
            self.assertEqual(f['target_sha256'],sha(raw(targets)))
            first=c.get(targets[0]);self.assertEqual(c.get(targets[0]),first)
            with self.assertRaisesRegex(Stop,'ALREADY_FROZEN'):c.freeze(inv,targets)
            self.assertEqual(len(c.state['requests']),10)
    def test_form_alone_cannot_certify_exchange_coverage(self):
        with self.collect()as c:
            inv,targets=self.seed_inventory(c)
            row=next(p for p in inv['proofs']if p['kind']=='exchange_all_events')
            form=next(r for r in c.state['requests']if r['group']=='kind_inventory'and r['request']['method']=='GET')
            row['request_ids']=[form['id']]
            with self.assertRaisesRegex(Stop,'REQUIRES_BOUND_QUERY'):c.freeze(inv,targets)
    def test_incomplete_or_other_issuer_inventory_blocked(self):
        with self.collect()as c:
            inv,targets=self.seed_inventory(c);inv['proofs'][0]['request_ids']=inv['proofs'][2]['request_ids']
            with self.assertRaisesRegex(Stop,'ISSUER_INVENTORY'):c.freeze(inv,targets)
    def test_unknown_original_and_existing_Q3_not_recollected(self):
        for existing in [True,False]:
            self.root=Path(self.tmp.name)/('private-'+str(existing))
            with self.collect()as c:
                inv,targets=self.seed_inventory(c);t=targets[0]
                t['receipt']=GRANT['existing_Q3_receipts'][t['security']]if existing else'20110331999999';t['params']['rcept_no']=t['receipt']
                with self.assertRaises(Stop):c.freeze(inv,targets)
    def test_frozen_targets_hash_cannot_be_silently_replaced(self):
        with self.collect()as c:
            inv,targets=self.seed_inventory(c);c.freeze(inv,targets)
            c.state['inventory_freeze']['targets'][0]['params']['rcept_no']='20110331999999'
            with self.assertRaisesRegex(Stop,'HASH_MISMATCH'):c.get(targets[0])
    def test_group_phase_total_http_limit_before_transport(self):
        for limit in ['group','phase','total']:
            self.root=Path(self.tmp.name)/limit
            with self.collect()as c:
                if limit=='group':rows=[dict(group='signal_market',phase='inventory')]*2
                elif limit=='phase':rows=[dict(group='kind_inventory',phase='inventory')]*15
                else:rows=[dict(group='event',phase='conditional')]*36
                c.state['requests']=[dict(x,id=str(i))for i,x in enumerate(rows)]
                with self.assertRaisesRegex(Stop,'HTTP_EXHAUSTED'):c.get(inventory_requests(GRANT)[0])
                self.assertIsNone(c.execution)
        self.assertEqual(self.requests,[])
    def test_lock_prevents_parallel_processes(self):
        with self.collect():
            with self.assertRaisesRegex(Stop,'ALREADY_ACTIVE'):self.collect()

if __name__=='__main__':unittest.main()
