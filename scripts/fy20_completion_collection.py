"""Proposed finite FY20 continuation. No source admission or automatic retry.

Source authority is absent until an explicitly approved private queue is bound.
Original 40 requests/two leases remain in the original ledger; budgets never reset.
"""
import copy,json,re,uuid,io,zipfile
from datetime import datetime
from urllib.parse import urlsplit,urljoin,urlunsplit,parse_qsl
from html import unescape
from bounded_official_evidence import Collector,Stop,Deadline,DataUnavailable,raw,sha,request_id,stamp,day,check_history
from fy20_metadata_collection import FYCollector
from b_official_request_preparation import kind_form_contract,kind_page,document_response

AMENDMENT='fy20-completion-20261103'
MEMBERS={'001430':'00106669','002380':'00105271','003200':'00146269','006360':'00120030','006390':'00164672','009540':'00164830','011790':'00139889','014590':'00106456','017370':'00142883','025850':'00160612','037320':'00261212','037550':'00314000','046440':'00405278','058450':'00146427','060720':'00378628','066910':'00306870','069920':'00426068','081000':'00508274','088010':'00548865','093230':'00480950'}
PURPOSES={'identity_calendar':{'identity_catalog','identity_document','calendar_catalog'},'selected_holding':{'issuer_inventory','exchange_inventory','event_original','execution_reference'}}

def evidence_text(body):
    if body.startswith(b'%PDF'):return ''  # preserve for offline review, never certify by binary decoding
    if body.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(body))as z:
            return '\n'.join(evidence_text(z.read(i))for i in z.namelist()if i.lower().endswith('.xml'))
    for encoding in ('utf8','cp949','euc-kr'):
        try:return body.decode(encoding,errors='strict')
        except UnicodeError:pass
    raise Stop('PARENT_SOURCE_ENCODING_UNVERIFIED')

def labeled_event_dates(text):
    plain=unescape(re.sub('<[^>]+>',' ',text))
    return {y+m.zfill(2)+d.zfill(2)for y,m,d in re.findall(r'(?:권리락일|배당락일|기준가격\s*적용일)\s*[:：]?\s*(2010)[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})',plain)}

def selected_dart_page(spec,body):
    o=json.loads(body)
    if o.get('status')=='013':raise DataUnavailable('SELECTED_ISSUER_EMPTY_NOT_NO_ACTION_CERTIFICATE')
    if o.get('status')!='000':raise Stop('DART_SERVICE_FAILURE_NO_RETRY')
    page,total,count=int(o['page_no']),int(o['total_page']),int(o['total_count']);rows=o.get('list',[])
    if total>2:raise DataUnavailable('SELECTED_ISSUER_PAGINATION_OVER_CAP')
    if (page!=int(spec['params']['page_no'])or total!=(count+99)//100 or total<1
        or len(rows)!=min(100,count-(page-1)*100)or len({r['rcept_no']for r in rows})!=len(rows)
        or any(r.get('corp_code')!=spec['params']['corp_code']or not re.fullmatch(r'\d{14}',r.get('rcept_no',''))
            or not '20091101'<=r.get('rcept_dt','')<='20110430'for r in rows)):
        raise Stop('DART_ISSUER_DATE_OR_PAGINATION_MISMATCH')
    return dict(page_no=page,total_page=total,total_count=count,rows=rows)

