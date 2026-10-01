# Strategy DSL v1

## Goal

Natural language is translated by an AI layer into a deterministic JSON strategy specification. The backtest engine never executes free-form model reasoning. The same JSON + same data + same engine version must produce the same target weights and NAV.

Flow:

`natural language -> Strategy DSL JSON -> validator/compiler -> target weights -> PROJECT v2-16 execution engine -> daily NAV -> CURRENT postprocess`

## v1 runtime scope

- Asset class: `kr_equity`
- Historical universe: KOSPI/KOSDAQ PIT panel from `data/krx_equities/yearly/`
- Factor sources are resolved through `scripts/factor_registry.py`; KRX panel fields and standardized DART PIT value factors are the first registered providers
- Composite ranking: weighted percentile ranks, best score = lowest composite score
- Portfolio weighting: equal weight
- Rebalance: selected months, last KRX trading day
- Execution: signal close -> at least next-session close (`lag_sessions >= 1`)
- Costs: explicit named fixed-bps scenarios
- Metrics/charts: canonical CURRENT postprocessor only

## Factor-decile research

Set `"portfolio": {"selection": "deciles", "weighting": "equal"}` in the same
Strategy DSL JSON and use the same validator, preflight and runner commands.
Omit `number_of_positions` or set it to null: deciles partitions the **full**
eligible universe, rather than the top N. The existing omitted-selection
default remains `top_n`, which still requires a positive integer position count.

After identical PIT providers, tradability/universe filters and the all-factor
finite-value intersection, composite ranks are computed once. Sort by composite
score ascending (best first), then zero-padded Code ascending. Divide this order
into ten contiguous buckets `D01` (best) through `D10` (worst), whose sizes differ
by at most one; remainder rows go to earlier buckets. Score ties may split at
boundaries, explicitly by Code, and the split count is audited. Fewer than ten
eligible codes is a hard execution error. Preflight normally checks sources only.
Relevant known corporate-action gaps additionally trigger the shared selection
builder, including the eligible-population check, before planned exposure is traced.

Each bucket is an independent long-only, equal-weight portfolio. Each receives
the full `initial_capital` independently; the ten outputs do not describe one
account with the same total capital. They share PROJECT v2-16 t+1-or-later close
execution, cash/holdings returns through the execution date, drift, cost
scenarios and verified corporate actions. Successors are retained even when
not selected by a bucket. An unregistered held-price gap or execution-day
tradability failure aborts the research run before any new result is written.

Outputs:

- root `daily_nav.csv`: `NAV_D01_Gross`, `NAV_D01_Net_<scenario>`, ..., plus
  optional `NAV_Benchmark`, on a common exact daily index.
- `decile_membership.csv`: signal-date membership, factor ranks, composite
  scores, bucket sizes and equal target weights.
- root `target_weights.csv`: long format `signal_date,decile,Code,target_weight`;
  each `D01`...`D10` directory also has wide target weights and its daily NAV.
- `decile_partition_audit.csv`, `decile_contract.json`, `execution_schedule.csv`,
  and `execution_trades.csv`: partition and execution evidence.
- standard execution plan/fingerprint and applicable provider, benchmark and
  corporate-action audit files.

CAGR, MDD, Sharpe and charts are still delegated once to CURRENT postprocess
over the combined daily NAV. No invented long-short spread NAV or alternate
performance formulas are provided. For short research windows, use
`--execution-only`; do not claim full standard-period performance coverage.

Runnable example: `config/strategies/kr_equity_size_deciles_research.json`.
Its KRX PIT universe is explicitly signal-date market cap >= KRW 10 trillion,
April 2020 rebalance, 2020-04-01 through 2020-05-08. It is a narrow real-data
execution regression, not validation of a complete small-cap/whole-market
history or an investment performance result.

## Optional index benchmark

Add `"benchmark": {"source": "index", "symbol": "KOSPI"}` to the same strategy JSON.
Supported symbols are `KOSPI`, `KOSDAQ`, `KOSPI200`, and `KOSDAQ150`; the source is
`data/indices/{symbol}.csv`. Both source and symbol must be explicit. Omitting
the benchmark leaves the existing strategy outputs unchanged.

