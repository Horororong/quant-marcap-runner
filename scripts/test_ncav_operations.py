"""Local boundary tests only: neither external credentials nor source requests."""
import base64, copy, gzip, json, os, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from ncav_actions_bridge import Journal, validate_envelope
from ncav_collection_queue import run, fingerprint, key
from ncav_official_requests import validate, classify

def task(page='1'):
    return dict(endpoint='official',corp_code='00123456',request=dict(method='GET',url='https://opendart.fss.or.kr/api/list.json',
        params=dict(corp_code='00123456',bgn_de='20100502',end_de='20110430',last_reprt_at='N',page_count='100',page_no=page)))
def plan():
    return dict(grant_id='ncav-fixture',tasks=[task()],max_http=4,max_http_per_run=2,max_runs=2,retries=0,
        seconds_per_execution=600,financial_publication='HOLD',classification='RESEARCH_ONLY',
        cohort_corps=['00123456'],signal_date='2010-04-30',inventory_start='20090101',inventory_end='20110430',
        valid_from='2026-11-13T00:00:00+09:00',valid_until='2026-11-19T23:59:59+09:00',max_reviewed_followups=1)
def response(page=1,pages=1,count=1):
    return json.dumps(dict(status='000',page_no=page,total_page=pages,total_count=count,
        list=[dict(corp_code='00123456',rcept_no='20110331000001',rcept_dt='20110331')])).encode()

class Missing(Exception):pass
class FakeStore:
    def __init__(self,p):
        self.module=SimpleNamespace(PRIVATE='fixture/private',PUBLIC='fixture/public',PREFIX='test/',BRANCH='fixture',Missing=Missing)
        self.module.content=lambda api,repo,path,ref: self.read(path)
        self.files={'test/budget.json':json.dumps(dict(executions=[],requests=[{'preserve':'B history'}],
            additional_finite_grants={'fy-fixture':{'executions':[],'requests':[{'old':1}]}},
            prepared_ncav_plans={fingerprint(p):dict(approved=True,plan=p)})).encode()}
        self.versions={k:'1'for k in self.files};self.fail_cas=False;self.writes=0
    def read(self,path):
        if path not in self.files:raise Missing()
        return self.files[path],self.versions[path]
    def __call__(self,method,path,body=None):
        if method=='GET' and path=='/repos/fixture/private':return dict(full_name='fixture/private',private=True,permissions={'push':True})
        if method=='GET' and '/actions/runs/'in path:return {'status':'completed'}
        if method!='PUT':raise AssertionError('Unexpected network-like operation')
        name=path.split('/contents/')[1]
        if name in self.files:
            if body.get('sha')!=self.versions[name] or self.fail_cas:raise RuntimeError('CAS_CONFLICT')
        elif 'sha'in body:raise AssertionError('Invalid creation')
        self.writes += 1
        self.files[name] = base64.b64decode(body['content'])
        self.versions[name] = format(self.writes + 1, '040x')
        return {'content': {'sha': self.versions[name]}, 'commit': {'sha': format(self.writes, '040x')}}