def validate_plan(amendment,plan):
    expected=dict(contract='fy20-completion-continuation-v1',approval_id=AMENDMENT,base_approval='fy20-asof-metadata-20261030',base_used_HTTP=40,base_used_executions=2,max_HTTP=70,additional_HTTP=0,additional_executions=2,run_seconds=600,max_retries=0,max_executions_per_KST_day=1,expires_at='2026-11-06T23:59:59+09:00',phase_caps={'identity_calendar':8,'selected_holding':22},signal='2010-04-30',proposed_fill='2010-05-03',end='2010-12-30',source_authority='PROPOSAL_ONLY_UNTIL_USER_APPROVES',financial_publication='HOLD',classification='RESEARCH_ONLY')
    if amendment!=expected:raise Stop('CONTINUATION_SCOPE_CHANGED')
    if plan.get('approval_id')!=AMENDMENT or plan.get('user_approved')is not True or plan.get('amendment_sha256')!=sha(raw(amendment)):
        raise Stop('NO_EXPLICIT_CONTINUATION_APPROVAL')
    if any(not re.fullmatch('[0-9a-f]{64}',plan.get(k,''))for k in ('original40_requests_sha256','original2_executions_sha256')):
        raise Stop('ORIGINAL_HISTORY_BINDING_REQUIRED')
    phase=plan.get('phase');targets=plan.get('targets',[])
    if phase not in PURPOSES or not targets or len(targets)>amendment['phase_caps'][phase]:raise Stop('PHASE_CAP_OR_EMPTY_PLAN')
    if len({request_id(s)for s in targets})!=len(targets):raise Stop('DUPLICATE_QUEUE')
    if phase=='selected_holding':
        selection=plan.get('selection',{})
        if (selection.get('status')!='PASS' or selection.get('declared_companies')!=20
            or set(selection.get('declared_codes',[]))!=set(MEMBERS)
            or selection.get('signal')!='2010-04-30' or selection.get('all_required_inputs_verified')is not True
            or not re.fullmatch('[0-9a-f]{64}',selection.get('selection_binding_sha256',''))
            or selection.get('proposed_fill_quote_tradable')is not True
            or len(selection.get('selected_codes',[]))!=1 or not set(selection['selected_codes'])<=set(MEMBERS)):
            raise Stop('VERIFIED_ALL20_SELECTION_AND_EXECUTABLE_FIRST_FILL_REQUIRED')
    return phase

