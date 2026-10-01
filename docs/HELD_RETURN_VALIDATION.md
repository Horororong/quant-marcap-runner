# Held-return validation and verified splits

Both public Strategy DSL runners require exchange `ChangesRatio` and validate
each already-held asset before its return enters NAV. The signal/date/eligibility
rules and CURRENT performance calculator are preserved.

## Return contract

Compare the effective executed return with `ChangesRatio / 100` in decimal units.
The absolute difference must be at most **1 basis point (0.0001)**. This permits
ordinary exchange percentage rounding (about half a basis point), not inference
of missing prices or corporate actions. Missing/non-finite reference returns or
unresolved discrepancies stop execution before outputs are created. Source
`ChangesRatio` is never substituted into NAV: prices and verified event values
remain the execution source.

Timing uses the positions **before** the day's rebalance. A first buy has no prior
stock holding; its execution-day price movement belongs to cash. A sale at the
close cannot hide a return earned by the old holding. Unheld anomalies do not
remove stocks or rewrite historical eligibility. Missing references in an
explicitly registered suspension and merger disposal/exchange values are audited
overrides. The new successor's ordinary held returns still require validation.

The source review-candidate threshold (25bp) is distinct from this 1bp execution
guard. Neither establishes complete corporate-action history or total returns.
Direct low-level engine calls keep an optional `reference_returns` DataFrame for
compatibility. They report `enabled=false` when absent; public DSL execution
always supplies the matrix.

## Stock-split contract

`stock_split` uses the same predecessor/successor code, a finite positive ratio
of new shares to old shares, and zero cash. `event_date` is trading resumption.
The effective event return is `share_ratio * event_close / last_trade_close - 1`.
When tradability is supplied, the prior price comes from the last tradable
observation. No trade, turnover or trading cost is manufactured for the split;
weights stay on the same security. The effective split return is still checked
against the exchange reference, so a wrong registry ratio fails.

Events without a possible prior holding are skipped rather than requiring
pre-window prices for an account that started in cash. Possible holdings include
earlier targets and registered successor transfers. This check does not change
target selection. The registry requires finite ratios/cash values, non-empty
source evidence, same-code zero-cash splits and different-code mergers.

## Verified EcoPro event and real source test

EcoPro's [2024-03-29 company announcement](https://www.ecopro.co.kr/sub0401/view/id/1492)
confirms a five-for-one split, suspension from April 9 through April 24 and
resumption on April 25. A [KRX KIND ETF notice](https://kind.krx.co.kr/external/2024/04/19/000218/20240419000600/68629.htm)
independently identifies security 086520 and the suspension interval.

The repository's actual 2024 KRX parquet has last traded close KRW 517,000 on
April 8, zero-volume unchanged observations through April 24, and close KRW
108,100 on April 25. Raw close division gives about -79.09%; five shares valued
at KRW 108,100 give `5 * 108100 / 517000 - 1 = 4.5454545%`, consistent with the
exchange's rounded `ChangesRatio = 4.55%`. This is an event-day validation,
not a full-period or total-return investment result.

`config/strategies/kr_equity_split_research.json` uses the actual March 29
KOSDAQ cross-section and highest nominal price to select EcoPro, buys at the
April 1 close, and stops the research interval on April 26. Independent tests
value the original shares before the event and five times the shares afterward,
check the original buy cost, zero split turnover, exact daily gross/net NAV,
and failure when the registry event is removed. No retrospective survival or
event-based eligibility filter is used.

## Audit outputs and remaining coverage

`return_reference_audit.json` records whether checking is enabled, the threshold,
checked held observations and explicit override counts by cost scenario.
`held_return_checks.csv` records those counts and the maximum validated difference
for each day. Deciles add a group label at the root and retain per-bucket audits.

Registry version 3 includes the existing Korean Paper merger, this EcoPro
split and BYC common/preferred splits. The BYC tests preserve negative actual
price returns, independently value every holding in both public modes, and fail
if the preferred event is missing. See [CORPORATE_ACTION_RECONCILIATION.md](CORPORATE_ACTION_RECONCILIATION.md). Other split/rights/spin-off/delisting events and dividend/total-return
sources remain incomplete. Expand verified records and explicit event types;
never bypass the guard, fill prices, infer cash flows, or screen out future failures.
