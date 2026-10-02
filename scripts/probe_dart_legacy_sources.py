"""Bounded original-source evidence capture, NOT a financial correctness audit.

Raw statement excerpts with source offsets/hashes are retained in Git. Original
ZIPs stay in an Actions artifact, never in the tracked data store. No metric is
calculated or certified here; reviewers must compare actual source columns.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
from collections import Counter

try:
    from scripts import backfill_dart_legacy_2000_2014 as legacy
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import backfill_dart_legacy_2000_2014 as legacy


# Representative failures from the committed index/state; fiscal labels do not
# prove report-period interpretation (several companies had non-December FYs).
RECEIPTS = ("20010103000052", "20010104000076", "20000814000085",
            "20000809000052", "20010213000010", "20010213000014",
            "20000515000887", "20000214000011")
EVIDENCE_CAPTURE_VERSION = 2
REPORT_DIR = Path("docs/audits/legacy/source_probes")
MAX_EXCERPT_CHARS = 40_000
MAX_MEMBER_BYTES = 20_000_000
MAX_TOTAL_ZIP_BYTES = 40_000_000


def decode_source(data):
    declaration = re.search(br'encoding\s*=\s*[\'"]([^\'"]+)', data[:200], re.I)
    declared = declaration.group(1).decode("ascii") if declaration else ""
    for encoding in dict.fromkeys([declared, "utf-8", "cp949", "euc-kr"]):
        if not encoding:
            continue
        try:
            return data.decode(encoding), encoding
        except (LookupError, UnicodeDecodeError):
            continue
    raise ValueError("Source encoding could not be decoded without replacement")


def source_excerpts(blob):
    """Keep literal source spans, never normalized/parsing-derived amounts."""
    result, remaining = [], MAX_EXCERPT_CHARS
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = sorted((entry for entry in archive.infolist() if not entry.is_dir()), key=lambda entry: entry.filename)
        if len(entries) > 100 or sum(entry.file_size for entry in entries) > MAX_MEMBER_BYTES:
            raise ValueError("Source ZIP expansion exceeds evidence budget")
        for entry in entries:
            raw = archive.read(entry)
            try:
                text, encoding = decode_source(raw)
            except ValueError:
                continue
            spans = []
            for table in re.finditer(r"<table\b[^>]*>[\s\S]*?</table\s*>", text, re.I):
                tokens = re.sub(r"\s+", "", re.sub(r"<[^>]*>", "", table.group()))
                if not any(token in tokens for token in ("자본총계", "매출액", "순이익", "순손실", "영업활동")):
                    continue
                start, end = max(0, table.start() - 800), table.end()
                take = min(end - start, remaining)
                if take <= 0:
                    break
                spans.append({"start_character": start, "end_character": start + take,
                              "clipped": take < end - start, "source_text": text[start:start + take]})
                remaining -= take
            # Keep inspectable evidence even when the financial content uses a
            # different native structure than HTML TABLE (e.g. encoded payload).
            # No-table / no-matching-account is NOT proof of missing statements.
            head_size = min(2000, remaining)
            remaining -= head_size
            contexts = []
            for token in ("자본총계", "매출액", "순이익", "순손실", "영업활동"):
                pattern = r"(?:\s|<[^>]*>)*".join(map(re.escape, token))
                match = re.search(pattern, text)
                if match and remaining:
                    start = max(0, match.start() - 1200)
                    end = min(len(text), match.end() + 3000, start + remaining)
                    contexts.append({"matched_token": token, "start_character": start,
                                     "end_character": end, "source_text": text[start:end]})
                    remaining -= end - start
            result.append({"member_name": entry.filename, "member_sha256": hashlib.sha256(raw).hexdigest(),
                           "source_encoding": encoding, "source_characters": len(text),
                           "source_head": text[:head_size],
                           "tag_counts": dict(Counter(re.findall(r"<([\w:-]+)\b", text)).most_common(30)),
                           "account_contexts": contexts, "excerpts": spans})
            if remaining <= 0:
                break
    return result


def probe(receipt, artifact_dir, guard):
    record = {"rcept_no": receipt,
              "public_viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
              "parser_version_at_probe": legacy.PARSER_VERSION,
              "evidence_capture_version": EVIDENCE_CAPTURE_VERSION,
              "independent_source_audit_status": "NOT_RUN",
              "source_absence_confirmed": False,
              "actions_run_id": os.getenv("GITHUB_RUN_ID", ""),
              "checked_at_utc": legacy.now_utc()}
    try:
        blob, sha = legacy.fetch_document(receipt)
        if len(blob) + sum(path.stat().st_size for path in artifact_dir.glob("*.zip")) > MAX_TOTAL_ZIP_BYTES:
            raise ValueError("Source ZIP exceeds evidence budget")
        record.update({"download_status": "DOWNLOADED", "document_sha256": sha,
                       "zip_bytes": len(blob), "members": source_excerpts(blob)})
        (artifact_dir / f"{receipt}-{sha[:16]}.zip").write_bytes(blob)
    except legacy.DocumentUnavailable as error:
        record.update({"download_status": "API_014", "error": legacy.safe_error(error)})
    except legacy.RateLimitExceeded as error:
        guard.stop("RATE_LIMIT")
        record.update({"download_status": "RATE_LIMIT", "error": legacy.safe_error(error)})
    except (legacy.CollectionPaused, legacy.FatalDartError) as error:
        record.update({"download_status": "DEFERRED", "error": legacy.safe_error(error)})
    except Exception as error:
        record.update({"download_status": "ERROR", "error": legacy.safe_error(error)})
    # A download API 014 cannot establish that the public DART viewer is empty.
    # Save its response for investigation without interpreting the viewer as a
    # statement, nor certifying financial amounts from HTTP 200 alone.
    if not guard.should_stop():
        try:
            guard.before_request()
            response = legacy.requests.get(record["public_viewer_url"], timeout=20)
            record["public_viewer_http_status"] = response.status_code
            body = response.content
            record["public_viewer_response_sha256"] = hashlib.sha256(body).hexdigest()
            if response.status_code == 200 and len(body) <= 500_000:
                (artifact_dir / f"{receipt}-viewer.html").write_bytes(body)
        except Exception as error:
            record["public_viewer_error"] = legacy.safe_error(error)
    return record


def main():
    if not legacy.API_KEY:
        raise RuntimeError("DART_API_KEY missing; evidence capture was not run")
    artifact_dir = Path(os.environ["LEGACY_SOURCE_ARTIFACT_DIR"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    guard = legacy.CollectionControl(max_requests=48, max_seconds=600, min_interval=0.5)
    previous = legacy.RUN_CONTROL
    legacy.RUN_CONTROL = guard
    try:
        with guard.signals():
            for receipt in RECEIPTS:
                path = REPORT_DIR / f"{receipt}.json"
                # Original-source reports are immutable evidence, independent of
                # parser version. Retry a failed probe only on an explicit run.
                if guard.should_stop():
                    continue
                if path.exists():
                    previous_report = json.loads(path.read_text(encoding="utf-8"))
                    if previous_report.get("evidence_capture_version") == EVIDENCE_CAPTURE_VERSION:
                        continue
                record = probe(receipt, artifact_dir, guard)
                descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=REPORT_DIR)
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, path)
                finally:
                    Path(temporary).unlink(missing_ok=True)
                print(f"source probe {receipt}: {record['download_status']} (audit NOT_RUN)", flush=True)
    finally:
        legacy.RUN_CONTROL = previous


if __name__ == "__main__":
    main()
