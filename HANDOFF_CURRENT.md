# Current Strategy DSL handoff

This handoff accompanies the Work continuation on 2026-10-01 (Asia/Seoul).
Read `AGENTS.md` and `BACKTEST_START_HERE.md` before changing or running a backtest.
GitHub refs, PR metadata and checks are authoritative for merge/CI status; this
file is an architectural checkpoint, not a substitute for checking live status.

## Goal and architecture

User goal: a Korean strategy request produces a Strategy DSL JSON and runs on
one generic engine, without creating strategy-specific Python for each request.

Korean request -> generated capabilities and JSON Schema -> deterministic aliases
-> Strategy DSL -> compiler/preflight -> registry providers -> target weights
-> PROJECT v2-16 execution -> daily NAV -> CURRENT postprocess.

The AI translation layer must inspect capabilities first. A complete arbitrary
Korean-language compiler/service is not implemented yet. Unsupported requests
must identify the missing capability instead of mapping to a similar strategy.

- Execution: `scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py`,
  execution engine `v2-16-exec-3`.
- Canonical metrics/charts: `scripts/quant_backtest_template_CURRENT.py`
  (currently `v2-17`) and `scripts/quant_backtest_postprocess.py`.
  The execution and performance template versions are distinct; do not rename
  one to pretend it has the other's implementation.
- Strategy schema: `1.0`; machine contract `20`; input-validation contract `1`; run orchestration `1`; factor registry `6`;
  preflight contract `3`; history-audit contract `1`; market-normalization contract `1`; corporate-action registry `5`.
- Generated contracts: `config/strategy_dsl_schema_v1.json` and
  `config/strategy_dsl_capabilities_v1.json`. Regenerate with
  `python scripts/export_strategy_dsl_contract.py --write`; CI uses `--check`.

## Review units and resumption

Checked execution is developed on a feature branch that combines strict input
validation `88553d8e1994ba15a32d4adc3e6e6b7815418d88` and PR #23
`6bbfe22d8fa92383ae57e3d810d9bcd2e9af95cf`. The prerequisite integration commit
is `51f245cf4636190c2feb6357fe923d6019a37cdd` (machine contract 19 / preflight 3).
Remote main was `b763c5ca903d652a815bbdbff6df978843a45c86` at implementation
start; PR #23 was open. This is feature-branch integration, not a main merge.
Prior exact-head CI passed for strict validation and PR #23 respectively:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36866455753
https://github.com/Horororong/quant-marcap-runner/actions/runs/36858609030
These runs are not evidence for the new final-head workflow; check live refs/CI.

Machine contract 20 / run orchestration 1 routes the public runner CLI through
`run_checked_strategy()`: frozen input, automatic shared preflight, CURRENT
formal-date readiness, existing top_n/decile execution and canonical reporting.
Run status separates validated NAV and completed formal report, publishes
checked stage directories and rejects output reuse. See
`docs/STRATEGY_DSL_RUN.md`. Source hashes/package/code manifest and a Korean
compiler remain later milestones. Component engine/provider/math is preserved.
The full Strategy DSL workflow includes lifecycle failure/actual CURRENT tests
and real CLI/KRX/DART/known-event E2E, as well as all prior regression contracts.
Strict input tests still cover 271 invalid file cases and eight base fingerprints;
failed execution attempts now persist diagnostics without publishing NAV.

PRs #7-#19 are merged. The canonical-performance main commit is
`ba6c3772a57de3276f31f23247395d1877b13b73`. PR #18 full CI passed:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36824544209
Its own main workflow also passed:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36825497414
Check live refs/checks again before merging further work.

Canonical performance v2-17 is merged: PROJECT delegates metrics to CURRENT;
exact daily calendar checks, Sortino, Calmar, complete-month win rate and explicit
benchmark statistics retain the four periods and nine charts. See
`docs/CANONICAL_PERFORMANCE.md` for compatibility and verification scope.

PR #19's tested head is `2585d24a26a88c9d4707e1beb79ec2a228cafb7c`; full CI
passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36831237355
It is merged on main at `b39d06ced5c85b17deb10747811d91f8a9364af3`.
PR #21 is merged at `aae1bdde220aac2d519fcf845e544bb1f9fecebc`. Its full tested-head
CI passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36837202267
and main CI passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36839116922.
That milestone fixes KOSDAQ GLOBAL classification and restores 46,753
pinned original observations across 2022–2026, without revising existing values
or extending stored windows. SourceMarket preserves then-observed membership.
Machine contract 15 and market-normalization version 1 expose this boundary.
See `docs/KRX_MARKET_NORMALIZATION.md` and its complete repair evidence. Require
full current-head CI, including both real public modes and existing DART/KRX
E2Es, before merge. Check live refs; never force-push main.

PR #22 is merged at `b4c2b4ab7a6fec794766b447dc9470372dcab539`.
Its tested head `587733f7c3e1c5497d36cbb74b8bcb78b4a5bbca` passed all 30
workflow lifecycle steps at:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36847851288
Its own main CI and subsequent data-update workflow passed at:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36849922237
https://github.com/Horororong/quant-marcap-runner/actions/runs/36849922248
The continuation base is `f77a4543d6e58e01c78bf234cc9347784b7b0e73`.

