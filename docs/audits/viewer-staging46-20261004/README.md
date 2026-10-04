# Fixed remaining 46 staging cells — independent source audit, 2026-10-04

## Current handoff

Branch `audit/viewer-staging46-20261004` follows draft PR #31. Main has not been
merged or modified. This checkpoint supersedes the earlier ten-item and
remaining-46 next-task statements in previous handoffs. Remote CI/publication
status will be recorded below only after actual completion.

The fixed plan selected **all 46 remaining cells** before examining their
amounts; plan SHA256 is
`a34001b3d3b9930a06581c2a96ddc5cca403a86ec93be4c5e7cb47a7f4cdfc38`.
No strategy, performance, confidence filter or value was used for selection.

## Independent evidence and results

Manual expectations were transcribed from original archived primary DART viewer
bodies, including complete table headers, original account/numeric cells and
literal character spans. The independent verifier imports no collector, viewer
adapter, financial-alias registry or performance code. Original gzip/body/cell
hashes, literal BR lines and manual dates/current-column expectations are checked
before comparing persisted staging amounts. All production parser versions are
observed separately; no financial value or collection checkpoint is changed.

- Five companies, five receipts, 13 financial metric types; original source
  calendar periods are 2000 Q1 and Q3, all OFS and explicitly KRW. This is a
  closed staging population, not a representative annual/CFS/2000–2014 sample.
- **46/46 numeric matches and 46/46 source-contract matches; zero numerical
  disagreements.** Forty source account/subtotal matches and six measurement
  qualifications are kept distinct. No production/parser correction is warranted
  from these matches. Measurement details and the previous four SG&A
  components are recorded in `measurement-qualifications.json`.
- R008/R026/R037 are the printed gross named bonds lines, before separately
  printed discounts; Daegu convertible bonds are also separate. These lines do
  not certify net carrying value or a complete definition of total debt.
- R034/R042/R044 are depreciation/amortization components under SG&A, not
  company-wide D&A or an EBITDA proxy. The previous ten-item supplement also
  contains four such SG&A components. Across all 78 staging cells, **10 require
  measurement qualifications**; numeric matching does not authorize new factors.
- Local older-baseline production lookup finds all 46 selected items absent.
  This is separate from matching staged values. The actual remote checkout
  also finds all 46 absent; its audit is preserved separately. Three remote
  production/checkpoint hashes differ from the older local baseline; the 46
  audit records, CSV and summary nevertheless match byte-for-byte. All five
  native states are `NO_METRICS` under `legacy-v5-single-amount`, while the
  archived primary viewer bodies demonstrably contain these 46 values. This
  separates a native extraction/source-route gap from absence of the financial
  amounts; it does not by itself isolate the native root cause or solve PIT.
  No newer remote input was replaced by the older local copy.
- Together with the original 22 golden matches and the previous ten-item audit,
  all **78 staging cells** now have primary numeric checks. The original
  72-item audit findings are preserved; this result does not convert those
  historical production failures into matches.
- Actual filing-publication dates and correction chains are unverified. Index
  receipt days are recorded separately. Every new item has
  `actual_filing_date=null`, `strategy_usable_date=null`, `pit_ready=false`,
  `production_ready=false`. No lag was fabricated and no strategy used these
  corrected/staged values.

`audit.csv`/`audit.json` preserve each identifier, term, item, OFS/unit, receipt,
original link/value, staged value, production values/version, numeric/date/scope
checks, actual-date/correction limitations and measurement implications.
`PRIMARY_CELL_EVIDENCE.json` preserves the original literal row and header
proofs; `EXPECTED_PRIMARY_CELLS.json` is the independent manual reference.

## Regression verification

Eleven audit failure-boundary tests pass locally: manual-token mismatch, previous
numeric column, incorrect end date, quarter-to-annual relabelling, OFS/CFS heading
substitution, unknown unit, altered original span, changed sample identity,
forged staging amounts, original-source full-population check and preservation
of an existing output directory. They supplement the existing 48 adapter tests,
without changing the adapter/native parser or weakening their guards.

A first test-run diagnostic failed because a newly stronger flow-date guard
rejected the wrong end date before the table-date guard. The expected failure
message was aligned with that earlier rejection; the erroneous date still fails.
The final passing log records the corrected regression; this was not a production discrepancy.

The existing legacy validation workflow runs the fixed audit against its actual
checkout and uploads a separate `legacy-staging-46-audit` artifact. No collection
workflow/lock/schedule was added or changed. Full Strategy DSL CI was triggered by
the handoff update. Legacy CI37192667866 passed at code c908a9e; full final-code
CI37192667867 completion evidence is recorded in the final section below.

Dedicated installed-kit Python subprocess `sandbox_runtime.py verify` succeeded;
kit `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`,
source `822c435f4b6148c2832e12370a6ccb324a9e875f`, Python 3.12.14. Installed
kit, pinned packages, raw data, registry and CURRENT owner were not edited.

## Collection and backtest boundary

Initial live main was `4833fb503105d810ea6e8e905d914f1ab3c28632`, PR #31 draft,
open and unmerged at `885b4c5c22b944f56545d90d6c2f3c6758fee0a9`.
Initial GitHub running/queued lists were empty. Earlier-machine collection state
is unobservable; this does not establish that it stopped. No collector was
launched or checkpoint reset. Last confirmed remote legacy checkpoint: 11,401
processed, 103,619 pending of 115,020 mapped, 616 PARSED_4F. Counts are parser
states, not independent quality certificates. Existing shared collection lock
and scheduled resume path remain in place.

