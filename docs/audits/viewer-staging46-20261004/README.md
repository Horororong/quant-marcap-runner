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
  from these matches.
- R008/R026/R037 are the printed gross named bonds lines, before separately
  printed discounts; Daegu convertible bonds are also separate. These lines do
  not certify net carrying value or a complete definition of total debt.
- R034/R042/R044 are depreciation/amortization components under SG&A, not
  company-wide D&A or an EBITDA proxy. The previous ten-item supplement also
  contains four such SG&A components. Across all 78 staging cells, **10 require
  measurement qualifications**; numeric matching does not authorize new factors.
- Local older-baseline production lookup finds all 46 selected items absent.
  This is separate from matching staged values. The remote checkout will be
  audited through the existing legacy CI and preserved as its own evidence.
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
The diagnostic log is preserved, not mistaken for a production discrepancy.

The existing legacy validation workflow runs the fixed audit against its actual
checkout and uploads a separate `legacy-staging-46-audit` artifact. No collection
workflow/lock/schedule was added or changed. Full Strategy DSL CI is triggered by
the handoff update; its actual result remains pending at initial publication.

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
