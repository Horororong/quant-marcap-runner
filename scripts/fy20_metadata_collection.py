"""Finite FY metadata transport. No financial or PIT promotion, no publication.

Reuses the deployed private transport primitives, but never rebinds B/B2's
grant or collector. Original source ZIPs are deliberately not fetched here.
"""
import fcntl,json,os,re,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from bounded_official_evidence import (
    Stop,Deadline,Collector,atomic,private_root,raw,sha,stamp,day,fetch,
    request_id,validate_response,check_history)

APPROVAL='fy20-asof-metadata-20261030'
PAIRS=(('00306870','20100331002117'),('00426068','20100331002119'),
 ('00405278','20100331002120'),('00378628','20100331002121'),
 ('00146269','20100331002124'),('00106669','20100331002127'),
 ('00105271','20100331002132'),('00160612','20100331002133'),
 ('00142883','20100331002136'),('00120030','20100331002137'),
 ('00146427','20100331002138'),('00106456','20100331002146'),
 ('00139889','20100331002149'),('00548865','20100331002153'),
 ('00314000','20100331002154'),('00164830','20100331002155'),
 ('00164672','20100331002159'),('00261212','20100331002160'),
 ('00480950','20100331002163'),('00508274','20100331002164'))
LIMITS={'list':40,'metadata':20,'correction':10}

def validate_grant(g):
    expected=dict(contract='fy20-asof-metadata-v1',approval_id=APPROVAL,
        approved=True,max_HTTP=70,max_executions=2,max_HTTP_per_execution=35,
        run_seconds=600,max_retries=0,max_executions_per_KST_day=1,
        expires_at='2026-11-04T23:59:59+09:00',group_limits=LIMITS,phase_limits=LIMITS,
        period_end='2009-12-31',signal_date='2010-04-30',scope='OFS',
        fields=['revenue','net_income','ocf','equity'],financial_publication='HOLD',
        classification='RESEARCH_ONLY',reset_prior_budgets=False)
    if any(g.get(k)!=v for k,v in expected.items()):raise Stop('FY20_APPROVAL_CONTRACT_CHANGED')
    if [(m.get('corp'),m.get('receipt'))for m in g.get('targets',[])]!=list(PAIRS):
        raise Stop('FY20_FIXED_FULL_COHORT_CHANGED')

def list_spec(m,page=1):
    return dict(group='list',method='GET',url='https://opendart.fss.or.kr/api/list.json',
        params=dict(corp_code=m['corp'],bgn_de='20090101',end_de='20100430',
            pblntf_ty='A',last_reprt_at='N',page_no=str(page),page_count='100',sort='date',sort_mth='asc'),
        purpose='Complete bounded official original/correction list; not a PIT certificate')

def metadata_spec(m):
    return dict(group='metadata',method='GET',url='https://dart.fss.or.kr/dsaf001/main.do',
        params={'rcpNo':m['receipt']},purpose='Exact original receipt/main/attachment menu; no ZIP repeat')

def correction_spec(corp,receipt):
    return dict(group='correction',method='GET',url='https://opendart.fss.or.kr/api/document.xml',
        params={'rcept_no':receipt},receipt=receipt,corp=corp,
        purpose='Offline reviewed material correction from hash-frozen complete list')

def parse_list(spec,body):
    try:o=json.loads(body)
    except (ValueError,TypeError):raise Stop('FY20_LIST_NOT_JSON')from None
    if o.get('status')=='013':
        if o.get('list')or int(o.get('total_count',0))or int(o.get('total_page',0)):
            raise Stop('FY20_EMPTY_LIST_CONTRADICTORY')
        return dict(page=int(spec['params']['page_no']),pages=0,count=0,rows=[],empty=True)
    if o.get('status')!='000':raise Stop('FY20_DART_SERVICE_ERROR_NO_RETRY')
    try:
        p,n,count=int(o['page_no']),int(o['total_page']),int(o['total_count']);rows=o['list']
        if p!=int(spec['params']['page_no'])or n<1 or count<1 or not isinstance(rows,list)or len(rows)>100:raise ValueError()
        if n!=(count+99)//100 or not rows:raise ValueError()
        for r in rows:
            if r.get('corp_code')!=spec['params']['corp_code']:raise ValueError()
            if not re.fullmatch(r'\d{14}',r.get('rcept_no','')):raise ValueError()
            if not '20090101'<=r.get('rcept_dt','')<='20100430':raise ValueError()
            if not r.get('report_nm'):raise ValueError()
    except (KeyError,ValueError,TypeError):raise Stop('FY20_LIST_IDENTITY_OR_PAGINATION_INVALID')from None
    return dict(page=p,pages=n,count=count,rows=rows,empty=False)

