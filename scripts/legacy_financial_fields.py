"""Single owner of legacy account aliases and strict numeric tokens (no I/O).

Extracted unchanged from the v5 collector; viewer source guards use these
fields without requiring collection/network dependencies.
"""
from __future__ import annotations
import math
import re

ALIASES = {
    "equity": [
        "자본총계", "자본합계", "자기자본", "자본총액",
    ],
    "revenue": [
        "매출액", "매출", "영업수익", "영업수익합계", "수익(매출액)",
    ],
    "net_income": [
        "당기순이익", "당기순이익(손실)", "당기순손익", "분기순이익", "분기순이익(손실)",
        "분기순손익", "분기순손실", "반기순이익", "반기순이익(손실)", "반기순손익", "반기순손실", "당기순손실",
    ],
    "ocf": [
        "영업활동으로인한현금흐름", "영업활동현금흐름", "영업활동으로부터의현금흐름",
        "영업활동에의한현금흐름", "영업활동으로부터의순현금흐름",
    ],
    "total_assets": [
        "자산총계", "총자산", "자산합계",
    ],
    "total_liabilities": [
        "부채총계", "총부채", "부채합계",
    ],
    "current_assets": [
        "유동자산", "유동자산총계", "유동자산합계",
    ],
    "current_liabilities": [
        "유동부채", "유동부채총계", "유동부채합계",
    ],
    "cash_and_equivalents": [
        "현금및현금성자산", "현금및현금등가물", "현금및현금성자산합계",
    ],
    "short_term_borrowings": [
        "단기차입금", "단기차입금합계", "단기금융부채",
    ],
    "current_portion_long_term_debt": [
        "유동성장기부채", "유동성장기차입금", "유동성사채",
    ],
    "long_term_borrowings": [
        "장기차입금", "장기차입금합계", "장기금융부채",
    ],
    "bonds_payable": [
        "사채", "회사채", "사채합계",
    ],
    "operating_income": [
        "영업이익", "영업이익(손실)", "영업손익", "영업손실",
    ],
    "gross_profit": [
        "매출총이익", "매출총이익(손실)", "매출총손익", "매출총손실",
    ],
    "cost_of_sales": [
        "매출원가", "영업비용",
    ],
    "ppe": [
        "유형자산", "유형자산합계", "유형자산순액",
    ],
    "capex_ppe": [
        "유형자산의취득", "유형자산취득", "유형자산의취득으로인한현금유출",
        "유형자산취득으로인한현금유출",
    ],
    "capex_intangibles": [
        "무형자산의취득", "무형자산취득", "무형자산의취득으로인한현금유출",
        "무형자산취득으로인한현금유출",
    ],
    "depreciation": [
        "감가상각비", "유형자산감가상각비",
    ],
    "amortization": [
        "무형자산상각비", "무형자산감가상각비",
    ],
    "ebitda": [
        "EBITDA", "상각전영업이익",
    ],
    "dividends_paid": [
        "배당금의지급", "배당금지급", "현금배당금의지급", "현금배당금지급",
    ],
    "cash_dividend_total": [
        "현금배당금총액", "현금배당금합계", "배당금총액",
    ],
    "dividend_per_share": [
        "주당현금배당금", "주당배당금", "보통주주당현금배당금",
    ],
}

# Explicit statement context is required. Unknown/malformed headings are data
# gaps; do not promote annual dividend/business summaries to current-period IS.
METRIC_STATEMENTS = {
    "equity": {"BS"},
    "total_assets": {"BS"},
    "total_liabilities": {"BS"},
    "current_assets": {"BS"},
    "current_liabilities": {"BS"},
    "cash_and_equivalents": {"BS"},
    "short_term_borrowings": {"BS"},
    "current_portion_long_term_debt": {"BS"},
    "long_term_borrowings": {"BS"},
    "bonds_payable": {"BS"},
    "ppe": {"BS"},
    "revenue": {"IS"},
    "net_income": {"IS"},
    "operating_income": {"IS"},
    "gross_profit": {"IS"},
    "cost_of_sales": {"IS"},
    "ebitda": {"IS"},
    "ocf": {"CF"},
    "capex_ppe": {"CF"},
    "capex_intangibles": {"CF"},
    "depreciation": {"CF", "IS"},
    "amortization": {"CF", "IS"},
    "dividends_paid": {"CF"},
}

UNIT_MULTIPLIERS = {
    "원": 1.0,
    "천원": 1_000.0,
    "백만원": 1_000_000.0,
    "억원": 100_000_000.0,
}


def norm_account(x: str) -> str:
    s = str(x or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("ㆍ", "").replace("·", "").replace("*", "")
    s = re.sub(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVXLC0-9.()\-]+", "", s)
    return s


def parse_number(x: str) -> float:
    s = str(x or "").strip()
    s = s.replace("△", "-").replace("▲", "-").replace("Δ", "-").replace("－", "-")
    negative_parentheses = s.startswith("(") and s.endswith(")")
    if negative_parentheses:
        s = s[1:-1].strip()
    # One complete numeric token. Commas must separate groups of three;
    # whitespace between numbers, footnotes and concatenated amounts are gaps.
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", s):
        return math.nan
    value = float(s.replace(",", ""))
    if not math.isfinite(value):
        return math.nan
    return -abs(value) if negative_parentheses else value


def choose_metric(account: str, statement: str) -> tuple[str, int] | tuple[None, int]:
    a = norm_account(account)
    best = None
    best_score = 999
    for metric, aliases in ALIASES.items():
        allowed = METRIC_STATEMENTS.get(metric, set())
        if not statement or statement not in allowed:
            continue
        for rank, alias in enumerate(aliases):
            na = norm_account(alias)
            if a == na:
                score = rank
            else:
                continue
            if score < best_score:
                best = metric; best_score = score
    return best, best_score
