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
- Strategy schema: `1.0`; machine contract `9`; factor registry `6`;
  preflight contract `1`; corporate-action registry `1`.
- Generated contracts: `config/strategy_dsl_schema_v1.json` and
  `config/strategy_dsl_capabilities_v1.json`. Regenerate with
  `python scripts/export_strategy_dsl_contract.py --write`; CI uses `--check`.

## Review units and resumption

PRs #7-#13 are merged. The pre-decile main commit
`7bb91b856e845b145d6668518302cec5739e3907` also passed its own full main CI:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36807015029

The current Work milestone adds reusable factor-decile research through
`portfolio.selection="deciles"`, sharing the top-N PIT/scoring and PROJECT
execution paths. Its branch must pass the full Strategy DSL CI (including both
real-data E2Es) before merging. Check GitHub's live refs, PRs and current-head
checks; do not infer outstanding work from an old chat or branch snapshot.
If reading this document on main, the milestone is already part of main.
Never force-push main.

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

## Next development sequence

1. Confirm the decile milestone acceptance and current main CI.
2. Expand verified corporate actions and history coverage before claiming
   production-grade full-history top-N or broad-universe decile results.
   Keep capability/data gaps distinct; do not screen by future survival.
3. Expand factors with explicit accounting-period definitions (annual/TTM,
   quality/growth) and supported portfolio/asset contracts through registries.
4. Add a tested Korean request compilation interface using generated schema,
   preserving ambiguity/gap behavior. Benchmark total-return support requires
   a separate verified source and explicit return-basis contract.

Decile implementation is present; an arbitrary-language compiler/service and
complete historical corporate-action coverage are still outstanding.
