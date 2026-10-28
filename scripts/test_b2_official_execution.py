"""B2 synthetic operational boundaries. No source HTTP and no financial certification."""
import copy,io,json,tempfile,unittest,zipfile
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
from b2_official_execution import *
from bounded_official_evidence import KST,fetch
from test_bounded_official_evidence import history
R=Path(__file__).resolve().parents[1]
G=json.loads((R/'config/research/fixed_three_evidence_approval_20261028.json').read_bytes())
A=json.loads((R/'config/research/b2_evidence_amendment_20261028.json').read_bytes())
# Synthetic protocol-only form. Production uses the pinned PRIVATE real form.
_FORM_NAMES='method forward currentPageSize pageIndex fromDate toDate searchCodeType repIsuSrtCd searchCorpName oldSearchCorpName reportNm reportNmTemp marketType orderMode orderStat'.split()
FORM=('<form id="searchForm" method="post">'+''.join('<input name="'+n+'">'for n in _FORM_NAMES)+'</form>searchDetailsSub details_sub /disclosure/details.do "A"+repIsuSrtCd 조회기간은 3년 이내만 가능합니다. SYNTHETIC ONLY').encode()
A={**A,'form_sha256':sha(FORM)}
NOW=datetime(2026,10,29,1,tzinfo=KST)

def seed(root):
    root.mkdir(mode=0o700);body=raw({'OutBlock_1':[]});location='raw/'+sha(body)+'.bin';atomic(root/location,body,binary=True)
    spec=inventory_requests(G)[0]
    state=dict(contract=G['contract'],approval_id=G['approval_id'],approval_sha256=sha(raw(G)),status='HOLD_FAILURE',inventory_freeze=None,
        executions=[dict(id='SYNTHETIC_OLD',day_kst='2026-10-28',status='HOLD_FAILURE')],requests=[dict(id=request_id(spec),execution_id='SYNTHETIC_OLD',group='signal_market',phase='inventory',status='FAILED_NO_RETRY',request=spec,body_path=location,sha256=sha(body),private_remote_preserved=True)])
    atomic(root/'budget.json',state);return copy.deepcopy(state)

def response(s,timeout):
    if s['group']=='execution_market':
        stocks=['049720']if '/ksq_'in s['url']else['000500','007160']
        return raw({'OutBlock_1':[dict(BAS_DD='20100503',ISU_CD=x,TDD_CLSPRC='100')for x in stocks]})
    stock=s.get('security','000500')
    if s['group']=='dart_inventory':
        receipts=[(G['existing_Q3_receipts'][stock],'분기보고서 (2009.09)'),('2011033100'+stock[-4:],'사업보고서 (2010.12)')]
        return raw(dict(status='000',page_no=1,total_page=1,page_count=100,total_count=2,list=[dict(corp_code=MEMBERS[stock][0],rcept_no=r,rcept_dt=r[:8],report_nm=t)for r,t in receipts]))
    if s['group']=='kind_inventory':
        receipt='2010060100'+stock[-4:];name=MEMBERS[stock][1]
        return (f'''전체 <em>1</em>건 : <strong>1</strong>/1<tr><td>2010-06-01 10:00</td><td><a id="companysum" onclick="companysummary_open('{stock[:5]}')">{name}</a></td><td onclick="openDisclsViewer('{receipt}','')">추가상장 SYNTHETIC</td></tr>''').encode()
    if s['group']=='calendar':return b'<html>SYNTHETIC Saturdays and Sundays closed; not real evidence</html>'
    if 'opendart' in s['url']:
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w')as z:z.writestr(s['receipt']+'.xml','<SYNTHETIC/>')
        return out.getvalue()
    if s['params'].get('method')=='searchInitInfo':return f'''<select id="mainDoc"><option value='{s['receipt']}|Y'>SYNTHETIC</option></select>'''.encode()
    if s['params'].get('method')=='searchContents':return f"parent.setPath('','https://kind.krx.co.kr/external/2010/06/01/000001/{s['params']['docNo']}/1.htm')".encode()
    return b'<html>SYNTHETIC ACTION BODY; independently unreviewed</html>'

