# Strategy DSL v1

## Goal

Natural language is translated by an AI layer into a deterministic JSON strategy specification. The backtest engine never executes free-form model reasoning. The same JSON + same data + same engine version must produce the same target weights and NAV.

Flow:

`natural language -> Strategy DSL JSON -> validator/compiler -> target weights -> PROJECT v2-16 execution engine -> daily NAV -> CURRENT postprocess`

## v1 runtime scope

- Asset class: `kr_equity`
- Historical universe: KOSPI/KOSDAQ PIT panel from `data/krx_equities/yearly/`
- Factor sources: existing KRX panel columns and standardized DART PIT value factors
- Composite ranking: weighted percentile ranks, best score = lowest composite score
- Portfolio weighting: equal weight
- Rebalance: selected months, last KRX trading day
- Execution: signal close -> at least next-session close (`lag_sessions >= 1`)
- Costs: explicit named fixed-bps scenarios
- Metrics/charts: canonical CURRENT postprocessor only

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
- `dart_pit_coverage.csv` when DART factors are used
- `execution_plan.json`
- `strategy_fingerprint.txt`
- canonical `metrics_CURRENT.csv`
- canonical `chat_manifest_CURRENT.json`

## Reproducibility contract

Every validated strategy has a SHA-256 `strategy_fingerprint` derived from canonical JSON. Results should be keyed by at least:

`strategy_fingerprint + engine_version + data_version/as-of`.

This is the basis for the future strategy-result database and natural-language research agent.