PR #23 introduced known-event planned-exposure preflight with machine
contract 17 / preflight 3, with no NAV/metric change. Its implementation is
included in the feature integration described above. Relevant known gaps invoke
shared PIT selection and exact lag, including all ten deciles; unaffected
strategies retain their historical universe. Timing/lineage and real KRX
positive/negative tests are in `scripts/test_corporate_action_preflight.py`.
Require full current-head CI including that new step and existing DART/KRX
E2Es before merge. Read live PR/checks for its eventual merge status.
See `docs/CORPORATE_ACTION_PREFLIGHT.md` for scope.

Repository: https://github.com/Horororong/quant-marcap-runner

## Supported contracts

- PIT KOSPI/KOSDAQ equity universe; selected-month, last-session rebalance;
  equal-weight cross-sectional percentile ranking; explicit fixed-bps costs.
- Portfolio selection defaults to `top_n` with a positive integer position
  count. `deciles` partitions the full post-filter finite-factor universe into
  ten balanced contiguous groups; position count is omitted/null. D01 is best,
  D10 worst; tied scores are split explicitly by zero-padded Code order. Fewer
  than ten eligible codes fails at execution. Every bucket is a separate
  long-only portfolio with independent initial capital, same PROJECT execution
  and costs. CURRENT remains the sole metrics/chart path. Full policy and
  output schemas are in `docs/STRATEGY_DSL.md` and generated capabilities.
- KRX panel factors: market cap, amount, volume, close, shares as registered.
- DART value factors: standalone-quarter earnings/cashflow/sales yields,
  book-to-price. Profitability: `quarterly_roe`, `quarterly_net_margin`,
  `quarterly_ocf_margin`. Positive denominators only. April/October signals
  only; actual filing-date PIT; CFS first, OFS fallback; completeness gate.
- Momentum uses decimal exchange `ChangesRatio` compounded over fixed windows:
  3-1 = 63 lookback minus latest 21; 6-1 = 126 minus 21;
  12-1 = 252 minus 21; 12-0 = 252 with no skip.
- Volatility: sample standard deviation of the latest 63/126/252 decimal daily
  `ChangesRatio` observations multiplied by sqrt(252), including signal day.
  Missing per-code observations produce NaN, never fabricated zero returns.
- Optional benchmark: explicit source `index` plus symbol KOSPI, KOSDAQ,
  KOSPI200 or KOSDAQ150. Uses `data/indices/{symbol}.csv` Close on exact strategy
  dates; first date normalized to 1.0. This is a price index without dividends,
  not a total-return index. Preflight checks raw source prices without NAV.
- Verified merger continuity currently includes Korean Paper 002300 ->
  Haesung Industrial 034810, ratio 1.6661460, successor listing 2020-07-13.
  Verified split: EcoPro 086520, five shares per old share, trading resumes
  2024-04-25 after suspension 2024-04-09..24. Evidence and independent test
  are in `docs/HELD_RETURN_VALIDATION.md`. Registry version 4 also includes BYC
  001460 and BYC preferred 001465, each ten shares per old share, resuming
  2024-04-17; Namyang common 003920/preferred 003925 ten-for-one on 2024-11-20;
  APR 278470 five-for-one on 2024-10-31. See
  `docs/CORPORATE_ACTION_RECONCILIATION.md`. The registry is incomplete.

## Non-negotiable correctness rules

1. No fabricated missing history, future observations, current-universe
   reconstruction of historical membership, or silently shortened periods.
2. No filing data before its actual availability date; no post-signal values
   in factors. A close-t signal executes no earlier than a later session close.
   Existing positions/cash earn their returns through the execution date.
3. No generic PER/PCR/PSR/ROE substitution with standalone-quarter definitions;
   no ambiguous momentum skip convention chosen silently.
4. No generic held-stock NaNs replaced with zero. Suspension/merger continuity
   is allowed only for explicitly verified events and recorded in audit output.
5. No benchmark filling/interpolation. Unsupported definitions are capability
   gaps; missing or malformed source data are data gaps.
6. Strategy/provider code produces weights and daily NAV. Metrics and chat
   charts come only from CURRENT postprocess. Preserve the four standard
   analysis periods; a short execution E2E is not full-history validation.
7. Preserve working main, use a PR for each feature, require the complete CI
   including real-data execution E2E before merging a code feature.

## Verification and practical scope

Workflow: `.github/workflows/test-strategy-dsl.yml`. It includes syntax,
contract sync, aliases, preflight, benchmark cases, momentum, volatility,
provider extension, corporate-action continuity, synthetic PROJECT execution,
real DART PIT selection/formulas and real-data execution E2E. The decile tests
add independent partition/balance/disjointness, JSON Schema/runtime agreement,
provider-backed filter/rank sharing, no-lookahead, missing-factor intersection,
small-universe failure, t+1/cash timing, exact costs, blocked/missing prices,
verified successor continuity and no new partial outputs on execution failure.