class Operations(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.p=plan();self.store=FakeStore(self.p)
    def journal(self,sub='one'):
        return Journal(self.store,self.store.module,self.root/sub,fingerprint(self.p))
    def execute(self,j,transport,**kw):
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'123'}):
            return run(self.p,j.root,approved=True,transport=transport,acquire_shared_day=lambda *a:None,
                now=datetime(2026,11,13,tzinfo=timezone.utc),max_http=2,mirror=j.mirror,preserve=j.preserve,**kw)
    def test_remote_charge_before_source_and_preserve_other_grants(self):
        before=json.loads(self.store.files['test/budget.json']);j=self.journal()
        def source(t):
            x=json.loads(self.store.files['test/budget.json'])['additional_finite_grants']['ncav-fixture']['queue_state']
            self.assertEqual(x['used_http'],1);self.assertEqual(x['tasks'][key(t)]['status'],'SENDING')
            return classify(t,response())
        out=self.execute(j,source);self.assertEqual(out['http'],1)
        after=json.loads(self.store.files['test/budget.json'])
        self.assertEqual(before['requests'],after['requests']);self.assertEqual(before['additional_finite_grants']['fy-fixture'],after['additional_finite_grants']['fy-fixture'])
        fresh=self.journal('fresh');self.assertEqual(self.execute(fresh,lambda t:self.fail('duplicate source'))['http'],0)
    def test_cas_failure_stops_before_source(self):
        j=self.journal();self.store.fail_cas=True
        with self.assertRaisesRegex(RuntimeError,'CAS'):self.execute(j,lambda t:self.fail('source before durable charge'))
    def test_interrupted_runner_no_reissue(self):
        j=self.journal()
        def die(t):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.execute(j,die)
        fresh=self.journal('fresh');fresh.reconcile_completed_runner(self.store)
        self.assertEqual(self.execute(fresh,lambda t:self.fail('uncertain request repeated'))['http'],0)
        s=json.loads((fresh.root/'ledger.json').read_text());self.assertEqual(s['used_http'],1);self.assertEqual(s['tasks'][key(task())]['status'],'UNKNOWN')
    def test_unapproved_envelope_and_cross_budget_block(self):
        with self.assertRaises(PermissionError):validate_envelope({'approved':False,'plan':self.p},fingerprint(self.p))
        self.p['grant_id']='fy20-existing'
        with self.assertRaises(ValueError):validate_envelope({'approved':True,'plan':self.p},fingerprint(self.p))
    def test_scope_keys_period_and_hosts(self):
        validate(task(),self.p)
        bad=task();bad['request']['params']['crtfc_key']='fixture'
        with self.assertRaises(ValueError):validate(bad,self.p)
        bad=task();bad['request']['url']='https://example.com/api/list.json'
        with self.assertRaises(ValueError):validate(bad,self.p)
    def test_pagination_and_empty_are_not_certification(self):
        one=classify(task(),response());self.assertFalse(one['metadata']['complete_evidence'])
        self.assertEqual(classify(task(),b'{"status":"013"}')['status'],'NO_DATA')
        with self.assertRaises(ValueError):classify(task(),b'{"status":"000","list":[]}')
        with self.assertRaises(ValueError):classify(task('2'),response())
    def test_page_two_skipped_if_only_one_page(self):
        second=task('2');second['page_parent']=key(task());self.p['tasks'].append(second);self.store=FakeStore(self.p)
        j=self.journal();seen=[]
        def source(t):seen.append(t);return classify(t,response())
        self.execute(j,source);self.assertEqual(len(seen),1)
    def test_old_resolved_followup_cannot_change(self):
        self.p['tasks']=[dict(endpoint='fnlttSinglAcntAll.json',corp_code='00123456',bsns_year='2026',reprt_code='11012',fs_div='CFS')]
        self.store=FakeStore(self.p);j=self.journal();j.followups=[task()]
        self.execute(j,lambda t:dict(status='STORED',body=b'fixture'),reviewed_tasks=[task()])
        fresh=self.journal('fresh')
        with self.assertRaisesRegex(ValueError,'disappeared'):self.execute(fresh,lambda t:self.fail('unexpected source'))
    def test_existing_other_grant_request_cannot_be_recollected(self):
        j=self.journal();j.outer['requests'].append({'request':task()['request'],'status':'COMPLETE'})
        with self.assertRaisesRegex(ValueError,'PRIOR_SOURCE'):j.verify_requests()
        self.assertEqual(self.store.writes,0)
    def test_invalid_per_run_caps(self):
        self.p['per_run_http_caps']=[2,9]
        with self.assertRaisesRegex(ValueError,'PER_RUN'):validate_envelope({'approved':True,'plan':self.p},fingerprint(self.p))
    def test_viewer_unbound_document_and_empty_market_blocked(self):
        d=task();d['request']={'method':'GET','url':'https://opendart.fss.or.kr/api/document.xml','params':{'rcept_no':'20110331000001'}}
        with self.assertRaisesRegex(ValueError,'BOUND'):validate(d,self.p)
        m={'endpoint':'official','role':'signal_market','request':{'method':'GET','url':'https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd','params':{'basDd':'20100430'}}}
        validate(m,self.p)
        with self.assertRaisesRegex(ValueError,'EMPTY'):classify(m,b'{"OutBlock_1":[]}')
    def test_deadline_checkpoint_retains_unrequested_without_reset(self):
        self.p['tasks'].append({**task(),'request':{**task()['request'],'params':{**task()['request']['params'],'bgn_de':'20100503'}}})
        self.store=FakeStore(self.p);j=self.journal();ticks=iter([0,0,571])
        out=self.execute(j,lambda t:classify(t,response()),clock=lambda:next(ticks))
        self.assertEqual(out['status'],'CHECKPOINT_TIME');self.assertEqual(out['http'],1)
        self.assertEqual(out['remaining_unrequested'],1)
    def test_nonheld_followup_cannot_skip_selection_review(self):
        self.p['followup_roles']=['held_annual'];self.store=FakeStore(self.p);j=self.journal()
        t=task();t['role']='held_annual';t['source_binding']={'kind':'dart_list','sha256':'0'*64};j.followups=[t]
        with self.assertRaisesRegex(ValueError,'HOLDING_REVIEW_REQUIRED'):j.verify_requests()
    def test_exact_viewer_node_binding(self):
        from ncav_actions_bridge import digest
        body=b'''var node1 = {}; node1['rcpNo'] = "20100331000001"; node1['dcmNo'] = "123"; node1['eleId'] = "25"; node1['offset'] = "100"; node1['length'] = "200"; node1['dtd'] = "dart3.xsd";'''
        h=digest(body);t=task();t['source_binding']={'kind':'viewer_node','sha256':h}
        t['request']={'method':'GET','url':'https://dart.fss.or.kr/report/viewer.do','params':dict(rcpNo='20100331000001',dcmNo='123',eleId='25',offset='100',length='200',dtd='dart3.xsd')}
        self.p['tasks']=[t];self.store=FakeStore(self.p);name='test/raw/'+h+'.bin.gz';self.store.files[name]=gzip.compress(body);self.store.versions[name]='1'
        j=self.journal();j.verify_requests();j.plan['tasks'][0]['request']['params']['offset']='101'
        with self.assertRaisesRegex(ValueError,'NODE_NOT_IN'):j.verify_requests()

if __name__=='__main__':unittest.main()