These are **price-index close** benchmarks, without dividends. They are not
total-return indexes. The runner adds `NAV_Benchmark = Close / first Close` on
the exact strategy daily dates and passes that series to CURRENT postprocess.
It does not implement additional performance formulas.

Preflight checks source prices without calculating benchmark NAV. Missing files,
missing strategy dates, duplicate/invalid dates, or invalid prices produce a
`data_gap`; unsupported benchmark definitions produce a `capability_gap`.
No filling, interpolation, or shortening of the requested period is allowed.
The execution plan records the benchmark definition; `benchmark_coverage.json`
records coverage metadata, the source path, and the return basis.

## Machine-readable contract for AI strategy generation

AI clients should not infer Strategy DSL support from Python source. Read these generated files first:

- `config/strategy_dsl_capabilities_v1.json` — supported markets, factors, filters, portfolio/execution rules, corporate-action policy, and explicit unsupported features.
- `config/strategy_dsl_schema_v1.json` — JSON Schema for the Strategy DSL document itself.

Both files are generated by `scripts/export_strategy_dsl_contract.py`. CI runs `--check`, so changing the factor registry, execution contract, or DSL without regenerating the machine contract fails the build.

Recommended AI flow:

`natural-language request -> capabilities check -> JSON Schema-constrained Strategy DSL -> --validate-only -> checked runner (automatic preflight/readiness/execution/CURRENT) -> run_status.json`

If the requested strategy uses an unsupported factor or execution rule, the compiler should return an explicit capability gap instead of silently substituting a different strategy.

## Strict execution input contract

Machine contract `18` adds input-validation contract `1`. `load_strategy_spec()`
and `StrategySpec.from_dict()` validate against the same live-registry schema
builder in `scripts/strategy_dsl.py` **before** normalization. The exporter uses
that builder too; runtime does not rely on a potentially stale generated file.
The existing Strategy DSL CI dependency `jsonschema` is also required at runtime.

Unknown fields are rejected at the root and every nested strategy object.
For example, `execution.stop_loss_pct` is a `capability_gap`; it cannot disappear
while producing a strategy without a stop loss. Only `metadata` accepts arbitrary
JSON properties, and metadata never adds executable strategy behavior.
Inputs must satisfy the generated schema, including required fields and exact
enum spellings. Previously accepted, schema-invalid coercions are now rejected:
`"false"` is not a boolean, `"4"`/`4.5` are not rebalance months, and `"1"` is not
a factor weight or transaction cost. Duplicate months/markets are rejected.
Existing schema defaults (e.g. factor weight/transform, tradability, top-N
selection, omitted cost components and initial capital) remain available.

Filter operands are part of the schema: comparisons require a number;
percentiles require `0 < value < 100`; `eq`/`ne` require a string, number or
boolean; `in`/`not_in` require a nonempty array of those scalars. `notnull` permits
only an omitted or null value. Unused operands cannot silently disappear.

The schema's `x-input-validation` and capabilities' `input_validation` describe
additional runtime rules that standard JSON Schema alone cannot enforce:

- Integer fields require integer tokens: `1.0` is rejected, even though standard
  JSON Schema considers it an integer. `from_dict()` also accepts tuple arrays
  produced by `StrategySpec.to_dict()` for the existing normalized round trip.
- All numbers, including metadata, must be finite and representable as a finite
  float. Total factor weights and total scenario costs must also be finite.
  JSON `NaN`, `Infinity`, overflow such as `1e400`, and boolean-as-number inputs
  cannot reach execution.
- Dates must be real `YYYY-MM-DD` calendar dates. `start <= end` and
  `book_start <= book_end` are required. A report `as_of_date` may follow the
  simulation window; validation does not silently alter any requested period.
- Duplicate JSON keys are rejected at every object, including metadata.
  Normalized factor names must remain unique, and registry source constraints
  (including DART rebalance-month restrictions) still apply.

