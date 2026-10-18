# Multi-security execution and unresolved historical sources

The common engine, explicit event-aware pending order model, source preparation,
readiness and CURRENT reports were implemented and actually exercised. **The new
full2019–2025 and2001–2025 multi-security requests remain blocked; no complete NAV,
performance claim or investment approval is issued for them.** Component success
is not shortened-period success for those requests. DART investment PIT remains0/6.

## Available unchanged complete studies

| Strategy | Complete period | Execution contract |
|---|---|---|
| Original size10deciles |2019–2020|Original fixed next-close |
|3–1momentum top3|2020|Original fixed next-close |
|Largest-cap top1|2024|Original fixed next-close |
|Largest-cap top1|2019–2025|Previously declared fixed next-close |
|Largest-cap top1|2001–2025|Previously declared split-only all-or-none deferred |

Metrics are copied, without recalculation, from CURRENT into
`results/available_comparison_CURRENT.csv`. Costs/turnover for the complete
original multi-security run are in the adjacent CSVs. They are price/stock-right
research returns excluding cash distributions, **not total returns**. Net means
explicit trading costs, not actual dividend-related tax or a brokerage account.
The25year top1 benchmark/result must not be presented as multi-security success.

## New implementation and frozen old behavior

`defer_full_rebalance_events_v1` is separate from default rejection and the old
split-only deferred model. Freeze original signal and targets; wait the entire
order for every real old/target share leg; no partial fill, cancel/reselect,
future fill price, credit against pending sales, or borrowing against rights.
Overlapping signals/end-pending orders fail with original signal and last blocked
codes. Illiquid rights are valued in NAV but excluded from liquid target capital;
Gross and Net quantities/cash/fees remain separate. Fee applies once; issuance,
approval and virtual settlement create no second cost or duplicated gain.

The narrow simultaneous-listing demerger model retains an observed flat cum-right
basket through the documented halt, then delivers both legs once at their joint
tradable close. It does not forward-fill a child price. Missing/changed halt rows,
unknown rights, non-simultaneous listings, integer/fractional/tax accounts and bad
reference prices fail. Official price-return and economic basket checks remain
separate. General held-return tolerance remains1bp, independent ledger1e-5KRW.

Full historical cross-sections are ranked BEFORE projecting needed observations.
Original technical lookback, held names and verified successor/child observations
survive projection. No future-survivor or future-price eligibility restriction.
An actual4.44e-16 normalized-NAV projection difference was fixed by preserving
legacy source-asset summation layout with zero contributions, not by tolerances,
rebasing expected hashes or replacing financial data. Numeric CSV hashes now match.

## Actual source-backed component results

- LG003550 / LX383800: ratio.9115879 parent and.4420605 child per old parent share
  (capital ratio.0884121 times par conversion5). Official parent listing
  20210524000070, child relisting20210525000477, reference methods
  20210526000318/20210526000323 and actual KRX20210527 quotes are preserved.
  Parent reference119500 and child12650 are actual opening-auction prices;
  evaluation prices126500/25300 must NOT replace these references.
- SKT017670 / SKSquare402340: fivefold par split then.6073625/.3926375 allocation:
  final3.0368125 parent and1.9631875 child per old share. Corrected terms
  20210817001055, actual completion20211102000453, child relisting
  20211125000535, reference methods20211126000322/325, and official KRX20211129
  quotes. References53400/82000 are actual auction openings, not evaluation61900.
  The standalone parent change-listing notice remains UNVERIFIED. Completion's
  Nov29 date is PLANNED in that document; parent reference notice plus actual
  traded quote/LIST_SHRS corroborate the research virtual joint day, not actual
  account credit or a complete legal-first-listing certification.
- CT068270 and HC0919902021: proposals20211217800219/20211217900217, official
  ex-date/reference notices20211228000729/767 (212000/86800), approvals
  20220325801692/20220325901111 and actual listings20220419000072/20220419000500
  establish2% rights, record2021-12-31, ex2021-12-29, approval2022-03-25,
  virtual listing2022-04-22. Issuance date is not broker credit. Companion cash
  dividends750/260 and integer fractional cash are NOT modeled or hidden.

Each actual source location/URL/hash is in `source_review.json`, source state,
`config/research/spinoffs_v2.json` and the new six-event stock-dividend facts.
Original catalogs and original four dividend facts are preserved. Source revision
v2 changes ONLY newly evidenced event inputs/identifiers, not selection/costs/rules.

| Actual component | Sessions | Gross/Net book-days | Max currency difference |
|---|---:|---:|---:|
|actual_lg_lx|26|78|7.45058059692e-09|
|actual_skt_square|32|96|5.58793544769e-09|
|actual_2021_dividends|102|306|6.51925802231e-09|

