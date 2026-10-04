"""Source diagnostics; a broken download never proves financial-item absence."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

DIAGNOSTIC_VERSION = "legacy-document-quality-v1"


def inspect_member(data: bytes, member: str) -> dict:
    result = {"member": member, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest(), "issues": []}
    # Native XML advertises its encoding. Do not repair replacement characters
    # or treat tolerant HTML parsing of a truncated XML as a complete source.
    if not member.lower().endswith(".xml"):
        return result
    match = re.search(br'<\?xml[^>]*encoding=[\"\x27]([^\"\x27]+)', data[:200], re.I)
    encoding = match.group(1).decode("ascii") if match else "utf-8"
    result["encoding"] = encoding
    try:
        text = data.decode(encoding, errors="strict")
    except (UnicodeError, LookupError):
        result["issues"].append("SOURCE_ENCODING_INVALID")
        return result
    result["replacement_characters"] = text.count("\ufffd")
    if result["replacement_characters"]:
        result["issues"].append("SOURCE_REPLACEMENT_CHARACTERS")
    try:
        ET.fromstring(text)
    except ET.ParseError as error:
        result["issues"].append("SOURCE_XML_INCOMPLETE_OR_INVALID")
        result["xml_error"] = str(error)
    return result


def empty_parse_status(diagnostics: list[dict]) -> str:
    return "SOURCE_GAP" if any(d["issues"] for d in diagnostics) else "NO_METRICS"
