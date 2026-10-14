"""Native DART structural financial reader; no network, pandas or audit controls.

Source dates, statement families, current column groups, units and amendment
regions must be evidenced. Unknowns remain review observations, never usable
money. Point-in-time eligibility is a separate, default-closed gate.
"""
from __future__ import annotations
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from html.parser import HTMLParser

try:
    from scripts.legacy_financial_fields import choose_metric, norm_account
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from legacy_financial_fields import choose_metric, norm_account

PARSER_VERSION = "legacy-v6-structural-evidence"
DATE = re.compile(r"(\d{4})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*(\d{1,2})(?:\s*[.일])?")
HEADING = re.compile(r"(?:연결)?(?:포괄손익계산서|손익계산서|대차대조표|재무상태표|현금흐름표|이익잉여금처분계산서|결손금처리계산서)")
TERM = re.compile(r"(?:제\s*)?(\d+)\s*(?:\([당전]\))?\s*기")
UNITS = {"원": Decimal(1), "천원": Decimal(1000), "백만원": Decimal(1000000), "억원": Decimal(100000000)}
TOKEN = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?\Z")
compact = lambda s: re.sub(r"\s+", "", str(s or ""))


def financial_account(label, statement):
    # Only explicit terminal note references and decorative total delimiters.
    # Profit(loss) is a financial account label and is never stripped.
    label = re.sub(r"\((?:주석|주)[\s\d,~과및등-]*\)\s*$", "", str(label)).strip("= ")
    return choose_metric(label, statement)


def decimal_amount(raw, account="", metric=""):
    """One whole monetary token; malformed comma grouping and missing stay missing."""
    s = compact(raw).replace("−", "-").replace("－", "-")
    if not s or s in {"-", "—", "–", "―"}:
        return None
    negative = False
    if s.startswith(("△", "▲", "Δ")):
        negative, s = True, s[1:]
    if s.startswith("(-)"):
        negative, s = True, s[3:]
    elif s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.startswith(("△", "▲", "Δ")):
        negative, s = True, s[1:]
    if not TOKEN.fullmatch(s):
        return None
    try:
        value = Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None
    if not value.is_finite() or len(value.as_tuple().digits) > 30:
        return None
    if negative:
        value = -abs(value)
    label = norm_account(account)
    if metric in {"net_income", "gross_profit", "operating_income"} and "손실" in label and "이익" not in label:
        value = -abs(value)
    return value


def dates(text):
    out = []
    for ds in DATE.findall(text):
        try:
            out.append(date(*map(int, ds)).isoformat())
        except ValueError:
            continue
    return out


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


