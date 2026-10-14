"""Six specifically inventoried documents, native Actions auth, no list queries.

No retries; raw errors and ZIPs are retained after credential-echo checks.
Financial parsing and operating datasets are deliberately not imported.
"""
import argparse, hashlib, io, json, os, re, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error, parse
import xml.etree.ElementTree as ET

HOME = Path(__file__).resolve().parent
REPO = HOME.parents[2]
MAX_DOCUMENTS = 20
MAX_BYTES = 8 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
MAX_SECONDS = 300

class Stop(Exception):
    def __init__(self, kind, http=None, dart=None):
        self.kind, self.http, self.dart = kind, http, dart
        super().__init__(kind)

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Stop('REDIRECT_BLOCKED', code)

def fetch(receipt, key):
    url = 'https://opendart.fss.or.kr/api/document.xml?' + parse.urlencode({'rcept_no': receipt, 'crtfc_key': key})
    try:
        with request.build_opener(NoRedirect()).open(request.Request(url), timeout=25) as response:
            return response.status, response.read(MAX_BYTES + 1)
    except Stop:
        raise
    except error.HTTPError as exc:
        raise Stop('HTTP_FAILURE', exc.code) from None
    except Exception:
        raise Stop('TRANSPORT_FAILURE') from None

def atomic(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

def decode(raw):
    for encoding in ('utf-8', 'cp949', 'euc-kr'):
        try:
            value = raw.decode(encoding)
            if value.encode(encoding) == raw:
                return value
        except UnicodeError:
            pass
    raise Stop('UNDECODABLE_SOURCE', 200)

def echo_check(raw, key):
    if any(v in raw for v in (key.encode(), parse.quote(key, safe='').encode())):
        raise Stop('CREDENTIAL_ECHO_BLOCKED', 200)
    text = decode(raw)
    # Detect escaped XML/JSON echoes as well as literal credentials.
    try:
        structural = re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)', '&amp;', text)
        xml_text = ''.join(ET.fromstring(structural).itertext()) if text.lstrip().startswith('<') else ''
    except ET.ParseError:
        xml_text = ''
    if key in text or key in xml_text:
        raise Stop('CREDENTIAL_ECHO_BLOCKED', 200)
    try:
        if key in json.dumps(json.loads(text), ensure_ascii=False):
            raise Stop('CREDENTIAL_ECHO_BLOCKED', 200)
    except (ValueError, TypeError):
        pass