Preflight reports violations as `status="capability_gap", phase="compile"`
(exit 2), before loading the engine, PIT data, factors or NAV. Input-gate errors
include an `error.path`; duplicate-key errors identify the key without claiming
an exact nested location. Valid input with unavailable PIT data remains a
`data_gap`. The runner and `--validate-only` use the same loader and fail before
writing numeric results. The checked execution CLI additionally persists failed
attempt diagnostics without publishing NAV. The new validation test covers both entry points, CLI failure
and data-access guards, plus all eight pre-change example fingerprints.
Execution, providers and canonical CURRENT performance calculations are unchanged.

## Checked execution lifecycle

Machine contract 20 / run orchestration 1 adds automatic shared preflight,
formal CURRENT date readiness, unique run directories and structured success
states to the existing `strategy_dsl_runner.py` CLI. `--validate-only` remains
compile-only. `--execution-only` explicitly requests research NAV; the default
requires both validated NAV and the full CURRENT report. Existing `--output-dir`
now must name a new directory; no previous run is overwritten. Read
[STRATEGY_DSL_RUN.md](STRATEGY_DSL_RUN.md) for commands, publication paths,
failure states, compatibility boundaries and tests.

## Preflight: capability gap vs data gap

Before NAV simulation, use:

```bash
python scripts/strategy_dsl_preflight.py config/strategies/<strategy>.json
```

The command prints structured JSON and classifies readiness as:

- `status="ok"` / exit 0: the DSL is supported and required PIT data checks pass.
- `status="capability_gap"` / exit 2: the requested factor, market, weighting, execution rule, or other strategy concept is not representable by the current machine contract.
- `status="data_gap"` / exit 3: the strategy is representable, but required KRX years, DART PIT coverage, raw shards, or another data contract is missing/incomplete.

For orchestration that must always receive JSON without a non-zero process exit, add `--always-zero`.

Preflight never calculates NAV, return drift, trading costs or performance. Its default fast path checks source coverage and DART metadata/shard presence. If a known corporate-action evidence gap is relevant to the requested dates and potential codes, it additionally uses the same PIT factor/target builders as execution and traces positive planned holdings with the exact execution lag. A planned exposure returns `data_gap`, `phase="corporate_actions"`, `ready_for_execution=false`, and an auditable `corporate_action_audit`. This checks known gaps only; `ok` is not a certificate of complete events or executable price paths. See [CORPORATE_ACTION_PREFLIGHT.md](CORPORATE_ACTION_PREFLIGHT.md).

## KRX realized-volatility factors

The `technical` provider also exposes annualized realized volatility from the exchange-reported daily `ChangesRatio` series:

- `volatility_3m`: sample standard deviation of the latest 63 daily decimal returns × √252.
- `volatility_6m`: sample standard deviation of the latest 126 daily decimal returns × √252.
- `volatility_12m`: sample standard deviation of the latest 252 daily decimal returns × √252.

The signal-day observation is included because execution occurs on a later session. Observations after the signal date are never read. Every requested daily observation must be present; an incomplete code/window receives `NaN`.

Aliases include `3개월 변동성`, `6개월 변동성`, `12개월 변동성`, plus fixed-direction phrases such as `3개월 저변동성`, which compiles directly to `volatility_3m / low`.

## KRX technical momentum factors

The `technical` provider derives fixed price-momentum factors from the historical KRX daily `ChangesRatio` series. It does not divide raw, unadjusted close prices and it never reads observations after the signal date.

Registered fields:

- `momentum_3_1`: 63-session lookback, skip the latest 21 sessions, compound the remaining 42 sessions.
- `momentum_6_1`: 126-session lookback, skip the latest 21 sessions, compound the remaining 105 sessions.
- `momentum_12_1`: 252-session lookback, skip the latest 21 sessions, compound the remaining 231 sessions.
- `momentum_12_0`: 252-session lookback through the signal date with no skip.

The adapter requires every daily `ChangesRatio` observation inside the requested window. A missing observation produces `NaN` for that code/factor instead of silently filling a zero return. The source-coverage gate checks whether enough historical trading sessions exist; factor construction performs the stricter per-code completeness check, also when relevant known events trigger shared preflight selection.