class NativeTables(HTMLParser):
    """Lossless BR lines and physical source coordinates; table text is not context."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack, self.outside = [], [], []
        self.in_cover, self.cover_text = False, []
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))

    def position(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "cover":
            self.in_cover = True
        if tag == "table":
            t = {"index": len(self.tables), "prefix": "".join(self.outside),
                 "rows": [], "row": None, "cell": None, "source_character": self.position(),
                 "in_cover": self.in_cover}
            self.outside = []
            self.tables.append(t)
            self.stack.append(t)
        elif self.stack:
            t = self.stack[-1]
            if tag == "tr":
                t["row"] = []
            elif tag in {"td", "th", "te", "tu"} and t["cell"] is None:
                attrs = dict(attrs)
                t["cell"] = {"tag": tag, "lines": [""], "colspan": int(attrs.get("colspan", 1)),
                             "rowspan": int(attrs.get("rowspan", 1)), "source_character": self.position()}
            elif tag == "br" and t["cell"] is not None:
                t["cell"]["lines"].append("")
        elif tag in {"p", "h1", "h2", "h3", "title", "div"}:
            self.outside.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, text):
        if self.in_cover:
            self.cover_text.append(text)
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"]["lines"][-1] += text
        elif not self.stack:
            self.outside.append(text)

    def handle_endtag(self, tag):
        if tag == "cover":
            self.in_cover = False
        if self.stack:
            t = self.stack[-1]
            if t["cell"] is not None and tag == t["cell"]["tag"]:
                t["cell"]["lines"] = [x.strip() for x in t["cell"]["lines"]]
                if t["row"] is not None:
                    t["row"].append(t["cell"])
                t["cell"] = None
            elif tag == "tr" and t["row"] is not None:
                t["rows"].append(t["row"])
                t["row"] = None
            elif tag == "table":
                self.stack.pop()
        elif tag in {"p", "h1", "h2", "h3", "div"}:
            self.outside.append("\n")


def cell_text(c):
    return " ".join(c["lines"])


def grid(rows):
    """Expand colspan/rowspan headers without losing physical cell locators."""
    result, carry = [], {}
    for ri, row in enumerate(rows):
        slots = {k: v[1] for k, v in carry.items() if v[0] >= ri}
        carry = {k: v for k, v in carry.items() if v[0] >= ri}
        column = 0
        for ci, c in enumerate(row):
            if not 1 <= c["colspan"] <= 64 or not 1 <= c["rowspan"] <= 64:
                raise ValueError("invalid source span")
            while column in slots:
                column += 1
            for k in range(column, column + c["colspan"]):
                slots[k] = (ri, ci, c)
                if c["rowspan"] > 1:
                    carry[k] = (ri + c["rowspan"] - 1, (ri, ci, c))
            column += c["colspan"]
        result.append(slots)
    return result


def source_contract(prefix):
    text = compact(prefix)
    matches = list(HEADING.finditer(text))
    if not matches:
        return None
    heading = matches[-1]
    token, tail = heading.group(), text[heading.end():]
    if "처분계산서" in token or "처리계산서" in token:
        return None
    statement = "BS" if token.endswith(("대차대조표", "재무상태표")) else "CF" if token.endswith("현금흐름표") else "IS"
    term = TERM.search(tail)
    if not term:
        return None
    # Only the first headed term's dates, never later comparison terms.
    nxt = TERM.search(tail, term.end())
    first = tail[term.start():nxt.start() if nxt else len(tail)]
    ds = dates(first)
    if len(ds) != (1 if statement == "BS" else 2):
        return None
    start, end = ("" if statement == "BS" else ds[0]), ds[-1]
    if start and start > end:
        return None
    return {"statement": statement, "scope": "CFS" if token.startswith("연결") else "OFS",
            "term": term.group(1), "period_start": start, "period_end": end, "heading": token}


def unit_for(table, heading_tail):
    # A blank nearest unit declaration is unknown, never inherited from a previous table.
    decl = list(re.finditer(r"단위[:：]\s*\(?\s*(백만원|천원|억원|원)?", heading_tail))
    unit = decl[-1].group(1) if decl else None
    inline = set()
    for row in table["rows"][:3]:
        for c in row:
            inline.update(re.findall(r"(?:금액|단위[:：]?)\s*[\(（:：]\s*(백만원|천원|억원|원)", compact(cell_text(c))))
    if len(inline) > 1 or (inline and unit and unit not in inline):
        return ""
    return next(iter(inline)) if inline else unit or ""


def kind(start, end, header):
    h = compact(header)
    if "반기" in h:
        return "H1"
    if "3분기" in h:
        return "Q3"
    if "1분기" in h:
        return "Q1"
    if start:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        months = (b.year - a.year) * 12 + b.month - a.month + 1
        return {3: "Q1", 6: "H1", 9: "Q3", 12: "FY"}.get(months, "QX")
    return "QX"


def parse_native(text):
    reader = NativeTables(text)
    reader.feed(text)
    cover = re.search(r"사업연도\s*((?:\d|\s|[.년월일/~-]|부터|까지){12,180})", " ".join(reader.cover_text))
    cover_dates = dates(cover.group(1)) if cover else []
    report_end = cover_dates[-1] if len(cover_dates) == 2 else ""
    report_period = kind(cover_dates[0], report_end, " ".join(reader.cover_text)[:180]) if len(cover_dates) == 2 else "QX"
    correction_file = "정정신고" in compact(text[:50000])
    zone, amendment, contract = False, "UNKNOWN" if correction_file else "ORIGINAL_FILED", None
    observations, issues, present = [], [], False
    for table in reader.tables:
        prefix = compact(table["prefix"])
        if table["in_cover"] or ("사업연도" in prefix and re.search(r"사업연도\d{4}", prefix)):
            amendment = "FILED_BODY"
        marks = list(re.finditer("정정전|정정후", prefix))
        if marks:
            amendment = "BEFORE" if marks[-1].group() == "정정전" else "AFTER"
        # Exclusion lasts until a fresh primary financial heading.
        events = list(re.finditer(r"4[.]재무제표|다[.]연결재무제표|부문별재무현황|사업부문별재무|합병전[ㆍ·]?후|외화자산과부채|주석", prefix))
        for event in events:
            zone = event.group() in {"4.재무제표", "다.연결재무제표"}
        rows = table["rows"]
        if not rows:
            continue
        # Native DART places statement dates and units in an adjacent, one-cell
        # header table. Consume only that structural header, never money tables.
        heading_matches = list(HEADING.finditer(prefix))
        if heading_matches:
            contract = source_contract(table["prefix"])
        header_text = " ".join(cell_text(c) for row in rows for c in row)
        header_only = (any(TERM.search(cell_text(c)) and dates(cell_text(c)) for row in rows for c in row)
                       and not any(financial_account(line, st)[0] for row in rows for c in row
                                   for line in c["lines"] for st in ("BS", "IS", "CF")))
        if header_only and heading_matches:
            fresh = source_contract(table["prefix"] + " " + header_text)
            if fresh:
                fresh["unit"] = unit_for(table, compact(header_text))
                contract = fresh
            else:
                issues.append({"table": table["index"], "reason": "STATEMENT_HEADER_UNVERIFIED"})
            continue
        # Presence is not accuracy: unaligned whole-cell data is an extraction gap.
        for row in rows:
            if any(any(financial_account(line, st)[0] for st in ("BS", "IS", "CF")) or
                   any(k in compact(cell_text(c)) for k in ("자산총계", "자본총계", "매출액", "영업활동으로인한현금흐름"))
                   for c in row for line in c["lines"]):
                if any(re.search(r"\d{2}", cell_text(c)) for c in row[1:]):
                    present = True
                    if len(row[0]["lines"]) == 1 and len(cell_text(row[0])) > 100:
                        issues.append({"table": table["index"], "reason": "COMBINED_CELL_BOUNDARIES_UNVERIFIED"})
        if not zone or not contract or (correction_file and amendment not in {"AFTER", "FILED_BODY"}):
            continue
        if not report_end:
            issues.append({"table": table["index"], "reason": "REPORT_PERIOD_UNVERIFIED"})
            continue
        if contract["period_end"] != report_end:
            issues.append({"table": table["index"], "reason": "COMPARATIVE_STATEMENT_PERIOD"})
            continue
        try:
            layout = grid(rows)
        except ValueError:
            issues.append({"table": table["index"], "reason": "SOURCE_LAYOUT_AMBIGUOUS"})
            continue
        current_header = None
        for hr in layout[:4]:
            for col, (ri, ci, c) in hr.items():
                h = compact(cell_text(c))
                mt = TERM.search(h)
                if mt and mt.group(1) == contract["term"] and "定正" not in h:
                    current_header = (ri, ci, c, h)
                    break
            if current_header:
                break
        if not current_header:
            issues.append({"table": table["index"], "reason": "CURRENT_HEADER_UNVERIFIED"})
            continue
        hi, hc, header, ht = current_header
        current_cols = sorted(k for k, v in layout[hi].items() if v[:2] == (hi, hc))
        nearest = compact(table["prefix"])
        heads = list(HEADING.finditer(nearest))
        tail = nearest[heads[-1].end():] if heads else nearest
        unit = unit_for(table, tail) if re.search(r"단위[:：]", tail) else unit_for(table, "") or contract.get("unit", "")
        bases = {}
        for hr in layout[hi+1:hi+3]:
            for col in current_cols:
                if col in hr:
                    value = compact(cell_text(hr[col][2]))
                    if value == "누적":
                        bases[col] = "cumulative"
                    elif value == "3개월":
                        bases[col] = "three_month"
        for ri, row in enumerate(rows):
            for ac, account in enumerate(row):
                account_lines = account["lines"]
                for li, label in enumerate(account_lines):
                    metric, priority = financial_account(label, contract["statement"])
                    if not metric:
                        continue
                    candidate_cells = {}
                    for col in current_cols:
                        entry = layout[ri].get(col)
                        if entry and entry[0] == ri and entry[1] > ac:
                            candidate_cells.setdefault(entry[1], (col, entry[2]))
                    for ci, (col, c) in candidate_cells.items():
                        if len(account_lines) > 1 and len(c["lines"]) != len(account_lines):
                            issues.append({"table": table["index"], "row": ri, "reason": "MULTILINE_ALIGNMENT_UNVERIFIED"})
                            continue
                        token = c["lines"][li] if len(account_lines) > 1 else cell_text(c)
                        value = decimal_amount(token, label, metric)
                        if value is None:
                            if compact(token) not in {"", "-", "—", "–", "―"}:
                                issues.append({"table": table["index"], "row": ri, "column": ci, "reason": "INVALID_NUMERIC_TOKEN"})
                            continue
                        basis = "instant" if contract["statement"] == "BS" else bases.get(col, "cumulative")
                        start = contract["period_start"]
                        if basis == "three_month":
                            end = date.fromisoformat(contract["period_end"])
                            ordinal = end.year * 12 + end.month - 3
                            start = date(ordinal // 12, ordinal % 12 + 1, 1).isoformat()
                        with localcontext() as context:
                            context.prec = 50
                            amount = value * UNITS[unit] if unit in UNITS else None
                        source_ok = amount is not None and (basis == "instant" or bool(start))
                        observations.append({**contract, "period_start": start, "period": kind(contract["period_start"], contract["period_end"], ht),
                            "metric": metric, "account_name": label, "raw_amount": token,
                            "amount_reported": str(value), "amount_krw": str(amount) if amount is not None else "",
                            "unit": unit, "unit_multiplier": str(UNITS[unit]) if unit in UNITS else "",
                            "unit_known": unit in UNITS, "priority": priority, "parser_confidence": 1.0 if source_ok else 0.0,
                            "table_index": table["index"], "row_index": ri, "value_col": ci, "source_line_index": li,
                            "source_character": c["source_character"], "measurement_basis": basis,
                            "amendment_region": amendment, "correction_file": correction_file,
                            "structural_status": "PASS" if source_ok else "UNVERIFIED",
                            "availability_status": "UNVERIFIED", "backtest_eligible": False,
                            "value_basis": "explicit current term and measurement basis from original headers",
                            "parser_version": PARSER_VERSION})
                        if contract["statement"] == "BS":
                            observations[-1]["period"] = report_period
    return {"candidates": observations, "issues": issues, "financial_data_present": present,
            "report_period_end": report_end, "correction_file": correction_file}


def select_verified(candidates):
    """No priority can turn unknown structure or contradictory originals into money."""
    groups = {}
    for row in candidates:
        if row.get("structural_status") != "PASS":
            continue
        groups.setdefault((row["metric"], row["scope"], row["period_end"], row["measurement_basis"]), []).append(row)
    selected = []
    for key, rows in sorted(groups.items()):
        if len({row["amount_krw"] for row in rows}) != 1:
            continue
        selected.append({**min(rows, key=lambda r: (r["amendment_region"] != "FILED_BODY", r["table_index"], r["row_index"])),
                         "candidate_count": len(rows)})
    # Keep one explicit basis per metric/scope for compatibility. Cumulative is
    # selected, never silently interpreted as a standalone quarter.
    out = {}
    for row in selected:
        key = row["metric"], row["scope"]
        if key not in out or row["measurement_basis"] == "cumulative":
            out[key] = row
    return list(out.values())


def backtest_usable(row, signal_date, evidence):
    """Only attested receipt-specific availability and mapping can open the gate."""
    if row.get("structural_status") != "PASS" or not isinstance(evidence, dict):
        return False
    if not all(evidence.get(k) is True for k in ("identity_verified", "correction_chain_verified", "publication_verified")):
        return False
    if not row.get("rcept_no") or not row.get("document_sha256"):
        return False
    if evidence.get("rcept_no") != row.get("rcept_no") or evidence.get("document_sha256") != row.get("document_sha256"):
        return False
    try:
        available = date.fromisoformat(evidence["available_date"])
        signal = date.fromisoformat(signal_date)
    except (KeyError, TypeError, ValueError):
        return False
    # A date alone cannot establish publication before a same-day close.
    return available < signal
