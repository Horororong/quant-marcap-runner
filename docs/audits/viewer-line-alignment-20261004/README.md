# Viewer terminal per-share note alignment — 2026-10-04

## Scope and source decision

This follow-up to draft PR #30 fixes only the five current-period, known-unit
cells withheld by v1's BR-line guard. The complete original bodies and frozen
manual 49-cell golden expectations remain unchanged. Selection and line-by-line
source inspection were recorded in `SOURCE_REVIEW_BEFORE_CHANGE.json` before
adapter v2 was implemented; no new strategy or performance was used to select
samples. This is a subset of the original eight-company, 72-item audit, not five
new independent samples or a certification of all data.

| Primary company / code / receipt | OFS source flow period | Item | Source token / KRW value | Original table / row / cell / BR line |
|---|---|---|---|---|
| 한국유나이티드 / 033270 / 20000809000052 | 2000-04-01–2000-06-30, Q1 | revenue | 8,023,251,729 / 8023251729 | 5 / 1 / 1 / 1 |
| same | same | net_income | 625,811,634 / 625811634 | 5 / 1 / 1 / 88 |
| 피어리스 / 002130 / 20010104000076 | 2000-01-01–2000-09-30, Q3 | revenue | 19,891,704,755 / 19891704755 | 5 / 1 / 1 / 0 |
| same | same | net_income | 6,516,196,541 / -6516196541 (explicit loss account) | 5 / 1 / 1 / 94 |
| 대우중공업 / 000200 / 20010103000052 | 2000-01-01–2000-09-30, Q3 | net_income | (-)3,423,467,689,539 / -3423467689539 | 6 / 54 / 2 / 0 |

The five-cell audit JSON/CSV also preserves corp identifiers, original stored
values (all five absent), index-recorded receipt dates (2000-08-09, 2001-01-03,
2001-01-04) and correction indicators. Those receipt-day fields are explicitly
marked unverified as actual legal publication times; correction chains are not
reviewed. No synthetic publication lag or PIT date is added.

Official viewer URLs, body SHA, literal-cell SHA/spans and every original BR
line are in the source review. Unit is explicitly 원 for all five. Actual filing
availability dates and correction chains remain unverified; no date is inferred
from receipt identifiers. `strategy_usable_date=null`, `pit_ready=false` and
`production_ready=false` remain mandatory. The source requests are explicit
calendar flow dates, not future-derived fiscal labels from the historical index.

United's financial prefix has 89 BR lines, ending at net income line 88; account
cell has 109 lines, current amount 95, prior amounts 94/89. Everything after
that financial prefix in numeric cells is blank. The account tail is solely
explicit BR-wrapped 주당경상이익/주당순이익 notes and blank lines.
Peerless's financial prefix has 95 lines, ending at net loss line 94; account
100/current 101/prior 95 lines. Extra lines likewise contain explicit per-share
notes in the account and blanks in amounts. Daewoo has one main financial line
and a complete basic per-share loss note: account 2 lines, detail columns 3
empty lines, subtotal columns 1 line. Its exact 당분기순손실 alias is supported
only in the viewer adapter; the native collector's alias contract is unchanged.

## Fail-closed implementation

Adapter version is `dart-viewer-period-scope-unit-column-v2`. An unequal-BR IS
row is allowed only when its account financial prefix ends in net income and
its terminal non-financial text consists entirely of strictly parsed, complete
parenthetical per-share notes. Every nonempty numeric column must end at the
same original prefix index, contain complete finite numeric tokens and have no
amount on a blank account line. Entirely empty detail columns remain empty.
Interior BRs are never deleted, inserted, shifted or padded. Extra amount-tail
values, unknown note text, malformed note numbers, shifted prior/current cells,
missing current amounts and ambiguous detail/subtotal values fail closed.
All original line indices/spans and a line-alignment proof are retained.

Period/scope/unit/current-column/duplicate/sign guards are unchanged. Prior
columns cannot supply a missing current value. Native parser stays
`legacy-v5-single-amount`; production collectors, source files, native checkpoints,
registry, DSL capabilities and canonical performance code are untouched.
This offline adapter remains a staging/audit tool, not a production PIT provider.
No execution-kit rebuild is required: the kit code closure excludes this source
adapter; the existing frozen kit was independently verified without edits.

