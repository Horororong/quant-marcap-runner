# NO_METRICS recovery and live resume — 2026-10-04

User priority: source diagnosis/fix → failed-source reprocessing → actual backfill
resume → PIT investigation. No strategy selection, optimization or UI expansion.

## Directly confirmed start

Local clean branch `work`, HEAD `4833fb503105d810ea6e8e905d914f1ab3c28632`,
matching initially queried main. AGENTS/PROJECT_CHARTER/start/handoff/pipeline/DSL
read. PRs #29–#32 remain open, unmerged; #32 has the prior 78-cell numeric audit.
Previous-environment files/processes are **unverifiable**. No local collector
was running; that is not evidence about another machine. Local Git fetch failed
at proxy:8080; a later network-permission call was cancelled and not retried.
Connected GitHub was used, with original blob/ZIP/body SHA verification.

Index: 138,540 rows/unique receipts, 115,020 mapped rows/unique receipts;
no index duplicate receipts. Official mapped durable checkpoint: processed
11,401, pending 103,619, parsed 4F 616, parsed partial 595, NO_METRICS 8,620,
NO_DOCUMENT 1,570; current quarantined errors 0. All-compatible-state
NO_DOCUMENT count 1,572 includes two unmapped records and must not replace the
mapped count. Earlier parser success counts are excluded. These are processing
statuses, not independently certified data or actual financial-item absence.

## Cause and limited collector correction

Reproduced five v5 NO_METRICS receipts against their exact checkpoint ZIP SHA:
`20000809000052`, `20010103000052`, `20010104000076`, `20010213000010`,
`20010213000014`. Four native XMLs fail strict structure parsing; four contain
replacement characters already in the declared UTF-8 source. The complete XML
`20010213000010` still has irreversible replacement-character damage. This is
a native source-quality failure, not evidence that the public financial values
are absent. Readable original viewer routes contain the independently audited
values. Native source and viewer dcm/eleId routes and hashes are preserved.

The collector now records **SOURCE_GAP** rather than terminal NO_METRICS for
damaged/unreadable source members. Tolerant partial extractions from these
damaged sources are withheld; original historical observations remain intact.
SOURCE_GAP is quarantined instead of repeatedly downloaded, has explicit member
diagnostics, and prevents collection_complete. Existing native financial parsing
is still `legacy-v5-single-amount`; diagnostic contract is
`legacy-document-quality-v1`. No global parser bump/re-download of all 11,401
processed receipts. The source version remains the same actual OpenDART route.

This fixes misclassification and establishes a bounded archived recovery path.
It does **not** claim a generic online viewer fallback or a fully repaired PIT
collector. Existing source-backed v2 viewer adapter is reused with unchanged
period/scope/unit/BR/current-column guards; prior annual OCF, unknown units and
unsupported layouts remain withheld. No invented current OCF.

Meaningful tests include actual five broken archives, existing normal amounts,
clean absent items, actual Vitz CFS source explicitly declaring no consolidation
obligation, truncated-but-tolerantly-readable amounts, source identity damage,
resume/no-op, and missing date/correction proof. Local: existing 48 adapter and
11 independent audit tests, six source-quality and four recovery tests passed;
generated-contract check passed. Native pytest cannot execute locally because
requests/bs4/pytest are absent; exact collector integration is checked in CI.

## Actual archived reprocessing

`recovery/plan.json` restores exactly five source-proven failures as a separate
reprocessing population; no native checkpoint reset or deletion. Batches **2 →
3 → 0**, recovered staging rows **33 → 78 → 78**, requests **0**. Per-receipt
records retain old NO_METRICS state, native/source diagnostics, original hashes,
new staging rows, viewer family literal and publication limitations. All 78
rows are the previously audited population, not 78 newly selected audit samples.
Independent 46-cell recheck passes, production/checkpoint hashes unchanged.

**Production valid-data recovery 0; full PIT verification 0.** Do not report
the 78 staging amounts as investable data, 4F recovery or completed ingestion.
Existing outputs refuse overwrite; explicit resume skips published receipts.
Native ZIPs and viewer snapshots are frozen in `tests/fixtures/legacy_dart/recovery_primary`.
Original artifact 11205027337 ZIP SHA:
`b05296686ac4d155495b6f121d0f401c08acf0e4d839a2be492a8612a4d8e4fb`.

## Live backfill

Initial recent refresh run37196262929 was in progress and later completed
success; its lock is `dart-recent-refresh`, separate from legacy. Immediately
before legacy resume, repository-wide running/queued queries were empty.
Existing scheduled fast workflow job111346825667 was re-run through GitHub,
yielding **run37172051500 / attempt2 / job111425020146**, started
2026-10-04T11:21:12Z. Actual checkout/setup/gate succeeded and collector step
was directly observed in progress. Latest checkout uses main and durable
checkpoint; it does not replay the prior 2,000 receipts. No new workflow,
schedule, daemon or local collector was started.

Existing lock `super-value-fast-pit-backfill`, cancel-in-progress=false; max
2,000 receipts, workers3, 2,500 request budget, 3,300s submission deadline,
0.5s shared request interval, checkpoint25, max error attempts3; provider 020
stops collection. This run uses currently deployed main v5, **not this
unmerged source-quality patch**. Its NO_METRICS results remain unaudited gaps.
Actual completion/artifact/before-after counts belong in `live-backfill.json`
when available; do not infer completed counts from a successful dispatch.

## PIT investigation of the existing 78 cells

