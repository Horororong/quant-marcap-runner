"""Stock-dividend sleeve in PROJECT's existing two-book allocator.

No strategy selection, allocation, costs, return overrides or performance here.
The owner StockDividendBook handles event ordering/quantity validation. PROJECT
continues to own targets, next-close execution, trading and settled liquidity.
"""
from dataclasses import asdict
from decimal import Decimal, Context, Inexact, localcontext
import json
import math

from stock_dividend import (StockDividendBook, Evidence, Terms, Decision, Credit,
                            Listing, RightMark, day, number, validate_market_reference)


def evidence(raw):
    return Evidence(**raw)


class DividendExecution:
    def __init__(self, rows, sessions, assets, *, allow_short=False):
        self.plans = []
        self.books = {}
        self.previous = {"Gross": 0., "Net": 0.}
        self.audit = []
        self.references = []
        if rows.empty:
            return
        if allow_short:
            raise ValueError("stock-dividend short/margin accounting unsupported")
        seen = set()
        observed = {str(s.date()) for s in sessions}
        for _, row in rows.iterrows():
            raw = row.get("stock_dividend_contract")
            if not isinstance(raw, str):
                raise ValueError("stock_dividend capability_gap: explicit stock_dividend_contract required")
            p = json.loads(raw)
            if set(p) != {"scope", "quantity_policy", "terms", "decisions", "credits", "listings", "marks", "market_reference"}:
                raise ValueError("stock-dividend contract has missing/unknown fields")
            t = Terms(**{**p["terms"], "evidence": evidence(p["terms"]["evidence"])})
            t.check(t.ex_date, p["scope"])
            if (t.event_id in seen or t.security not in assets or t.ex_date != str(row.event_date.date())
                    or t.security != row.predecessor_code or row.successor_code != t.security
                    or float(row.cash_per_share) != 0 or number(str(row.share_ratio), "row rate") != number(t.rate, "terms rate")):
                raise ValueError("stock-dividend identity/rate/date mismatch or duplicate")
            seen.add(t.event_id)
            for action in [*p["decisions"], *p["credits"], *p["listings"]]:
                d = action["actual_date"]
                day(d)
                if t.ex_date > d or (str(sessions[0].date()) <= d <= str(sessions[-1].date()) and d not in observed):
                    raise ValueError("actual action date must be a supplied observed session, not a weekday estimate")
            if t.ex_date not in observed:
                raise ValueError("stock dividend requires observed ex-date and explicit opening entitlement; no reconstructed history")
            if p["market_reference"].keys() != {"reference_price", "evidence"}:
                raise ValueError("explicit official-reference price/evidence required")
            number(p["market_reference"]["reference_price"], "reference price", positive=True)
            p["terms"] = t
            self.plans.append(p)
        scopes = {(p["scope"], p["quantity_policy"]) for p in self.plans}
        if len(scopes) != 1:
            raise ValueError("cannot mix synthetic and evidenced event books")
        scope, quantity_policy = scopes.pop()
        self.books = {b: StockDividendBook("0", scope=scope, quantity_policy=quantity_policy) for b in self.previous}

    def phase(self, session, prices, opening_quantities):
        """Return sleeve-value delta and newly tradable quantities, per book."""
        if not self.plans:
            return {b: (0., 0., {}) for b in self.previous}
        output = {}
        for label, book in self.books.items():
            shares = {}
            for security, q in opening_quantities[label].items():
                q = number(str(q), "allocator quantity")
                if book.quantity_policy == "whole":
                    if q != q.to_integral_value():
                        raise ValueError("whole-account entitlement cannot round fractional target-weight quantities")
                    q = int(q)
                shares[security] = q
            book.shares = shares
            entitlements, decisions, credits, listings, marks = [], [], [], [], []
            for p in self.plans:
                t = p["terms"]
                if session == t.ex_date:
                    entitlements.append(t)
                if session < t.ex_date:
                    continue
                for a in p["decisions"]:
                    if session == a["actual_date"]:
                        d = {**a, "event_id": t.event_id, "evidence": evidence(a["evidence"])}
                        if d.get("cancellation_evidence"):
                            d["cancellation_evidence"] = evidence(d["cancellation_evidence"])
                        decisions.append(Decision(**d))
                for a in p["credits"]:
                    if session == a["actual_date"]:
                        # Actual account credit is not inferred from a planned
                        # aggregate issuance. Primary mode requires both accounts.
                        if p["scope"] == "synthetic":
                            with localcontext(Context(prec=50)) as ctx:
                                ctx.traps[Inexact] = True
                                q = (Decimal(shares.get(t.security, 0)) * number(t.rate, "rate")
                                     if session == t.ex_date else book.claims[t.event_id]["quantity"])
                            q = int(q) if book.quantity_policy == "whole" and q == q.to_integral_value() else str(q)
                        else:
                            q = a["shares_by_book"][label]
                        credits.append(Credit(t.event_id, session, q, evidence(a["evidence"]), a["tax_treatment"], evidence(a["tax_evidence"])))
                for a in p["listings"]:
                    if session == a["actual_date"]:
                        listings.append(Listing(t.event_id, session, evidence(a["evidence"])))
                for a in p["marks"]:
                    if session == a["session"]:
                        # Zero-position accounts have no economic right to mark.
                        q = (shares.get(t.security, 0) * number(t.rate, "rate") if session == t.ex_date else book.claims[t.event_id]["quantity"])
                        if q:
                            marks.append(RightMark(event_id=t.event_id, **{**a, "evidence": evidence(a["evidence"])}))
            snapshot = book.close(session, {c: str(v) for c, v in prices.items() if math.isfinite(v) and v > 0},
                                  entitlements=entitlements, decisions=decisions, credits=credits, listings=listings, marks=marks)
            new_value = float(Decimal(snapshot["rights_value"]) + Decimal(snapshot["locked_value"]))
            released = {c: float(book.shares.get(c, 0) - shares.get(c, 0)) for c in set(book.shares) | set(shares)}
            release_value = sum(q * prices[c] for c, q in released.items() if q)
            output[label] = (new_value + release_value - self.previous[label], new_value, released)
            self.previous[label] = new_value
            self.audit.append({"book": label, **snapshot})
            # The engine audit above owns the full immutable input/state trail.
            # Avoid cloning that entire historical trail inside every atomic
            # subledger close; no financial state/claim is cleared here.
            book.history.clear()
        return output

    def check_reference(self, session, prices, observed, held):
        checked = set()
        for p in self.plans:
            t = p["terms"]
            if session == t.ex_date and held.get(t.security, False):
                if observed is None:
                    raise ValueError("stock-dividend ex-date requires independent market-reference series")
                r = observed[t.security]
                result = validate_market_reference(session=session, security=t.security, close=str(prices[t.security]),
                    changes_ratio_pct=str(float(r) * 100), scope=p["scope"],
                    reference_price=p["market_reference"]["reference_price"], evidence=evidence(p["market_reference"]["evidence"]))
                self.references.append(result)
                checked.add(t.security)
        return checked
