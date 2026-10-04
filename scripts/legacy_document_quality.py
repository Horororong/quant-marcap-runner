"""Lossless native-source diagnostics; missing items and source gaps differ."""
from __future__ import annotations
import hashlib
import re
import xml.etree.ElementTree as ET

DIAGNOSTIC_VERSION = "legacy-document-quality-v2"
SUPPORTED_ENCODINGS = {"utf-8", "utf8", "cp949", "euc-kr", "euckr"}


def inspect_member(data: bytes, member: str) -> dict:
    result = {"member": member, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest(), "issues": [], "warnings": []}
    if not member.lower().endswith(".xml"):
        return result
    match = re.search(br'<\?xml[^>]*encoding=[\"\x27]([^\"\x27]+)', data[:200], re.I)
    encoding = match.group(1).decode("ascii") if match else "utf-8"
    result["encoding"] = encoding
    if encoding.lower() not in SUPPORTED_ENCODINGS:
        result["issues"].append("SOURCE_ENCODING_INVALID")
        return result
    # The existing native HTML path supports these legacy encodings. Actual
    # complete 2002 disclosures have CP949 bytes despite a UTF-8 declaration.
    # Never replace bytes, retry past replacement characters, or guess amounts.
    text = None
    for candidate in dict.fromkeys([encoding, "utf-8", "cp949", "euc-kr"]):
        try:
            decoded = data.decode(candidate, errors="strict")
            if decoded.encode(candidate) != data:
                continue
            text = decoded
            result["resolved_encoding"] = candidate
            if candidate.lower() != encoding.lower():
                result["warnings"].append("LEGACY_ENCODING_DECLARATION_MISMATCH")
            break
        except (UnicodeError, LookupError):
            continue
    if text is None:
        result["issues"].append("SOURCE_ENCODING_INVALID")
        return result
    result["replacement_characters"] = text.count("\ufffd")
    if result["replacement_characters"]:
        result["issues"].append("SOURCE_REPLACEMENT_CHARACTERS")
    # The pre-existing HTML parser supports literal &, e.g. M&A / Buy & Sell.
    # Inspect structure through its XML-escaped view; raw input and numerical
    # content are unchanged and still parsed from the original decoded text.
    structural, count = re.subn(r'&(?!(?:#\d+|#x[\da-fA-F]+|amp|lt|gt|apos|quot);)', '&amp;', text)
    if count:
        result["warnings"].append("LEGACY_HTML_AMPERSAND_SYNTAX")
        result["ampersand_escapes_for_structure"] = count
    try:
        ET.fromstring(structural)
    except ET.ParseError as error:
        result["issues"].append("SOURCE_XML_INCOMPLETE_OR_INVALID")
        result["xml_error"] = str(error)
    return result


def empty_parse_status(diagnostics: list[dict]) -> str:
    return "SOURCE_GAP" if any(d["issues"] for d in diagnostics) else "NO_METRICS"


def needs_encoding_recheck(row: dict) -> bool:
    # A finite one-version migration of the exact false-blocked population;
    # other source gaps/normal receipts are not blanket requeued.
    return (row.get("status") == "SOURCE_GAP"
            and row.get("source_diagnostic_version") == "legacy-document-quality-v1"
            and '"SOURCE_ENCODING_INVALID"' in str(row.get("error", "")))
