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

## Factor registry / provider contract

The ranking engine does not branch on source names. Factor validation and data sourcing are centralized in `scripts/factor_registry.py`.

- `FactorDefinition` declares `source + field + storage(panel/external)`.
- panel factors are read directly from the KRX PIT cross-section.
- external factors are supplied by a registered provider implementing `factor_frame()` and `coverage_report()`.
- adding a new external source requires new factor definitions plus a provider factory; the generic ranking and execution loops do not change.
- `factor_registry_version` is recorded in every compiled execution plan.

This is the extension point for future quality, growth, momentum, macro, or other PIT-safe factor providers.

## DART PIT value factors

DSL v1 now supports these standardized DART fields:

- `earnings_yield` = standalone-quarter net income / signal-date market cap
- `book_to_price` = latest reported equity / signal-date market cap
- `cashflow_yield` = standalone-quarter operating cash flow / signal-date market cap
- `sales_yield` = standalone-quarter revenue / signal-date market cap

The adapter uses only filings whose filing date is on or before the signal date. April reconstructs Q4 from FY minus Q3 cumulative values; October reconstructs Q2 from H1 minus Q1 where a standalone current-period value is unavailable. CFS is preferred over OFS when the CFS row is complete. Before a signal is evaluated, the adapter checks the historical code map plus DART backfill state and refuses to run if any required report period is not fully terminal (CFS OK, or CFS NO_DATA with terminal OFS fallback) or the corresponding raw shards are missing.

See `config/strategies/super_value_dart_dsl.json`.

## Deliberately unsupported in v1

The runner fails rather than inventing an answer for these cases:

- DART financial factors beyond the four standardized value fields (ROE/GP-A/NCAV/EV-EBIT, etc.)
- momentum lookbacks / technical derived factors
- dynamic historical sell-tax schedules
- next-open/VWAP execution
- market-cap/factor weighting
- explicit corporate-action/delisting return adapter
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
- `execution_plan.json`
- `strategy_fingerprint.txt`
- canonical `metrics_CURRENT.csv`
- canonical `chat_manifest_CURRENT.json`

## Reproducibility contract

Every validated strategy has a SHA-256 `strategy_fingerprint` derived from canonical JSON. Results should be keyed by at least:

`strategy_fingerprint + factor_registry_version + engine_version + data_version/as-of`.

The registry version is stored in the compiled execution plan so a change in factor semantics is auditable even when the strategy JSON itself is unchanged.\n\nThis is the basis for the future strategy-result database and natural-language research agent.
