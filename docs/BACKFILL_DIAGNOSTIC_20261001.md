# DART collection checkpoint — 2026-10-01

This is a read-only diagnosis of repository main
`b763c5ca903d652a815bbdbff6df978843a45c86`, not live visibility into another GPT
chat sandbox. No collection was restarted and no production data/status file
was rewritten. Recheck actual files and GitHub runs before relying on this
checkpoint.

## Observed full-history state

- `data/status/dart_full_backfill_state.csv`: 130,414 unique task keys
  `(stock_code, corp_code, year, period, fs_div)`, 89,366 `OK`, 41,048 `NO_DATA`;
  latest stored update 2026-09-30 20:25:33 UTC.
- `data/financials/full_history/`: 176 compressed shards. The collector calls
  `fnlttSinglAcntAll.json` and retains returned financial-statement account rows,
  not only the seven currently exposed DART factor fields.
- Historical map: 4,142 stock-code rows, 3,986 valid eight-digit corp codes,
  156 unresolved mappings. Current adapter expected populations use valid
  mappings; their coverage is not all-security coverage certification.
- `dart_full_backfill_status.csv` is older (2026-09-23 11:12 UTC) and reports
  78,479 completed tasks. `dart_pit_coverage_status.csv` is also older and reports
  75,479. These counters cannot be used as current progress. Different summary
  write times and stale totals must be reconciled with the authoritative task
  state before computing completion percentages or remaining-time estimates.
- Recomputed **current adapter** coverage from the stored map/state is ready
  for 2015 FY and 2016–2020 Q1/H1/Q3/FY. That means CFS-first/OFS-fallback terminal
  status and required shard presence for the mapped population. It does not
  certify correct per-account values, amendment lineage or unmapped companies.
  `NO_DATA` is a completed request, not usable accounting data.

## Observed legacy state

The unique receipt states contain 13,345 filings: 3,488 `PARSED_4F`, 3,012
`PARSED_PARTIAL`, 5,577 `NO_METRICS`, 1,239 `NO_DOCUMENT`, 28 `ERROR`, and one
`RATE_LIMIT`. Latest stored update is 2026-09-30 22:43:55 UTC. `PARSED_4F` means
the parser found equity/revenue/net income/OCF in one scope; it is not an
independent validation of source amounts, period semantics or PIT availability.

`process_filing()` currently downloads original ZIP documents, parses selected
metrics and saves normalized rows plus document hashes/parser versions. It does
not archive those original ZIP bytes. Broadening extraction later may therefore
require expensive downloads again. The existing DART provider reads
`full_history`, not `legacy_2000_2014`; collected legacy rows still require a
validated adapter bridge before DSL execution can use them.

## GitHub observation and uncertainty

The latest entries visible on the relevant workflow pages at inspection were:

- [full history run](https://github.com/Horororong/quant-marcap-runner/actions/runs/35865140400),
  September 23, `Failure`, exit-code-1 annotation;
- [legacy run](https://github.com/Horororong/quant-marcap-runner/actions/runs/35866018627),
  September 23, `Failure`, exit-code-1 annotation.

Authenticated logs were unavailable, so the failure cause is not established.
Later stored task timestamps demonstrate later data updates, not continuous
operation of those GitHub jobs. All three current historical-backfill workflows
declare `workflow_dispatch` only, without a schedule. Another chat may run its
own collector; this checkout cannot determine that process's live state.
The available evidence supports accumulated work, but not a claim that collection
is currently healthy, continuous or finished.

## Recommended collection boundary

Collect and preserve broad reusable financial raw material, then derive factors
through versioned PIT providers. Avoid separate downloads per derived factor.
For legacy sources, archive immutable original documents before further large
processing, retain receipt/filing/correction lineage, and version parsers. Keep
collection task completion, parse success, usable account coverage and validated
PIT coverage as distinct counters. Publish fresh summaries from the same state
snapshot, with explicit last-success/error/rate-limit information.

Annual/TTM, growth, quality, leverage, accruals and dividend factors need explicit
period/denominator/source contracts and tests before registry exposure. Prices,
momentum and volatility reuse repository KRX history; dividend events and PIT
security classifications need their own data contracts. Current seven DART
factors and seven technical factors are a research starting point, not the full
general-purpose factor library.