class CompletionCollector(FYCollector):
    def __init__(self,root,base_grant,history,amendment,plan,form,**kwargs):
        self.phase=validate_plan(amendment,plan);self.amendment=amendment;self.plan=plan
        self.form=kind_form_contract(form);self.original_prefix=None
        super().__init__(root,base_grant,history,**kwargs)
        self.original_prefix=copy.deepcopy(self.state['requests'][:40])
        self.original_executions=copy.deepcopy(self.state['executions'][:2])
        if len(self.original_prefix)!=40 or len(self.original_executions)!=2:raise Stop('ORIGINAL40_TWO_HISTORY_REQUIRED')
        if sha(raw(self.original_prefix))!=plan['original40_requests_sha256']or sha(raw(self.original_executions))!=plan['original2_executions_sha256']:
            raise Stop('ORIGINAL_HISTORY_BINDING_MISMATCH')
        key=sha(raw(amendment));prior=self.state.get('completion_amendment_sha256')
        if prior and prior!=key:raise Stop('NO_CONTINUATION_REBIND')
        if len(self.state['executions'])>2 and not prior:raise Stop('UNBOUND_CONTINUATION_HISTORY')
        self.grant={**base_grant,'max_executions':4,'expires_at':amendment['expires_at'],
            'phase_limits':{**base_grant['phase_limits'],**amendment['phase_caps']},
            'group_limits':{**base_grant['group_limits'],'completion_evidence':30}}
        self.state['completion_amendment_sha256']=key
    def validate_held_state(self):
        if self.state.get('status')in {'HOLD_FAILURE','RUNNING'}:raise Stop('PREVIOUS_FAILURE_OR_INTERRUPTED_RUN_HELD')
        if (len(self.state.get('requests',[]))<40 or len(self.state.get('executions',[]))<2
            or sha(raw(self.state['requests'][:40]))!=self.plan['original40_requests_sha256']
            or sha(raw(self.state['executions'][:2]))!=self.plan['original2_executions_sha256']):
            raise Stop('ORIGINAL_HISTORY_BINDING_MISMATCH')
    def phase_for(self,group):return self.phase
    def group_limit(self,group):return self.grant['group_limits'][group]
    def check_form(self,spec):pass  # exact retained form is checked in __init__/validate_spec
    def validate_spec(self,s):
        if s not in self.plan['targets']or s.get('group')!='completion_evidence'or s.get('purpose')not in PURPOSES[self.phase]:raise Stop('OUTSIDE_FROZEN_PRIVATE_QUEUE')
        if set(s)-{'group','method','url','params','purpose','security','parent_ids'}:raise Stop('UNKNOWN_REQUEST_FIELD')
        u=urlsplit(s['url']);p=s['params'];purpose=s['purpose'];stock=s.get('security')
        if self.phase=='identity_calendar'and purpose.startswith('identity_')and stock!='081000':raise Stop('ILJIN_ONLY_IDENTITY_REVIEW')
        if u.scheme!='https'or u.query or u.fragment or u.username or u.password or re.search('key|token|auth',str(p),re.I):raise Stop('SOURCE_URL_OR_SECRET_SCOPE')
        if self.phase=='selected_holding'and stock not in self.plan['selection']['selected_codes']:raise Stop('NONHOLDER_REQUEST_FORBIDDEN')
        parents=[];parent_urls=[];owned_parent=False;owned_texts=[];event_texts=[]
        for key in s.get('parent_ids',[]):
            body=self.cached(key)
            if body is None:raise Stop('PARENT_RESPONSE_MISSING')
            text=evidence_text(body);parents.append(text)
            parent=next(r['request']for r in self.state['requests']if r['id']==key)
            parent_urls.append(parent['url'])
            owned=bool(stock and(parent.get('security')==stock or parent.get('params',{}).get('corp_code')==MEMBERS.get(stock)))
            owned_parent|=owned
            if owned:
                owned_texts.append(text)
                if parent.get('purpose')=='event_original':event_texts.append(text)
        if u.hostname=='law.krx.co.kr':
            # Root discovers supported history. It is never a 2010 certificate.
            if purpose!='calendar_catalog'or s['method']!='GET':raise Stop('LAW_DISCOVERY_ONLY')
            if s['url']=='https://law.krx.co.kr/'and not p:pass
            else:
                literal=False
                for text,parent_url in zip(parents,parent_urls):
                    for href in re.findall(r'href=["\x27]([^"\x27]+)',text,re.I):
                        if not re.search(r'2010|history|연혁|개정',unescape(href),re.I):continue
                        target=urlsplit(urljoin(parent_url,unescape(href)));pairs=parse_qsl(target.query,keep_blank_values=True)
                        literal|=(target.scheme=='https'and target.hostname=='law.krx.co.kr'and target.path==u.path
                            and not target.fragment and len(pairs)==len(dict(pairs))and dict(pairs)==p)
                if not literal:raise Stop('LITERAL_HISTORY_LINK_REQUIRED')
        elif u.hostname=='kind.krx.co.kr'and u.path=='/disclosure/details.do':
            if s['method']!='POST'or stock not in MEMBERS:raise Stop('EXACT_KIND_QUERY_REQUIRED')
            if purpose=='identity_catalog':
                if stock!='081000'or p.get('fromDate')!='2010-03-31'or p.get('toDate')!='2010-04-30':raise Stop('ILJIN_DATED_CATALOG_ONLY')
            elif purpose=='exchange_inventory':
                if p.get('fromDate')!='2009-11-01'or p.get('toDate')!='2011-04-30':raise Stop('EXACT_HOLDING_INVENTORY_WINDOW')
            else:raise Stop('KIND_PURPOSE')
            allowed={'method','forward','currentPageSize','pageIndex','orderMode','orderStat','fromDate','toDate','searchCodeType','repIsuSrtCd','searchCorpName','oldSearchCorpName','reportNm','reportNmTemp','marketType'}
            allowed|={k for k in self.form['field_names']if re.fullmatch(r'p?DisclosureType\d+|disclosureType\d+',k)}
            if (set(p)-allowed or not set(p)<=set(self.form['field_names'])or p.get('method')!='searchDetailsSub'or p.get('forward')!='details_sub'
                or p.get('repIsuSrtCd')!='A'+stock or p.get('currentPageSize')!='100'or p.get('pageIndex')not in {'1','2'}
                or p.get('orderMode')!='0'or p.get('orderStat')!='D'or p.get('searchCodeType')!='char'
                or not p.get('searchCorpName')or p.get('oldSearchCorpName')!=p['searchCorpName']
                or any(p.get(k,'')for k in allowed if re.fullmatch(r'p?DisclosureType\d+|disclosureType\d+|reportNm|reportNmTemp|marketType',k))):raise Stop('KIND_FORM_SCOPE')
        elif u.hostname=='opendart.fss.or.kr'and u.path=='/api/list.json':
            expected=dict(corp_code=MEMBERS.get(stock),bgn_de='20091101',end_de='20110430',last_reprt_at='N',page_no=p.get('page_no'),page_count='100',sort='date',sort_mth='asc')
            if purpose!='issuer_inventory'or s['method']!='GET'or p!=expected or p['page_no']not in {'1','2'}:raise Stop('FULL_SELECTED_ISSUER_WINDOW_REQUIRED')
        elif u.hostname=='data-dbg.krx.co.kr':
            if (purpose!='execution_reference'or s['method']!='GET'or u.path not in {'/svc/apis/sto/stk_bydd_trd','/svc/apis/sto/ksq_bydd_trd'}or set(p)!={'basDd'}or not '20100104'<=p['basDd']<='20101230'or not owned_parent):raise Stop('SUPPORTED_DATED_REFERENCE_REQUIRED')
            if p['basDd']not in set().union(*(labeled_event_dates(t)for t in event_texts)):raise Stop('OFFICIAL_EVENT_DATE_LITERAL_REQUIRED')
        else:
            if purpose not in {'event_original','identity_document'}or not owned_parent or s['method']!='GET':raise Stop('UNREVIEWED_ROUTE')
            if u.hostname=='opendart.fss.or.kr'and u.path=='/api/document.xml':
                rc=p.get('rcept_no','')
                receipts=set()
                for text in owned_texts:
                    try:o=json.loads(text)
                    except ValueError:continue
                    receipts|={r['rcept_no']for r in o.get('list',[])if r.get('corp_code')==MEMBERS[stock]}
                if set(p)!={'rcept_no'}or not re.fullmatch(r'\d{14}',rc)or rc not in receipts:raise Stop('RECEIPT_NOT_IN_RETAINED_LIST')
            elif u.hostname=='kind.krx.co.kr':
                if not(u.path=='/common/disclsviewer.do'or u.path.startswith('/external/')):raise Stop('KIND_SOURCE_PATH')
                literal=any(s['url']in unescape(t)or(str(p.get('acptNo','NONMATCH'))in t and p.get('method')=='searchInitInfo')for t in owned_texts)
                if not literal:
                    from b2_official_execution import viewer_children
                    for key in s.get('parent_ids',[]):
                        prior=next(r['request']for r in self.state['requests']if r['id']==key)
                        literal|=any(c['url']==s['url']and c['params']==p for c in viewer_children(prior,self.cached(key)))
                if not literal:raise Stop('LITERAL_KIND_PARENT_REQUIRED')
            else:raise Stop('UNAPPROVED_SOURCE_HOST')
        return request_id(s)
    def start(self):
        if self.execution:return
        if not self.source_ready:raise Stop('AUTH_NETWORK_PRIVATE_NOT_READY')
        now=self.now();check_history(self.history,now)
        if now>datetime.fromisoformat(self.amendment['expires_at']):raise Stop('CONTINUATION_EXPIRED')
        if len(self.state['executions'])>=4:raise Stop('CONTINUATION_EXECUTIONS_EXHAUSTED')
        if any(e['day_kst']==day(now)for e in self.state['executions']):raise Stop('ONCE_PER_KST_DAY')
        if any(e.get('completion_phase')==self.phase for e in self.state['executions']):raise Stop('PHASE_EXECUTION_ALREADY_USED')
        self.execution=dict(id=uuid.uuid4().hex,day_kst=day(now),started_at=stamp(now),status='RUNNING',completion_phase=self.phase,history_main_sha=self.history['main_sha'],history_state_sha256=self.history['state_sha256'])
        self.state['executions'].append(self.execution);self.state['status']='RUNNING';self.save()
    def get(self,spec):
        key=self.validate_spec(spec)
        if self.cached(key)is None:
            category=lambda p:('identity'if p.startswith('identity_')else p)
            caps={'identity':5,'calendar_catalog':3,'issuer_inventory':2,'exchange_inventory':2,'event_original':14,'execution_reference':4}
            label=category(spec['purpose']);used=sum(r['group']=='completion_evidence'and category(r['request']['purpose'])==label for r in self.state['requests'])
            if used>=caps[label]:raise DataUnavailable('CATEGORY_CAP_PENDING')
        return Collector.get(self,spec)
    def validate_body(self,s,b):
        if s['purpose']=='issuer_inventory':selected_dart_page(s,b)
        elif s['purpose']in {'identity_catalog','exchange_inventory'}:kind_page(s,b)
        elif s['url'].endswith('/api/document.xml'):document_response({**s,'receipt':s['params']['rcept_no']},b)
        elif not b.strip():raise DataUnavailable('EMPTY_RESPONSE_NOT_DATA')
        elif re.search(rb'captcha|access denied|invalid.*key',b,re.I):raise Stop('SOURCE_ACCESS_FAILURE')
        elif s['purpose']=='execution_reference':
            o=json.loads(b);rows=o.get('OutBlock_1',[])
            if not rows or not all(str(r.get('BAS_DD'))==s['params']['basDd']for r in rows)or not any(r.get('ISU_CD')==s['security']for r in rows):raise DataUnavailable('DATED_MARKET_EMPTY_OR_WRONG_DATE')
    def freeze_child(self,s):
        if len(self.plan['targets'])>=self.amendment['phase_caps'][self.phase]:raise DataUnavailable('LITERAL_CHILD_CAP_PENDING')
        prior=list(self.plan['targets']);self.plan['targets'].append(s)
        try:self.validate_spec(s)
        except BaseException:self.plan['targets']=prior;raise
        self.state.setdefault('completion_frozen_children',[]).append(copy.deepcopy(s));self.save()
    def save(self):
        if self.original_prefix is not None:
            if self.state['requests'][:40]!=self.original_prefix or self.state['executions'][:2]!=self.original_executions:raise Stop('ORIGINAL_HISTORY_MUTATION')
        return super().save()