class B2Operations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'private';self.old=seed(self.root);self.calls=[]
    def collector(self,**kw):
        opts=dict(amendment=A,form_body=FORM,source_ready=True,transport=self.transport,now=lambda:NOW);opts.update(kw)
        return B2Collector(self.root,G,history(opts['now']()),**opts)
    def transport(self,s,t):self.calls.append(copy.deepcopy(s));return response(s,t)
    def test_full_synthetic_single_lease_preserves_old_history_and_never_certifies(self):
        with self.collector()as c:out=run_b2(c)
        state=json.loads((self.root/'budget.json').read_bytes())
        self.assertEqual(state['requests'][0],self.old['requests'][0]);self.assertEqual(state['executions'][0],self.old['executions'][0])
        self.assertEqual(len(state['executions']),2);self.assertLessEqual(len(state['requests']),36)
        self.assertEqual(state['executions'][-1]['status'],'FINISHED');self.assertEqual(len(self.calls),out['source_HTTP_this_run'])
        self.assertFalse(out['financial_eligible']);self.assertFalse(out['calendar_eligible']);self.assertFalse(out['source_collection_complete'])
        self.assertEqual(len({request_id(s)for s in self.calls}),len(self.calls))
        self.assertTrue(all(s.get('params',{}).get('basDd')!='20091230'for s in self.calls))
        self.assertTrue(all(s.get('receipt')not in G['existing_Q3_receipts'].values()for s in self.calls))
        self.assertEqual(len(out['completed_followups']),12)
    def test_same_day_and_expiry_do_not_activate_or_charge(self):
        for now in [NOW-timedelta(days=1),datetime(2026,11,5,tzinfo=KST)]:
            before=(self.root/'budget.json').read_bytes()
            with self.assertRaises(Stop),self.collector(now=lambda:now)as c:run_b2(c)
            self.assertEqual((self.root/'budget.json').read_bytes(),before)
        self.assertFalse(self.calls)
    def test_other_failure_cannot_be_resolved_by_b2(self):
        state=copy.deepcopy(self.old);state['requests'][0]['request']['params']['basDd']='20100430';atomic(self.root/'budget.json',state)
        with self.assertRaisesRegex(Stop,'ONLY_DIAGNOSED'):self.collector()
        self.assertFalse(self.calls)
    def test_changed_raw_or_missing_private_readback_blocks(self):
        for field,value in [('sha256','0'*64),('private_remote_preserved',False)]:
            s=copy.deepcopy(self.old);s['requests'][0][field]=value;atomic(self.root/'budget.json',s)
            with self.assertRaises(Stop):self.collector()
    def test_budget_or_signal_amendment_cannot_expand(self):
        for field,value in [('remaining_HTTP',36),('remaining_executions',2),('retries',1),('signal_date','2009-12-30'),('reset_budget',True)]:
            with self.assertRaisesRegex(Stop,'AMENDMENT_SCOPE'):self.collector(amendment={**A,field:value})
    def test_completed_final_execution_cannot_start_again(self):
        with self.collector()as c:c.get(primary_requests(G,c.form)[0])
        before=(self.root/'budget.json').read_bytes()
        with self.assertRaisesRegex(Stop,'EXACT_UNUSED'):self.collector()
        self.assertEqual((self.root/'budget.json').read_bytes(),before)
    def test_market_empty_keeps_independent_dart_kind_requests(self):
        def transport(s,t):
            self.calls.append(s)
            return raw({'OutBlock_1':[]})if s['group']=='execution_market'else response(s,t)
        with self.collector(transport=transport)as c:out=run_b2(c)
        self.assertTrue(any(s['group']=='dart_inventory'for s in self.calls));self.assertTrue(any(s['group']=='kind_inventory'for s in self.calls))
        self.assertEqual(sum(x['status']=='SOURCE_GAP'for x in out['inventories'].values()),2)
        self.assertEqual(len({request_id(s)for s in self.calls}),len(self.calls))
    def test_auth_error_stops_before_any_other_branch_and_keeps_charge(self):
        def transport(s,t):self.calls.append(s);raise Stop('SOURCE_HTTP_401_NO_RETRY')
        with self.assertRaisesRegex(Stop,'401'),self.collector(transport=transport)as c:run_b2(c)
        state=json.loads((self.root/'budget.json').read_bytes());self.assertEqual(len(self.calls),1)
        self.assertEqual((len(state['requests']),len(state['executions'])),(2,2));self.assertEqual(state['status'],'HOLD_FAILURE')
    def test_deadline_saves_partial_and_no_third_execution(self):
        ticks=[0.]
        def transport(s,t):ticks[0]=520.;return response(s,t)
        with self.assertRaises(Deadline),self.collector(transport=transport,monotonic=lambda:ticks[0])as c:run_b2(c)
        state=json.loads((self.root/'budget.json').read_bytes());self.assertEqual(state['executions'][-1]['status'],'STOPPED_TIME')
        self.assertEqual(len(state['requests']),2);self.assertTrue((self.root/'b2_outcome.json').exists())
        with self.assertRaises(Stop):self.collector()
    def test_false_first_fill_or_old_signal_request_blocked(self):
        with self.collector()as c:
            for s in [inventory_requests(G)[0],{**primary_requests(G,c.form)[0],'params':{'basDd':'20100504'}}]:
                with self.assertRaises(Stop):c.get(s)
        self.assertFalse(self.calls)
    def test_kind_scope_cannot_gain_filter_or_other_security(self):
        with self.collector()as c:
            s=next(s for s in primary_requests(G,c.form)if s['group']=='kind_inventory')
            s['params']['reportNm']='배당'
            with self.assertRaises(Stop):c.get(s)
        self.assertFalse(self.calls)
    def test_exact_ajax_header_without_auth_leak(self):
        with patch('bounded_official_evidence.request.build_opener')as opener:
            resp=opener.return_value.open.return_value.__enter__.return_value;resp.status=200;resp.read.return_value=b'<html>SYNTHETIC</html>'
            fetch(next(s for s in primary_requests(G,kind_form_contract(FORM))if s['group']=='kind_inventory'),1)
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('X-requested-with'),'XMLHttpRequest');self.assertIsNone(req.get_header('Auth_key'))
    def test_literal_kind_chain_and_outside_host_or_wrong_document_rejected(self):
        s=dict(group='event',method='GET',url='https://kind.krx.co.kr/common/disclsviewer.do',params=dict(method='searchContents',docNo='20100601000001'),security='000500',receipt='20100601000001',purpose='SYNTHETIC',evidence_ids=['fake'])
        with self.assertRaises(SourceGap):viewer_children(s,b"https://evil.invalid/x")
        with self.assertRaisesRegex(Stop,'ID_MISMATCH'):viewer_children(s,b'https://kind.krx.co.kr/external/2010/06/01/other/1.htm')
    def test_unknown_followup_or_forged_inventory_binding_blocks(self):
        with self.collector()as c:
            d=next(s for s in primary_requests(G,c.form)if s['group']=='dart_inventory');c.get(d)
            t=dict(group='event',method='GET',url='https://evil.invalid/file',params={},security='000500',receipt='20110331000500',purpose='SYNTHETIC',evidence_ids=[request_id(d)])
            with self.assertRaisesRegex(Stop,'NOT_LITERAL'):c.frozen_batch([request_id(d)],[t])
            with self.assertRaises(Stop):c.get(t)
    def test_grant_old_phase_totals_and_new_group_ceiling(self):
        self.assertEqual(sum(LIMITS.values()),36)
        self.assertEqual(2+6+6,14);self.assertEqual(3+2+16,21)
        with self.collector()as c:
            self.assertEqual(c.remaining()['HTTP'],35);self.assertEqual(c.remaining()['executions'],1)
            self.assertEqual(c.remaining()['phase'],{'inventory':14,'conditional':21})
    def test_private_storage_failure_prevents_source_transport(self):
        def mirror(*args):raise Stop('PRIVATE_WRITE_FAILED')
        with self.assertRaises(Stop):self.collector(mirror=mirror)
        self.assertFalse(self.calls)
    def test_annual_versions_cannot_consume_other_issuers_three_slots(self):
        inventories={}
        for s in primary_requests(G,kind_form_contract(FORM)):
            if s['group']!='dart_inventory':continue
            p=dart_page(s,response(s,1));inventories['DART:'+s['security']]=dict(status='COMPLETE',evidence={'pages':[p]})
        first=inventories['DART:000500']['evidence']['pages'][0]
        original=copy.deepcopy(first['rows'][-1]);original.update(rcept_no='20110401000001',rcept_dt='20110401',report_nm='[기재정정] 사업보고서 (2010.12)');first['rows'].append(original)
        targets,_=targets_from_inventories(inventories,G)
        self.assertEqual({s['security']for s in targets if s['group']=='annual'},set(MEMBERS))
        self.assertEqual(sum(s['group']=='annual'for s in targets),3)
        self.assertEqual(next(s for s in targets if s['receipt']=='20110401000001')['group'],'event')
        self.assertTrue(all(s['group']=='annual'for s in targets[:3]))

if __name__=='__main__':unittest.main(verbosity=2)
