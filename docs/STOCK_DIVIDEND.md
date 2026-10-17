# Stock-dividend subledger contract 1

Owner: `scripts/stock_dividend.py`. This is an implemented common corporate-action
component, **not completed PROJECT/DSL stock-dividend execution support**. Public
registry and PROJECT reject `stock_dividend` with an explicit capability gap.
The original merger/split/cash behavior and ordinary 1bp guard remain intact.
Synthetic tests are not evidence for registering any real event.

`StockDividendBook.close` atomically processes one supplied observed session:
opening eligible whole-share holdings → ex-date rights → actual approval → actual
credit → actual tradability release → close trades → explicit rights valuation.
Ex-date new purchases get no entitlement. Sales after entitlement do not remove
the original account's rights. Conditional and approved claims remain distinct.
No assumed approval, price, probability, calendar, credit or listing date exists.

Before actual credit, a right is never tradable or spendable. Credit moves its
whole-share quantity to locked stock; a separately evidenced listing/release
moves that quantity to tradable stock. Neither operation books cash income or
applies a return multiplier. At unchanged marks/prices, classification changes
leave value unchanged. Price changes and changes in the explicitly supplied
conditional/liquidity valuation remain visible; they are not forced to zero.

Every positive pending claim requires an exact-session unit mark, evidence and
valuation rationale (including conditional approval and liquidity assumptions).
An ordinary-share close is **not** a default rights value. Historical valuation
and usable-session metadata require independent source review. A hash/URL/kind
label cannot authenticate a fact. Primary metadata and synthetic metadata are
kept in the input audit; synthetic evidence is rejected in evidenced research.
All books explicitly remain investment-unapproved. Same-session evidence usable
at the close is caller-established; no same-close trade signal is authorized.

Amounts use exact Decimal inputs, a fixed 50-digit local context (inexact book
arithmetic rejects rather than silently rounding) and whole-share
stock trades. Every close is transactional: failed valuation, funding, approval,
credit, listing or trade restores all previous state/history. Missing prices,
future evidence, duplicate entitlements/receipts and overlapping pending events
on one security reject. Independent amount/quantity oracles test value and cash.

Unsupported and blocked: fractional cash settlement (fractions remain claims,
never rounded away), withholding or tax, unknown no-deduction treatment, shorting,
margin, partial credits, cancellation/compensation and interacting corporate
actions. Receipt requires independently verified `verified_none` tax treatment.
This limited no-deduction contract is not an assertion about Korean investors.
Initial quantities must be independently established eligible opening holdings;
the subledger does not reconstruct exchange settlement or legal record ownership.

`validate_market_reference` separately checks an explicitly evidenced effective
reference price: `Close / reference_price - 1` against `ChangesRatio / 100`, with
the unchanged 1bp tolerance. It never reverse-solves an official base. Its result
does not certify economic value, cashflow, original source accuracy or PIT.
Economic value is cash + tradable stock + locked stock + marked rights, which
need not earn the same return as the market-reference series.

Remaining public integration is substantive: the weight allocator must carry
separate gross/net rights and locked-stock sleeves, constrain target trades and
cost liquidity, reconcile quantities, export audits, preserve next-close timing,
and validate both price/reference and independently computed asset books. This
must be implemented before adding stock_dividend to supported event types. The
generated capability contract exposes the subledger and this explicit boundary.
No production event or operating PIT gate is changed in Stage12.
