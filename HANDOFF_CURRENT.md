# Current Strategy DSL handoff

This handoff accompanies the Work continuation on 2026-10-01 (Asia/Seoul).
Read `AGENTS.md` and `BACKTEST_START_HERE.md` before changing or running a backtest.
GitHub refs, PR metadata and checks are authoritative for merge/CI status; this
file is an architectural checkpoint, not a substitute for checking live status.

## Git growth review

The recent-storage fix is ported independently from tested commit
`155d08a3f4c6233168105a7baee05721050a40d4` onto main checkpoint
`b763c5ca903d652a815bbdbff6df978843a45c86`. It fixes rotation filename drift,
deterministic CSV/gzip output and timestamp-only churn while preserving real
rotation state, correction updates and existing files/history. This port does
not activate the separate strict-input, execution-orchestration or broad-source
archive feature branches. Read `docs/GIT_STORAGE_AUDIT_20261001.md` for the audit.
The generated DSL/runtime contracts stay at main's versions below. Require the
complete final-head Strategy DSL CI before integration.

Four-week read-only growth observation uses
`config/git_storage_baseline_20261001.json` and
`.github/workflows/observe-git-storage.yml`. Reports go to 90-day Actions
artifacts, never recurring Git commits; weekly full-history downloads stop
after October 29. See `docs/GIT_STORAGE_OBSERVATION.md` for metric limitations
and `docs/GPT_SANDBOX_ROADMAP.md` for the user's Codex-development/GPT-sandbox
execution goal, missing deployment units and the proposed offline-kit milestone.

The integration also preserves automatic backfill checkpoint
`8784c9aaab277a82c1b74ffda0bd3163c8892c79` (October 1 21:16 UTC): five new
2024 financial shards, historical mapping and collection state updates. The
storage changes do not revise those observations. Validate the final combined
commit against this current dataset, not only the earlier b763c5c snapshot.

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

The next review unit adds known-event planned-exposure preflight, machine
contract 17 / preflight 3, with no NAV/metric change. Relevant known gaps invoke
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
