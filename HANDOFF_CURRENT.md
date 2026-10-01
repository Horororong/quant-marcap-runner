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
  execution engine `v2-16-exec-1`.
- Canonical metrics/charts: `scripts/quant_backtest_template_CURRENT.py`
  (currently `v2-15`) and `scripts/quant_backtest_postprocess.py`.
  The execution and performance template versions are distinct; do not rename
  one to pretend it has the other's implementation.
- Strategy schema: `1.0`; machine contract `8`; factor registry `6`;
  preflight contract `1`; corporate-action registry `1`.
- Generated contracts: `config/strategy_dsl_schema_v1.json` and
  `config/strategy_dsl_capabilities_v1.json`. Regenerate with
  `python scripts/export_strategy_dsl_contract.py --write`; CI uses `--check`.

## Review units and resumption

- PRs #7-#10 were merged before this Work continuation: aliases, preflight,
  external universe filters and fixed-window KRX momentum.
- PR #11 (quarterly profitability) was checked against its successful full CI
  and merged in this continuation.
- PR #12 (realized volatility) integrates #11, resolves shared alias/contract
  conflicts, and uses registry 6 / machine contract 7. The local full suite passed.
- PR #13 introduces optional price-index benchmarks, integrates #12, and advances
  the machine contract to 8. This handoff ships in that review unit.
- The prior benchmark branch failed because generated contracts were stale.
  They have now been regenerated; strict benchmark and preflight regression
  coverage was added.

If reading from `main`, verify #12/#13 merge status and their full CI at GitHub
before deciding that any work is outstanding. If reading from the PR branch,
merge #12 only after its current head full E2E succeeds, then merge #13 only
when its current head full E2E succeeds and it is mergeable. Never force-push main.

Repository: https://github.com/Horororong/quant-marcap-runner
PRs: https://github.com/Horororong/quant-marcap-runner/pull/11,
https://github.com/Horororong/quant-marcap-runner/pull/12,
https://github.com/Horororong/quant-marcap-runner/pull/13

## Supported contracts

- PIT KOSPI/KOSDAQ equity universe; selected-month, last-session rebalance;
  equal-weight cross-sectional percentile ranking; explicit fixed-bps costs.
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
  This is not a complete historical corporate-action registry.

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
real DART PIT selection/formulas and real-data execution E2E.

Real DART/execution regression uses 2020-04-01 through 2020-11-30. This verifies
that path, not a full 2001-present performance report. Technical provider tests
use deliberately synthetic panels for independent formulas and no-lookahead;
never present their NAV as an investment backtest.

Runnable benchmark example: `config/strategies/super_value_dart_benchmark_dsl.json`.
Validate, preflight, then run with `--execution-only` for its explicitly short
research window. Request canonical performance only with actual source history
sufficient for the required standard periods.

## Next development sequence

1. Confirm #11-#13 acceptance and current main CI before further work.
2. Add reusable factor-decile research: deterministic ten-bucket partition,
   explicit tie/small-universe rules, identical PIT providers and execution
   contract, per-bucket weights/daily NAV, CURRENT-only metrics. Test future
   mutations, missing data, partition disjointness, t+1 execution and costs;
   document whether portfolios are independently investable and their scope.
3. Expand verified corporate actions and history coverage before claiming
   production-grade full-history results. Keep capability/data gaps distinct.
4. Expand factors with explicit accounting-period definitions (annual/TTM,
   quality/growth) and then supported assets/portfolio rules, through registries.
5. Add a tested Korean request compilation interface using the generated schema,
   preserving ambiguity/gap behavior. Benchmark total-return support requires
   a separate verified data source and explicit return-basis contract.

No decile implementation or broad arbitrary-language compiler is claimed here.
