"""Fixed three-company Q3 source transport, no parsing or financial publication.

Derived from the locally tested bounded collector. HTTP intents are persisted
before each request. It never exports a key or reads it back from a Secrets API.
"""
import datetime,hashlib,io,json,os,re,time,zipfile
from pathlib import Path
KST=datetime.timezone(datetime.timedelta(hours=9));UTC=datetime.timezone.utc
MAX_HTTP=12;MAX_SECONDS=600
FROZEN_41_SHA='7bfafadb83322a9c7e2d358fd3c0f9331784b7597770c133ed83fb3e78283904'
TARGETS=[{'name': '사조산업', 'stock': '007160', 'corp': '00124799', 'receipt': '20091116000562'}, {'name': '가온전선', 'stock': '000500', 'corp': '00104768', 'receipt': '20091116000251'}, {'name': '고려신용정보', 'stock': '049720', 'corp': '00336297', 'receipt': '20091113001077'}]
LIST_BASE=dict(bgn_de='20090101',end_de='20100430',pblntf_ty='A',last_reprt_at='N',page_count='100')
def sha(b):
    return hashlib.sha256(b).hexdigest()

def canonical(d):
    return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def operating_bytes(d):
    return (json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()

def atomic(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)

def gate(original, supp, cfg, active, now):
    if original.get('contract') != 'limited-source-observation-v1':
        raise ValueError('ORIGINAL_CONTRACT')
    runs = original['runs']
    attempts = runs + [s for r in runs for s in r.get('resume_segments', [])] + supp['attempts']
    today = now.astimezone(KST).date().isoformat()
    if any((r['day_kst'] == today for r in attempts)):
        raise ValueError('ONCE_PER_KST_DAY')
    if active:
        raise ValueError('ACTIVE_COLLECTION_WORKFLOW')
    rs = cfg['receipts']
    if len(rs) != 41 or sha(('\n'.join(rs) + '\n').encode()) != FROZEN_41_SHA:
        raise ValueError('FY_FROZEN_ORDER_CHANGED')
    original_attempts = runs + [s for r in runs for s in r.get('resume_segments', [])]
    if len(original_attempts) != 3 or sum((r['reserved_documents'] for r in runs)) > 300:
        raise ValueError('ORIGINAL_THREE_EXECUTIONS_OR_RESERVATIONS')
    if (original.get('first_review') or {}).get('status') != 'PASS_SOURCE_SAMPLE_NOT_POPULATION_CERTIFICATION':
        raise ValueError('ORIGINAL_SOURCE_REVIEW_REQUIRED')
    if supp['approval_id'] != 'finite41-20261023' or supp['original_runs_sha256'] != sha(operating_bytes(runs)):
        raise ValueError('FY_ORIGINAL_HISTORY_CHANGED')
    if supp['approval_sha256'] != sha(operating_bytes(cfg)):
        raise ValueError('FY_APPROVAL_BINDING_CHANGED')
    if supp.get('financial_publication') != 'HOLD' or supp.get('backtest_eligible') is not False or supp.get('investment_PIT') != '0/6':
        raise ValueError('FINANCIAL_GATE_CHANGED')
    if supp.get('phase') not in {'PAUSED', 'COMPLETE'} or original['phase'] not in {'PAUSED_QUEUE', 'OBSERVATION_COMPLETE'}:
        raise ValueError('EXISTING_SOURCE_LEASE_OR_FAILURE_HELD')
    complete = supp['completed_receipts']
    if complete != rs[:len(complete)] or supp.get('remaining_receipts') != rs[len(complete):] or len(complete) != len(set(complete)):
        raise ValueError('FY_CHECKPOINT_PREFIX')
    if original['last_checkpoint'] != (complete[-1] if complete else '20100331002063') or any((r not in original['completed_receipts'] for r in complete)):
        raise ValueError('FY_FINAL_CHECKPOINT')
    # Owner's latest instruction prioritizes Q3 at the next shared daily window.
    # Do not change the FY expiry, budget, histories or shared daily/failure gates.
    if len(complete) == 41 and (supp['phase'] != 'COMPLETE' or len(supp['attempts']) != 2):
        raise ValueError('FY_COMPLETION_STATE')
    if any((r.get('status') != 'COMPLETE' for r in supp['attempts'])):
        raise ValueError('FY_PRIOR_FAILURE_HELD')
    if sum((r['http_reserved'] for r in supp['attempts'])) > 82:
        raise ValueError('FY_BUDGET_CORRUPT')
    return 'OPEN'


class HTTPFailure(Exception):
    pass

class Budget:

    def __init__(self, state, path, clock=time.monotonic, persist=None, reserve_seconds=15):
        self.state = state
        self.path = path
        self.clock = clock
        self.started = clock()
        self.persist = persist or (lambda: atomic(self.path, self.state))
        self.reserve_seconds = reserve_seconds

    def remaining(self):
        return MAX_SECONDS - (self.clock() - self.started)

    def request(self, label, endpoint, params, key, transport):
        if self.state['HTTP_attempts'] >= MAX_HTTP:
            raise ValueError('HTTP_BUDGET_EXHAUSTED')
        if self.remaining() < self.reserve_seconds:
            raise ValueError('TIME_BUDGET_CHECKPOINT_SAVED')
        if endpoint not in {'list.json', 'document.xml'}:
            raise ValueError('UNAPPROVED_ENDPOINT')
        if any(k.lower() in {'crtfc_key','api_key','token','authorization'} for k in params):
            raise ValueError('AUTH_PARAMETER_MUST_NOT_BE_PERSISTED')
        self.state['HTTP_attempts'] += 1
        event = dict(number=self.state['HTTP_attempts'], label=label, endpoint=endpoint, source_url='https://opendart.fss.or.kr/api/'+endpoint, params=params, intent_recorded_at_utc=datetime.datetime.now(UTC).isoformat(), status='ATTEMPT_STARTED')
        self.state['requests'].append(event)
        self.persist()
        try:
            if self.remaining() < self.reserve_seconds:
                raise HTTPFailure('TIME_BUDGET_BEFORE_WIRE_INTENT_CHARGED')
            status, body = transport(endpoint, params, key, min(45, self.remaining() - 10))
            event.update(HTTP_status=status, response_bytes=len(body),response_received_at_utc=datetime.datetime.now(UTC).isoformat())
            if key.encode() in body:
                raise HTTPFailure('CREDENTIAL_ECHO_REJECTED')
            if status != 200:
                raise HTTPFailure('SOURCE_HTTP_' + str(status))
            event.update(status='RECEIVED', sha256=sha(body))
            return body
        except HTTPFailure as e:
            event.update(status='FAILED', reason=str(e))
            raise
        except Exception as e:
            event.update(status='FAILED', reason='TRANSPORT_' + type(e).__name__)
            raise HTTPFailure('TRANSPORT_' + type(e).__name__) from None
        finally:
            self.persist()

def live_transport(endpoint, params, key, timeout):
    # Same pinned, bounded, no-redirect standard-library transport as FY.
    # There is no fallback API or automatic retry. URL/key never enters state.
    from scripts import dart_http
    response = dart_http.get('https://opendart.fss.or.kr/api/' + endpoint,
                             dict(params, crtfc_key=key), timeout=timeout)
    return response.status_code, response.content

def validate_page(body, target, page):
    try:
        d = json.loads(body)
    except Exception:
        raise ValueError('INVALID_OFFICIAL_LIST_JSON') from None
    if d.get('status') != '000':
        raise ValueError('DART_LIST_STATUS_' + str(d.get('status', 'MISSING')))
    if int(d['page_no']) != page or int(d['page_count']) != 100 or (not 1 <= int(d['total_page']) <= 2):
        raise ValueError('OFFICIAL_LIST_PAGINATION_CAP_OR_MISMATCH')
    if any((x['corp_code'] != target['corp'] for x in d['list'])):
        raise ValueError('OFFICIAL_LIST_COMPANY_MISMATCH')
    return d

def confirm_receipt(pages, target):
    entries = [r for p in pages for r in p['list']]
    ids = [r['rcept_no'] for r in entries]
    if len(ids) != len(set(ids)) or len(entries) != int(pages[0]['total_count']):
        raise ValueError('OFFICIAL_LIST_INCOMPLETE_OR_DUPLICATE')
    exact = [r for r in entries if r['rcept_no'] == target['receipt']]
    if len(exact) != 1 or exact[0]['corp_code'] != target['corp'] or (not re.search('분기보고서\\s*\\(2009\\.09\\)', exact[0]['report_nm'])) or (exact[0]['rcept_dt'] > '20100430'):
        raise ValueError('EXPECTED_Q3_RECEIPT_NOT_PROVED')
    if exact[0]['rcept_dt']!=target['receipt'][:8]:raise ValueError('OFFICIAL_RECEIPT_DATE_MISMATCH')
    try:datetime.datetime.strptime(exact[0]['rcept_dt'],'%Y%m%d')
    except ValueError:raise ValueError('OFFICIAL_RECEIPT_DATE_INVALID')from None
    return dict(receipt=target['receipt'], official_original=exact[0], same_period_versions=[r for r in entries if re.search('분기보고서\\s*\\(2009\\.09\\)', r['report_nm'])], version_relationship='UNVERIFIED_UNTIL_ORIGINAL_REFERENCES_REVIEWED', semantic='UNREVIEWED', PIT='UNVERIFIED', engine_eligible=False)

def validate_archive(blob, target):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos = z.infolist()
            if len(infos) > 200 or sum((i.file_size for i in infos)) > 128 * 1024 * 1024:
                raise ValueError('ZIP_EXPANSION_CAP')
            if z.testzip() is not None:
                raise ValueError('ZIP_CRC')
            members = [dict(name=i.filename, bytes=i.file_size, sha256=sha(z.read(i))) for i in infos if not i.is_dir()]
            if not members:
                raise ValueError('ZIP_EMPTY')
            if any((Path(i['name']).is_absolute() or '..' in Path(i['name']).parts for i in members)):
                raise ValueError('ZIP_UNSAFE_PATH')
            primary = target['receipt'] + '.xml'
            if primary not in [m['name'] for m in members]:
                raise ValueError('ORIGINAL_PRIMARY_MEMBER_NOT_FOUND')
            raw = z.read(primary)
    except zipfile.BadZipFile:
        code = re.search(b'<status>\\s*(\\d{3})\\s*</status>', blob[:4096])
        if code:
            raise ValueError('DART_DOCUMENT_STATUS_' + code[1].decode('ascii')) from None
        raise ValueError('SOURCE_NOT_A_VALID_ZIP') from None
    for enc in ['utf-8', 'cp949', 'euc-kr']:
        try:
            text = raw.decode(enc)
            assert text.encode(enc) == raw
            break
        except (UnicodeError, AssertionError):
            continue
    else:
        raise ValueError('SOURCE_ENCODING')
    issuer = re.search('<COMPANY-NAME\\b[^>]*AREGCIK="(\\d{8})"[^>]*>([^<]+)', text[:4000])
    if not issuer or issuer[1] != target['corp']:
        raise ValueError('ORIGINAL_ISSUER_MISMATCH')
    return dict(archive_sha256=sha(blob), ZIP_CRC='PASS', members=members, original_issuer=issuer[2], semantic='UNREVIEWED', PIT='UNVERIFIED', engine_eligible=False)

def collect(root, budget, transport, key, cache, after_raw=None):
    docs = []
    for target in TARGETS:
        pages = []
        for page in [1, 2]:
            params = dict(LIST_BASE, corp_code=target['corp'], page_no=str(page))
            cache_file = cache / (target['corp'] + '-list' + str(page) + '.json')
            proof_file = cache_file.with_suffix('.proof.json')
            body = None
            cached_proof = None
            if cache_file.is_file() and proof_file.is_file():
                proof = json.loads(proof_file.read_text())
                cached = cache_file.read_bytes()
                if proof.get('params') == params and proof.get('sha256') == sha(cached) and (proof.get('endpoint') == 'list.json'):
                    body = cached
                    cached_proof = proof
            if body is None:
                body = budget.request(target['corp'] + '-list' + str(page), 'list.json', params, key, transport)
                collected_at = budget.state['requests'][-1]['response_received_at_utc']
            else:
                collected_at = cached_proof.get('observed_at_utc')
            # Reused metadata must travel with reused originals too. A cache
            # hit is not a new HTTP observation or a newly known collection time.
            f = root / 'metadata' / cache_file.name
            f.parent.mkdir(exist_ok=True)
            f.write_bytes(body)
            atomic(f.with_suffix('.proof.json'),dict(params=params,endpoint='list.json',source_url='https://opendart.fss.or.kr/api/list.json',sha256=sha(body),observed_at_utc=collected_at,cache_reused=cached_proof is not None,copied_at_utc=datetime.datetime.now(UTC).isoformat()))
            d = validate_page(body, target, page)
            pages.append(d)
            if page >= int(d['total_page']):
                break
        official = confirm_receipt(pages, target)
        atomic(root / (target['receipt'] + '-official.json'), official)
        docs.append((target, official))
    for target, official in docs:
        cache_file = cache / (target['receipt'] + '.zip')
        proof_file = cache_file.with_suffix('.proof.json')
        blob = None
        cached_provenance = None
        if cache_file.is_file() and proof_file.is_file():
            proof = json.loads(proof_file.read_text())
            cached = cache_file.read_bytes()
            if proof.get('receipt') == target['receipt'] and proof.get('sha256') == sha(cached):
                blob = cached
                cached_provenance = proof.get('request_provenance')
        downloaded = blob is None
        if downloaded:
            blob = budget.request(target['receipt'], 'document.xml', dict(rcept_no=target['receipt']), key, transport)
            event=budget.state['requests'][-1]
            assert event['endpoint']=='document.xml'and event['params']==dict(rcept_no=target['receipt'])
            provenance=dict(source_url=event['source_url'],params=event['params'],intent_recorded_at_utc=event['intent_recorded_at_utc'],collected_at_utc=event['response_received_at_utc'],collection_time_status='RESPONSE_RECEIVED_UTC',cache_reused=False)
        else:
            provenance=cached_provenance or dict(source_url='https://opendart.fss.or.kr/api/document.xml',params=dict(rcept_no=target['receipt']),collected_at_utc=None,collection_time_status='UNKNOWN_FOR_LEGACY_CACHE',cache_reused=True)
        check = validate_archive(blob, target)
        hints_path = cache.parent / 'LEGACY_SOURCE_HINTS.json'
        hints = json.loads(hints_path.read_text()).get(target['receipt'], {}) if hints_path.is_file() else {}
        expected = hints.get('legacy_archive_sha256_hints', [])
        check['legacy_archive_sha256_hints'] = expected
        check['legacy_archive_match'] = 'MATCH' if check['archive_sha256'] in expected else 'DIFFERENT_UNVERIFIED_NO_OLD_OVERWRITE' if expected else 'NO_PRIOR_FINGERPRINT'
        f = root / (target['receipt'] + '-' + check['archive_sha256'] + '.zip')
        if f.exists():
            raise ValueError('NEW_OUTPUT_COLLISION')
        f.write_bytes(blob)
        proof = root / (target['receipt'] + '-source.json')
        atomic(proof, dict(target=target, downloaded=downloaded, source=check, official=official,request_provenance=provenance))
        budget.state['completed_receipts'].append(target['receipt'])
        budget.state['new_raw_documents'] += int(downloaded)
        atomic(budget.path, budget.state)
        if after_raw:
            after_raw(target, f, proof)
    return docs
