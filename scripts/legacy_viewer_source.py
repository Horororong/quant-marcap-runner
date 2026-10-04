"""Fail-closed adapter for already captured DART financial-body viewer sources.

This is an offline source adapter, not a downloader or a PIT data provider.
It never updates the native collector checkpoint or promotes a filing to 4F.
Versioned source guards are separate from the unchanged native v5 parser.
"""
from __future__ import annotations

import calendar
import hashlib
import math
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

try:
    from scripts.legacy_financial_fields import choose_metric, norm_account, parse_number, UNIT_MULTIPLIERS
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from legacy_financial_fields import choose_metric, norm_account, parse_number, UNIT_MULTIPLIERS

ADAPTER_VERSION = "dart-viewer-period-scope-unit-column-v2"
MAX_BODY_BYTES = 2_000_000
DATE_RE = re.compile(r"(\d{4})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*(\d{1,2})(?:\s*[.일])?")
TERM_RE = re.compile(r"제\s*(\d+)\s*기")


def compact(text):
    return re.sub(r"\s+", "", text)


def period_kind(text):
    text = compact(text)
    for token, kind in (("1분기", "Q1"), ("3분기", "Q3"), ("반기", "H1"), ("연간", "FY")):
        if token in text:
            return kind
    return "QX" if "분기" in text else ""


def statement_heading(text):
    # Use only text outside preceding tables, never previous financial values.
    matches = list(re.finditer(r"현금흐름표|포괄손익계산서|손익계산서|대차대조표|재무상태표|이익잉여금처분계산서|결손금처리계산서", compact(text)))
    if not matches:
        return ""
    token = matches[-1].group()
    if token in {"이익잉여금처분계산서", "결손금처리계산서"}:
        return "OTHER"
    return "CF" if token == "현금흐름표" else "IS" if "손익" in token else "BS"


