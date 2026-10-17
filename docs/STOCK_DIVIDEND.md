# Stock-dividend contract 2

Owners: `scripts/stock_dividend.py` (quantity/event validation),
`scripts/stock_dividend_execution.py` (two-book sleeve), and the existing
`simulate_target_weight_portfolio` in PROJECT (allocation, cash, costs, NAV).
Both top-N and deciles call that same allocator. No strategy backtester or
performance formula is added. No actual stock dividend is registered yet.

Each `stock_dividend` registry row requires `stock_dividend_contract` JSON:
`scope`, `quantity_policy`, `terms`, `decisions`, `credits`, `listings`, `marks`,
`market_reference`. The row's code, effective date and additional-share rate
must exactly agree with its terms; cash_per_share is zero. Unknown root fields
reject. Registry files reject synthetic scopes. Primary labels/URLs/hashes are
traceability metadata, not independent source authentication or PIT approval.

Daily ordering is opening eligible shares → ex-date rights → actual approval or
cancellation → actual credit → actual tradability release → existing close
rebalance. Only ex-date opening eligible holdings receive rights; post-ex buys
receive none. An old-stock sale does not sell the account's rights. Each book
captures its own actual model quantity, so Gross/Net rights differ after costs.
The engine does not reconstruct settlement/record ownership: independently
reviewed ex-date/record-date terms and eligible opening holdings are required.

Every positive conditional/approved right needs an exact-session unit value,
evidence usable by that close and an explicit conditional/liquidity rationale.
There is no default stock-close mark, approval probability, forward fill or
payment date. The book checks 50-digit Decimal arithmetic without silently
rounding; the pre-existing allocator still uses floating-point weights.
An approved right becomes separately locked stock only on evidenced actual
credit. A separately evidenced observed listing/release date makes it tradable.
No weekday/date estimate is used. Whole-share primary credits require explicit
`shares_by_book` for Gross and Net, equal to each account's entitlement.

The engine calculates economic value from ordinary tradable positions plus the
independently valued sleeve. It adds the sleeve's value change and the released
quantity exactly once. The receipt/release creates no cash income or trading
cost; any change of unit valuation remains an explicit economic gain/loss.
Actual close trades and fixed-bps costs retain the original pre-cost turnover /
post-cost target allocation convention. Targets mean **tradable-stock weights**
of total NAV. Illiquid rights/locked stock enter NAV but cannot be sold, spent,
or proportionately erased by costs. Insufficient settled liquidity fails; the
engine does not scale targets. `weights`/`net_weights` separate Cash,
CashReceivable and StockDividendIlliquid. Two-book input/state audits and
reference checks export as `stock_dividend_books_<scenario>.json` and
`stock_dividend_price_checks_<scenario>.json`; a subledger snapshot's `value`
is the dividend securities/sleeve value, not the whole portfolio NAV.

Actual rejection/cancellation needs an actual decision and independently
verified no-compensation evidence. It removes the conditional asset and books
the loss of its previous marked value. Unknown compensation remains blocked.
Tax/withholding deductions, fractional cash, partial credits, shorts, borrowing
and interacting split/merger/cash events on the same security remain blocked.
A primary target allocation yielding fractional quantities is rejected rather
than rounded. Thus this extension does not yet solve legal account-level
fractional distribution in the original continuous-weight research strategy.

`quantity_policy=synthetic_pro_rata` is an explicit theoretical test convention:
continuous quantities and exact pro-rata credit, no fractional cash. It is
accepted **only in synthetic scope**, never in the production registry or as
historical legal settlement. Fixed trading-cost assumptions are separate from
historical distribution taxes. Credit otherwise requires `verified_none` tax
metadata and evidence; no actual Korean taxpayer's zero-tax status is assumed.

On exactly the registered ex-date, a held security requires a separately
explicit reference price and exchange ChangesRatio; Close/reference−1 is
checked at the unchanged 1bp tolerance. The economic return is not compared to
ChangesRatio. Other days, unregistered events, and existing corporate actions
retain their previous held-return validation. This is not a blanket exemption,
return replacement, inferred reference price, or an operating PIT-gate change.
All synthetic and evidenced-research books remain investment-unapproved.

Tests: `test_stock_dividend.py` and `test_stock_dividend_execution.py`. The latter
uses an independent share/cash oracle for every daily Gross/Net NAV and settled
cash balance, costs, sales before/after credit, post-ex new buys, cancellation,
credit/listing transitions, continuous-fraction boundaries and multiple events.
Floating-point oracle comparisons allow 1e-8 currency units on 10000 capital;
this numerical allowance does not change any market-return tolerance.

## Explicit real-data research contract v1 (subledger contract3)

An optional validated DSL `research` object selects a different, fingerprinted
research model; absent it, contract2 whole-account behavior and old DSL
fingerprints/NAV remain unchanged. Its fact catalog is a separate SHA-pinned
`config/research/` file, never the operating production event registry.

Conditional-right valuation is a modeling decision, not an unavailable official
price. Alternatives: zero until confirmation defers value and creates a later
recognition jump; full underlying-share equivalence ignores conditional approval
and liquidity discounts; a declared fraction of underlying close makes those
risks visible as a sensitivity scenario, without claiming an observed probability.
The baseline chooses full share equivalence (fraction1.0) before observing results;
0.9 and settlement-delay scenarios test sensitivity, never optimize the choice.
Approved rights use full share equivalence. Cancellation still needs actual
primary decision/no-compensation facts and recognizes loss, not a retrospective
assumption of successful approval. Directly observed market reference-price
returns and these modeled economic NAV returns remain different quantities.

Actual facts retain source/publication/effective dates. Date-only evidence is
usable after its publication date on the first supplied observed session. A
retrospective report does not backdate an approval used in NAV. Model marks use
only the current underlying close and currently recognized state; they are
`research_model` evidence, never primary price observations.

`research_pro_rata` has continuous units, including rights and final delivery.
It deliberately does not model whole-account fractional cash. Virtual delivery
at the official market listing close (plus explicit observed-session lag) is a
virtual-account settlement convention, NOT a claimed actual brokerage credit.
It requires a known approval and primary official listing evidence. No source
listing means no guessed virtual date; rights stay nontradable. Credit and release
occur once with zero new income/cost; any mark change is separately visible.
Conditional/approved rights cannot be sold or fund rebalances. Original settled
cash, post-cost target allocation and insufficient-liquidity errors are unchanged.

Both Gross and Net exclude stock-dividend withholding and fractional cash.
Net deducts the existing declared trading commissions/tax/spread/slippage only.
The model never says a real taxpayer owes zero dividend tax. Whole-account
credit still requires its original verified treatment and integer boundaries.
This research model gives no operating DART/PIT approval and no total-return,
legal ownership, personalized tax or broker-account certification. Report labels
and diagnostics show these assumptions. Reused event facts do not become
historical trading signals before their public availability.