`pit-items.csv` joins all 78 original amounts to five receipts and archived
public viewer family options. Displayed public dates are independently visible:
United 2000-08-09; Daewoo 2001-01-03; Peerless 2001-01-04;
Ildong/Daegu 2001-02-13. They are not derived from receipt IDs or fiscal ends.
Dates are corroborated for **78 items / 5 receipts**, but complete PIT is **0**.

Each archived family currently lists one receipt. This does not prove absence
of historical amendments or that its selected dcmNo was available at original
publication. No historical original/corrected value pair or publication clock
is preserved, so changed amounts and correction-before-signal misuse cannot be
certified. Current v5 production contains no values for these five receipts;
staging has never been promoted. No strategy was executed in this task.

Current modern provider loads `full_history` and gates filing_date <= normalized
signal day; next-close execution requires lag_sessions>=1. Legacy staging is
not connected to that provider. Date-only viewer evidence cannot prove
before-close signal availability. No arbitrary lag or next-day PIT date is
invented. Full correction chains, historical version hashes, actual publication
timing and period/mapping reconciliation remain prerequisites.

## Runtime and scope

No old installed runtime was initially found. Subsequently restored the exact
original 311,922,550-byte report ZIP from all 13 existing artifact segments;
every segment SHA/length, full original SHA and ZIP CRC were checked. Original
bootstrap installed offline into `/workspace/scratch/quant-original-kit/runtime`;
its isolated Python subprocess `sandbox_runtime.py verify` returned status=ok.
Kit26e4ec02e569, source822c435, CPython3.12.14; pinned packages include
pandas3.0.6/numpy2.4.6/pyarrow25.0.1/exchange-calendars4.13.2. Actual
`bootstrap-result.json`/`kit-verify.json` retain all contracts/packages/coverage.
No engine import/backtest or internet kit-package bypass was used. This collector-only change is excluded from the sandbox kit source
profile; a strategy runtime integrity/coverage check remains required before
future strategy execution. Engine/registry/report calculations were not edited.
CI separately checks pinned clean kit replay; neither local verify nor CI is
investment validation. Full-data numeric quality, PIT and strategy
cost/OOS/robustness/operability validation remain incomplete independently.

## Reproduce/resume safely

From this source checkout, use fresh directories (commands invoke development
collectors, not a backtest runtime):

```bash
timeout -k 5s 30s python scripts/test_legacy_document_quality.py
timeout -k 5s 30s python scripts/test_legacy_no_metrics_recovery.py
timeout -k 5s 30s python scripts/recover_legacy_no_metrics.py --output-dir /tmp/quant-recovery-new --max-receipts 2
timeout -k 5s 30s python scripts/recover_legacy_no_metrics.py --output-dir /tmp/quant-recovery-new --max-receipts 3 --resume
python scripts/export_strategy_dsl_contract.py --check
```

For online resume, inspect active/queued Actions first, then use the existing
main `backfill-super-value-fast.yml` manual entry or legacy manual entry under
the same lock. From an authenticated CLI: `gh workflow run
backfill-super-value-fast.yml --repo Horororong/quant-marcap-runner --ref main`.
Do not run this while attempt2 is active; the exact actual current status is in
the final live evidence. Do not reset states, force-push or replace latest main
datasets with this local initial snapshot. Review source patch with complete CI
before deployment; then explicitly plan remaining NO_METRICS source diagnosis
and online fallback separately from PIT promotion.

## Source-code publication and native CI

Remote source commit `1af7b8952d1d346129b2eae1ccde67f105ca1eae`, draft
[PR #33](https://github.com/Horororong/quant-marcap-runner/pull/33), stacked on
#32. Latest main `06b90b5` recent-data blobs were preserved exactly through a
second parent and three data-blob overlays, not reconstructed. Local commits
`bc76477`/`99ebbbe` include SHA-verified prior source rehydration; remote review
contains the same new source blobs on prior #32 ancestry. Native validator
[37199649781](https://github.com/Horororong/quant-marcap-runner/actions/runs/37199649781)
completed success. Actual log `native-ci.log` shows seven new collector tests,
six source-quality tests, four recovery tests, existing parser/resume suites,
48 adapter and 11 independent audit guards; all pass. Historical independent
72-cell failures and 46-cell/78-population evidence remain unchanged. Full
CI37199649791 remains pending until its actual completion evidence is captured.

## Completed live bounded batch (direct final evidence)

Run37172051500 attempt2/job111425020146 completed success at 11:48:32 UTC.
Actual collection report: selected/completed/requests2000; BATCH_COMPLETE;
rate_limited=false; 25-receipt checkpoint logs through2000. Artifact11302815319
was downloaded and full ZIP SHA273fbd2b45953157cb2828aa480834fad795d1af5013f8035b27af011051f84a
verified. Data commit778b02b9b3b7373ece88fd4bb61453308bcd70c3 is on main.

Mapped pending103619→101619; processed11401→13401; 4F616→1523 (+907);
partial595→1341 (+746); NO_METRICS8620→8943 (+323); NO_DOCUMENT1570→1594
(+24); quarantined errors0→0. Technical parsed receipt recovery1653 is not
independent numeric/PIT certification. These counts come from the actual
artifact/current status and execution report, not an assumed background run.
Overall collection/quality remains false. No second batch was launched.

New normalized2001/2002 blobs and state are confirmed in the data commit, but
the current connector returns empty content for >1MiB files and rejects binary
GitHub Fetch. Independent literal-preservation/new-row re-audit of those remote
blobs is therefore not completed; see live-durability-check.json. Local original
state/index/all normalized hashes remain unchanged. Latest remote data was not
replaced by the initial local snapshot. The resumed run used deployed v5; this
review-only SOURCE_GAP patch has not been merged/deployed.