| Conditions | Actual evidence and period | Boundary |
|---|---|---|
| Existing KOSPI/KOSDAQ price/size DSL report example | Prior checked runner and official CURRENT output, 2019-01-02–2020-12-30 | `status=ok`, `nav_ready=true`, `report_ready=true`; not a new investable-strategy validation, `report_complete=false` for unavailable standard periods |
| Quarterly-factor 2020 request | Existing 2020-04-01–2020-11-30 preflight evidence | Readiness only; no newly consented research NAV was run |
| Book period | Not specified | No result invented |
| 2000/latest, 2021/latest and maximum/latest | Kit coverage is only 2019/2020/2024 whole-year panels, separate from repository 32-year history | `data_gap`; no period shortening |
| Legacy 2000–2014 financial requests | This 78-cell audit cannot establish PIT/completeness/OCF/correction chains | `data_gap`, not execution permission |
| Annual PER/ROE/TTM definitions | Registered support must be checked without quarterly substitution | `capability_gap` where unsupported, separate from missing data |

Report software remains implemented and previously CI/browser tested. Data
preparation, full independent data quality and actual cost/OOS/robustness
strategy validation remain incomplete. Corporate-action dividends, legal cash
consideration, total-return benchmarks, annual/connected/current OCF and actual
availability/corrections remain gaps. Prior source audit/coverage documents
retain the detailed dataset/calendar/universe boundaries; this task makes no
new price or corporate-action financial-certification claim.

## Safe reproduction and resume

Run from the source checkout using a fresh output directory:

```bash
timeout -k 5s 60s python docs/audits/viewer-staging46-20261004/test_audit_guards.py
timeout -k 5s 60s python docs/audits/viewer-staging46-20261004/verify_remaining_cells.py --output-dir /tmp/quant-staging46-recheck-new
timeout -k 5s 30s python scripts/test_legacy_viewer_source.py
timeout -k 5s 60s python scripts/export_strategy_dsl_contract.py --check
```

The independent audit refuses an existing output directory. It checks every
production/checkpoint input hash before/after and has bounded gzip/CSV budgets.
Do not discard legacy values, reset collection state, dispatch a duplicate
collector, publish the staged metrics as PIT, or introduce research NAV without
confirmed consent. Next source-quality task: verify actual publication dates
and correction chains for these five receipts using authorized primary sources;
unavailable originals must remain explicitly unverified.

## Actual remote legacy evidence

- Draft PR [#32](https://github.com/Horororong/quant-marcap-runner/pull/32), stacked
  on PR #31. Remote code commit `c908a9e1923f20004df7ebf8c8dafcc89ed3fc35`
  corresponds byte-for-byte to all 16 changed files at local `4e5dfdf`.
- [Legacy CI37192667866](https://github.com/Horororong/quant-marcap-runner/actions/runs/37192667866),
  job111407971401, passed against that exact code and actual remote data. Logs
  include all 11 audit regressions, 48 adapter tests and existing native suites.
- Downloaded artifact `legacy-staging-46-audit`, ID11299761244, 11,100 bytes,
  verified ZIP SHA256 `571e2a7cc7a5a62ef9e2bcb4700985bda1268e1cc403812e52e2579b36d6a11a`.
  All 46 staged numeric/contract matches, 46 production missing, zero PIT items,
  original input hashes unchanged during audit. `remote-audit/` is the actual
  extracted artifact, not a local rerun represented as remote evidence.
- Original 72-item artifact ID11300025470, 14,298 bytes, verified ZIP SHA256
  `ffa647285bdd06ab0cff614b133deb8753b061c1f8897c2b86eaaf608b6168f4`. Findings
  remain 49 missing / 18 period / 3 amount / 2 semantic. Summary exactly matches
  the prior remote audit; historical failures remain unresolved.
- Live main coverage file SHA256
  `1f9a7b168160b1a5a633d3695023f30d0b2468ab69d91ca4eb3dc001403830a2`
  matches prior live-main evidence. `collection-status.json` is derived from
  this newly fetched file, not from an assumed local collector state.
- Shared lock `super-value-fast-pit-backfill`, daily 15:30 UTC and October
  07:30/23:30 UTC scheduled bounded batches remain unchanged. The manual legacy
  entry point shares that lock and resumes existing checkpoints; no dispatch
  occurred in this task. Earlier-machine collection remains unobservable.

## Preserved report and adapter regression artifacts

Full-code CI generated the existing requested-period report with
`status=ok`, `nav_ready=true`, `report_ready=true`, `report_complete=false`.
Its original fingerprint remains
`455268d0fd7f2c4330e2592f021098af0c0d81ae101a67c34265c54064fec352`.
Unavailable book/from-2000/from-2021 periods are not invented. This CI example
is a software regression, not a newly selected or validated investment strategy.

Downloaded source replay artifact ID11299607288 (28,311 bytes) and report preview
artifact ID11299567952 (2,509,299 bytes); ZIP digests and file checks are recorded
in `regression-output-preservation.json`. The four original replay files and
CURRENT metrics/NAV/benchmark CSVs are byte-identical to prior verified outputs.
The real browser result is `passed`, covering three available periods, ending
wealth, true logarithmic ticks/hover, drawdown, shared zoom, costs, benchmark,
legend, mobile layout and missing periods. It is preserved in
`report-browser-regression.json`; HTML/PNG/CSV remain in the actual artifact.
No plot was rendered inline in this conversation and no cross-project automatic
file-sharing capability was assumed.

## Final-code full CI checkpoint

At intermediate evidence publication, full CI37192667867 is still running at
DART Super Value integration; CPython 3.11/3.12 replay jobs and legacy CI passed.
No full-CI success is claimed until actual completed evidence replaces this
checkpoint. Workflow job limit is 45 minutes; the original-quarter command is
bounded to 840 seconds/15 minutes. Do not restart the running checks.
