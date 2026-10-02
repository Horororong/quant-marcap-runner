"""Capture frozen DART viewer routes as evidence, never financial metrics.

The routes come from an already captured viewer artifact. No original ZIP or
viewer TOC is requested again. Reports checkpoint each response after its bytes
are saved; even failed reports are not automatically retried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler

try:
    from scripts.legacy_backfill_runtime import CollectionControl, CollectionPaused
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from legacy_backfill_runtime import CollectionControl, CollectionPaused

ROUTES = Path("docs/audits/legacy/initial-financial-body-routes-20261002.json")
REPORT_DIR = Path("docs/audits/legacy/viewer_sections")
CAPTURE_VERSION = 1
MAX_BODY_BYTES = 2_000_000
MAX_TOTAL_BYTES = 12_000_000
PARAMETERS = ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect is a transport observation, not permission for an
        # unbudgeted second request or an unrelated source.
        return None


def validated_routes(document):
    result, seen = [], set()
    for receipt in document["receipts"]:
        number = receipt["rcept_no"]
        if not re.fullmatch(r"[0-9]{14}", number):
            raise ValueError("Invalid receipt in source evidence")
        for section in receipt["financial_section_pointers"]:
            params = section["parameters"]
            if set(params) != set(PARAMETERS) or params["rcpNo"] != number:
                raise ValueError("Viewer pointer has mismatched parameters")
            if params["dtd"] != "dart2.dtd" or any(
                not isinstance(params[k], str) or not re.fullmatch(r"[0-9]+", params[k])
                for k in PARAMETERS if k != "dtd"
            ):
                raise ValueError("Viewer pointer has unsupported values")
            if int(params["length"]) <= 0:
                raise ValueError("Empty viewer section")
            url = "https://dart.fss.or.kr/report/viewer.do?" + urlencode({k: params[k] for k in PARAMETERS})
            if section["url"] != url:
                raise ValueError("Viewer URL differs from its captured parameters")
            key = (number, params["eleId"])
            if key in seen:
                raise ValueError("Duplicate viewer section")
            seen.add(key)
            result.append({"rcept_no": number, "eleId": params["eleId"],
                           "heading": section["heading"], "url": url,
                           "viewer_sha256": receipt["viewer_sha256"],
                           "pointer_sha256": hashlib.sha256(url.encode()).hexdigest()})
    if not result or len(result) > 12:
        raise ValueError("Expected at most twelve frozen financial-body routes")
    return result


def read_response(response, control, limit):
    data = bytearray()
    while True:
        if control.should_stop():
            raise CollectionPaused(control.stop_reason)
        part = response.read(min(65_536, limit + 1 - len(data)))
        if not part:
            return bytes(data)
        data.extend(part)
        if len(data) > limit:
            raise ValueError("Viewer response exceeds evidence byte budget")


def literal_excerpt(raw):
    # No replacement decoding or amount normalization. Retain declared charset
    # evidence and refuse a guessed encoding when neither strict decode works.
    declaration = re.search(br"charset\s*=\s*[\"']?([\w-]+)", raw[:4096], re.I)
    declared = declaration.group(1).decode("ascii") if declaration else ""
    for encoding in dict.fromkeys([declared, "utf-8", "cp949"]):
        if not encoding:
            continue
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
        excerpts = [{"start_character": 0, "source_text": text[:2000]}]
        for token in ("자본총계", "매출액", "순이익", "순손실", "영업활동"):
            match = re.search(r"(?:\s|<[^>]*>)*".join(map(re.escape, token)), text)
            if match:
                start = max(0, match.start() - 400)
                excerpts.append({"matched_token": token, "start_character": start,
                                 "source_text": text[start:start + 1800]})
        return {"source_encoding": encoding, "source_characters": len(text),
                "replacement_characters_in_source": text.count("\ufffd"), "literal_excerpts": excerpts}
    return {"source_encoding": "UNDECODABLE", "literal_excerpts": []}


def publish(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def capture(routes, report_dir, artifact_dir, control, opener=None):
    opener = opener or build_opener(NoRedirects())
    artifact_dir.mkdir(parents=True, exist_ok=True)
    total = sum(p.stat().st_size for p in artifact_dir.glob("viewer-section-*.html"))
    saved = 0
    for route in routes:
        report_path = report_dir / f"{route['rcept_no']}-{route['eleId']}.json"
        if report_path.exists():
            previous = json.loads(report_path.read_text())
            if previous.get("pointer_sha256") != route["pointer_sha256"]:
                raise ValueError("Captured pointer changed; preserve and review previous evidence")
            # Successful and failed captures are immutable for this probe.
            continue
        if control.should_stop():
            break
        record = {**route, "capture_version": CAPTURE_VERSION,
                  "actions_run_id": os.getenv("GITHUB_RUN_ID", ""),
                  "download_status": "NOT_RUN", "independent_financial_audit": "NOT_RUN",
                  "source_absence_confirmed": False}
        try:
            control.before_request()
            try:
                response = opener.open(route["url"], timeout=20)
            except HTTPError as error:
                response = error
            with response:
                record["http_status"] = response.getcode()
                limit = min(MAX_BODY_BYTES, MAX_TOTAL_BYTES - total)
                if limit <= 0:
                    raise ValueError("Total viewer evidence budget exhausted")
                raw = read_response(response, control, limit)
            name = f"viewer-section-{route['rcept_no']}-{route['eleId']}.html"
            publish(artifact_dir / name, raw)  # Bytes before checkpoint.
            total += len(raw)
            record.update({"body_sha256": hashlib.sha256(raw).hexdigest(),
                           "body_bytes": len(raw), "artifact_file": name,
                           "download_status": "HTTP_RESPONSE_CAPTURED", **literal_excerpt(raw)})
            if record["http_status"] in (403, 429):
                control.stop("VIEWER_ACCESS_BLOCKED")
        except CollectionPaused as error:
            record.update(download_status="DEFERRED", error=str(error))
        except (URLError, TimeoutError, OSError) as error:
            record.update(download_status="TRANSPORT_ERROR", error=type(error).__name__)
            control.stop("VIEWER_TRANSPORT_ERROR")
        except ValueError as error:
            record.update(download_status="EVIDENCE_BUDGET_ERROR", error=str(error))
            control.stop("EVIDENCE_BUDGET")
        publish(report_path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode())
        saved += 1
        print(f"viewer section {route['rcept_no']}/{route['eleId']}: {record['download_status']} HTTP={record.get('http_status')} audit=NOT_RUN", flush=True)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=Path, default=ROUTES)
    args = parser.parse_args()
    routes = validated_routes(json.loads(args.routes.read_text()))
    control = CollectionControl(max_requests=12, max_seconds=300, min_interval=0.5)
    with control.signals():
        saved = capture(routes, REPORT_DIR, Path(os.environ["LEGACY_SOURCE_ARTIFACT_DIR"]), control)
    print(f"viewer sections saved={saved} attempts={control.requests} stop={control.stop_reason or 'BATCH_COMPLETE'}", flush=True)


if __name__ == "__main__":
    main()