## Actual local evidence

- 48 regressions passed (33 existing plus 15 new failure/source boundary tests).
- Original 12 bodies / 49 golden cells: **22 MATCH**, 22 prior-period withheld,
  5 unknown-unit withheld, 0 accepted mismatch or guard failure. Previous v1
  evidence remains in its separate audit directory.
- All 63 previous staging rows retain identical values, tokens, periods, units
  and source coordinates. V2 emits 78 rows; 22 have independent manual matching,
  56 were outside the frozen 49-cell golden (including ten newly exposed
  non-golden rows); the separate ten-item audit below now leaves **46 unaudited**.
- Independent original 72-item audit recheck against local baseline remains
  49 stored-missing / 18 period / 3 amount / 2 semantic findings. Known v4 records
  are preserved; no historical stored value is silently corrected or promoted.
- Generated DSL contract check, compile check, whitespace check and immutable
  dedicated-Python kit verify passed. Full final-code remote CI succeeded at code commit
  `1895508aa09d014558e895715ffaaf4cfbe69322`; exact completion evidence is below.

## Live collection and backtest boundary

Initial live main was `4833fb503105d810ea6e8e905d914f1ab3c28632`; PR #30 was open,
draft and unmerged at `b8e79a74f46234a509aebf7d080e6492d96103fa`. Its exact code CI
37184664330 and legacy CI37184664255 were successful. The initial GitHub running
and queued lists were empty. The earlier execution environment is unobservable;
no new collector was started. Shared-lock scheduled collection and all native
checkpoints are preserved. Last confirmed remote legacy mapped checkpoint was
11,401 processed / 103,619 pending / 616 PARSED_4F; this source patch does not
change those figures or demonstrate collection/quality completion.

Data preparation, full independent quality verification and actual cost/OOS/
robustness strategy validation remain incomplete. No new requested research NAV
or performance calculation was run. Prior verified software report path is the
2019–2020 price/size example; quarter-factor 2020 readiness is only preflight.
2000/latest and 2021/latest kit requests still have data gaps; annual PER/ROE/TTM
cannot be replaced with quarterly proxies. Prior-period annual OCF/CFS, unknown
units, filing availability/corrections, corporate-action dividends and total-
return benchmarks remain unresolved. See the preceding audit for full coverage.

## Reproduce safely

Run from the normal source checkout, not by modifying the installed frozen kit.
Choose a fresh output directory for each version; existing v1 evidence stays intact.

```bash
timeout -k 5s 30s python scripts/test_legacy_viewer_source.py
timeout -k 5s 30s python scripts/replay_legacy_viewer_sources.py --output-dir /tmp/quant-viewer-v2-replay-new
timeout -k 5s 60s python scripts/recheck_legacy_primary_audit.py --output-dir /tmp/quant-primary-72-v2-new
timeout -k 5s 60s python scripts/export_strategy_dsl_contract.py --check
```

Do not reset collection checkpoints, dispatch duplicate collection or promote
staging rows without actual availability/correction and source-quality evidence.
Next source-quality unit: independently audit the remaining 46 staging rows
using a pre-recorded sample plan and original source cells. Do not promote any
of the 32 matched rows without verified availability and correction chains.

## Additional independent ten-item source audit

While mandatory CI was running, all ten newly exposed non-golden fields were
selected without a performance/value filter in `ADDITIONAL_SAMPLE_PLAN.json`.
Manual literal account/token expectations came from the original complete BR
lines inspected before the adapter change, not from computing expectations
with the new parser. The ten fields are amortization, cost of sales, depreciation,
gross profit and operating income for United and Peerless. They are distinct
from the existing 72 original samples (verified receipt/metric/scope disjointness).

