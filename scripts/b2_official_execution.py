"""B2 purpose amendment over the ORIGINAL private B ledger; no new budget.

Only transport/collection preparation. Nothing here certifies financial values,
absence of actions, an official historical calendar, or permission to execute NAV.
"""
import copy,json,re
from pathlib import Path
from urllib.parse import urlsplit
from html import unescape
from bounded_official_evidence import (Collector,Stop,Deadline,raw,sha,atomic,request_id,
    inventory_requests,validate_request,validate_response,check_history,day,stamp)
from b_official_request_preparation import (SourceGap,MEMBERS,KRX_DAILY,route_period_check,
    dart_page,close_pages,kind_form_contract,kind_query,kind_page,document_response)

FORM_PATH='docs/research/stage14-celltrion-2019-20261017/evidence/kind_form_redacted.html'
CALENDAR_URLS=(
 'https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp',
 'https://global.krx.co.kr/contents/GLB/06/0602/0602020204/GLB0602020204T1.jsp')
LIMITS={'signal_market':1,'execution_market':2,'dart_inventory':6,'kind_inventory':6,'annual':3,'calendar':2,'event':16}
ACTION=re.compile('배당|증자|감자|분할|합병|주식교환|주식이전|주식병합|주식분할|상장|매매거래|거래정지|거래재개|주권|권리|해산|회생|정리매매')


def validate_amendment(a,grant,form):
    expected=dict(contract='b2-purpose-amendment-v1',strategy_id='research_fixed_three_q3_b2_20100430',
        original_approval_sha256=sha(raw(grant)),signal_date='2010-04-30',proposed_first_fill='2010-05-03',
        final_valuation='2010-12-30',remaining_HTTP=35,remaining_executions=1,seconds=600,retries=0,
        shared_KST_daily_limit=1,expires_at=grant['expires_at'],cumulative_group_limits=LIMITS,
        financial_publication='HOLD',classification='RESEARCH_ONLY',reset_budget=False,
        form_sha256=sha(form),calendar_urls=list(CALENDAR_URLS))
    if a!=expected:raise Stop('B2_AMENDMENT_SCOPE_OR_BUDGET_CHANGED')
    kind_form_contract(form)


def primary_requests(grant,form):
    rows=[dict(group='execution_market',method='GET',url=url,params={'basDd':'20100503'},
        purpose='B2 proposed first fill: verify actual official date and fixed-cohort prices; not calendar completeness')for url in sorted(KRX_DAILY)]
    rows += [s for s in inventory_requests(grant)if s['group']=='dart_inventory']
    for stock in MEMBERS:
        s=kind_query(stock,form)
        for k in ('required_headers','historical_data_status'):s.pop(k)
        rows.append(s)
    return rows


def viewer_children(spec,body):
    """Only literal exact links in a preserved parent; no guessed receipt URLs."""
    if spec['url']!='https://kind.krx.co.kr/common/disclsviewer.do':return []
    text=body.decode('utf-8',errors='strict');params=spec['params'];out=[]
    if params.get('method')=='searchInitInfo':
        m=re.search(r'<select[^>]*id=[\'"]mainDoc[\'"][^>]*>(.*?)</select>',text,re.S)
        if not m:raise SourceGap('KIND_MAIN_DOCUMENT_CONTROL_NOT_FOUND')
        docs=re.findall(r'<option[^>]*value=[\'"](\d{14})\|[A-Z][\'"]',m.group(1))
        if not docs:raise SourceGap('KIND_MAIN_DOCUMENT_ID_NOT_FOUND')
        # Preserve every original/amended version listed, not just selected/latest.
        for doc in dict.fromkeys(docs):out.append(('https://kind.krx.co.kr/common/disclsviewer.do',dict(method='searchContents',docNo=doc)))
    elif params.get('method')=='searchContents':
        links=re.findall(r'https://kind\.krx\.co\.kr/external/[^\s\'"<>]+',text)
        for link in dict.fromkeys(links):
            u=urlsplit(unescape(link))
            if u.query or u.fragment or '..'in Path(u.path).parts or not u.path.endswith(('.htm','.html')):
                raise Stop('KIND_EXTERNAL_DOCUMENT_PATH_INVALID')
            if params['docNo'] not in u.path:raise Stop('KIND_EXTERNAL_DOCUMENT_ID_MISMATCH')
            out.append((unescape(link),{}))
        if not out:raise SourceGap('KIND_EXACT_BODY_LINK_NOT_RETURNED')
    return [dict(group='event',method='GET',url=u,params=p,security=spec['security'],
        receipt=spec.get('receipt'),purpose='B2 literal original/amended action-document child',
        evidence_ids=[request_id(spec)])for u,p in out]


