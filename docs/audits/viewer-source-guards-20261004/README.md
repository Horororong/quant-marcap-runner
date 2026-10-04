# Viewer source guard checkpoint — 2026-10-04

## Implemented and locally checked

`scripts/legacy_viewer_source.py` is an offline, versioned adapter for the
already captured DART viewer financial-body sections. It verifies source body
SHA/length, official route identity, strict encoding, route/body scope, explicit
statement/date/unit headers and the numeric column belonging to the requested
source period. Empty BR lines, column spans, previous periods and note columns
are preserved. It rejects ambiguous multiple amounts, duplicate metrics,
unknown units and unsupported row alignment. It does not guess a sign from
parentheses alone (the Daegu source prints positive BS totals that way).

The adapter uses the native collector's account/amount rules, extracted
unchanged into `scripts/legacy_financial_fields.py`. All six moved definitions
were AST-compared with the prior collector. Native parser version remains
`legacy-v5-single-amount`; collection/checkpoint behavior and generated DSL
contracts are unchanged. Viewer-specific `(-)` signs and the exact Ildong
`당기순이(손)익` label belong to the separate adapter version
`dart-viewer-period-scope-unit-column-v1`.

31 local regression tests passed. Standard full Strategy DSL CI is required
before this change is considered complete; its actual status will be appended
after the run finishes. No new execution kit is required for this source-only
change: no bundled runtime/provider/engine code changed, and legacy remains an
unpublished capability. Never edit the installed frozen runtime to add this
adapter.

## Independent primary-source comparison

The original [sample plan](../data-readiness-20261004/SAMPLE_PLAN.md) and manual
72-item audit predate this adapter. All 49 viewer-source cells from that audit
were retained as independent golden expectations; none were selected using
strategy performance or this parser's outputs. The original 12 primary HTML
bodies from Actions artifact **11221241095**, capture run **36994245000**, are
stored with lossless gzip compression in `tests/fixtures/legacy_dart/viewer_primary`.
Original body SHA values, official URLs, capture metadata and original cell
coordinates remain inspectable. Compression adds 168,214 bytes in total.

The replay compares extracted values with the previously hand-selected primary
cells, not with another run of the same collector:

| Outcome | Items | Meaning |
|---|---:|---|
| MATCH | 17 | Current source period/scope/unit/token/value agree |
| WITHHELD_PRIOR_PERIOD | 22 | Older annual CFS/CF values cannot become current quarterly values |
| WITHHELD_UNKNOWN_UNIT | 5 | Vitz BS/IS unit is blank; no KRW value is invented |
| WITHHELD_LAYOUT_GUARD | 5 | United/Peerless compressed IS and Daewoo loss row have unequal BR-line counts |
| MISMATCH / GUARD_FAILURE | 0 | No accepted audited value disagrees with the primary expectation |

Only these 17 accepted cells have independent numeric comparison in this new
adapter. They are a subset of the previous audit, not 17 additional independent
samples. The adapter emits 63 staging rows; the remaining **46 rows are not
independently value-verified**. Neither they nor the 17 matched rows are
production/PIT ready. Real filing availability and correction chains are not
verified. `strategy_usable_date=null`, `pit_ready=false`, `production_ready=false`.
No financial metrics or native collector state were written under `data/`.

## Data preparation and actual-strategy validation remain open

The existing native scheduled collector and checkpoints are preserved. Latest
remote main when this task started: `4833fb503105d810ea6e8e905d914f1ab3c28632`.
No new collector was launched. The earlier execution environment remains
unobservable, so its collector state cannot be inferred from this workspace.
Live GitHub runs checked at the start showed no running collection job.
Current remote legacy checkpoint: 11,401 processed mapped filings, **103,619
pending**, 616 PARSED_4F, 8,620 NO_METRICS, 1,570 NO_DOCUMENT; neither collection
nor quality is complete. Local data still corresponds to the earlier audit
baseline, not the later remote data snapshot. Publication must use the remote
feature tree as its base so newer main data is not overwritten.

Direct DART access/API credentials are unavailable in this execution environment.
The existing source evidence suffices for this replay; it does not suffice to
certify 2000–2014 or to retrieve current-quarter OCF that is absent from these
sections. No alternate supplier, proxy, online installation or native checkpoint
reset was used. Continuing source acquisition requires the existing authorized
Actions collection/audit path and its bounded shared-lock schedule.

Actual investment strategy cost/OOS/robustness validation is not complete.
No new research NAV has been launched without confirmed consent. Existing DSL
examples and required CI remain software-path checks, not investment evidence.
Legacy annual PER/ROE/TTM remain unsupported; existing quarterly definitions
cannot substitute for them. Broad financial PIT/correction-chain audit and
corporate-action/dividend/benchmark gaps from the prior audit still apply.

## Reproduce / resume without collecting or overwriting

From a normal development checkout (not inside the frozen installed kit):

```bash
timeout -k 5s 30s python scripts/test_legacy_viewer_source.py
timeout -k 5s 30s python scripts/replay_legacy_viewer_sources.py \
  --output-dir /tmp/legacy-viewer-source-review-new
```

Outputs include all source gaps, staging provenance, 49-row golden comparison
and summary. Existing identical outputs are retained; differing files cause a
failure and require a new output directory. The collector's pending list is
not consumed. Full CI also runs both commands and saves their results as the
`legacy-viewer-source-replay` artifact. The next data task is to inspect the
five blocked current-period cells' full original BR structure before extending
layout support; zero-padding, line shifting and guessed prior values are forbidden.