Natural-language aliases are intentionally explicit: `12-1 모멘텀`, `6-1 모멘텀`, `3-1 모멘텀`, and `12-0 모멘텀`. Generic phrases such as “12개월 모멘텀” remain ambiguous and should not be silently compiled to a skip/no-skip definition.

## Registry-backed universe filters

Universe filters use the same field registry as ranking factors. A filter field is valid only when its name resolves unambiguously to one registered source.

Examples:

- `{"field":"Marcap","op":"exclude_bottom_pct","value":20}` is loaded directly from the KRX PIT panel.
- `{"field":"book_to_price","op":"gt","value":0}` automatically activates the DART provider before the filter is applied.

External filter fields are included in provider coverage/preflight checks and source-level constraints. Therefore a DART-backed filter also inherits the current April/October rebalance limitation. The runner no longer tries to request external filter columns from the KRX parquet loader.

The machine-readable contract exports the valid set as `filter_fields`, and the JSON Schema constrains `universe.filters[].field` to that registry-backed set.

## Factor registry / provider contract

The ranking engine does not branch on source names. Factor validation and data sourcing are centralized in `scripts/factor_registry.py`.

- `FactorDefinition` declares `source + field + storage(panel/external)`.
- panel factors are read directly from the KRX PIT cross-section.
- external factors are supplied by a registered provider implementing `factor_frame()` and `coverage_report()`.
- adding a new external source requires new factor definitions plus a provider factory; the generic ranking and execution loops do not change.
- `factor_registry_version` is recorded in every compiled execution plan.

This is the extension point for future quality, growth, momentum, macro, or other PIT-safe factor providers.

## Natural-language factor aliases

`scripts/strategy_dsl_aliases.py` provides a deterministic lexical bridge between common Korean/English factor names and canonical fields. The alias catalog is exported into `strategy_dsl_capabilities_v1.json`.

Examples:

- `슈퍼가치 PER 낮은` -> `dart.earnings_yield`, canonical direction `high` (standalone-quarter definition only)
- `PBR 낮은` -> `dart.book_to_price`, canonical direction `high`
- generic `PER/PCR/PSR` -> no automatic alias yet; trailing/annual definitions are a capability gap
- `슈퍼가치 PCR/PSR` can map to the registered standalone-quarter cash-flow/sales yields
- `소형주` -> `krx.Marcap`, fixed canonical direction `low`
- `거래대금 high` -> `krx.Amount`, direction `high`

Inverse aliases encode direction inversion explicitly only when their accounting-period definition matches the registered factor. Generic PER/PCR/PSR are intentionally not mapped to standalone-quarter factors. Unknown, ambiguous, or semantically mismatched aliases fail instead of being substituted silently.

## DART quarterly profitability factors

The DART provider also exposes three profitability fields whose accounting period is explicit in the field name:

- `quarterly_roe`: standalone-quarter net income / latest reported equity, only when equity is positive.
- `quarterly_net_margin`: standalone-quarter net income / standalone-quarter revenue, only when revenue is positive.
- `quarterly_ocf_margin`: standalone-quarter operating cash flow / standalone-quarter revenue, only when revenue is positive.

These fields inherit the current DART source contract: April and October signal months only, PIT filing-date enforcement, CFS-first/OFS-fallback logic, and full-source completeness gating.

Natural-language aliases are likewise explicit: `분기 ROE`, `분기 순이익률`, and `분기 OCF 마진`. Generic `ROE` is intentionally **not** mapped to `quarterly_roe`; annual/TTM ROE requires a separate definition.

## DART PIT value factors

Current DART value-factor execution is a source-level capability with a fixed rebalance-month contract: **April and October only**. This constraint is exported as `factor_source_constraints.dart.rebalance_months=[4,10]` and is validated during DSL compilation. A DART strategy requesting another rebalance month is a `capability_gap`, not a `data_gap`.

DSL v1 now supports these standardized DART fields:

