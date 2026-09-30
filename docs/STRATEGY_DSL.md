# Strategy DSL v1

## Goal

Natural language is translated by an AI layer into a deterministic JSON strategy specification. The backtest engine never executes free-form model reasoning. The same JSON + same data + same engine version must produce the same target weights and NAV.

Flow:

`natural language -> Strategy DSL JSON -> validator/compiler -> target weights -> PROJECT v2-16 execution engine -> daily NAV -> CURRENT postprocess`

## v1 runtime scope

- Asset class: `kr_equity`
- Historical universe: KOSPI/KOSDAQ PIT panel from `data/krx_equities/yearly/`
- Factor source: existing KRX panel columns (`Marcap`, `Amount`, `Volume`, `Close`, etc.)
- Composite ranking: weighted percentile ranks, best score = lowest composite score
- Portfolio weighting: equal weight
- Rebalance: selected months, last KRX trading day
- Execution: signal close -> at least next-session close (`lag_sessions >= 1`)
- Costs: explicit named fixed-bps scenarios
- Metrics/charts: canonical CURRENT postprocessor only

## Deliberately unsupported in v1

The runner fails rather than inventing an answer for these cases:

- DART financial factors (PER/PBR/PCR/PSR/ROE/GP-A, etc.)
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

Execution:

```bash
python scripts/strategy_dsl_runner.py config/strategies/kr_equity_rank_demo.json
```

Outputs go to `results/dsl/<strategy_id>/` and include:

- `daily_nav.csv`
- `target_weights.csv`
- `selections.csv`
- `execution_plan.json`
- `strategy_fingerprint.txt`
- canonical `metrics_CURRENT.csv`
- canonical `chat_manifest_CURRENT.json`

## Reproducibility contract

Every validated strategy has a SHA-256 `strategy_fingerprint` derived from canonical JSON. Results should be keyed by at least:

`strategy_fingerprint + engine_version + data_version/as-of`.

This is the basis for the future strategy-result database and natural-language research agent.