class SourceTables(HTMLParser):
    """Preserve empty BR lines and column spans rather than flattening amounts."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.tables = []
        self.outside = []
        self.table = self.row = self.cell = None
        self.bad = False

    def character_offset(self):
        line, col = self.getpos()
        return self.offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.table is not None:
                raise ValueError("nested source tables unsupported")
            if len(self.tables) >= 400:
                raise ValueError("source table budget exceeded")
            self.table = {"index": len(self.tables), "prefix": "".join(self.outside), "rows": []}
            self.outside = []
        elif tag == "tr" and self.table is not None:
            if self.row is not None:
                raise ValueError("unclosed source row")
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            if self.cell is not None:
                raise ValueError("unclosed source cell")
            attrs = dict(attrs)
            colspan, rowspan = int(attrs.get("colspan", "1")), int(attrs.get("rowspan", "1"))
            if not 1 <= colspan <= 64 or not 1 <= rowspan <= 64:
                raise ValueError("unsupported source span")
            self.cell = {"lines": [""], "colspan": colspan, "rowspan": rowspan,
                         "start_character": self.character_offset(), "header": tag == "th"}
        elif tag == "br":
            if self.cell is not None:
                if len(self.cell["lines"]) >= 2000:
                    raise ValueError("source line budget exceeded")
                self.cell["lines"].append("")
            elif self.table is None:
                self.outside.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cell["lines"] = [x.strip() for x in self.cell["lines"]]
            self.cell["end_character"] = self.character_offset() + len(f"</{tag}>")
            self.row.append(self.cell)
            if len(self.row) > 200:
                raise ValueError("source column budget exceeded")
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cell is not None:
                raise ValueError("unclosed source cell")
            self.table["rows"].append(self.row)
            if len(self.table["rows"]) > 20000:
                raise ValueError("source row budget exceeded")
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.row is not None:
                raise ValueError("unclosed source row")
            self.tables.append(self.table)
            self.table = None
        elif self.table is None and tag in {"p", "h1", "h2", "h3", "div"}:
            self.outside.append("\n")

    def handle_data(self, text):
        if self.cell is not None:
            self.cell["lines"][-1] += re.sub(r"\s+", " ", text)
        elif self.table is None:
            self.outside.append(text)


def cell_text(cell):
    return " ".join(cell["lines"])


def date_contracts(table):
    contracts = []
    for row in table["rows"]:
        for cell in row:
            # Financial dates occur in separate cells, not arbitrary notes.
            text = cell_text(cell)
            term = TERM_RE.search(text)
            dates = DATE_RE.findall(text)
            if not term or len(dates) not in {1, 2}:
                continue
            try:
                parsed = [date(*map(int, ds)).isoformat() for ds in dates]
            except ValueError:
                continue
            contracts.append({"term": term.group(1), "kind": period_kind(text),
                              "start": parsed[0] if len(parsed) == 2 else "", "end": parsed[-1]})
    return contracts


def source_units(table):
    values = []
    for row in table["rows"]:
        for cell in row:
            text = compact(cell_text(cell))
            if "단위" in text:
                match = re.search(r"단위[:：]?\(?(백만원|천원|억원|원)(?:[)\]]|$)", text)
                values.append(match.group(1) if match else "")
    return values


def valid_flow_period(contract, kind):
    if not contract["start"]:
        return False
    start, end = date.fromisoformat(contract["start"]), date.fromisoformat(contract["end"])
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    return (start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1]
            and months == {"Q1": 3, "H1": 6, "Q3": 9, "FY": 12}[kind])


def viewer_amount(token):
    # This explicit negative-prefix syntax is visible in the Daewoo originals.
    if token.startswith("(-)"):
        token = "-" + token[3:]
    # Parentheses alone are ambiguous in historical viewer layouts (Daegu
    # prints positive BS totals in parentheses). Never infer their sign here.
    if token.startswith("(") and not re.match(r"\([\-△▲Δ]", token):
        return math.nan
    return parse_number(token)


def viewer_metric(account, statement):
    clean = re.sub(r"\s*\(주\s*\d+(?:\s*,\s*\d+)*\)\s*$", "", account)
    metric, _ = choose_metric(clean, statement)
    # Exact source-backed viewer spellings; native v5 aliases stay unchanged.
    if not metric and statement == "IS" and norm_account(clean) in {"당기순이(손)익", "당분기순손실"}:
        metric = "net_income"
    return metric, clean


# Full parenthetical per-share notes in the inspected United/Peerless/Daewoo
# originals, including BR-wrapped notes. Arbitrary footnotes are not supported.
PER_SHARE_NOTE = re.compile(
    r"\((?:(?:당분기|\d+전기))?(?:기본)?주당(?:분기)?(?:경상|순)(?:이익|손실):"
    r"(?:(?:분기|\d+\((?:전전|전)\)기))?(?:\(-\)|[-△▲Δ])?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?원\)"
)


def financial_prefix_before_per_share_tail(row, statement):
    """Prove a ragged row's financial prefix without padding or shifting lines.

    Only an IS prefix ending in net income followed solely by explicit per-share
    notes is supported. All numeric columns must end at that same original
    BR index (or be entirely empty), with no amount on a blank account line.
    Prior columns are checked too, but never supply a missing current value.
    """
    if statement != "IS":
        return None
    accounts = row[0]["lines"]
    boundary = next((i for i, line in enumerate(accounts) if compact(line).startswith("(") and "주당" in line), None)
    if boundary is None:
        return None
    suffix = compact("".join(accounts[boundary:]))
    position, notes = 0, 0
    while position < len(suffix):
        match = PER_SHARE_NOTE.match(suffix, position)
        if match is None:
            return None
        position, notes = match.end(), notes + 1
    if not notes:
        return None
    end = boundary
    while end and not accounts[end - 1]:
        end -= 1
    if not end or viewer_metric(accounts[end - 1], statement)[0] != "net_income":
        return None
    for cell in row[1:]:
        nonblank = [i for i, line in enumerate(cell["lines"]) if line]
        if nonblank and nonblank[-1] != end - 1:
            return None
        for i in nonblank:
            if not accounts[i] or not math.isfinite(viewer_amount(cell["lines"][i])):
                return None
    return {"contract": "is-prefix-before-explicit-per-share-tail-v2", "financial_prefix_lines": end,
            "original_line_counts": [len(c["lines"]) for c in row], "per_share_note_count": notes,
            "account_note_lines": accounts[end:]}


def adapt_viewer(body: bytes, capture: dict, request: dict) -> dict:
    """Return guarded staging rows and gaps. No inferred filing/availability date.

    request has exact source period_end, kind (Q1/H1/Q3/FY) and scope.
    Callers cannot substitute the index's first-of-month date or future-derived
    fiscal-year labels for these source contracts.
    """
    result = {"adapter_version": ADAPTER_VERSION, "rows": [], "gaps": [],
              "pit_ready": False, "production_ready": False}
    def gap(reason, **details):
        result["gaps"].append({"reason": reason, **details})

    if request.get("kind") not in {"Q1", "H1", "Q3", "FY"} or request.get("scope") not in {"OFS", "CFS"}:
        raise ValueError("explicit period kind and scope required")
    end = date.fromisoformat(request["period_end"])
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise ValueError("exact source period end required, not a first-of-month index label")
    receipt = capture.get("rcept_no", "")
    url = urlparse(capture.get("url", ""))
    query = parse_qs(url.query)
    if (not re.fullmatch(r"\d{14}", receipt) or url.scheme != "https" or url.netloc != "dart.fss.or.kr"
            or url.path != "/report/viewer.do" or query.get("rcpNo") != [receipt]
            or query.get("eleId") != [str(capture.get("eleId", ""))]
            or capture.get("http_status") != 200 or len(body) > MAX_BODY_BYTES
            or hashlib.sha256(body).hexdigest() != capture.get("body_sha256")
            or len(body) != capture.get("body_bytes")):
        gap("SOURCE_IDENTITY_MISMATCH")
        return result
    try:
        text = body.decode(capture["source_encoding"], errors="strict")
    except (UnicodeError, LookupError, KeyError):
        gap("SOURCE_ENCODING_UNKNOWN")
        return result
    if "\ufffd" in text:
        gap("SOURCE_ENCODING_UNKNOWN")
        return result
    heading = compact(capture.get("heading", ""))
    scope = "CFS" if "연결재무제표" in heading else "OFS" if re.fullmatch(r"\d+\.재무제표", heading) else ""
    if not scope or scope != request["scope"] or heading not in compact(text[:2000]):
        gap("SCOPE_UNPROVEN_OR_MISMATCH")
        return result
    parser = SourceTables(text)
    try:
        parser.feed(text)
        parser.close()
        if parser.table is not None:
            raise ValueError("unclosed source table")
    except (ValueError, IndexError) as error:
        gap("UNSUPPORTED_SOURCE_LAYOUT", detail=str(error))
        return result
    # Generic "분기" headings may be resolved only by a same-term, same-end
    # explicit cumulative date range in this source, not an index FY guess.
    flow_kinds = {}
    for table in parser.tables:
        for contract in date_contracts(table):
            for kind in ("Q1", "H1", "Q3", "FY"):
                if valid_flow_period(contract, kind):
                    flow_kinds.setdefault((contract["term"], contract["end"]), set()).add(kind)
    statement, block = "", None
    for table in parser.tables:
        heading_statement = statement_heading(table["prefix"])
        if heading_statement:
            statement, block = heading_statement, None
        # An explicit contrary scope heading never inherits the route's scope.
        prefix = compact(table["prefix"])
        if (scope == "OFS" and any(s in prefix for s in ("연결재무제표", "연결대차대조표", "연결손익계산서", "연결현금흐름표"))) or (scope == "CFS" and any(s in prefix for s in ("별도재무제표", "개별재무제표"))):
            gap("SCOPE_UNPROVEN_OR_MISMATCH", table=table["index"])
            block = None
            continue
        header_index = next((i for i, row in enumerate(table["rows"][:8]) if row and compact(cell_text(row[0])) == "과목"), None)
        if header_index is None:
            contracts = date_contracts(table)
            block = {"dates": contracts, "units": source_units(table), "statement": statement} if contracts else None
            continue
        if not block or block["statement"] not in {"BS", "IS", "CF"}:
            gap("STATEMENT_OR_PERIOD_UNPROVEN", table=table["index"])
            continue
        units = block["units"]
        inline_units = source_units(table)
        if len(units) != 1 or not units[0] or (inline_units and inline_units != units):
            gap("UNIT_UNPROVEN", table=table["index"])
            block = None
            continue
        header = table["rows"][header_index]
        groups, cursor = [], 0
        for cell in header:
            label = cell_text(cell)
            term = TERM_RE.search(label)
            if term:
                kind = period_kind(label)
                matches = [c for c in block["dates"] if c["term"] == term.group(1)
                           and (c["kind"] == kind or c["kind"] == "QX" and kind in {"Q1", "Q3"}
                                or not c["kind"] and kind in {"", "FY", "QX"})]
                if len(matches) == 1:
                    contract = matches[0]
                    use_kind = kind
                    if kind in {"", "QX"}:
                        proven = flow_kinds.get((contract["term"], contract["end"]), set())
                        if len(proven) == 1:
                            inferred = next(iter(proven))
                            use_kind = inferred if kind == "" or inferred in {"Q1", "Q3"} else ""
                    if (contract["end"] == request["period_end"] and use_kind == request["kind"]
                            and (statement == "BS" or valid_flow_period(contract, use_kind))):
                        groups.append((cursor, cursor + cell["colspan"], contract, label))
            cursor += cell["colspan"]
        if len(groups) != 1:
            gap("CURRENT_PERIOD_COLUMN_UNPROVEN", table=table["index"])
            block = None
            continue
        left, right, contract, label = groups[0]
        table_rows = []
        for ri, row in enumerate(table["rows"][header_index + 1:], header_index + 1):
            if not row:
                continue
            # Body rowspan/colspan layouts beyond header grouping are gaps.
            if any(c["rowspan"] != 1 or c["colspan"] != 1 for c in row) or len(row) != cursor:
                # A header's second row may have an inherited account rowspan.
                if all(compact(cell_text(c)) in {"", "금액", "주석"} for c in row):
                    continue
                gap("BODY_COLUMN_ALIGNMENT_UNPROVEN", table=table["index"], row=ri)
                continue
            counts = [len(c["lines"]) for c in row]
            alignment = None
            if len(row[0]["lines"]) == 1 and any(sum(bool(line) for line in row[ci]["lines"]) > 1 for ci in range(left, right)):
                gap("BR_LINE_ALIGNMENT_UNPROVEN", table=table["index"], row=ri)
                continue
            if len(row[0]["lines"]) > 1 and len(set(counts)) != 1:
                alignment = financial_prefix_before_per_share_tail(row, statement)
                if alignment is None:
                    gap("BR_LINE_ALIGNMENT_UNPROVEN", table=table["index"], row=ri)
                    continue
            accounts = row[0]["lines"][:alignment["financial_prefix_lines"]] if alignment else row[0]["lines"]
            for li, account in enumerate(accounts):
                metric, account_clean = viewer_metric(account, statement)
                if not metric:
                    continue
                tokens = [(ci, row[ci]["lines"][li] if li < len(row[ci]["lines"]) else "") for ci in range(left, right)]
                present = [(ci, token) for ci, token in tokens if token.strip()]
                if len(present) != 1:
                    gap("CURRENT_AMOUNT_UNPROVEN", table=table["index"], row=ri, metric=metric)
                    continue
                ci, token = present[0]
                value = viewer_amount(token)
                if not math.isfinite(value):
                    gap("CURRENT_AMOUNT_UNPROVEN", table=table["index"], row=ri, metric=metric)
                    continue
                if metric in {"net_income", "operating_income", "gross_profit"} and "손실" in norm_account(account_clean):
                    value = -abs(value)
                unit = units[0]
                amount = value * UNIT_MULTIPLIERS[unit]
                if not math.isfinite(amount):
                    gap("NONFINITE_AMOUNT", table=table["index"], row=ri, metric=metric)
                    continue
                cell = row[ci]
                table_rows.append({"rcept_no": receipt, "metric": metric, "scope": scope, "statement": statement,
                                   "period_start": contract["start"] if statement != "BS" else "", "period_end": contract["end"],
                                   "period_kind": request["kind"], "unit": unit, "unit_multiplier": UNIT_MULTIPLIERS[unit],
                                   "account_name": account, "raw_amount": token, "amount_reported": value, "amount_krw": amount,
                                   "source_url": capture["url"], "source_sha256": capture["body_sha256"],
                                   "table_index": table["index"], "row_index": ri, "cell_index": ci, "line_index": li,
                                   "cell_start_character": cell["start_character"], "cell_end_character": cell["end_character"],
                                   "current_column_header": label, "adapter_version": ADAPTER_VERSION,
                                   "filing_date_verified": False, "strategy_usable_date": None})
                if alignment:
                    table_rows[-1]["line_alignment_evidence"] = alignment
        # Conflicting duplicates are rejected, not selected by alias priority.
        for metric in sorted({r["metric"] for r in table_rows}):
            selected = [r for r in table_rows if r["metric"] == metric]
            if len(selected) != 1:
                gap("DUPLICATE_CURRENT_METRIC", table=table["index"], metric=metric)
            else:
                result["rows"].extend(selected)
        block = None  # Units/period may not bleed into a subsequent data table.
    # Likewise, never merge conflicting same-period statements within a source.
    duplicates = {metric for metric in {r["metric"] for r in result["rows"]}
                  if sum(r["metric"] == metric for r in result["rows"]) > 1}
    result["rows"] = [r for r in result["rows"] if r["metric"] not in duplicates]
    for metric in sorted(duplicates):
        gap("DUPLICATE_CURRENT_METRIC", metric=metric)
    return result