class B2Collector(Collector):
    def __init__(self,*args,amendment,form_body,**kwargs):
        self.amendment=amendment;self.form_body=form_body;self.form=kind_form_contract(form_body)
        grant=args[1] if len(args)>1 else kwargs['grant']
        validate_amendment(amendment,grant,form_body)
        super().__init__(*args,**kwargs)

    def validate_held_state(self):
        # All original rows/counters/hashes survive. Only the diagnosed old
        # unsupported-period response can be admitted to the new purpose.
        s=self.state
        if len(s['executions'])!=1 or len(s['requests'])!=1 or s.get('b2_amendment'):
            raise Stop('B2_EXACT_UNUSED_FINAL_LEASE_CHECKPOINT_REQUIRED')
        e,r=s['executions'][0],s['requests'][0];q=r['request']
        if (s['status']!='HOLD_FAILURE' or e['status']!='HOLD_FAILURE' or r['status']!='FAILED_NO_RETRY'
            or q['group']!='signal_market' or q['method']!='GET'
            or q['url']!='https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd'
            or q['params']!={'basDd':'20091230'} or not r.get('private_remote_preserved')):
            raise Stop('B2_ONLY_DIAGNOSED_UNSUPPORTED_PERIOD_HOLD_CAN_TRANSITION')
        body=(self.root/r['body_path']).read_bytes()
        if sha(body)!=r['sha256'] or json.loads(body).get('OutBlock_1')!=[]:
            raise Stop('B2_PRIOR_FAILURE_EVIDENCE_CHANGED')
        self.prior_bytes=raw(s)

    def start(self):
        if self.execution:return
        check_history(self.history,self.now())
        if any(e['day_kst']==day(self.now())for e in self.state['executions']):raise Stop('ONCE_PER_KST_DAY')
        if raw(self.state)!=self.prior_bytes:raise Stop('B2_CHECKPOINT_MUTATED_BEFORE_LEASE')
        # Base start enforces authentication, expiry, total2 and durable charge.
        super().start()
        self.state['b2_amendment']=dict(approval=self.amendment,sha256=sha(raw(self.amendment)),
            prior_state_sha256=sha(self.prior_bytes),reason='Original B API history planning error; separate user-approved B2 purpose',
            original_B_status='BLOCKED_UNCHANGED',activated_at=stamp(self.now()))
        self.save()

    def phase_for(self,group):return 'inventory'if group in {'execution_market','dart_inventory','kind_inventory'}else'conditional'
    def group_limit(self,group):return LIMITS[group]
    def check_form(self,spec):
        if spec['group']=='kind_inventory'and spec.get('form_sha256')!=sha(self.form_body):raise Stop('RETAINED_FORM_BINDING_CHANGED')

    def validate_spec(self,s):
        group=s['group'];key=request_id(s)
        if group=='execution_market':
            if s not in primary_requests(self.grant,self.form)[:2]:raise Stop('B2_FIXED_FIRST_FILL_MARKET_REQUEST_REQUIRED')
            route_period_check(s['url'],s['params']['basDd'])
        elif group=='dart_inventory':validate_request(s,self.grant)
        elif group=='kind_inventory':
            expected=kind_query(s.get('security'),self.form,int(s.get('params',{}).get('pageIndex','0')))
            for k in ('required_headers','historical_data_status'):expected.pop(k)
            if s!=expected:raise Stop('B2_KIND_EXACT_RETAINED_FORM_QUERY_REQUIRED')
        elif group=='calendar':
            if (s['method']!='GET' or s['url']not in CALENDAR_URLS or s['params']!={} or set(s)!={'group','method','url','params','purpose'}):raise Stop('B2_CALENDAR_EXACT_VERIFIED_GUIDE_PATH_REQUIRED')
        elif group in {'annual','event'}:
            freezes=self.state.get('b2_followup_freezes',[])
            if not freezes:raise Stop('B2_FROZEN_FOLLOWUP_REQUIRED')
            found=False
            for f in freezes:
                if sha(raw(f['targets']))!=f['targets_sha256'] or sha(raw(f['parents']))!=f['parents_sha256']:raise Stop('B2_FREEZE_HASH_MISMATCH')
                known={r['id']:r for r in self.state['requests']if r['status']=='COMPLETE'}
                if any(pid not in known or known[pid]['sha256']!=h for pid,h in f['parents'].items()):raise Stop('B2_FREEZE_PARENT_CHANGED')
                if s in f['targets']:found=True
            if not found:raise Stop('B2_EXACT_FROZEN_TARGET_REQUIRED')
            if s.get('receipt')in self.grant['existing_Q3_receipts'].values():raise Stop('B2_REUSE_EXISTING_Q3_NO_REDOWNLOAD')
        else:raise Stop('B2_OLD_OR_UNKNOWN_REQUEST_SCOPE_FORBIDDEN')
        return key

    def validate_body(self,s,b):
        if s['group']=='dart_inventory':dart_page(s,b)
        elif s['group']=='kind_inventory':kind_page(s,b)
        elif s['group']=='execution_market':
            obj=json.loads(b);rows=obj.get('OutBlock_1')
            if rows==[]:raise SourceGap('B2_SUPPORTED_DATE_BUT_NO_MARKET_ROWS')
            validate_response(s,b)
            wanted={'049720'}if '/ksq_'in s['url']else{'000500','007160'}
            chosen=[r for r in rows if r.get('ISU_CD')in wanted]
            if len(chosen)!=len(wanted):raise SourceGap('B2_FIXED_COHORT_FILL_MARKET_ROWS_MISSING')
            if len({r['ISU_CD']for r in chosen})!=len(chosen):raise Stop('B2_DUPLICATE_MARKET_ROWS')
            for r in chosen:
                if float(str(r.get('TDD_CLSPRC','0')).replace(',',''))<=0:raise SourceGap('B2_FILL_CLOSE_MISSING')
        elif s['url']=='https://opendart.fss.or.kr/api/document.xml':document_response(s,b)
        else:
            if not b.strip():raise SourceGap('B2_EMPTY_DOCUMENT_NOT_EVIDENCE')
            text=b.decode('utf-8',errors='replace')
            if re.search('captcha|접근.*(?:차단|제한)|로그인이 필요',text,re.I):raise Stop('B2_ACCESS_RESTRICTION_NO_RETRY')
            if s['group']=='calendar'and 'Saturdays'not in text:raise SourceGap('B2_CALENDAR_GUIDE_CONTENT_NOT_CONFIRMED')

    def frozen_batch(self,parents,targets):
        if not targets:return
        known={r['id']:r for r in self.state['requests']if r['status']=='COMPLETE'}
        if not parents or not set(parents)<=set(known):raise Stop('B2_PARENT_NOT_DURABLY_PRESERVED')
        if len({request_id(s)for s in targets})!=len(targets):raise Stop('B2_DUPLICATE_FREEZE_TARGET')
        for t in targets:
            if (set(t)!={'group','method','url','params','security','receipt','purpose','evidence_ids'}
                or t['group']not in {'annual','event'} or t['method']!='GET'
                or t['security']not in MEMBERS or not t['purpose']
                or not t['evidence_ids'] or not set(t['evidence_ids'])<=set(parents)):
                raise Stop('B2_CONDITIONAL_SCOPE_OR_PARENT_BINDING')
            proved=False
            for pid in t['evidence_ids']:
                parent=known[pid];s=parent['request'];body=self.cached(pid)
                if s.get('security')!=t['security']:continue
                if s['group']=='dart_inventory':
                    p=dart_page(s,body)
                    if (t['url']=='https://opendart.fss.or.kr/api/document.xml'
                        and t['params']=={'rcept_no':t['receipt']}
                        and any(r['rcept_no']==t['receipt']for r in p['rows'])):proved=True
                elif s['group']=='kind_inventory':
                    p=kind_page(s,body)
                    if (t['group']=='event'and t['url']=='https://kind.krx.co.kr/common/disclsviewer.do'
                        and t['params']==dict(method='searchInitInfo',acptNo=t['receipt'])
                        and any(r['receipt']==t['receipt']for r in p['rows'])):proved=True
                elif t in viewer_children(s,body):proved=True
            if not proved:raise Stop('B2_FOLLOWUP_NOT_LITERAL_IN_PRESERVED_PARENT')
        f=dict(parents={k:known[k]['sha256']for k in parents},targets=targets,frozen_at=stamp(self.now()))
        f.update(parents_sha256=sha(raw(f['parents'])),targets_sha256=sha(raw(targets)))
        self.state.setdefault('b2_followup_freezes',[]).append(f);self.save()
        atomic(self.root/'b2_followups.json',self.state['b2_followup_freezes'])


