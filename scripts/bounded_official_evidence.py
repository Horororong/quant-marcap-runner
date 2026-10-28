"""Local, private, finite official-evidence transport. No publication endpoints.

One immutable approval, durable before-HTTP counters, no retries, shared-day
history, scoped request cache, deadline checkpoint and closed-inventory freeze.
Neither a successful fetch nor a frozen list grants financial/PIT eligibility.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib import request,error,parse
import fcntl,hashlib,io,json,os,stat,time,uuid,zipfile,re

KST=timezone(timedelta(hours=9));UTC=timezone.utc
GROUP_PHASE={'signal_market':'inventory','dart_inventory':'inventory','kind_inventory':'inventory','annual':'conditional','event':'conditional'}
HOSTS={'opendart.fss.or.kr','dart.fss.or.kr','data-dbg.krx.co.kr','kind.krx.co.kr'}
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(o):return (json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def stamp(now=None):return (now or datetime.now(UTC)).isoformat()
def day(now):return now.astimezone(KST).date().isoformat()
class Stop(RuntimeError):pass
class Deadline(Stop):pass
class DataUnavailable(Stop):pass

def private_root(path):
    path=Path(path)
    if any(p.is_symlink()for p in [path,*path.parents]):raise Stop('PRIVATE_ROOT_SYMLINK')
    path=path.resolve();path.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.stat().st_uid!=os.getuid() or stat.S_IMODE(path.stat().st_mode)!=0o700:raise Stop('PRIVATE_ROOT_REQUIRES_OWNER_0700')
    # Managed sandboxes install EMPTY, read-only .git guard directories at
    # mount roots. They are not Git repositories (git rev-parse also refuses
    # them). Reject files/worktrees, populated metadata and bare repositories.
    for p in [path,*path.parents]:
        marker=p/'.git'
        if marker.is_symlink() or marker.is_file() or (marker.is_dir() and any(marker.iterdir())):
            raise Stop('PRIVATE_ROOT_INSIDE_GIT')
        if (p/'HEAD').is_file() and (p/'objects').is_dir():raise Stop('PRIVATE_ROOT_INSIDE_BARE_GIT')
    return path

def atomic(path,obj,*,binary=False):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    data=obj if binary else raw(obj);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb')as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def validate_grant(g):
    expected=dict(contract='bounded-fixed-three-official-evidence-v1',approval_id='fixed-three-official-evidence-20261028',approved=True,
                  max_executions=2,max_HTTP=36,max_retries=0,run_seconds=600,max_executions_per_KST_day=1,
                  phase_limits={'inventory':15,'conditional':21},group_limits={'signal_market':2,'dart_inventory':6,'kind_inventory':7,'annual':3,'event':18},
                  expires_at='2026-11-04T23:59:59+09:00',signal_date='2009-12-30',holding_start='2010-01-04',holding_end='2010-12-30',
                  financial_publication='HOLD',classification='RESEARCH_ONLY',investment_approved=False,reset_prior_budgets=False)
    if any(g.get(k)!=v for k,v in expected.items()):raise Stop('APPROVED_FINITE_CONTRACT_CHANGED')
    if {(m['stock_code'],m['corp_code'])for m in g['members']}!={('007160','00124799'),('000500','00104768'),('049720','00336297')}or len(g['members'])!=3:raise Stop('APPROVED_COHORT_CHANGED')
    if g.get('existing_Q3_receipts')!={'007160':'20091116000562','000500':'20091116000251','049720':'20091113001077'}:raise Stop('PRESERVED_Q3_REUSE_BINDING_CHANGED')

def request_id(spec):return sha(raw({k:spec.get(k)for k in ['method','url','params']}))
def validate_request(spec,g,*,frozen=None):
    if set(spec)-{'group','method','url','params','purpose','security','receipt','evidence_ids','kind_binding'}:raise Stop('UNKNOWN_REQUEST_FIELD')
    url=parse.urlsplit(spec['url']);params=spec.get('params',{});group=spec['group'];method=spec['method']
    if (group not in GROUP_PHASE or url.scheme!='https' or url.hostname not in HOSTS or url.port not in {None,443}
            or url.username or url.password or url.query or url.fragment
            or any(k.lower()in {'crtfc_key','auth_key','authorization','token','password'}for k in params)):
        raise Stop('UNAPPROVED_URL_OR_SECRET_PARAMETERS')
    if not spec.get('purpose'):raise Stop('REQUEST_PURPOSE_REQUIRED')
    corp={x['corp_code']for x in g['members']};stocks={x['stock_code']for x in g['members']}
    if group=='signal_market':
        if method!='GET' or spec['url']not in {'https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd','https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd'}or params!={'basDd':'20091230'}:raise Stop('FIXED_SIGNAL_MARKET_SCOPE')
    elif group=='dart_inventory':
        expected={'bgn_de':'20090101','end_de':'20110430','last_reprt_at':'N','page_count':'100','sort':'date','sort_mth':'asc'}
        identity=next((m['stock_code']for m in g['members']if m['corp_code']==params.get('corp_code')),None)
        if (method!='GET' or spec['url']!='https://opendart.fss.or.kr/api/list.json' or spec.get('security')!=identity
                or params.get('corp_code')not in corp or str(params.get('page_no'))not in {'1','2'}
                or set(params)!=(set(expected)|{'corp_code','page_no'})or any(str(params[k])!=v for k,v in expected.items())):raise Stop('FIXED_ALL_FILINGS_SCOPE')
    elif group=='kind_inventory':
        if spec['url']!='https://kind.krx.co.kr/disclosure/details.do':raise Stop('KIND_FIXED_OFFICIAL_FORM_PATH')
        if method=='GET':
            if params!={'method':'searchDetailsMain'}:raise Stop('KIND_FIXED_FORM_DISCOVERY')
        elif method=='POST':
            binding=spec.get('kind_binding',{})
            if (spec.get('security')not in stocks or params.get('method')!='searchDetailsSub'
                    or binding.get('from')!='2009-11-01' or binding.get('through')!='2011-04-30'
                    or binding.get('stock_code')!=spec['security'] or not binding.get('form_sha256')
                    or not binding.get('all_event_types') or not binding.get('field_map')):raise Stop('KIND_FORM_AND_EXACT_CRITERIA_BINDING_REQUIRED')
            mapping=binding['field_map']
            required={'stock_code':spec['security'],'from':'2009-11-01','through':'2011-04-30'}
            if any(mapping.get(k)not in params or str(params[mapping[k]]).replace('-','')!=v.replace('-','')for k,v in required.items()):raise Stop('KIND_QUERY_CRITERIA_NOT_APPLIED')
            allowed={'method',*mapping.values(),*binding.get('page_fields',[]),*binding.get('all_event_fields',[])}
            if set(params)-allowed:raise Stop('KIND_EXTRA_UNBOUND_FORM_FIELDS')
            if any(str(params.get(k,''))not in {'','0','ALL','all'}for k in binding.get('all_event_fields',[])):raise Stop('KIND_FILTERED_EVENT_CLASS_NOT_COMPLETE')
        else:raise Stop('KIND_READONLY_METHOD_REQUIRED')
    else:
        if frozen is not None and (frozen.get('target_sha256')!=sha(raw(frozen.get('targets')))
                                   or frozen.get('inventory_sha256')!=sha(raw(frozen.get('inventory')))):
            raise Stop('FROZEN_INVENTORY_OR_TARGET_HASH_MISMATCH')
        if method!='GET' or frozen is None or request_id(spec)not in {request_id(x)for x in frozen['targets']}:raise Stop('FROZEN_CONDITIONAL_REQUEST_REQUIRED')
        if spec.get('security')not in stocks or not spec.get('evidence_ids'):raise Stop('CONDITIONAL_ISSUER_AND_INVENTORY_BINDING_REQUIRED')
        if url.hostname=='opendart.fss.or.kr':
            if url.path!='/api/document.xml' or set(params)!={'rcept_no'} or params['rcept_no']!=spec.get('receipt') or not str(params['rcept_no']).isdigit()or len(str(params['rcept_no']))!=14:raise Stop('EXACT_DOCUMENT_RECEIPT_REQUIRED')
        elif url.hostname=='data-dbg.krx.co.kr':
            if url.path not in {'/svc/apis/sto/stk_bydd_trd','/svc/apis/sto/ksq_bydd_trd'}or set(params)!={'basDd'}:raise Stop('EVENT_MARKET_DATE_REQUIRED')
            dt=datetime.strptime(params['basDd'],'%Y%m%d').date()
            if not datetime(2009,11,1).date()<=dt<=datetime(2011,4,30).date():raise Stop('EVENT_MARKET_OUTSIDE_APPROVED_EVIDENCE_RANGE')
        elif url.hostname=='dart.fss.or.kr':
            if url.path not in {'/dsaf001/main.do','/report/viewer.do'}or params.get('rcpNo')!=spec.get('receipt'):raise Stop('INVENTORY_LINKED_DART_VIEWER_REQUIRED')
        elif url.hostname=='kind.krx.co.kr':
            if not(url.path.startswith('/external/')or url.path=='/common/disclsviewer.do'):raise Stop('INVENTORY_LINKED_KIND_NOTICE_REQUIRED')
    return request_id(spec)

def check_history(snapshot,now):
    if snapshot.get('contract')!='fixed-three-shared-source-history-v1':raise Stop('SHARED_HISTORY_CONTRACT')
    observed=datetime.fromisoformat(snapshot['observed_at'])
    if not 0<=(now-observed).total_seconds()<=120:raise Stop('SHARED_HISTORY_SNAPSHOT_STALE')
    if snapshot.get('day_kst')!=day(now)or snapshot.get('active_source_runs'):raise Stop('SHARED_SOURCE_DAY_OR_ACTIVE_RUN')
    if snapshot.get('old_authorized_channels_exhausted')is not True:raise Stop('REMOTE_SHARED_LEASE_CANNOT_BE_SAFELY_EXCLUDED')
    if any(x['day_kst']==day(now)for x in snapshot['executions']):raise Stop('ONCE_PER_KST_DAY')
    if len(snapshot.get('state_sha256',{}))!=3 or not snapshot.get('main_sha'):raise Stop('SHARED_LEDGER_BINDINGS_REQUIRED')

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise Stop('REDIRECT_NOT_APPROVED_NO_RETRY')

def fetch(spec,timeout):
    params=dict(spec.get('params',{}));headers={'Accept':'*/*','User-Agent':'bounded-fixed-three-research'}
    host=parse.urlsplit(spec['url']).hostname
    key=''
    if host=='opendart.fss.or.kr':key=os.environ.get('DART_API_KEY','');params['crtfc_key']=key
    elif host=='data-dbg.krx.co.kr':key=os.environ.get('KRX_AUTH_KEY','');headers['AUTH_KEY']=key
    if host in {'opendart.fss.or.kr','data-dbg.krx.co.kr'}and not key:raise Stop('AUTH_NOT_CONFIGURED')
    encoded=parse.urlencode(params).encode();url=spec['url'];data=None
    if spec['method']=='GET':url+='?'+encoded.decode()
    else:data=encoded;headers['Content-Type']='application/x-www-form-urlencoded'
    if host=='kind.krx.co.kr' and spec['method']=='POST':headers['X-Requested-With']='XMLHttpRequest'
    req=request.Request(url,data=data,method=spec['method'],headers=headers)
    try:
        with request.build_opener(NoRedirect()).open(req,timeout=timeout)as response:
            body=response.read(32*1024*1024+1);status=response.status
    except error.HTTPError as exc:raise Stop('SOURCE_HTTP_'+str(exc.code)+'_NO_RETRY')from None
    except Stop:raise
    except Exception:raise Stop('SOURCE_TRANSPORT_FAILURE_NO_RETRY')from None
    if status!=200 or len(body)>32*1024*1024:raise Stop('SOURCE_STATUS_OR_SIZE_LIMIT')
    if key and (key.encode()in body or parse.quote(key,safe='').encode()in body):raise Stop('SOURCE_CREDENTIAL_ECHO_BLOCKED')
    if b'crtfc_key='in body or b'Authorization: Bearer 'in body:raise Stop('SOURCE_CREDENTIAL_PATTERN_BLOCKED')
    return body

def validate_response(spec,body):
    host=parse.urlsplit(spec['url']).hostname
    if host=='opendart.fss.or.kr'and parse.urlsplit(spec['url']).path.endswith('list.json'):
        o=json.loads(body)
        if o.get('status')not in {'000','013'}:raise Stop('DART_SERVICE_STATUS_'+str(o.get('status'))+'_NO_RETRY')
        if o.get('status')=='000':
            rows=o.get('list');page=int(o['page_no']);pages=int(o['total_page'])
            if not isinstance(rows,list)or page!=int(spec['params']['page_no']):raise Stop('DART_PAGE_IDENTITY')
            if any(x.get('corp_code')!=spec['params']['corp_code']for x in rows):raise Stop('DART_ISSUER_MISMATCH')
            if pages>2:raise Stop('DART_INVENTORY_PAGES_EXCEED_APPROVED_SCOPE')
    elif host=='data-dbg.krx.co.kr':
        o=json.loads(body);rows=o.get('OutBlock_1')
        if not isinstance(rows,list)or not rows or any(str(x.get('BAS_DD'))!=spec['params']['basDd']for x in rows):raise Stop('KRX_DATE_OR_SERVICE_SCOPE')
    elif host=='opendart.fss.or.kr':
        try:
            with zipfile.ZipFile(io.BytesIO(body))as z:
                if sum(i.file_size for i in z.infolist())>128*1024*1024:raise Stop('DOCUMENT_UNCOMPRESSED_SIZE_LIMIT')
                if any(Path(x).is_absolute()or'..'in Path(x).parts for x in z.namelist()):raise Stop('UNSAFE_SOURCE_ARCHIVE_PATH')
                if z.testzip()is not None:raise Stop('DOCUMENT_CRC_FAILURE')
                if not any(spec['receipt']in n and n.lower().endswith('.xml')for n in z.namelist()):raise Stop('DOCUMENT_RECEIPT_MEMBER_MISMATCH')
        except zipfile.BadZipFile:raise Stop('DOCUMENT_NOT_ZIP_NO_RETRY')from None
    elif not body.strip():raise Stop('EMPTY_OFFICIAL_DOCUMENT')

class Collector:
    def __init__(self,root,grant,history,*,transport=fetch,now=lambda:datetime.now(UTC),monotonic=time.monotonic,source_ready=False,mirror=None,preserve=None):
        validate_grant(grant);self.root=private_root(root);self.grant=grant;self.history=history;self.transport=transport;self.now=now;self.monotonic=monotonic
        self.started=monotonic();self.deadline=self.started+grant['run_seconds'];self.source_ready=source_ready;self.execution=None
        self.mirror=mirror;self.preserve=preserve
        fd=os.open(self.root/'.lease.lock',os.O_RDWR|os.O_CREAT,0o600);self.lock=os.fdopen(fd,'r+')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.lock.close();raise Stop('LOCAL_COLLECTION_ALREADY_ACTIVE')
        path=self.root/'budget.json'
        self.state=json.loads(path.read_text())if path.exists()else dict(contract=grant['contract'],approval_id=grant['approval_id'],approval_sha256=sha(raw(grant)),executions=[],requests=[],status='READY',inventory_freeze=None)
        if self.state['approval_sha256']!=sha(raw(grant)):self.close();raise Stop('BUDGET_CANNOT_BE_REBOUND_OR_RESET')
        if any(e['status']=='RUNNING'for e in self.state['executions']):self.close();raise Stop('INTERRUPTED_LEASE_HELD_NO_AUTOMATIC_RETRY')
        try:self.validate_held_state()
        except BaseException:self.close();raise
        try:self.save()
        except BaseException:self.close();raise
    def __enter__(self):return self
    def validate_held_state(self):
        if self.state['status']=='HOLD_FAILURE':raise Stop('ACTUAL_SOURCE_FAILURE_HELD')
    def validate_spec(self,spec):return validate_request(spec,self.grant,frozen=self.state['inventory_freeze'])
    def check_form(self,spec):
        if spec['group']=='kind_inventory'and spec['method']=='POST':
            hashes={r.get('sha256')for r in self.state['requests']if r['group']=='kind_inventory'and r['status']=='COMPLETE'}
            if spec['kind_binding']['form_sha256']not in hashes:raise Stop('KIND_FORM_NOT_IN_VERIFIED_CACHE')
    def validate_body(self,spec,body):return validate_response(spec,body)
    def group_limit(self,group):return self.grant['group_limits'][group]
    def phase_for(self,group):return GROUP_PHASE[group]
    def __exit__(self,kind,error,tb):
        try:
            if self.execution:
                self.execution.update(finished_at=stamp(self.now()),status='STOPPED_TIME'if isinstance(error,Deadline)else'HOLD_FAILURE'if kind else'FINISHED',elapsed_seconds=self.monotonic()-self.started)
                self.state['status']='PAUSED_TIME'if isinstance(error,Deadline)else'HOLD_FAILURE'if kind else'PAUSED'
                self.save()
        finally:self.close()
    def close(self):
        if not self.lock.closed:self.lock.close()
    def save(self):
        atomic(self.root/'budget.json',self.state)
        if self.mirror:self.mirror(self.state,self.deadline)
    def remaining(self):
        return dict(HTTP=self.grant['max_HTTP']-len(self.state['requests']),executions=self.grant['max_executions']-len(self.state['executions']),phase={p:self.grant['phase_limits'][p]-sum(r['phase']==p for r in self.state['requests'])for p in self.grant['phase_limits']})
    def start(self):
        if self.execution:return
        if not self.source_ready:raise Stop('AUTH_NETWORK_PRIVATE_PREFLIGHT_NOT_READY_NO_LEASE')
        if self.transport is fetch and not all(os.environ.get(k)for k in ['DART_API_KEY','KRX_AUTH_KEY']):raise Stop('AUTH_ENV_MISSING_NO_LEASE')
        now=self.now()
        if now>datetime.fromisoformat(self.grant['expires_at']):raise Stop('APPROVAL_EXPIRED')
        check_history(self.history,now)
        if len(self.state['executions'])>=self.grant['max_executions']:raise Stop('EXECUTION_BUDGET_EXHAUSTED')
        if any(e['day_kst']==day(now)for e in self.state['executions']):raise Stop('ONCE_PER_KST_DAY')
        self.execution=dict(id=uuid.uuid4().hex,day_kst=day(now),started_at=stamp(now),status='RUNNING',history_main_sha=self.history['main_sha'],history_state_sha256=self.history['state_sha256'])
        self.state['executions'].append(self.execution);self.state['status']='RUNNING';self.save()
    def cached(self,key):
        prior=next((r for r in self.state['requests']if r['id']==key),None)
        if not prior:return None
        if prior['status']!='COMPLETE':raise Stop('REQUEST_ALREADY_ATTEMPTED_RETRY_FORBIDDEN')
        path=self.root/prior['body_path'];body=path.read_bytes()
        if sha(body)!=prior['sha256']:raise Stop('PRIVATE_CACHE_HASH_MISMATCH')
        return body
    def get(self,spec):
        spec=json.loads(raw(spec))
        key=self.validate_spec(spec);self.check_form(spec)
        cached=self.cached(key)
        if cached is not None:return cached
        # Reserve time for private remote persistence and the final checkpoint.
        if self.monotonic()+90>=self.deadline:raise Deadline('STOP_BEFORE_600S_CHECKPOINT_SAVED')
        if self.now()>datetime.fromisoformat(self.grant['expires_at']):raise Stop('APPROVAL_EXPIRED')
        if self.execution and day(self.now())!=self.execution['day_kst']:raise Deadline('STOP_AT_KST_DAY_BOUNDARY')
        phase=self.phase_for(spec['group'])
        if len(self.state['requests'])>=self.grant['max_HTTP']or sum(r['phase']==phase for r in self.state['requests'])>=self.grant['phase_limits'][phase]or sum(r['group']==spec['group']for r in self.state['requests'])>=self.group_limit(spec['group']):raise Stop('TOTAL_PHASE_OR_GROUP_HTTP_EXHAUSTED')
        self.start()
        row=dict(id=key,phase=phase,group=spec['group'],request=spec,execution_id=self.execution['id'],status='ATTEMPT_STARTED',started_at=stamp(self.now()))
        self.state['requests'].append(row);self.save()  # durable accounting BEFORE transport
        try:
            row['transport_started']=True;self.save()
            body=self.transport(spec,min(25,max(1,self.deadline-self.monotonic()-5)))
            location='raw/'+sha(body)+'.bin';atomic(self.root/location,body,binary=True)
            row.update(status='RESPONSE_RECEIVED',body_path=location,bytes=len(body),sha256=sha(body));self.save()
            if self.preserve:self.preserve(location,body,self.deadline)
            row['private_remote_preserved']=bool(self.preserve)
            self.validate_body(spec,body)
            row.update(status='COMPLETE',body_path=location,bytes=len(body),sha256=sha(body),finished_at=stamp(self.now()))
            atomic(self.root/'receipts'/str(key+'.json'),row);self.save();return body
        except DataUnavailable as exc:
            row.update(status='SOURCE_GAP_NO_RETRY',reason=str(exc));self.save();raise
        except BaseException:
            row['status']='FAILED_NO_RETRY';self.save();raise
    def freeze(self,inventory,targets):
        if self.state.get('inventory_freeze'):raise Stop('FOLLOWUP_LIST_ALREADY_FROZEN_NO_REPLACEMENT')
        members={m['stock_code']for m in self.grant['members']};proofs=inventory.get('proofs',[])
        required={(s,k)for s in members for k in ('issuer_all_filings','exchange_all_events')}
        if not inventory.get('complete')or len(proofs)!=6 or {(p['security'],p['kind'])for p in proofs}!=required:raise Stop('ALL_COHORT_INVENTORIES_MUST_BE_COMPLETE')
        known={r['id']:r for r in self.state['requests']if r['status']=='COMPLETE'}
        if len([r for r in known.values()if r['group']=='signal_market'])!=2:
            raise Stop('BOTH_ORIGINAL_SIGNAL_MARKETS_MUST_BE_PRESERVED')
        for p in proofs:
            if not p.get('request_ids')or not set(p['request_ids'])<=set(known)or not p.get('total_pages_verified'):raise Stop('INVENTORY_PAGES_NOT_BOUND_TO_ACTUAL_RESPONSES')
            rs=[known[i]for i in p['request_ids']]
            if p['kind']=='issuer_all_filings':
                company=next(m['corp_code']for m in self.grant['members']if m['stock_code']==p['security'])
                if any(x['group']!='dart_inventory'or x['request']['params']['corp_code']!=company for x in rs):raise Stop('ISSUER_INVENTORY_SOURCE_MISMATCH')
                pages=[json.loads(self.cached(x['id']))for x in rs]
                total=int(pages[0].get('total_page',0));count=int(pages[0].get('total_count',0))
                if (total<1 or len(pages)!=total or {int(x['page_no'])for x in pages}!=set(range(1,total+1))
                        or any(int(x['total_page'])!=total or int(x['total_count'])!=count for x in pages)):raise Stop('ISSUER_INVENTORY_INCOMPLETE_PAGINATION')
                receipts=[v['rcept_no']for page in pages for v in page['list']]
                if len(receipts)!=count or len(set(receipts))!=count or self.grant['existing_Q3_receipts'][p['security']]not in receipts:raise Stop('ISSUER_INVENTORY_MISSING_ROWS_OR_KNOWN_Q3')
            else:
                if any(x['group']!='kind_inventory'or x['request']['method']!='POST'or x['request'].get('security')!=p['security']for x in rs):raise Stop('EXCHANGE_INVENTORY_REQUIRES_BOUND_QUERY_NOT_FORM')
                parsed=p.get('parsed_pages',[])
                if len(parsed)!=len(rs)or not parsed:raise Stop('EXCHANGE_PAGE_PARSE_REQUIRED')
                for page in parsed:
                    original=next((x for x in rs if x['id']==page.get('request_id')),None)
                    if not original or page.get('response_sha256')!=original['sha256']:raise Stop('EXCHANGE_PARSE_NOT_BOUND')
                    text=self.cached(original['id']).decode(page.get('encoding','utf-8'),errors='strict')
                    if p['security']not in text or not page.get('count_literal')or page['count_literal']not in text:raise Stop('EXCHANGE_QUERY_ECHO_AND_COUNT_NOT_PROVED')
                    if any(row.get('security')!=p['security']or row.get('source_literal','')not in text or not row.get('source_literal')for row in page.get('rows',[])):raise Stop('EXCHANGE_ROW_NOT_BOUND')
                total=parsed[0]['total_pages'];count=parsed[0]['total_count']
                if (len(parsed)!=total or {x['page_no']for x in parsed}!=set(range(1,total+1))
                        or any(x['total_pages']!=total or x['total_count']!=count for x in parsed)
                        or sum(len(x.get('rows',[]))for x in parsed)!=count):raise Stop('EXCHANGE_INVENTORY_INCOMPLETE_PAGINATION')
        if len({request_id(t)for t in targets})!=len(targets)or sum(t['group']=='annual'for t in targets)>3 or sum(t['group']=='event'for t in targets)>18:raise Stop('FOLLOWUP_CAP_OR_DUPLICATES')
        inventory=json.loads(raw(inventory));targets=json.loads(raw(targets))
        frozen=dict(inventory=inventory,inventory_sha256=sha(raw(inventory)),targets=targets,target_sha256=sha(raw(targets)),frozen_at=stamp(self.now()))
        for t in targets:
            if t['group']not in {'annual','event'}:raise Stop('FOLLOWUP_SCOPE')
            validate_request(t,self.grant,frozen=frozen)
            if not set(t.get('evidence_ids',[]))<=set(known):raise Stop('FOLLOWUP_WITHOUT_INVENTORY_SOURCE')
            receipt=t.get('receipt')
            if receipt and receipt in self.grant['existing_Q3_receipts'].values():raise Stop('PRESERVED_Q3_MUST_BE_REUSED_NOT_COLLECTED')
            if receipt:
                allowed=[]
                for source_id in t['evidence_ids']:
                    source=known[source_id]
                    if source['group']=='dart_inventory'and source['request'].get('security')==t['security']:
                        allowed.extend(x['rcept_no']for x in json.loads(self.cached(source_id)).get('list',[]))
                if receipt not in allowed:raise Stop('FOLLOWUP_RECEIPT_NOT_IN_ISSUER_INVENTORY')
            if not receipt:
                # Exact exchange URLs or event-date queries must be visibly
                # justified in independently reviewed, hash-bound inventory.
                if not any(r.get('request_binding')=={k:t.get(k)for k in ('method','url','params')}
                           and set(t['evidence_ids'])&set(p['request_ids'])
                           for p in proofs if p['security']==t['security']
                           for page in p.get('parsed_pages',[])for r in page.get('rows',[])):
                    raise Stop('FOLLOWUP_EXCHANGE_TARGET_NOT_BOUND_TO_REVIEWED_INVENTORY')
        if len(targets)>self.remaining()['HTTP']:raise Stop('FOLLOWUP_EXCEEDS_REMAINING_TOTAL_HTTP')
        atomic(self.root/'frozen_followups.json',frozen);self.state['inventory_freeze']=frozen;self.save();return frozen

def inventory_requests(g):
    rows=[dict(group='signal_market',method='GET',url=f'https://data-dbg.krx.co.kr/svc/apis/sto/{m}_bydd_trd',params={'basDd':'20091230'},purpose='Original signal official market/identity/cap')for m in ('stk','ksq')]
    rows += [dict(group='dart_inventory',method='GET',url='https://opendart.fss.or.kr/api/list.json',params=dict(corp_code=m['corp_code'],bgn_de='20090101',end_de='20110430',last_reprt_at='N',page_count='100',page_no='1',sort='date',sort_mth='asc'),purpose='All filing classes/originals/corrections for fixed issuer',security=m['stock_code'])for m in g['members']]
    return rows

def run_inventory(collector):
    for spec in inventory_requests(collector.grant):
        body=collector.get(spec)
        if spec['group']=='dart_inventory':
            obj=json.loads(body)
            if int(obj.get('total_page',0))==2:
                follow=dict(spec,params={**spec['params'],'page_no':'2'});collector.get(follow)
    # Form discovery is one counted call. Never guess a historical-code field
    # or mark a filing list as complete exchange-event coverage.
    spec=dict(group='kind_inventory',method='GET',url='https://kind.krx.co.kr/disclosure/details.do',params={'method':'searchDetailsMain'},purpose='Discover exact official historical-security/all-event form and page controls')
    body=collector.get(spec)
    atomic(collector.root/'kind_form_review_required.json',dict(status='OFFLINE_FORM_MAPPING_REQUIRED',request_id=request_id(spec),sha256=sha(body),raw_private=True,inventory_complete=False,followups_allowed=False))
    return dict(status='PARTIAL_INVENTORY_FORM_MAPPING_REQUIRED',inventory_complete=False,remaining=collector.remaining(),
                source_HTTP_charged=len(collector.state['requests']),source_responses_observed=sum('body_path'in r for r in collector.state['requests']),
                new_financial_eligibility=0)