- `earnings_yield` = standalone-quarter net income / signal-date market cap
- `book_to_price` = latest reported equity / signal-date market cap
- `cashflow_yield` = standalone-quarter operating cash flow / signal-date market cap
- `sales_yield` = standalone-quarter revenue / signal-date market cap

The adapter uses only filings whose filing date is on or before the signal date. April reconstructs Q4 from FY minus Q3 cumulative values; October reconstructs Q2 from H1 minus Q1 where a standalone current-period value is unavailable. CFS is preferred over OFS when the CFS row is complete. Before a signal is evaluated, the adapter checks the historical code map plus DART backfill state and refuses to run if any required report period is not fully terminal (CFS OK, or CFS NO_DATA with terminal OFS fallback) or the corresponding raw shards are missing.

See `config/strategies/super_value_dart_dsl.json`.

## Corporate-action continuity

Execution does not silently replace missing held-stock returns with 0%. Verified events are stored in `config/kr_corporate_actions.csv` and loaded by `scripts/corporate_action_registry.py`.

For a registered stock merger the PROJECT execution engine:

1. keeps the predecessor flat only during the verified post-last-trade suspension interval,
2. calculates the merger-date economic return from `successor close × share ratio` (stock-only; nonzero cash is rejected),
3. applies that return to NAV,
4. transfers the post-event portfolio weight from predecessor to successor without turnover or trading cost,
5. writes `corporate_actions_applied.csv` for audit.

The first registered event is Korean Paper (002300) -> Haesung Industrial (034810), 1 old share to 1.6661460 successor shares, successor listing date 2020-07-13. This registry must be expanded with verified source documents before full-history results are treated as production-valid.

## Deliberately unsupported in v1

The runner fails rather than inventing an answer for these cases:

- DART financial factors beyond the registered value and quarterly profitability fields (annual/TTM ROE, GP-A, NCAV, EV-EBIT, etc.)
- parameterized/ad-hoc momentum lookbacks beyond the registered fixed technical fields
- dynamic historical sell-tax schedules
- next-open/VWAP execution
- market-cap/factor weighting
- ETF/macro/asset-allocation DSL

These are adapters to add without changing the core schema philosophy.

## Example

See `config/strategies/kr_equity_rank_demo.json`.

Validation only:

```bash
python scripts/strategy_dsl_runner.py config/strategies/kr_equity_rank_demo.json --validate-only
```

Execution with canonical performance postprocess:

```bash
python scripts/strategy_dsl_runner.py config/strategies/kr_equity_rank_demo.json
```

Execution stage only (target weights -> PROJECT v2-16 t+1 execution -> daily NAV):

```bash
python scripts/strategy_dsl_runner.py config/strategies/super_value_dart_dsl.json --execution-only
```

The execution-only path is intentional for research windows whose PIT factor coverage is valid but which do not yet span the canonical 2000+/2021+/longest reporting windows. It does not calculate alternative performance metrics; formal metrics still go through `quant_backtest_postprocess.py` only.

Outputs go to `results/dsl/<strategy_id>/` and include:

- `daily_nav.csv`
- `target_weights.csv`
- `selections.csv`
- `factor_provider_coverage.csv` when external factor providers are used
- `corporate_actions_applied.csv` when a registered event affects a held position
- `execution_plan.json`
- `strategy_fingerprint.txt`
- canonical `metrics_CURRENT.csv`
- canonical `chat_manifest_CURRENT.json`

## Reproducibility contract

Every validated strategy has a SHA-256 `strategy_fingerprint` derived from canonical JSON. Results should be keyed by at least:

`strategy_fingerprint + factor_registry_version + engine_version + data_version/as-of`.

The registry version is stored in the compiled execution plan so a change in factor semantics is auditable even when the strategy JSON itself is unchanged.This is the basis for the future strategy-result database and natural-language research agent.


## Historical source coverage

