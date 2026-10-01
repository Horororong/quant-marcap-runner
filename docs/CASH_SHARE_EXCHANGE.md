# Cash-only share exchange execution

Execution `v2-16-exec-3`, machine contract 16, registry contract 5.
This is a generic, bounded fixed-KRW cash-exchange contract. It is not a claim
that Jeisys Medical cash proceeds or complete historical events are supported.

## Exact entitlement and liquidity

`cash_share_exchange` requires completed legal `event_date`, predecessor code,
empty successor code, `share_ratio=0`, positive finite `cash_per_share`, and a
primary `source` HTTPS URL. Unlike a stock merger, it allocates no successor
shares. Unlike a split, it retires the held security.

Payment requires `payment_date`, `payment_status=verified_actual`, and a primary
`payment_source` HTTPS URL. Registry review must verify that evidence establishes
actual payment and applicable cash treatment; a URL or status label alone is not
independent proof. Planned dates, delisting dates and appraisal-right payments
are not substitutes. Missing or unverified payment metadata rejects execution,
even when a caller only wants an earlier pending-receivable window.

The engine requires original source Volume, tradability, and exchange reference
returns. From the last observed traded close through entitlement, every session
must have observed flat closes, Volume zero and reference return zero. Missing
observations are rejected. The last price and exchange cash determine the
entitlement-day return. That return is an explicitly audited disposal override;
other held securities and prior ordinary returns retain the 1bp reference guard.

Shares become a fixed nominal receivable on entitlement. The receivable counts
in NAV and has zero interest; it is not settled cash. Receipt converts it to
Cash at the first observed session close on/after the actual payment date. It
creates no second gain, artificial sale, turnover, tax, spread or slippage.
A run ending before receipt retains the claim without extending its window.
Multiple claims and different payment dates are accounted for separately.

Gross and Net books keep separate fixed cash amounts. Net trading costs are
paid by the liquid sleeve and never reduce the claim's nominal amount. The
existing fixed-bps target-weight convention still allocates requested equity
weights on post-cost Net NAV; this can leave less settled cash for those targets.
Insufficient settled cash, including post-cost cash, fails rather than silently
scaling targets, borrowing against claims or reinvesting unpaid proceeds.
A converted security cannot be repurchased after entitlement.

No discounting, interest, default, disputed amount, withholding, appraisal
rights, fractional successor shares, mixed stock/cash merger or partial receipt
is implemented by this cash-only contract. Such cases need their own evidence
and explicit supported contract.

## Audit outputs and test scope

Both public top_n and decile paths pass original volumes and references to the
same PROJECT engine. Cash-event runs add CashReceivable alongside Cash. The
engine returns separate gross/net weights, entitlements and receipts. Public
outputs add `cash_entitlements.csv`, `cash_payments.csv` when received in-window,
and `cash_balances_{gross|net}_{scenario}.csv`; deciles store these in each
bucket directory. Amounts are in initial-capital currency units, not NAV units.
Payment processing dates and evidence URLs are retained. Legacy turnover columns
refer to Gross target changes; net_buy_turnover/net_sell_turnover expose actual
Net cost calculation weights when the books diverge. Performance remains
exclusively in CURRENT; there are no new metric formulas here.

Run `python scripts/test_cash_share_exchange.py`. An independent share-quantity
and cash-amount ledger compares every Gross/Net NAV and liquidity observation,
including intervening trades/costs. Synthetic fixtures verify multiple claims,
receipt timing, non-session receipt, pending end-window, no double gains,
blocked early reinvestment, retired security selection, missing suspension
observations and uncompromised reference checks. They are software fixtures,
not actual investment backtests.

## Jeisys Medical 287410: evidence gap

Primary-source references and the annual-report HTML checksum are recorded in
`docs/audits/jeisys-cash-exchange/evidence.json`.

- KRX Aug 19 decision specifies cash only, KRW 13,000 per ordinary share.
  Its statutory 1:1.3575606 exchange ratio is not delivered successor shares.
- KRX Oct 16 notice establishes trading suspension starting Oct 21, 2024.
- KRX Oct 23 completed-exchange report establishes legal completion Oct 23.
  It explicitly identifies Nov 7 payment as expected and subject to change.
- The 2024 annual report filed Apr 7, 2025 confirms actual Oct 23 exchange and
  Nov 7 delisting. Those statements do not confirm actual cash receipt Nov 7.
  Appraisal-right cash KRW 12,910 is a different entitlement.

No cash exchange is added to the production executable registry. The known gap
in `config/kr_corporate_action_gaps.json` instead rejects an affected existing
holding from Oct 23 and a subsequent target selecting it. This does not remove
the stock from historical signal-day eligibility or block unaffected holdings.

The real-source regression uses Sep 2–Oct 24, 2024. Among 53 KOSDAQ securities
with Sep 30 Close in [12000,14000], Jeisys ranks third by descending signal-day
Marcap. top_n=3 and D01 both stop at the known Oct 23 evidence gap before writing
partial reports. top_n=1 succeeds without globally excluding Jeisys. This is
actual-source rejection coverage, not a verified actual cash-payment backtest.

Next: obtain primary evidence of actual exchange payment and applicable net
amount treatment, independently reconcile actual share quantities and cash,
then replace this blocker with a reviewed executable entry and test both modes
through actual receipt. Preserve existing history and every unresolved candidate.