def validate(payload, key, corp):
    if len(payload) > MAX_BYTES:
        raise Stop('RESPONSE_SIZE_LIMIT', 200)
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        echo_check(payload, key)
        try:
            root = ET.fromstring(decode(payload))
            status = root.findtext('status', '')
        except ET.ParseError:
            raise Stop('INVALID_RESPONSE', 200) from None
        if not re.fullmatch(r'\d{3}', status):
            raise Stop('INVALID_DART_STATUS', 200)
        return {'kind': 'DART_ERROR', 'dart_status': status, 'members': []}
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        info = z.infolist()
        if not info or sum(x.file_size for x in info) > MAX_EXPANDED:
            raise Stop('ARCHIVE_EXPANSION_LIMIT', 200)
        if z.testzip() is not None:
            raise Stop('ARCHIVE_CRC_FAILURE', 200)
        members = []; identities = []
        for member in info:
            if member.is_dir():
                continue
            raw = z.read(member)
            # Official document API serves XML members; other formats are held.
            echo_check(raw, key)
            structural = re.sub(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)', '&amp;', decode(raw))
            try:
                root = ET.fromstring(structural)
            except ET.ParseError:
                raise Stop('INVALID_DOCUMENT_XML', 200) from None
            company = root.find('COMPANY-NAME')
            if company is not None:
                identities.append(company.get('AREGCIK', ''))
            members.append({'name': member.filename, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        if not identities or any(x != corp for x in identities):
            raise Stop('DOCUMENT_CORP_MISMATCH', 200)
        return {'kind': 'ZIP', 'dart_status': None, 'members': members, 'corp_codes': identities}

def load_plan(path):
    rows = json.loads(path.read_text())['documents']
    if not 1 <= len(rows) <= MAX_DOCUMENTS or len({r['rcept_no'] for r in rows}) != len(rows):
        raise Stop('INVALID_PLAN')
    cached = json.loads((REPO/'docs/audits/historical-pit-stage4-20261014/results/source_facts.json').read_text())
    cached_receipts = {r['rcept_no'] for r in cached}
    history = {}
    for p in (REPO/'docs/audits/dart-history-stage5-20261014/results/raw').glob('*.json'):
        for r in json.loads(p.read_text())['list']:
            history[r['rcept_no']] = r
    for row in rows:
        if not re.fullmatch(r'\d{14}', row['rcept_no']) or not re.fullmatch(r'\d{8}', row['corp_code']):
            raise Stop('INVALID_IDENTITY')
        source = history.get(row['rcept_no'])
        if row['rcept_no'] in cached_receipts or not source or source['corp_code'] != row['corp_code']:
            raise Stop('UNPROVEN_OR_ALREADY_CACHED_RECEIPT')
    return rows

def acquire(rows, key, output, transport=fetch, clock=time.monotonic):
    if output.exists():
        raise Stop('EXISTING_OUTPUT_REQUIRES_REVIEW')
    output.mkdir(parents=True); (output/'raw').mkdir()
    state = {'code_sha': os.getenv('GITHUB_SHA', 'LOCAL_TEST'), 'checked_at': datetime.now(timezone.utc).isoformat(),
             'status': 'STARTED', 'requests': 0, 'completed': [], 'responses': [], 'max_new_documents': MAX_DOCUMENTS,
             'endpoint': 'https://opendart.fss.or.kr/api/document.xml', 'backtest_eligible': False}
    atomic(output/'run_state.json', state); started = clock()
    try:
        if not key or not re.fullmatch(r'[A-Za-z0-9]{40}', key):
            raise Stop('AUTH_ENV_MISSING_OR_INVALID')
        if not 1 <= len(rows) <= MAX_DOCUMENTS or len({x['rcept_no'] for x in rows}) != len(rows):
            raise Stop('INVALID_PLAN')
        for row in rows:
            if clock()-started > MAX_SECONDS:
                raise Stop('TIME_LIMIT')
            state['active_receipt'] = row['rcept_no']; state['requests'] += 1
            atomic(output/'run_state.json', state)
            http, payload = transport(row['rcept_no'], key)
            if http != 200:
                raise Stop('HTTP_FAILURE', http)
            result = validate(payload, key, row['corp_code'])
            suffix = '.zip' if result['kind'] == 'ZIP' else '.xml'
            filename = 'raw/' + row['rcept_no'] + suffix
            (output/filename).write_bytes(payload)
            state['responses'].append({**row, **result, 'http_status': http, 'file': filename,
                                      'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                                      'received_at': datetime.now(timezone.utc).isoformat()})
            atomic(output/'run_state.json', state)
            if result['kind'] != 'ZIP':
                raise Stop('DART_FAILURE', http, result['dart_status'])
            state['completed'].append(row['rcept_no'])
        state['status'] = 'COMPLETE'
    except Stop as exc:
        state['status'] = 'STOPPED'
        state['error'] = {'kind': exc.kind, 'http_status': exc.http, 'dart_status': exc.dart}
    atomic(output/'run_state.json', state); atomic(output/'response_manifest.json', state['responses'])
    return state

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        state = acquire(load_plan(HOME/'document_plan.json'), os.getenv('DART_API_KEY', ''), args.output)
    except Stop as exc:
        print(json.dumps({'status':'STOPPED','error':exc.kind})); return 2
    print(json.dumps({k: state[k] for k in ['status', 'requests', 'completed']}))
    if state['status'] != 'COMPLETE':
        print(json.dumps(state['error'])); return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