Both public top-N and all10decile helpers use the same common demerger execution.
The two new dividend components include ex-holder entitlements, sale before
release, rebalancing, distinct Net quantities, approval, virtual settlement and
no event-day duplicate cost. Their model is continuous-share-equivalent rights
marked at contemporaneous underlying close (conditional haircut1.0), then virtual
listing-close settlement; this is an explicit research assumption, not an observed
rights quote or certainty of future approval. No DART/operating PIT gate is relaxed.

## Complete requested executions and precise first blocks

All five complete inputs were actually passed through run/check. Each expected
exit3, no accepted NAV or performance. See `results/requested_incidents.csv` and
CI full preflight artifacts for all cohorts/dates; secondary diagnostics under a
fallback schedule are explicitly diagnostic_only and NOT actual execution.

- `research_size_deciles_2019_2025_event_deferred_v1` ({'start': '2019-01-01', 'end': '2025-12-31'}): `{"kind": "held_return_reference_gap", "classification": "historical_fact", "verdict": "UNVERIFIED", "security": "068270", "date": "2021-12-29", "portfolio": "D03", "detail": "Planned holding fails unchanged1bp source/event comparison", "required": "Official ex-date/reference and action terms, or original-price correction evidence; no inferred split/return override", "occurrences": 1, "affected_through": "2021-12-29", "previous_date": "2021-12-28", "previous_close": 216000.0, "close": 201000.0, "exchange_return": -0.0519, "effective_comparison_return": -0.06944444444444442, "difference_bps": 175.44444444444417, "basis": "raw_close", "origin_signal": "2021-04-30", "incident_id": "f80d5cb951e8ab0fd3f8"}`. 18 incidents, 4 diagnostic-only.
- `research_broad_size_deciles_2001_2025_v1` ({'start': '2001-01-01', 'end': '2025-12-31'}): `{"kind": "pending_order_event_contract_gap", "classification": "execution_constraint", "verdict": "UNVERIFIED", "security": null, "date": "2002-05-02", "portfolio": "D01", "detail": "pending_order_conflict: original signal 2001-04-30 remains unfilled at new execution 2002-05-02", "required": "Exact verified share/rights lineage and executable lifecycle; no guessed event. Other source diagnostics below use original earliest schedule, not certified actual fills.", "occurrences": 1, "affected_through": "2002-05-02", "origin_signal": "2001-04-30 00:00:00", "planned_date": "2001-05-02 00:00:00", "last_blocked": {"date": "2002-04-30", "securities": ["000300", "000315", "000317", "000475", "001110", "001697", "001785", "001787", "001797", "002105", "002180", "002470", "002580", "002585", "003260", "003660", "004465", "007595", "008985", "012265", "012670", "013005", "013095", "013097", "016555", "017090", "017120", "033300", "042675", "047890", "052530"]}, "incident_id": "084204e968f40c53bcd1"}`. 9970 incidents, 9960 diagnostic-only.
- `research_broad_size_top10_2001_2025_v1` ({'start': '2001-01-01', 'end': '2025-12-31'}): `{"kind": "pending_order_event_contract_gap", "classification": "execution_constraint", "verdict": "UNVERIFIED", "security": null, "date": "2003-05-02", "portfolio": "top_n", "detail": "pending_order_conflict: original signal 2002-04-30 remains unfilled at new execution 2003-05-02", "required": "Exact verified share/rights lineage and executable lifecycle; no guessed event. Other source diagnostics below use original earliest schedule, not certified actual fills.", "occurrences": 1, "affected_through": "2003-05-02", "origin_signal": "2002-04-30 00:00:00", "planned_date": "2002-05-02 00:00:00", "last_blocked": {"date": "2003-04-30", "securities": ["015580", "023130"]}, "incident_id": "eb1d56120b2aa988ad71"}`. 19 incidents, 18 diagnostic-only.
- `research_broad_momentum_top10_2001_2025_v1` ({'start': '2001-01-01', 'end': '2025-12-31'}): `{"kind": "pending_order_event_contract_gap", "classification": "execution_constraint", "verdict": "UNVERIFIED", "security": null, "date": "2003-05-02", "portfolio": "top_n", "detail": "pending_order_conflict: original signal 2002-04-30 remains unfilled at new execution 2003-05-02", "required": "Exact verified share/rights lineage and executable lifecycle; no guessed event. Other source diagnostics below use original earliest schedule, not certified actual fills.", "occurrences": 1, "affected_through": "2003-05-02", "origin_signal": "2002-04-30 00:00:00", "planned_date": "2002-05-02 00:00:00", "last_blocked": {"date": "2003-04-30", "securities": ["002580", "018415"]}, "incident_id": "eb1d56120b2aa988ad71"}`. 100 incidents, 99 diagnostic-only.
- `research_size_deciles_2019_2025_event_deferred_v2` ({'start': '2019-01-01', 'end': '2025-12-31'}): `{"kind": "held_return_reference_gap", "classification": "historical_fact", "verdict": "UNVERIFIED", "security": "207940", "date": "2022-02-28", "portfolio": "D02", "detail": "Planned holding fails unchanged1bp source/event comparison", "required": "Official ex-date/reference and action terms, or original-price correction evidence; no inferred split/return override", "occurrences": 1, "affected_through": "2022-02-28", "previous_date": "2022-02-25", "previous_close": 769000.0, "close": 779000.0, "exchange_return": 0.025, "effective_comparison_return": 0.013003901170351106, "difference_bps": 119.96098829648895, "basis": "raw_close", "origin_signal": "2021-04-30", "incident_id": "ebaafd770239b4a4361d"}`. 16 incidents, 4 diagnostic-only.