def collect_queue(c):
    """Literal child discovery is bounded and never a financial attestation."""
    todo=list(c.plan['targets']);seen={request_id(s)for s in todo};gaps=[];observed=0;before=len(c.state['requests'])
    inventories_frozen=False
    while todo or(c.phase=='selected_holding'and not inventories_frozen):
        if not todo:
            inventories_frozen=True
            try:children=closed_holding_targets(c)
            except DataUnavailable as exc:gaps.append(str(exc));break
            for child in children:
                key=request_id(child)
                if key in seen:continue
                try:c.freeze_child(child)
                except DataUnavailable as exc:gaps.append(str(exc));break
                seen.add(key);todo.append(child)
            if not todo:break
        s=todo.pop(0)
        try:body=c.get(s)
        except DataUnavailable as exc:gaps.append(str(exc));continue
        observed+=1;parent=request_id(s);children=[]
        if s['purpose']=='calendar_catalog':
            text=evidence_text(body)
            for href in re.findall(r'href=["\x27]([^"\x27]+)',text,re.I):
                url=urljoin(s['url'],unescape(href))
                if re.search(r'2010|history|연혁|개정',unescape(href),re.I)and urlsplit(url).hostname=='law.krx.co.kr':
                    # Only a literal published link, never a guessed historical URL.
                    parts=urlsplit(url);pairs=parse_qsl(parts.query,keep_blank_values=True)
                    if parts.fragment or len(pairs)!=len(dict(pairs)):continue
                    children.append(dict(group='completion_evidence',method='GET',url=urlunsplit((parts.scheme,parts.netloc,parts.path,'','')),params=dict(pairs),purpose='calendar_catalog',parent_ids=[parent]))
        elif s['purpose']in {'identity_catalog','exchange_inventory'}:
            page=kind_page(s,body)
            if page['page_no']==1 and page['total_page']==2:
                children.append({**s,'params':{**s['params'],'pageIndex':'2'},'parent_ids':[parent]})
            if s['purpose']=='identity_catalog':
                for row in page['rows']:
                    if '사업보고서'in row['source_literal']:
                        children.append(dict(group='completion_evidence',method='GET',url='https://kind.krx.co.kr/common/disclsviewer.do',params=dict(method='searchInitInfo',acptNo=row['receipt']),purpose='identity_document',security='081000',parent_ids=[parent]))
        elif s['purpose']=='issuer_inventory':
            page=selected_dart_page(s,body)
            if page['page_no']==1 and page['total_page']==2:
                children.append({**s,'params':{**s['params'],'page_no':'2'},'parent_ids':[parent]})
        elif s['url'].startswith('https://kind.krx.co.kr/common/disclsviewer.do'):
            from b2_official_execution import viewer_children
            for ch in viewer_children(s,body):
                children.append(dict(group='completion_evidence',method='GET',url=ch['url'],params=ch['params'],purpose=s['purpose'],security=s['security'],parent_ids=[parent]))
        if s['purpose']=='event_original'and c.phase=='selected_holding':
            market=c.plan['selection'].get('market')
            if market in {'KOSPI','KOSDAQ'}:
                prefix='stk'if market=='KOSPI'else'ksq'
                for date in sorted(labeled_event_dates(evidence_text(body))):
                    children.append(dict(group='completion_evidence',method='GET',url='https://data-dbg.krx.co.kr/svc/apis/sto/'+prefix+'_bydd_trd',params={'basDd':date},purpose='execution_reference',security=s['security'],parent_ids=[parent]))
        for child in children:
            key=request_id(child)
            if key in seen:continue
            try:c.freeze_child(child)
            except DataUnavailable as exc:gaps.append(str(exc));break
            seen.add(key);todo.append(child)
    added=len(c.state['requests'])-before
    return dict(status='RAW_RESPONSES_PRESERVED_REVIEW_REQUIRED'if added else'NO_COLLECTION_CACHED_ONLY',observed_responses=observed,new_HTTP=added,source_gaps=gaps,
                financial_values_admitted=0,backtest_completed=False,financial_publication='HOLD')

