"""Validated corpCode transport. No response text, URL query or credentials in errors."""
from __future__ import annotations

import io
import re
import time
import zipfile
import xml.etree.ElementTree as ET


class CorpCodeError(RuntimeError):
    def __init__(self, kind, *, status="", retryable=False, attempts=1):
        self.kind = kind
        self.status = status
        self.retryable = retryable
        self.attempts = attempts
        super().__init__(f"corpCode {kind}" + (f" status={status}" if status else "") + f" attempts={attempts}")


def parse_corp_code(payload):
    """Require a complete ZIP/XML company list; XML error bodies are not empty maps."""
    archive = io.BytesIO(payload)
    if not zipfile.is_zipfile(archive):
        try:
            root = ET.fromstring(payload)
        except (ET.ParseError, ValueError):
            raise CorpCodeError("invalid_response") from None
        status = (root.findtext("status") or "").strip()
        if not re.fullmatch(r"\d{3}", status):
            raise CorpCodeError("invalid_response")
        if status == "020":
            raise CorpCodeError("rate_limit", status=status)
        if status in {"010", "011", "012", "901"}:
            raise CorpCodeError("fatal_api", status=status)
        # Maintenance is explicit, but waiting repeatedly inside a bounded batch
        # does not fix it. Unknown/empty responses are never assumed transient.
        raise CorpCodeError("api_error", status=status)
    try:
        with zipfile.ZipFile(archive) as z:
            members = [name for name in z.namelist() if name.lower().endswith(".xml")]
            if len(members) != 1:
                raise CorpCodeError("invalid_archive")
            root = ET.fromstring(z.read(members[0]))
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError, OSError) as exc:
        if isinstance(exc, CorpCodeError):
            raise
        raise CorpCodeError("invalid_archive") from None
    rows = [{child.tag: child.text for child in node} for node in root.findall("list")]
    if root.tag != "result" or not rows:
        raise CorpCodeError("invalid_company_list")
    if any(not re.fullmatch(r"\d{8}", (row.get("corp_code") or "").strip())
           or not (row.get("corp_name") or "").strip() for row in rows):
        raise CorpCodeError("invalid_company_list")
    return rows


def fetch_corp_code(get, url, api_key, *, transport_errors=(TimeoutError, ConnectionError),
                    sleep=time.sleep, max_attempts=3):
    if not 1 <= max_attempts <= 3:
        raise ValueError("corpCode max_attempts must be 1..3")
    for attempt in range(1, max_attempts + 1):
        try:
            response = get(url, params={"crtfc_key": api_key}, timeout=60)
            status = response.status_code
            if status == 429:
                raise CorpCodeError("rate_limit", status="429")
            if status != 200:
                raise CorpCodeError("http_error", status=str(status),
                                    retryable=status in {500, 502, 503, 504})
            return parse_corp_code(response.content)
        except transport_errors:
            error = CorpCodeError("transport_error", retryable=True, attempts=attempt)
        except CorpCodeError as exc:
            error = exc
            error.attempts = attempt
        if not error.retryable or attempt == max_attempts:
            raise CorpCodeError(error.kind, status=error.status,
                                retryable=error.retryable, attempts=attempt) from None
        sleep(float(attempt))
    raise AssertionError("unreachable")