Real DART/execution regression uses 2020-04-01 through 2020-11-30. This verifies
that path, not a full 2001-present performance report. Technical provider tests
use deliberately synthetic panels for independent formulas and no-lookahead;
never present their NAV as an investment backtest.

Runnable benchmark example: `config/strategies/super_value_dart_benchmark_dsl.json`.
Validate, preflight, then run with `--execution-only` for its explicitly short
research window. Request canonical performance only with actual source history
sufficient for the required standard periods.

Real KRX decile regression/example:
`config/strategies/kr_equity_size_deciles_research.json`, 2020-04-01 through
2020-05-08, explicitly signal-date Marcap >= KRW 10 trillion. It validates
narrow-window selection, t+1, equal initial holdings, exact cost deductions,
benchmark dates and artifacts against an independent raw-price oracle.
It does not claim broad-universe/full-history investment performance.

## History-audit checkpoint

Source diagnostics and reproducible commands are in `docs/KRX_HISTORY_AUDIT.md`.
The original 2020/2024 snapshots and pre-repair reconciliation remain archived.
The new snapshots in `docs/audits/krx-history-2024-repaired` and
`docs/audits/corporate-actions-2024-repaired` record the repaired 2024 source
hash, 657,429 observations and 2,797 codes. Both markets have all 244 sessions.
There are 257 >25bp price/reference candidates: six match consistent registered
splits and 251 remain unmatched. There are zero internal observation gaps and
140/52 censored starts/ends. These are source observations, not proven losses,
corporate-action counts or a completeness certificate.

Code 287410's former 89-session gap was a KOSDAQ GLOBAL ingestion omission.
The repair restores those actual rows and its 207 observations. Its later cash
exchange has verified legal completion and delisting, but actual payment and
applicable net proceeds remain unverified. The new generic cash-only contract is tested with synthetic payment
evidence; no production cash registry entry exists. The known gap blocks affected
holdings from 2024-10-23 instead of inferring receipt or excluding the stock.
See `docs/CASH_SHARE_EXCHANGE.md` and primary evidence there. The Aug 19 tax
disclosure is historical guidance, not proof of actual deduction or universal
net receipt. No production event or automatic tax model is added.

Public DSL runners now require ChangesRatio source data and validate each
pre-rebalance held asset's effective return against ChangesRatio/100 within
1bp before NAV/cost calculation. Missing/non-finite references or unresolved
differences fail; no automatic substitution by exchange returns. First buys
are cash beforehand; sells still require the prior holding's return to pass.
Verified merger disposal values have explicit override audits. Split event
returns are still reference-checked; wrong ratios do not bypass the gate.
Per-scenario/decile audits record checks and explicit override counts.
Low-level direct engine calls retain an optional reference matrix for backwards
compatibility and explicitly report enabled=false when it is absent.

The 25bp source-diagnostic threshold is distinct from the 1bp execution guard.
Neither certifies whole-market events, dividends or total returns. Rights,
spin-offs, unsupported events, missing sources and remaining history still need
verified handling. Do not silently exclude stocks that would fail the guard.

## Next development sequence

1. Verify live main and full current-head CI for the known-event preflight milestone.
2. Continue exact primary-source investigation of the 251 unmatched 2024 price
   candidates and remaining years. For 287410, verify actual cash-exchange
   actual payment and applicable net-proceeds evidence. The distinct cash
   receivable/payment contract now exists; replace the blocker with a reviewed
   executable entry only after evidence and actual proceeds/timing tests in both
   public modes. Do not reuse a stock split or merger approximation. Preserve
   all audit candidates and never use future survival as a strategy filter.
   The event registry, dividends and full historical coverage remain incomplete.
3. Expand factors with explicit accounting-period definitions (annual/TTM,
   quality/growth) and supported portfolio/asset contracts through registries.
4. Add a tested Korean request compilation interface using generated schema,
   preserving ambiguity/gap behavior. Benchmark total-return support requires
   a separate verified source and explicit return-basis contract.

Deciles, market-session validation and held-return checks are present. An arbitrary-language
compiler/service and complete historical corporate-action coverage are still
outstanding.

Annual/rolling performance and evaluated OOS reports remain follow-up work;
this milestone does not claim full-history corporate-action correctness.

## DART collection continuation

Collection storage/status contract 1 is developed from checked-run commit
b2d3631 on a feature branch. Engine/registry/machine/performance versions are
unchanged. Read docs/DART_COLLECTION.md before collection changes. The actual
scheduled updater is backfill-super-value-fast.yml: September 30 run 36770908185
succeeded, beyond the earlier three manual-workflow diagnosis. New code preserves
whole responses/ZIPs, changed amounts, checkpoint/resume and current-plan counts;
fast scheduling explicitly requests all_filings/both. Signal acceleration no
longer discards non-super-value source accounts. Full 2015 quarterly tasks remain
excluded. Local state snapshots are not live-process or PIT certificates.
Deploy verified code to the collection owner before claiming the fixes are live;
this checkout lacks DART_API_KEY and cannot launch an authenticated collector.