def targets_from_inventories(inventories,grant):
    """Deterministic candidate retrieval, not absence/completeness adjudication.

    Preserve all list rows. Unclassified rows remain for offline review; title
    matching never certifies that no corporate action occurred.
    """
    targets=[];unclassified=[]
    for name,inv in inventories.items():
        if inv.get('status')!='COMPLETE' or not name.startswith(('KIND:','DART:')):continue
        kind=name.startswith('KIND:')
        for page in inv['evidence']['pages']:
            for row in page['rows']:
                receipt=row['receipt']if kind else row['rcept_no'];stock=page['security']
                title=unescape(re.sub('<[^>]+>',' ',row['source_literal']))if kind else row.get('report_nm','')
                if receipt in grant['existing_Q3_receipts'].values():continue
                annual=not kind and bool(re.search(r'사업보고서.*2010\.12',title))
                if not annual and not ACTION.search(title):
                    unclassified.append(dict(security=stock,receipt=receipt,title=title,requires_offline_review=True));continue
                spec=dict(group='annual'if annual else'event',method='GET',security=stock,receipt=receipt,
                    evidence_ids=[page['request_id']],purpose='B2 action evidence candidate; title matching is not financial or completeness certification')
                if kind:spec.update(url='https://kind.krx.co.kr/common/disclsviewer.do',params=dict(method='searchInitInfo',acptNo=receipt))
                else:spec.update(url='https://opendart.fss.or.kr/api/document.xml',params=dict(rcept_no=receipt))
                targets.append(spec)
    unique={request_id(s):s for s in targets}
    ordered=sorted(unique.values(),key=lambda s:(0 if s['group']=='annual'else 1 if 'opendart' in s['url'] else 2,s['security'],s['receipt']))
    return ordered,unclassified


