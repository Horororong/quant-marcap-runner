"""Bounded standard-library OpenDART transport for the immutable offline kit.

No request URL/credential/body is logged. HTTPS proxy and CA settings remain
inherited. Connect, socket-read, wall-time and response-size budgets differ.
"""
import http.client
import hashlib
import json
import os
import socket
import ssl
import time
from pathlib import Path
from urllib import error, parse, request
import xml.etree.ElementTree as ET

class Timeout(RuntimeError): pass
class ConnectionError(RuntimeError): pass
class HTTPError(RuntimeError): pass

def preserve_error_response(content, receipt):
    """Preserve exact explicit service XML, never keys, URLs or arbitrary HTML."""
    try:
        root=ET.fromstring(content)
    except ET.ParseError:return
    status=root.findtext('status') if root.tag=='result' else None
    if not status:return
    progress('api_response',receipt=receipt,dart_status=status.strip())
    target=os.getenv('LEGACY_DART_RESPONSE_DIR')
    if not target:return
    key=os.getenv('DART_API_KEY','')
    if key and key.encode() in content:raise ValueError('CREDENTIAL_IN_RESPONSE_NOT_PRESERVED')
    folder=Path(target);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(receipt+'-'+hashlib.sha256(content).hexdigest()+'.xml')
    if not path.exists():
        with path.open('xb') as f:f.write(content);f.flush();os.fsync(f.fileno())

def progress(stage, **fields):
    allowed = {'receipt','attempt','http_status','dart_status','bytes','elapsed_seconds','checkpoint','run_id','stop_reason'}
    safe = {k:v for k,v in fields.items() if k in allowed}
    record = dict(stage=stage, monotonic=time.monotonic(), **safe)
    dest=os.getenv('LEGACY_DART_PROGRESS_FILE')
    if dest:
        path=Path(dest);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a') as f: f.write(json.dumps(record)+'\n');f.flush()
    print(json.dumps(record),flush=True)

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args): return None

class Response:
    def __init__(self, status, content, content_type=''):
        self.status_code=status;self.content=content;self.content_type=content_type
    @property
    def text(self): return self.content.decode('utf-8',errors='replace')
    def json(self): return json.loads(self.content)
    def raise_for_status(self):
        if self.status_code>=400: raise HTTPError('HTTP_STATUS_'+str(self.status_code))

def get(url, params=None, timeout=35, *, _opener=None):
    p=parse.urlparse(url)
    if p.scheme!='https' or p.hostname!='opendart.fss.or.kr' or not p.path.startswith('/api/'):
        raise ValueError('Unapproved DART endpoint')
    connect=10.0;read=15.0;wall=min(float(timeout),35.0)
    started=time.monotonic();limit=32*1024*1024
    class Connection(http.client.HTTPSConnection):
        def connect(self):
            super().connect();self.sock.settimeout(read)
    class Handler(request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(Connection,req,context=self._context,check_hostname=self._check_hostname)
    opener=_opener or request.build_opener(NoRedirect(),Handler(context=ssl.create_default_context()))
    target=url+('?' + parse.urlencode(params) if params else '')
    try:
        try: stream=opener.open(request.Request(target),timeout=min(connect,wall))
        except error.HTTPError as e: stream=e
        with stream as response:
            data=bytearray()
            while True:
                if time.monotonic()-started>=wall: raise Timeout('DART_RESPONSE_WALL_BUDGET')
                chunk=response.read1(65536) if hasattr(response,'read1') else response.read(65536)
                if not chunk: break
                data.extend(chunk)
                if len(data)>limit: raise ValueError('DART_RESPONSE_BYTE_BUDGET')
            return Response(response.code,bytes(data),response.headers.get('Content-Type',''))
    except (socket.timeout,TimeoutError): raise Timeout('DART_SOCKET_TIMEOUT') from None
    except error.URLError as e:
        if isinstance(e.reason,(socket.timeout,TimeoutError)): raise Timeout('DART_SOCKET_TIMEOUT') from None
        raise ConnectionError('DART_CONNECTION_ERROR') from None
    except (OSError, http.client.HTTPException): raise ConnectionError('DART_TRANSPORT_ERROR') from None
