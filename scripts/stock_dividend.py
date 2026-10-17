"""Quantity subledger for evidenced stock dividends; never a return override.

This common corporate-action component is not yet wired to the weight-based
PROJECT allocator. It deliberately cannot register an executable DSL event.
Inputs labelled synthetic are accepted only in a synthetic book. Evidence
metadata is an audit contract, not automatic certification of a web document.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Context, Decimal, Inexact, InvalidOperation, localcontext
import re
from typing import Mapping

from execution_contract import HELD_RETURN_TOLERANCE_BPS

EVENT = "stock_dividend"
CONTRACT_VERSION = "1"
CONTRACT = {
    "version": CONTRACT_VERSION,
    "owner": "scripts/stock_dividend.py",
    "scope": "quantity subledger and market-reference validation; not DSL execution support",
    "public_execution": "blocked: pending-rights integration with target weights, costs and audit export is incomplete",
    "rights": "ex-date opening quantities only; separate conditional/approved rights survive sales",
    "valuation": "explicit as-of unit mark, evidence and rationale for every pending right; no default close/probability",
    "receipt": "actual credit moves approved whole-share rights into locked shares without second income",
    "tradability": "separate actual listing/release evidence; locked shares cannot be sold",
    "unsupported": ["fractional cash settlement", "withholding/tax", "shorts", "borrowing", "rejection/cancellation cash compensation"],
    "price_reference": "Close / evidenced reference price - 1 versus ChangesRatio / 100; existing 1bp tolerance",
    "economic_value": "settled cash + tradable shares + locked shares + explicitly marked rights; never equated to ChangesRatio",
    "certification": "synthetic and evidenced_research books only; no investment/PIT approval",
    "arithmetic": "50-digit Decimal book rejects inexact arithmetic; reference-price division is a separate rounded diagnostic",
}


def number(value, name, *, positive=False):
    if isinstance(value, (bool, float)):
        raise ValueError(f"{name}: use exact decimal strings/integers, not bool/float")
    try:
        result = Decimal(value)
    except Exception:
        raise ValueError(f"{name}: invalid decimal") from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(f"{name}: requires finite {'positive' if positive else 'nonnegative'} value")
    return result


def day(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date requires YYYY-MM-DD")
    return date.fromisoformat(value)


def code(value):
    if type(value) is not str or not re.fullmatch(r"\d{6}", value):
        raise ValueError("security requires exact six-digit code")
    return value


@dataclass(frozen=True)
class Evidence:
    source: str
    sha256: str
    location: str
    usable_session: str
    kind: str  # synthetic or primary; requires independent human/source review

    def check(self, session, scope):
        if self.kind not in {"synthetic", "primary"}:
            raise ValueError("unsupported evidence kind")
        if scope == "evidenced_research" and self.kind != "primary":
            raise ValueError("synthetic evidence cannot enter evidenced research")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256) or not self.location.strip():
            raise ValueError("evidence requires SHA256 and exact location")
        if self.kind == "primary" and not re.fullmatch(r"https://[^\s]+", self.source):
            raise ValueError("primary evidence requires HTTPS source")
        if self.kind == "synthetic" and not self.source.startswith("synthetic:"):
            raise ValueError("synthetic evidence must be explicitly labelled")
        if day(self.usable_session) > day(session):
            raise ValueError("future evidence is unavailable at this session")


@dataclass(frozen=True)
class Terms:
    event_id: str
    security: str
    ex_date: str
    record_date: str
    rate: str  # additional shares per eligible old share, NOT a split multiplier
    evidence: Evidence  # establishes rate, eligibility and these distinct dates

    def check(self, session, scope):
        if not self.event_id.strip() or code(self.security) != self.security:
            raise ValueError("invalid event identifier/security")
        if day(self.ex_date) != day(session) or day(self.record_date) < day(self.ex_date):
            raise ValueError("entitlement requires exact ex-date and verified record date")
        number(self.rate, "additional share rate", positive=True)
        self.evidence.check(session, scope)


@dataclass(frozen=True)
class Decision:
    event_id: str
    actual_date: str
    approved: bool
    evidence: Evidence


@dataclass(frozen=True)
class Credit:
    event_id: str
    actual_date: str
    shares: int
    evidence: Evidence
    tax_treatment: str
    tax_evidence: Evidence


@dataclass(frozen=True)
class Listing:
    event_id: str
    actual_date: str
    evidence: Evidence


@dataclass(frozen=True)
class RightMark:
    event_id: str
    session: str
    unit_value: str
    rationale: str  # including conditional approval/liquidity assumptions
    evidence: Evidence


@dataclass(frozen=True)
class Trade:
    security: str
    side: str
    shares: int
    fee: str = "0"  # exact externally calculated settled trading cost


def whole(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name}: nonnegative whole shares required")
    return value


class StockDividendBook:
    """Long-only amount/quantity subledger, one atomic close per supplied session.

    Ordering: ex-date OPENING holdings -> decision -> actual credit -> listing
    -> close trades -> explicit rights marks. Caller supplies observed sessions
    and prices; no inferred calendar, payment date, tax, price or mark is made.
    Initial shares must be caller-established eligible opening holdings. This
    class does not reconstruct trade settlement or legal record-date ownership.
    """

    def __init__(self, cash, shares: Mapping[str, int] | None = None, *, scope):
        if scope not in {"synthetic", "evidenced_research"}:
            raise ValueError("book requires synthetic or evidenced_research scope")
        self.scope = scope
        self.cash = number(cash, "cash")
        self.shares = {code(c): whole(q, "opening shares") for c, q in (shares or {}).items()}
        self.claims = {}
        self.last_session = None
        self.history = []

    def close(self, session, prices, *, entitlements=(), decisions=(), credits=(), listings=(), trades=(), marks=()):
        # An invalid multi-action close must leave cash, rights, shares and log
        # exactly intact. No partially applied approval/credit/trade survives.
        draft = deepcopy(self)
        entitlements, decisions, credits, listings, trades, marks = (
            tuple(items) for items in (entitlements, decisions, credits, listings, trades, marks))
        with localcontext(Context(prec=50)) as ctx:
            ctx.traps[Inexact] = True
            try:
                result = draft._close(session, prices, entitlements, decisions, credits, listings, trades, marks)
            except Inexact:
                raise ValueError("ledger arithmetic exceeds exact 50-digit precision; no silent rounding") from None
        self.__dict__.update(draft.__dict__)
        return result

    def _close(self, session, prices, entitlements, decisions, credits, listings, trades, marks):
        dt = day(session)
        if self.last_session is not None and dt <= day(self.last_session):
            raise ValueError("sessions must strictly increase; duplicate close forbidden")
        px = {code(c): number(p, "close", positive=True) for c, p in prices.items()}
        actions = []
        for terms in entitlements:
            terms.check(session, self.scope)
            if terms.event_id in self.claims:
                raise ValueError("duplicate stock-dividend entitlement")
            if any(c["terms"].security == terms.security and c["terms"].ex_date == terms.ex_date for c in self.claims.values()):
                raise ValueError("duplicate security/ex-date entitlement under another identifier")
            if any(c["terms"].security == terms.security and c["state"] != "released" for c in self.claims.values()):
                raise ValueError("overlapping pending corporate actions on one security unsupported")
            # Rights stay attached to the original account after old shares sell.
            eligible = self.shares.get(terms.security, 0)
            self.claims[terms.event_id] = {
                "terms": terms, "eligible_shares": eligible,
                "quantity": Decimal(eligible) * number(terms.rate, "rate", positive=True),
                "state": "conditional", "locked": 0,
            }
            actions.append({"event": terms.event_id, "action": "entitlement", "eligible_shares": eligible})
        for decision in decisions:
            claim = self.claims[decision.event_id]
            decision.evidence.check(session, self.scope)
            if day(decision.actual_date) != dt or type(decision.approved) is not bool or claim["state"] != "conditional":
                raise ValueError("decision requires a pending conditional right")
            if not decision.approved:
                # Cancellation valuation/compensation is not silently zeroed.
                raise ValueError("rejected dividend requires unsupported cancellation accounting")
            claim["state"] = "approved"
            actions.append({"event": decision.event_id, "action": "approval"})
        for credit in credits:
            claim = self.claims[credit.event_id]
            credit.evidence.check(session, self.scope)
            credit.tax_evidence.check(session, self.scope)
            whole(credit.shares, "credited shares")
            if day(credit.actual_date) != dt or dt < day(claim["terms"].record_date) or claim["state"] != "approved":
                raise ValueError("credit requires approved right and exact actual credit date; no plans")
            if credit.tax_treatment != "verified_none":
                raise ValueError("withholding/tax unsupported; verified no-deduction treatment required")
            if claim["quantity"] != claim["quantity"].to_integral_value():
                raise ValueError("fractional cash settlement unsupported; cannot discard or fabricate fractions")
            if Decimal(credit.shares) != claim["quantity"]:
                raise ValueError("actual credit differs from entitlement; partial credit unsupported")
            claim["locked"], claim["state"] = credit.shares, "credited_locked"
            actions.append({"event": credit.event_id, "action": "actual_credit", "shares": credit.shares})
        for listing in listings:
            claim = self.claims[listing.event_id]
            listing.evidence.check(session, self.scope)
            if day(listing.actual_date) != dt or claim["state"] != "credited_locked":
                raise ValueError("tradable release requires credited shares and exact actual listing date")
            security = claim["terms"].security
            self.shares[security] = self.shares.get(security, 0) + claim["locked"]
            claim["locked"], claim["state"] = 0, "released"
            actions.append({"event": listing.event_id, "action": "tradable_release"})
        for trade in trades:
            security = code(trade.security)
            q = whole(trade.shares, "trade shares")
            if q == 0 or trade.side not in {"buy", "sell"}:
                raise ValueError("trade requires positive quantity and buy/sell side")
            value, fee = Decimal(q) * px[security], number(trade.fee, "trade fee")
            held = self.shares.get(security, 0)
            if trade.side == "buy":
                if self.cash < value + fee:
                    raise ValueError("insufficient settled cash; rights/locked shares cannot fund purchases")
                self.cash -= value + fee
                self.shares[security] = held + q
            else:
                if q > held:
                    raise ValueError("insufficient tradable shares; pending rights/locked shares cannot be sold")
                if self.cash + value < fee:
                    raise ValueError("insufficient cash for fees")
                self.cash += value - fee
                self.shares[security] = held - q
            actions.append({"action": trade.side, "security": security, "shares": q, "fee": str(fee)})
        required = {eid for eid, c in self.claims.items() if c["state"] in {"conditional", "approved"} and c["quantity"] > 0}
        mark_map = {}
        for mark in marks:
            if mark.event_id in mark_map or mark.event_id not in required:
                raise ValueError("duplicate or extraneous rights mark")
            if day(mark.session) != dt or not mark.rationale.strip():
                raise ValueError("rights mark requires exact session and valuation rationale")
            mark.evidence.check(session, self.scope)
            mark_map[mark.event_id] = number(mark.unit_value, "rights unit mark")
        if required != set(mark_map):
            raise ValueError("explicit as-of mark required for every pending right; no default valuation")
        tradable_value = sum((Decimal(q) * px[c] for c, q in self.shares.items() if q), Decimal(0))
        locked_value = sum((Decimal(c["locked"]) * px[c["terms"].security] for c in self.claims.values() if c["locked"]), Decimal(0))
        rights_value = sum((self.claims[eid]["quantity"] * p for eid, p in mark_map.items()), Decimal(0))
        # Receipt changes asset classification. Its price/valuation change, if
        # any, remains visible; no cash income or 1+rate multiplier is added.
        result = {"session": session, "scope": self.scope, "investment_approved": False,
                  "cash": str(self.cash), "tradable_shares": dict(self.shares),
                  "claims": {eid: {"security": c["terms"].security, "eligible_shares": c["eligible_shares"],
                                   "quantity": str(c["quantity"]), "state": c["state"], "locked_shares": c["locked"]}
                             for eid, c in self.claims.items()},
                  "tradable_value": str(tradable_value), "locked_value": str(locked_value),
                  "rights_value": str(rights_value), "value": str(self.cash + tradable_value + locked_value + rights_value),
                  "actions": actions,
                  "inputs": {"prices": {c: str(p) for c, p in px.items()},
                             **{name: [asdict(item) for item in items] for name, items in
                                [("entitlements", entitlements), ("decisions", decisions), ("credits", credits),
                                 ("listings", listings), ("trades", trades), ("marks", marks)]}}}
        self.last_session = session
        self.history.append(deepcopy(result))
        return result


def validate_market_reference(*, session, security, close, reference_price, changes_ratio_pct, evidence, scope):
    """Market-price check only. This does not certify an entitlement or NAV.

    Explicit reference price is required; never invert ChangesRatio to invent it.
    Evidence must identify the security, effective date and reference-price row.
    """
    code(security)
    if scope not in {"synthetic", "evidenced_research"}:
        raise ValueError("invalid reference-check scope")
    evidence.check(session, scope)
    px, base = number(close, "close", positive=True), number(reference_price, "reference price", positive=True)
    if isinstance(changes_ratio_pct, (bool, float)):
        raise ValueError("ChangesRatio requires exact decimal")
    try:
        reference = Decimal(changes_ratio_pct)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid ChangesRatio") from None
    if not reference.is_finite() or reference < -100:
        raise ValueError("invalid ChangesRatio")
    with localcontext(Context(prec=50)):
        price_return = px / base - 1
        difference = abs(price_return - reference / 100) * 10000
    if difference > Decimal(str(HELD_RETURN_TOLERANCE_BPS)):
        raise ValueError("official-reference price check exceeds existing 1bp tolerance")
    return {"basis": "reference_price", "security": security, "session": session,
            "return": str(price_return), "difference_bps": str(difference),
            "reference_price": str(base), "close": str(px), "changes_ratio_pct": str(reference),
            "evidence": asdict(evidence), "tolerance_bps": str(HELD_RETURN_TOLERANCE_BPS),
            "economic_return_certified": False, "investment_approved": False}


def reject_public_execution(events):
    """Shared registry/PROJECT boundary until the allocator supports this book."""
    if events is not None and not events.empty and events["event_type"].eq(EVENT).any():
        raise ValueError("stock_dividend capability_gap: quantity subledger exists, but public target-weight/cost integration is incomplete; verified event and rights valuation/credit/listing evidence required")