`verify_additional_cells.py` imports no collector or adapter. It checks original
gzip/body/literal-cell SHA, slices pre-recorded raw cells, decodes HTML and splits
original BR tokens independently, preserving blanks, then compares exact manual
accounts/tokens and Decimal values with persisted staging. Original source
period/scope/unit are the same already inspected IS headers used in the fixed
audit. Ten of ten match, including Peerless's negative operating income.
Production stored values for these ten additional fields were **not rechecked**;
the table labels them as unchecked rather than missing/correct. Filing/correction
evidence remains unverified and usable dates remain null.

The original 72-item stored-data recheck remains unchanged; these are ten additional
primary-to-staging comparisons, not an 82-item production-data certification.
Across viewer staging, 22 original golden matches plus 10 supplementary matches
make **32 independently matched rows of 78**; **46 remain unaudited**. The frozen
49-cell replay JSON correctly retains its original-only count of 22 matches /
56 outside that golden, and is byte-identical to the current CI replay.

```bash
timeout -k 5s 30s python docs/audits/viewer-line-alignment-20261004/verify_additional_cells.py --output-dir /tmp/quant-viewer-extra10-new
```

## Final completion checkpoint

- Draft [PR #31](https://github.com/Horororong/quant-marcap-runner/pull/31), stacked
  on PR #30, remains unmerged. Tested remote code commit:
  `1895508aa09d014558e895715ffaaf4cfbe69322` (local corresponding source commit
  `8849104`). Final evidence-only commits preserve the tested code blobs.
- [Full Strategy DSL CI37187021329](https://github.com/Horororong/quant-marcap-runner/actions/runs/37187021329)
  succeeded, updated **2026-10-04 08:12:15 UTC**. Test and clean offline CP311/CP312
  jobs succeeded; the unrelated verified-kit download job was legitimately skipped.
  Legacy CI37187021335 also succeeded. Native parser, source guard, generated
  contracts, real DART/KRX/top-N/decile/checked CLI, CURRENT and browser checks
  passed without changing the existing workflow contracts.
- Actual remote 72-item audit artifact **11297795579** was downloaded and SHA
  checked; findings remain 49 missing/18 period/3 amount/2 semantic. Actual remote
  source replay artifact **11297194132** matches all four local replay files byte
  for byte. Exact input/body hashes and CI metadata are preserved in this directory.
- Actual report artifact **11297700610** passed the existing browser interaction
  checks. Metrics/NAV/benchmark CSV SHA match the preceding verified CI exactly.
  The existing report example is `status=ok, nav_ready=true, report_ready=true`,
  but `report_complete=false`: configured ready periods are reported, unavailable
  default/book/long-history periods are not certified. This remains software
  regression evidence, not actual investment cost/OOS/robustness validation.
- All **418 data blobs and 5 historical checkpoint documents** retain their
  original remote SHA. Main remained `4833fb503105d810ea6e8e905d914f1ab3c28632`;
  latest GitHub running/queued lists were empty, local collector scan empty, and
  the earlier execution environment unobservable. No collector/reset/dispatch
  was started. Coverage was fetched directly from that exact main: mapped
  115,020 / processed 11,401 / pending 103,619 / reported PARSED_4F 616.
- Supplementary `additional-10-complete-records/` is the latest ten-item audit
  table with complete identifier/period/unknown-publication metadata. The earlier
  `additional-10-audit/` first pass is preserved. Both have ten matches. No
  production data value was checked/promoted for these ten supplementary fields.
- This final checkpoint supersedes the initial pending-CI and ten-row next-task
  lines in `HANDOFF_CURRENT.md`, which links here. The ten-row source review is
  now complete; next is a pre-recorded independent audit of the remaining 46
  staging rows. Availability/correction and current OCF gaps still block PIT
  promotion even for the 32 source-matched rows.

| Project area | Actual state after this task |
|---|---|
| Report function | Existing configured-window software regression passed; no new UI added |
| Data preparation | Incomplete; legacy collection/PIT/current OCF and long-history gaps remain |
| Independent quality | Original 72-item recheck plus ten additional primary-to-staging matches; full data certification incomplete |
| Actual strategy validation | Cost/OOS/robustness/operational validation incomplete; no new requested research NAV run |
