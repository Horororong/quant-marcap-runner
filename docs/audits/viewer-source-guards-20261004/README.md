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

33 local regression tests passed. Standard full Strategy DSL CI37184664330 completed successfully on the
final code commit be450e9f9f38909f60d354edad07012e3604b2bd. No new execution kit is required for this source-only
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

## Reproducible independent 72-item recheck against current checkout

The two complete original OpenDART ZIP files (artifact **11205027337**, run
**36953686608**) are preserved losslessly in `tests/fixtures/legacy_dart/native_primary`
(72,515 bytes). Both document SHA and member SHA match the original source-probe
records. `scripts/recheck_legacy_primary_audit.py` verifies all fourteen primary
bodies and invokes the pre-existing independent source comparator in a bounded
subprocess. It neither imports the collector nor derives expected values using
this adapter. Input file hashes are checked before/after; repeated/differing
output directories are rejected.

Local recheck against the earlier checkout reproduced the 72-item results:
49 stored-missing, 18 period mismatches, 3 amount mismatches, 2 semantic
mismatches. These preserved v4 errors have not been rewritten, and legacy
remains unavailable to production DSL requests. This adds reproducibility and
CI checking of the **same** independent sample, not 72 new samples or full-data
certification. The legacy-validation CI and full Strategy DSL CI now also run
this audit against the actual remote checkout, including main's later backfill
files. Current remote input hashes and findings must be inspected in their
`legacy-primary-72-recheck` / `legacy-viewer-source-replay` artifacts after the
new CI completes; local baseline results cannot substitute for those findings.

GitHub's blob-fetch connector returned a `UnicodeDecodeError` for a gzip
financial blob; its generic fetch returned HTTP 400 saying only UTF-8 text is
accepted. These are binary-content limitations, not established authorization
denials. The CI checkout path avoids that content limitation using the existing
repository's own files, without any alternate data supplier or network bypass.

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

## Actual frozen-kit strategy readiness checks (no NAV)

The already installed dedicated Python invoked `sandbox_runtime.py verify`
with a 60-second subprocess timeout: status=ok, kit 26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd,
source 822c435f4b6148c2832e12370a6ccb324a9e875f, CP312 pinned runtime.
Read-only canonical preflight ran with the same installed Python and a
120-second timeout, without importing engine modules into the ambient kernel.

| Existing definition / request | Checked result | Investment report / OOS |
|---|---|---|
| Existing standalone-quarter super-value DSL, 2020-04-01–2020-11-30 | preflight `ok`, ready_for_execution=true; signal dates 2020-04-29/2020-10-30; fingerprint ae45125a95e513c4996f4111355297bfc3c53ed65b072138e435857a9e093159 | no new NAV/report; original gross-only cost configuration is not investable cost validation |
| Same factors/universe, requested start 2000 (through existing 2020 endpoint) | `data_gap`, missing kit KRX 2000–2018; period not shortened | blocked |
| Same factors/universe, 2021-01-01–2026-10-01 | `data_gap`, missing kit KRX 2021/2022/2023/2025/2026 | blocked |
| Annual PER/ROE/TTM or 2000–2014 legacy PIT factors | existing capability/source-quality gaps unchanged | blocked; no quarterly proxy substitution |

The date-adjusted JSON files are read-only readiness probes, not newly selected
strategies, optimization or book-validation periods. They produce no NAV and
no performance numbers. Kit coverage and repository coverage remain separate.
The prior CURRENT report-validation example's formal 2019–2020 path remains
software evidence; this source task adds no investment-performance claim.
`preflight status=ok` is not `nav_ready=true` or `report_ready=true`.

## Reproduce / resume without collecting or overwriting

From a normal development checkout (not inside the frozen installed kit):

```bash
timeout -k 5s 30s python scripts/test_legacy_viewer_source.py
timeout -k 5s 60s python scripts/recheck_legacy_primary_audit.py \
  --output-dir /tmp/legacy-primary-72-review-new
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


## Verified remote primary-audit checkpoint

On actual code commit `be450e9f9f38909f60d354edad07012e3604b2bd`, legacy
validation [CI37184664255](https://github.com/Horororong/quant-marcap-runner/actions/runs/37184664255)
completed successfully, including native parser/resume/schema checks, the 33
new source regressions and the independent 72-item comparator. Artifact
11296975611 was downloaded; ZIP SHA and CRC passed. Its input hashes prove the
remote audit read the later main's changed `legacy_metrics_2001.csv.gz`,
`legacy_metrics_2002.csv.gz` and collector checkpoint, not the older local
snapshot. The 72-item findings remain 49 missing / 18 period / 3 amount / 2
semantic. All input hashes stayed unchanged during the audit.

The full Strategy DSL CI source artifact11296566580 was also downloaded;
ZIP SHA/CRC and the 49-cell replay summary match local evidence. Four accepted
BS totals satisfy assets = liabilities + equity; this is **secondary arithmetic
consistency**, not a new independent audit. **None of the six quarterly sources
provides current-period OCF or a complete usable 4F row.** Previous annual CF
and CFS cannot fill that gap. See `source-consistency.json`, the remote audit
summary/provenance and `remote_ci_evidence.json`.


## Final code CI and project status

Full [CI37184664330](https://github.com/Horororong/quant-marcap-runner/actions/runs/37184664330)
completed/success on **be450e9f9f38909f60d354edad07012e3604b2bd** at
2026-10-04 07:24 UTC. The test job and CP311/CP312 sandbox replays all succeeded;
download-only job was skipped. All required generated-contract, native
parser/resume/automation, canonical report, real KRX/DART/decile/corporate-action
and checked-CLI regressions passed. Full job/step state and filtered completed
logs are saved in `full_ci_success.json` and `full-ci-completion.log`. Later
evidence-only documentation commits do not change the tested source code,
fixtures, workflow or financial inputs.

The existing browser report regression passed (artifact11297120535). Its
metrics_CURRENT.csv, daily_nav_canonical.csv and benchmark statistics are
**byte-identical** to the previously verified CI report. No UI was rebuilt and
no investment-performance metrics were calculated by this audit. Branch data
preservation was independently checked against main: **418 data blob SHAs,
zero changed blobs**, including later normalized financial shards/checkpoints.
PR #30 is a draft stacked on audit PR #29; neither has been merged into main.

| Project area | Actual judgment |
|---|---|
| Report functionality | implemented + browser/CURRENT/CSV regression verified |
| Data preparation | incomplete; legacy collection pending 103,619 at main4833fb5, modern pending gaps persist |
| Independent financial quality | reproducible 72-item failure-oriented sample and 49-cell guarded replay; full-data/PIT/revision certification incomplete |
| Actual strategy validation | incomplete; existing quarter DSL preflight passes its small kit window, no new research NAV/cost/OOS/robustness study |

The source guard feature and its required regressions are complete **within
this staged offline scope**. This does not complete legacy data preparation,
full-data certification or actual investment strategy validation. Next data
work: independently establish the five blocked current-period cells' BR/label
alignment from their full primary sources before extending the adapter. Current
quarter OCF, independent 2019–2020 strategy-source samples and correction/PIT
chains still require primary acquisition/review through authorized collection.