def run_b2(c):
    outcomes={};requests=primary_requests(c.grant,c.form)
    def observe(name,fn):
        try:outcomes[name]=dict(status='COMPLETE',evidence=fn())
        except SourceGap as exc:outcomes[name]=dict(status='SOURCE_GAP',reason=str(exc))
        atomic(c.root/'b2_processing.json',outcomes)
    def pages(s):
        parser=kind_page if s['group']=='kind_inventory'else dart_page
        first=parser(s,c.get(s));all_pages=[first]
        if first['total_page']==2:
            p=copy.deepcopy(s);p['params']['pageIndex'if s['group']=='kind_inventory'else'page_no']='2'
            all_pages.append(parser(p,c.get(p)))
        return close_pages(all_pages,kind=s['group']=='kind_inventory',
            known_receipt=None if s['group']=='kind_inventory'else c.grant['existing_Q3_receipts'][s['security']])
    try:
        # Independent inventory branches continue on explicit data gaps only;
        # auth/access/quota/malformed data/transport/budget/private failures stop.
        for s in requests:
            name=('MARKET:'+s['url'].split('/')[-1] if s['group']=='execution_market'else
                ('DART:'if s['group']=='dart_inventory'else'KIND:')+s['security'])
            observe(name,lambda s=s:dict(response_sha256=sha(c.get(s)),calendar_complete=False)if s['group']=='execution_market'else pages(s))
        for u in CALENDAR_URLS:
            s=dict(group='calendar',method='GET',url=u,params={},purpose='B2 official holiday rule; retrospective2010 applicability needs independent review')
            observe('CALENDAR:'+u,lambda s=s:dict(response_sha256=sha(c.get(s)),historical_applicability='REQUIRES_REVIEW'))
        targets,unclassified=targets_from_inventories(outcomes,c.grant)
        parents=sorted({pid for t in targets for pid in t['evidence_ids']})
        if targets:c.frozen_batch(parents,targets)
        pending=[];queue=list(targets);completed=[]
        while queue:
            s=queue.pop(0);group=s['group']
            used=sum(r['group']==group for r in c.state['requests'])
            if used>=c.group_limit(group) or c.remaining()['HTTP']<=0 or c.remaining()['phase']['conditional']<=0:
                pending.append(s);continue
            try:
                body=c.get(s);completed.append(request_id(s))
                children=viewer_children(s,body)
                if children:c.frozen_batch([request_id(s)],children);queue[0:0]=children
            except SourceGap as exc:
                outcomes['DOCUMENT:'+request_id(s)]=dict(status='SOURCE_GAP',reason=str(exc))
        report=dict(status='COLLECTED_PENDING_INDEPENDENT_REVIEW',source_collection_complete=False,
            inventories=outcomes,unclassified_filing_rows=unclassified,pending_targets=pending,
            completed_followups=completed,financial_eligible=False,calendar_eligible=False,
            remaining=c.remaining(),source_HTTP_this_run=len(c.state['requests'])-1,new_financial_values=0)
        atomic(c.root/'b2_outcome.json',report)
        if c.preserve:
            location='raw/'+sha(raw(report))+'.bin'
            c.preserve(location,raw(report),c.deadline)
            c.state['b2_outcome']=dict(body_path=location,sha256=sha(raw(report)));c.save()
        return report
    except Deadline:
        partial=dict(status='STOPPED_TIME',source_collection_complete=False,inventories=outcomes,
                     remaining=c.remaining(),financial_eligible=False)
        atomic(c.root/'b2_outcome.json',partial)
        raise