def review_inventory(member,responses):
    """Empty/over-cap/incomplete/omitted-original lists never close a chain."""
    pages=[parse_list(spec,b)for spec,b in responses]
    if not pages or pages[0]['empty']:return dict(status='SOURCE_GAP_EMPTY_LIST',complete=False)
    n=pages[0]['pages'];count=pages[0]['count']
    if n>2:return dict(status='PAGE_CAP_EXCEEDED',complete=False,required_pages=n)
    if (len(pages)!=n or {p['page']for p in pages}!=set(range(1,n+1))
        or any(p['pages']!=n or p['count']!=count for p in pages)):
        return dict(status='INCOMPLETE_LIST',complete=False)
    rows=[r for p in pages for r in p['rows']];receipts=[r['rcept_no']for r in rows]
    if len(receipts)!=count or len(set(receipts))!=count:raise Stop('FY20_LIST_DUPLICATE_OR_COUNT_MISMATCH')
    if member['receipt']not in receipts:return dict(status='KNOWN_ORIGINAL_ABSENT',complete=False)
    return dict(status='LIST_COMPLETE_REQUIRES_VERSION_REVIEW',complete=True,rows=rows,
        response_bindings=[dict(request_id=request_id(s),sha256=sha(b))for s,b in responses],
        financial_eligible=False)

