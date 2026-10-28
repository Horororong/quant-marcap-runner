"""Offline B route/response preparation. No transport, lease mutation or dispatch.

Used to validate a final remaining-lease plan against retained evidence. A parsed
response is not financial/PIT admission. Existing Collector HOLD is not cleared.
"""
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
from xml.etree import ElementTree

from bounded_official_evidence import Stop, DataUnavailable, raw, sha, request_id, validate_grant, validate_response

MEMBERS = {'000500': ('00104768', '가온전선'),
           '007160': ('00124799', '사조산업'),
           '049720': ('00336297', '고려신용정보')}
KRX_DAILY = {'https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd',
             'https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd'}


class SourceGap(DataUnavailable):
    """Documented absent/unsupported data: isolate scope, never certify no-event."""


def route_period_check(url, requested_date):
    """Only the two officially documented daily services are established here."""
    if url not in KRX_DAILY:
        raise SourceGap('UNVERIFIED_MARKET_ROUTE_NOT_EXECUTABLE')
    dt = datetime.strptime(requested_date, '%Y%m%d').date()
    if dt < datetime(2010, 1, 4).date():
        raise SourceGap('DOCUMENTED_KRX_START_20100104_NO_HTTP')
    return {'documented_period_supported': True, 'actual_data_verified': False}


def _json(body):
    try:
        obj = json.loads(body)
        if not isinstance(obj, dict):
            raise ValueError()
        return obj
    except (ValueError, TypeError, UnicodeError):
        raise Stop('MALFORMED_JSON_NOT_DATA') from None


def dart_page(spec, body):
    """Strict official list contract; 013 is a gap, not a complete empty filing list."""
    o = _json(body)
    status = o.get('status')
    if status == '013':
        raise SourceGap('DART_NO_DATA_KNOWN_Q3_NOT_RECOVERED')
    if status != '000':
        # Includes key/IP/quota/access failures: never catch as a data gap.
        raise Stop('DART_SERVICE_STATUS_' + str(status) + '_NO_RETRY')
    p = spec['params']
    try:
        page, pages, count, size = [int(o[k]) for k in
                                    ('page_no', 'total_page', 'total_count', 'page_count')]
        rows = o['list']
    except (KeyError, ValueError, TypeError):
        raise Stop('DART_COUNTS_MISSING_OR_INVALID') from None
    if size != 100 or page != int(p['page_no']) or count < 1 or pages != (count + 99)//100:
        raise Stop('DART_COUNTS_OR_PAGE_CONTRADICTION')
    if pages > 2:
        raise SourceGap('DART_MORE_THAN_TWO_PAGES_SCOPE_INCOMPLETE')
    if not 1 <= page <= pages or not isinstance(rows, list) or len(rows) != min(100, count - (page-1)*100):
        raise Stop('DART_PAGE_ROWS_INCOMPLETE')
    receipts = []
    for r in rows:
        receipt, date = r.get('rcept_no', ''), r.get('rcept_dt', '')
        if (r.get('corp_code') != p['corp_code'] or
                not re.fullmatch(r'\d{14}', receipt) or not re.fullmatch(r'\d{8}', date) or
                not p['bgn_de'] <= date <= p['end_de'] or receipt[:8] != date):
            raise Stop('DART_ISSUER_RECEIPT_DATE_MISMATCH')
        receipts.append(receipt)
    if len(set(receipts)) != len(receipts):
        raise Stop('DART_DUPLICATE_ROWS')
    return dict(page_no=page, total_page=pages, total_count=count, rows=rows,
                security=spec['security'], corp_code=p['corp_code'],
                request_id=request_id(spec), response_sha256=sha(body))


def close_pages(pages, *, known_receipt=None, kind=False):
    """Close one issuer only after all pages, counts, source hashes and IDs agree."""
    if not pages:
        raise SourceGap('NO_INVENTORY_PAGES')
    count, total = pages[0]['total_count'], pages[0]['total_page']
    if len({(p.get('security'), p.get('corp_code')) for p in pages}) != 1:
        raise Stop('INVENTORY_CROSS_ISSUER_PAGES')
    if ({p['page_no'] for p in pages} != set(range(1, total+1)) or len(pages) != total or
            any(p['total_count'] != count or p['total_page'] != total for p in pages)):
        raise Stop('INVENTORY_PAGINATION_INCOMPLETE_OR_CONTRADICTORY')
    ids = [r['receipt'] if kind else r['rcept_no'] for p in pages for r in p['rows']]
    if len(ids) != count or len(set(ids)) != count:
        raise Stop('INVENTORY_MISSING_OR_DUPLICATE_RECEIPTS')
    if known_receipt and known_receipt not in ids:
        raise SourceGap('KNOWN_Q3_MISSING_FROM_INVENTORY')
    if not ids:
        raise SourceGap('EMPTY_LIST_NOT_HISTORICAL_COVERAGE_PROOF')
    return dict(complete=True, receipts=ids, pages=pages, source_sha256=sha(raw(pages)),
                financial_eligible=False)