def closed_holding_targets(c):
    """Freeze both complete catalogs before conditional document requests.

    Title matching selects source-review candidates only. Missing or unknown
    events remain unverified; this function can never certify an empty family.
    """
    stock=c.plan['selection']['selected_codes'][0];all_pages={}
    for purpose in ('issuer_inventory','exchange_inventory'):
        rs=[r for r in c.state['requests']if r.get('group')=='completion_evidence'and r['status']=='COMPLETE'and r['request'].get('purpose')==purpose and r['request'].get('security')==stock]
        parser=selected_dart_page if purpose=='issuer_inventory'else kind_page
        pages=[(r,parser(r['request'],c.cached(r['id'])))for r in rs]
        if not pages:raise DataUnavailable('HOLDING_INVENTORY_NOT_CLOSED')
        total=pages[0][1]['total_page'];count=pages[0][1]['total_count']
        if(len(pages)!=total or {p['page_no']for r,p in pages}!=set(range(1,total+1))
            or any(p['total_page']!=total or p['total_count']!=count for r,p in pages)
            or sum(len(p['rows'])for r,p in pages)!=count):raise DataUnavailable('HOLDING_INVENTORY_NOT_CLOSED')
        all_pages[purpose]=pages
    freeze=[dict(id=r['id'],sha256=r['sha256'])for pages in all_pages.values()for r,p in pages]
    c.state['completion_holding_inventory_freeze']=dict(stock=stock,pages=freeze,sha256=sha(raw(freeze)))
    c.save();targets=[]
    action=re.compile('배당|증자|감자|분할|합병|주식교환|주식이전|주식병합|주식분할|상장|매매거래|거래정지|거래재개|주권|권리|해산|회생|정리매매|주주총회')
    for r,p in all_pages['issuer_inventory']:
        for row in p['rows']:
            title=row['report_nm']
            if action.search(title)or('사업보고서'in title and'2010.12'in title):
                targets.append(dict(group='completion_evidence',method='GET',url='https://opendart.fss.or.kr/api/document.xml',params={'rcept_no':row['rcept_no']},purpose='event_original',security=stock,parent_ids=[r['id']]))
    # Prefer issuer originals; don't re-fetch exchange mirrors of ordinary
    # dividends. Exchange-only listing/rights/trading notices remain candidates.
    for r,p in all_pages['exchange_inventory']:
        for row in p['rows']:
            if re.search('추가상장|변경상장|매매거래|거래정지|거래재개|권리락|배당락|기준가격',row['source_literal']):
                targets.append(dict(group='completion_evidence',method='GET',url='https://kind.krx.co.kr/common/disclsviewer.do',params=dict(method='searchInitInfo',acptNo=row['receipt']),purpose='event_original',security=stock,parent_ids=[r['id']]))
    return targets