class FYCollector(Collector):
    def __init__(self,root,grant,history,*,transport=fetch,now=lambda:datetime.now(timezone.utc),
                 monotonic=time.monotonic,source_ready=False,mirror=None,preserve=None):
        validate_grant(grant)
        self.root=private_root(root);self.grant=grant;self.history=history;self.transport=transport
        self.now=now;self.monotonic=monotonic;self.started=monotonic();self.deadline=self.started+600
        self.source_ready=source_ready;self.mirror=mirror;self.preserve=preserve;self.execution=None
        self.lock=os.fdopen(os.open(self.root/'.lease.lock',os.O_RDWR|os.O_CREAT,0o600),'r+')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.close();raise Stop('LOCAL_COLLECTION_ALREADY_ACTIVE')
        try:
            p=self.root/'budget.json'
            self.state=json.loads(p.read_bytes())if p.exists()else dict(contract=grant['contract'],approval_id=APPROVAL,
                approval_sha256=sha(raw(grant)),executions=[],requests=[],status='READY',inventory={},correction_freeze=None)
            if self.state.get('approval_sha256')!=sha(raw(grant)):raise Stop('FY20_NO_REBIND_OR_RESET')
            if any(e['status']=='RUNNING'for e in self.state['executions']):raise Stop('FY20_INTERRUPTED_LEASE_HELD')
            self.validate_held_state();self.save()
        except BaseException:self.close();raise
    def remaining(self):
        return dict(HTTP=70-len(self.state['requests']),executions=2-len(self.state['executions']),
                    group={g:cap-sum(r['group']==g for r in self.state['requests'])for g,cap in LIMITS.items()})
    def phase_for(self,group):return group
    def group_limit(self,group):return LIMITS[group]
    def check_form(self,spec):pass
    def validate_spec(self,spec):
        if spec.get('group')=='list':
            allowed=[list_spec(m,p)for m in self.grant['targets']for p in (1,2)]
        elif spec.get('group')=='metadata':allowed=[metadata_spec(m)for m in self.grant['targets']]
        else:
            frozen=self.state.get('correction_freeze')or{}
            if frozen.get('sha256')!=sha(raw(frozen.get('targets'))):raise Stop('FY20_CORRECTION_FREEZE_MISSING_OR_CHANGED')
            allowed=[correction_spec(t['corp'],t['receipt'])for t in frozen['targets']]
        if spec not in allowed:raise Stop('FY20_REQUEST_OUTSIDE_FIXED_APPROVAL')
        return request_id(spec)
    def validate_body(self,spec,body):
        if spec['group']=='list':parse_list(spec,body)
        elif spec['group']=='metadata':
            try:text=body.decode('utf-8')
            except UnicodeError:raise Stop('FY20_MENU_ENCODING_UNVERIFIED')from None
            # Store and hold an unexpected menu; never a publication certificate.
            if spec['params']['rcpNo']not in text or not re.search(r'<(?:html|script|select)\b',text,re.I):
                raise Stop('FY20_MENU_RECEIPT_OR_HTML_MISSING')
        else:validate_response(spec,body)
    def start(self):
        if self.execution:return
        if not self.source_ready or(self.transport is fetch and not os.environ.get('DART_API_KEY')):
            raise Stop('FY20_SOURCE_PREFLIGHT_NOT_READY_NO_LEASE')
        now=self.now()
        if now>datetime.fromisoformat(self.grant['expires_at']):raise Stop('APPROVAL_EXPIRED')
        check_history(self.history,now)
        if len(self.state['executions'])>=2:raise Stop('FY20_EXECUTIONS_EXHAUSTED')
        if any(e['day_kst']==day(now)for e in self.state['executions']):raise Stop('ONCE_PER_KST_DAY')
        self.execution=dict(id=uuid.uuid4().hex,day_kst=day(now),started_at=stamp(now),status='RUNNING',
            history_main_sha=self.history['main_sha'],history_state_sha256=self.history['state_sha256'])
        self.state['executions'].append(self.execution);self.state['status']='RUNNING';self.save()
    def get(self,spec):
        self.validate_spec(spec)
        if self.cached(request_id(spec))is None and self.execution:
            if sum(r['execution_id']==self.execution['id']for r in self.state['requests'])>=35:
                raise Deadline('FY20_RUN_HTTP_CAP_CHECKPOINT')
        try:return super().get(spec)
        except Stop as exc:
            diagnostic=getattr(exc,'control_diagnostic',None)
            if diagnostic and self.state['requests']:
                self.state['requests'][-1]['control_diagnostic']=diagnostic;self.save()
            raise
    def freeze_corrections(self,targets):
        if self.state.get('correction_freeze'):raise Stop('FY20_CORRECTION_FREEZE_IMMUTABLE')
        if not isinstance(targets,list)or len(targets)>10:raise Stop('FY20_CORRECTION_CAP')
        seen=set();members=dict(PAIRS)
        for t in targets:
            if set(t)!={'corp','receipt','inventory_sha256','original_menu_sha256','material_fields','relation_review'}:
                raise Stop('FY20_EXPLICIT_MATERIAL_VERSION_REVIEW_REQUIRED')
            inventory=self.state['inventory'].get(t['corp'],{})
            if not inventory.get('complete')or sha(raw(inventory))!=t['inventory_sha256']:
                raise Stop('FY20_INCOMPLETE_OR_CHANGED_CORRECTION_INVENTORY')
            match=next((r for r in inventory['rows']if r['rcept_no']==t['receipt']),None)
            if (not match or t['corp']not in members or t['receipt']==members[t['corp']]
                or t['receipt']in seen or not t['material_fields']or not set(t['material_fields'])<=set(self.grant['fields'])
                or not t['relation_review']or '정정'not in match['report_nm']or'2009.12'not in match['report_nm']):
                raise Stop('FY20_CORRECTION_NOT_MATERIAL_BOUND_FY_VERSION')
            meta=metadata_spec({'receipt':members[t['corp']]})
            record=next((r for r in self.state['requests']if r['id']==request_id(meta)and r['status']=='COMPLETE'),None)
            if not record or t['original_menu_sha256']!=record['sha256']:raise Stop('FY20_CORRECTION_MENU_NOT_BOUND')
            seen.add(t['receipt'])
        self.state['correction_freeze']=dict(targets=targets,sha256=sha(raw(targets)),frozen_at=stamp(self.now()))
        self.save()

def collect_metadata(c,corrections=None):
    for m in c.grant['targets']:
        responses=[];s=list_spec(m);b=c.get(s);responses.append((s,b));first=parse_list(s,b)
        if first['pages']==2:
            s=list_spec(m,2);responses.append((s,c.get(s)))
        c.state['inventory'][m['corp']]=review_inventory(m,responses);c.save()
    for m in c.grant['targets']:c.get(metadata_spec(m))
    if corrections is not None and not c.state.get('correction_freeze'):c.freeze_corrections(corrections)
    if c.state.get('correction_freeze'):
        for t in c.state['correction_freeze']['targets']:c.get(correction_spec(t['corp'],t['receipt']))
    return dict(status='METADATA_PRESERVED_OFFLINE_REVIEW_REQUIRED',new_PIT_values=0,new_provider_values=0,
                remaining=c.remaining(),source_collection_is_financial_certification=False)