class FormNames(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.names = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'searchForm':
            self.active = a.get('method', '').lower() == 'post'
        if self.active and tag in {'input', 'select'} and a.get('name'):
            self.names.add(a['name'])
    def handle_endtag(self, tag):
        if tag == 'form': self.active = False


def kind_form_contract(body):
    text = body.decode('utf-8', errors='strict')
    parser = FormNames(); parser.feed(text)
    needed = {'method', 'forward', 'currentPageSize', 'pageIndex', 'fromDate', 'toDate',
              'searchCodeType', 'repIsuSrtCd', 'searchCorpName', 'oldSearchCorpName',
              'reportNm', 'reportNmTemp', 'marketType', 'orderMode', 'orderStat'}
    if (not needed <= parser.names or not all(s in text for s in
            ('searchDetailsSub', 'details_sub', '/disclosure/details.do',
             '"A"+repIsuSrtCd', '조회기간은 3년 이내만 가능합니다.'))):
        raise Stop('KIND_FORM_CONTRACT_CHANGED_OR_NOT_PROVED')
    return dict(form_sha256=sha(body), field_names=sorted(parser.names),
                request_method='POST', historical_2009_data_verified=False)


def kind_query(stock, form, page=1):
    if stock not in MEMBERS or page not in (1, 2):
        raise Stop('KIND_FIXED_ISSUER_OR_PAGE_SCOPE')
    params = dict(method='searchDetailsSub', forward='details_sub', currentPageSize='100',
                  pageIndex=str(page), orderMode='0', orderStat='D', fromDate='2009-11-01',
                  toDate='2011-04-30', searchCodeType='char', repIsuSrtCd='A'+stock,
                  searchCorpName=MEMBERS[stock][1], oldSearchCorpName=MEMBERS[stock][1],
                  reportNm='', reportNmTemp='', marketType='')
    if not set(params) <= set(form['field_names']):
        raise Stop('KIND_PARAMETERS_NOT_IN_RETAINED_FORM')
    # All declared filing categories remain unfiltered; no hidden title filter.
    params.update({k: '' for k in form['field_names'] if re.fullmatch(r'p?DisclosureType\d+|disclosureType\d+', k)})
    return dict(method='POST', url='https://kind.krx.co.kr/disclosure/details.do',
                params=params, security=stock, group='kind_inventory',
                purpose='All event classes for fixed company and full approved interval',
                form_sha256=form['form_sha256'],
                required_headers={'X-Requested-With': 'XMLHttpRequest'},
                historical_data_status='MUST_VALIDATE_ACTUAL_RESPONSE')


def kind_page(spec, body):
    """Observed response has 5-digit UI company IDs, not 6-digit quote codes.

    Require exact company name AND explicit expected UI ID. This validates the
    query response only; it does NOT assert historical security identity/PIT.
    """
    if not body.strip(): raise SourceGap('KIND_EMPTY_BODY_NOT_DATA')
    text = body.decode('utf-8', errors='strict')
    if re.search(r'captcha|접근.*(?:차단|제한)|비정상.*접근|로그인이 필요', text, re.I):
        raise Stop('KIND_ACCESS_RESTRICTION_NO_RETRY')
    m = re.search(r'전체\s*<em>\s*([\d,]+)\s*</em>\s*건\s*:\s*<strong>\s*(\d+)\s*</strong>\s*/\s*(\d+)', text)
    if not m: raise Stop('KIND_TOTAL_AND_PAGE_NOT_PROVED')
    count, page, pages = [int(x.replace(',', '')) for x in m.groups()]
    if count == 0: raise SourceGap('KIND_ZERO_RESULTS_NOT_NO_ACTION_CERTIFICATE')
    if pages != (count + 99)//100 or page != int(spec['params']['pageIndex']):
        raise Stop('KIND_COUNT_PAGE_CONTRADICTION')
    if pages > 2: raise SourceGap('KIND_PAGES_EXCEED_PER_ISSUER_BOUND')
    stock = spec['security']; expected_name = spec['params']['searchCorpName']
    rows = []
    for row in re.findall(r'<tr\b.*?</tr>', text, re.S | re.I):
        receipt = re.search(r"openDisclsViewer\(['\"](\d{14})['\"]", row)
        if not receipt: continue
        issuer = re.search(r"companysummary_open\(['\"](\d+)['\"]", row)
        company = re.search(r"<a[^>]*id=[\"']companysum[\"'][^>]*>(.*?)</a>", row, re.S)
        name = unescape(re.sub('<[^>]+>', '', company.group(1))).strip() if company else ''
        date = re.search(r'\b(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}', row)
        if (not issuer or issuer.group(1) != stock[:5] or name != expected_name or not date or
                not spec['params']['fromDate'] <= date.group(1) <= spec['params']['toDate']):
            raise Stop('KIND_RETURNED_ISSUER_OR_DATE_MISMATCH')
        rows.append(dict(receipt=receipt.group(1), security=stock, date=date.group(1),
                         source_literal=row, ui_company_id=issuer.group(1)))
    if len(rows) != min(100, count - (page-1)*100):
        raise Stop('KIND_PARSED_ROWS_NOT_TOTAL')
    if len({r['receipt'] for r in rows}) != len(rows): raise Stop('KIND_DUPLICATE_ROWS')
    return dict(page_no=page, total_page=pages, total_count=count, rows=rows, security=stock,
                request_id=request_id(spec), response_sha256=sha(body),
                historical_identity_certified=False)


def independent_branches(branches):
    """Narrow gap isolation. Auth, quota, corruption, transport and budget stop all.

    Callbacks must use the existing bounded/private transport when integrated.
    This preparation module contains no network or retry implementation.
    """
    results = {}
    for name, action in branches:
        try:
            results[name] = dict(status='OBSERVED', evidence=action())
        except SourceGap as exc:
            results[name] = dict(status='SOURCE_GAP', reason=str(exc))
    return dict(branches=results, collection_complete=False, financial_eligible=False)


def document_response(spec, body):
    """OpenDART200 can be an XML error envelope instead of the promised ZIP."""
    if not body.startswith(b'PK'):
        try:
            status = ElementTree.fromstring(body).findtext('status')
        except ElementTree.ParseError:
            raise Stop('DOCUMENT_MALFORMED_OR_NOT_ZIP') from None
        if status in {'013', '014'}:
            raise SourceGap('DOCUMENT_ABSENT_' + status + '_NO_RETRY')
        raise Stop('DOCUMENT_SERVICE_STATUS_' + str(status) + '_NO_RETRY')
    validate_response(spec, body)  # existing path/size/CRC/exact receipt checks
    return dict(archive_integrity=True, response_sha256=sha(body), financial_eligible=False,
                issuer_period_version='REQUIRES_INDEPENDENT_REVIEW')


def remaining_plan(grant, ledger):
    validate_grant(grant)
    if ledger['approval_sha256'] != sha(raw(grant)):
        raise Stop('LEDGER_APPROVAL_MISMATCH')
    used_http, used_runs = len(ledger['requests']), len(ledger['executions'])
    if (used_http, used_runs) != (1, 1):
        raise Stop('REPLAN_CHECKPOINT_CHANGED_REASSESS_NO_RESET')
    return dict(
        status='BLOCKED_BEFORE_FINAL_LEASE', planning_error='API_HISTORY_START_NOT_CHECKED',
        authentication_setup='COMPLETE_DO_NOT_REPEAT',
        HTTP_remaining=36-used_http, executions_remaining=2-used_runs,
        expires_at=grant['expires_at'], retries=0, seconds=600, day_limit=1,
        inventory_remaining=14, conditional_remaining=21,
        executable_market_requests=[],
        document_branch_caps=dict(dart_inventory=6, kind_inventory=7, annual=3, event=18),
        document_branch_max_HTTP=34, unallocated_inventory_slot=1,
        accounting='No transfer of unused inventory slot into conditional/group caps',
        sequence=['Retained cache and checkpoint validation offline',
                  'Live shared-day/expiry/HOLD resolution before final lease',
                  'DART3 issuer page1, then needed page2 within6; gaps isolated',
                  'KIND form refresh<=1 only if required; cached form reuse first;3 queries and pages within7',
                  'Close all3 issuer+exchange inventories; freeze exact targets/evidence hashes',
                  'Read only frozen originals/viewer links within3annual+18event',
                  'Checkpoint before600s; originalB remains blocked without same-date market proof'],
        dispatched=False, ledger_changed=False, financial_publication='HOLD',
        blockers=['No verified official20091230 market route',
                  'Live adapter must integrate scoped gap isolation, KIND binding and receipt freeze',
                  'Last-lease plan needs typed diagnosis-bound HOLD transition; no automatic clear',
                  '600s cannot guarantee34requests at25s each plus private persistence',
                  'Unreviewed inventory targets cannot be guessed to finish within one lease'])