Preflight contract 3 and both public execution modes require the exact XKRX
sessions between `period.start` and `period.end` for **each** requested market.
Missing first/interior/last sessions and unexpected non-session dates fail as
`data_gap`; the full requested interval is preserved. Weekend/holiday request
endpoints are valid. Calendar construction uses explicit requested bounds and
records the exchange_calendars version, avoiding its moving default range.
Preflight errors include `history_coverage` when date coverage fails. Successful
runs save `history_coverage.json`; no factors or NAV are calculated by this gate.

Calendar discrepancies must be reconciled against official history rather than
filled or bypassed. This is a market-level date check. `complete` does not certify
per-code history, held-price return correctness, dividends or corporate actions.

Use `scripts/krx_history_audit.py` to export per-code observation spans and review
candidates from actual source history. Its gap and price-reference checks do not
alter the universe or execution; candidate events require independent evidence.
Commands, threshold definitions, real-data snapshots and remaining scope are in
[KRX_HISTORY_AUDIT.md](KRX_HISTORY_AUDIT.md).


## Held-return reference validation and stock splits

Both public portfolio modes require source `ChangesRatio` and pass decimal
exchange returns to PROJECT execution. Each held asset is checked before NAV
and before execution-day rebalance within 1bp of the effective price/event return.
Missing/non-finite references or unresolved differences fail, without removing
stocks or replacing NAV returns by ChangesRatio. Verified same-code split
returns are reference-checked after multiplying by the registered share ratio.
Verified merger disposal values and registered missing-reference suspensions
have explicit audit counts; successor ordinary returns are still checked.

Successful runs save `return_reference_audit.json` and `held_return_checks.csv`.
Deciles save combined root audits and the individual scenario audits in each
bucket directory. Low-level direct calls can omit the reference for compatibility
and report `enabled=false`; such calls are not validated public DSL execution.
The 1bp execution threshold differs from the 25bp source review-candidate threshold.

The short runnable real split regression is
`config/strategies/kr_equity_split_research.json`. It selects the highest nominal
KOSDAQ price on 2024-03-29, buys on 2024-04-01, and validates the registered EcoPro
split without claiming investment merit or long-horizon performance. Use
`--execution-only`. Evidence, formulas and limits are in
[HELD_RETURN_VALIDATION.md](HELD_RETURN_VALIDATION.md).

## Corporate-action source reconciliation

The source-only command in [CORPORATE_ACTION_RECONCILIATION.md](CORPORATE_ACTION_RECONCILIATION.md)
checks manually evidenced registered splits and preserves every review candidate.
Registry version 3 adds BYC common/preferred as separate ten-for-one records.
Reconciliation never feeds strategy eligibility or replaces the public held-return
check. Its success is not whole-market history certification.

## Canonical performance v2-17

PROJECT v2-16 / execution v2-16-exec-3 generates daily NAV. All performance
calculations and charts delegate to CURRENT v2-17. Machine contract 13 exports
the independent performance version. Both top-N and decile reporting paths
pass XKRX into postprocess. Missing/extra sessions stop canonical report
creation; no report silently labels incomplete daily NAV as daily risk.
Explicit benchmarks also generate `benchmark_statistics_CURRENT.csv`.
The existing four periods and nine charts remain; short `--execution-only`
regressions are not long-history performance reports. Definitions, optional
CLI arguments and the legacy PROJECT period policy are in
`docs/CANONICAL_PERFORMANCE.md`.

## Cash-only exchanges and known evidence gaps

The generic `cash_share_exchange` contract separates fixed nominal receivables
from settled Cash and rejects targets/costs that would spend unpaid proceeds.
It requires verified actual payment metadata and observed zero-volume suspension.
Receipt has no second NAV gain or transaction costs. Gross and Net amounts are
accounted for separately. See `docs/CASH_SHARE_EXCHANGE.md` for exact boundaries
and audit outputs. No production cash event is registered yet. Jeisys 287410
remains blocked for affected holdings from 2024-10-23 because actual payment
and applicable net-proceeds evidence are unresolved; historical signal eligibility is preserved.
Preflight also checks positive planned exposure through the shared selection/lag
contract; see `docs/CORPORATE_ACTION_PREFLIGHT.md`.