The separate original10T-filter2001 strategy still yields only4 eligible names
at its first signal, not a data gap. The original strict2019–2025 still rejects
LG2021-05-03; no rewriting of fixed-lag execution. Broad2001–2025 inputs remove
that filter explicitly in separate predeclared DSLs, keeping top10/all10buckets,
whole25years, exact original factor/cost/observations. A whole-order basket of
hundreds of illiquid names may be intrinsically unfillable; changing to partial
fills would require a NEW predeclared allocation/cash/priority contract, not a
silent success fix or exclusion of those names.

Historical source needs include015580신한은행 (last observed2001-09-07),
023130국민은행 (2001-11-08),002580삼미 (2002-04-19),018415현대금속1우
(pending2002), and012170의성실업 price/reference discontinuity2001-06-21.
Their corporate transfer/merger/capital-reduction/retirement terms and dates
cannot be inferred from missing quotes, present-day identity or price ratios.
The limited official KIND2001 searches returned HTTP200 with no candidates,
not proof of absence. Needed next inputs: official archival document identifiers
or original exchange change-listing/transfer notices with predecessor/successor,
share/cash ratio, entitlement and first tradable dates; archival access/licensed
historical corporate-action feed may be needed. No unsupported ratio is invented.
Later incidents (including HC2023 retirement and other rights/distributions)
remain individually listed, not certified as complete history.

## Regressions, source acquisition and verification scope

Frozen211 old evidence/result files stayed exact. Original2019–2020 selections,
weights, NAV, CURRENT metrics/canonical CSV match old hashes; JSON/Korean values
match. Independent original10-bucket ledger has14820book-days with max error
8.568167686462402e-8KRW (limit1e-5). Full2020momentum projected observations also
match old numeric CSV hashes exactly. No expected baseline was regenerated.
The final CI separately re-executes old2024,2019–2025 and25year top1 studies,
original financial518/core64/original60 preservation and original DART E2E.
Local browser launch exited1/SIGTRAP: sandbox denied Linux setsockopt; local
presentation is UNVERIFIED. Final actual CI browser steps must be read separately.

Bounded acquisition runs (zero retries):39098192578,39098397785,39098617733,
39099447457,39099597651,39099791139,39100135180. The2001 archive run39099447457
failed with NO_RETURNED_CANDIDATES; all other source runs succeeded. Final validation
makes zero source requests. Source jobs are pinned/retired, no repeated download.

The2026 KOSPI and KOSDAQ cash-equity closure notices20260520000117/121 establish
June3 and July17 closures; pinned XKRX4.13.2 differs. Authenticated KOSPI endpoint
returned a valid2026-09-18 response, so missing benchmark is NOT proven inaccessible.
A bounded provenance-preserving calendar overlay and benchmark extension are still
UNAPPLIED; original files remain exact. These gaps do not block2001–2025 research.

## Publication and continuation

Relevant implementation: execution_scheduling.py, execution_contract.py,
research_spinoff.py, annual_selected_preparation.py, research_planned_readiness.py,
PROJECT common target engine, both public DSL modes, DSL/exported contracts,
CURRENT postprocess disclosure, event/spinoff unit tests, source catalogs,
predeclared DSLs, examples and this folder. Reproduction commands and runtime
are in reproduction.md. `result_manifest.json` pins local results. Full raw
preflights, accepted original-run reports and browser proof live in CI artifacts.

Final workflow is split into4 real verification jobs, preserving all original
assertions and20minute limits. A successful software/regression CI is NOT a
successful blocked backtest or PIT certificate. Read the exact final remote SHA,
run/jobs/logs/artifacts linked in the final handoff; this report cannot attest
its own future CI state. Source gaps remain UNVERIFIED. No main merge, raw-data
mutation, bulk backfill, internet pip, new financial processing or operating-gate
relaxation was performed. Existing518/core64/original60 controls are retained.
