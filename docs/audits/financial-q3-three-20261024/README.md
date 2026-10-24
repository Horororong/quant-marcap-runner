# Fixed Q3 collection through the existing GitHub route — RESEARCH_ONLY

## Existing authenticated source path

Repository Horororong/quant-marcap-runner, source workflow
`.github/workflows/backfill-dart-legacy-2000-2014.yml`, main branch only,
first GitHub run attempt only. The source step injects
`DART_API_KEY: ${{ secrets.DART_API_KEY }}` and
`GH_TOKEN: ${{ github.token }}`. The key is never read back through the Secrets
API, printed, exported to the workspace, or copied into a backup. The default
workflow token preserves state/originals in this repository with contents:write.
No new authentication secret or permission to read secret values is requested.

Actual successful run40024818567:
https://github.com/Horororong/quant-marcap-runner/actions/runs/40024818567
dispatch/checkoutmain3b505b5fb299e4d162a9676d9f4e757d4415fc69,
resultmain299e97b47a06cadcf2414c07f9dac606a428e233. Original fixed-kit step,
collector and artifact preservation succeeded. The saved source evidence records
21DARTHTTP/0retry/21originals/273candidates/0duplicates/251.381 source seconds.
This establishes actual DART access for that GitHub runner execution; it is not
a new credential-validity or external-quota probe today. No source HTTP or daily
gate was repeated during this preparation. No token expiry is inferred.

The current workspace is separate: environment revision106/current/enforced
has onlyGH_BACKUP_TOKEN and permitsapi.github.com/uploads.github.com, without
a local DART binding oropendart.fss.or.kr allowance. This proposal uses the
existing Actions authentication; workspace DART configuration is unnecessary.

The older `backfill-dart-legacy-quarterly.yml` is unsuitable for this approval:
300-company/800-document defaults, independent concurrency,180-minute job and
Internet pip installation. It was inspected, not executed or modified.

## Approval boundaries and exact operating base

Prepared on a NEW sparse code-only checkout/branch
`ops/q3-three-github-20261024`, parent **299e97b47a06cadcf2414c07f9dac606a428e233**.
This is a minimal operating delta, not a merge of the private research branch.
Existing six approved source-owner bytes and both original/FY supplemental
configurations are unchanged. Existing state/data files are not part of the code
delta. The old3-execution history, FY fixed41 order and checkpoint are preserved.

Existing collection authorization remains:

|Budget|Approved cap|Current unused allocation|
|---|---|---|
|FY supplemental remaining|1execution/20documents/40DARTHTTP including retry/600source seconds|All remaining20; previous21actual but42HTTP reserved; no reservation freed|
|Q3 separate approval|1execution/3named reports plus official lists/12DARTHTTP including all lists and retries/600source seconds|0executions and0HTTP used|

10/24KST daily opportunity was already used by run40024818567. The owner's latest
instruction gives Q3 priority at the next10/25KST window, replacing the earlier
FY-first preference without changing the shared daily cap. After Q3 on10/25,
FY cannot also run that day. Its original expiry10/25KST23:59:59 is preserved:
the first later daily window10/26 is outside that FY authorization window.
The20documents/oneexecution/40HTTP remain unspent, with checkpoint2116/next2117,
not silently cancelled, extended, or marked complete. A further finite-window
authorization would be needed to execute FY after expiry; this does not increase
or reset its budget. A clean FY expiry does not cancel the independent Q3
approval; an active or failed source lease still blocks it.
No automation is newly armed. Existing cron does not supply the Q3 or FY
supplemental approval parameters. Saving a dispatch command is not scheduling it.

The owner has explicitly approved d9b097a2ae25a33b4a16d3cfd0062a8853693892,
its12files/133940bytes, fixed-kit CI, checked minimal main merge and PUBLIC
preservation of the named originals and official lists. That exact code is now
published and [remoteCI40072566997](https://github.com/Horororong/quant-marcap-runner/actions/runs/40072566997)
succeeded at the exact checkout. The directly requested Q3-first scheduling and
per-request provenance changes are a separately recorded follow-up; they do not
alter targets, budgets, expiry, source hashes, or financial/PIT gates.
The code requires a second explicit dispatch marker
`q3-three-public-preservation-20261024` in addition to the already approved
collection marker `q3-three-company-20261024`, before a lease or DART call.
There is no collection-budget increase or financial/PIT promotion to approve.

## Fixed targets and preservation scope

|Company|Corp|Stock hint|Expected receipt|Required strategy fields|
|---|---|---|---|---|
|사조산업|00124799|007160|20091116000562|Jan1–Sep30FY2009 cumulative revenue/net_income/OCF|
|가온전선|00104768|000500|20091116000251|Same three cumulative flows|
|고려신용정보|00336297|049720|20091113001077|Same three cumulative flows|

Official list API `/api/list.json`: each fixed company,20090101..20100430,
pblntf_tyA,last_reprt_atN,page_count100,at most2pages/company. Every list
request counts toward12. Exact target receipt/date/issuer/report kind,
complete pagination/counts and no duplicate receipts are required. Original and
same-period correction references are preserved; this alone does not close the
PIT/version chain or certify an actual two-version comparison.

Only the three proved targets use `/api/document.xml`. No fourth report,
corp-master request, other period, financial API or automatic retry is allowed.
Existing exact cache+parameter/hash proofs are reused before HTTP. API020,
authentication/quota/service/CRC/identity/hash/publication failure stops the run;
unused calls cannot be consumed through another execution.

The new PUBLIC source scope, if approved, is those3ZIP originals, at most6
official list pages and associated request/hash/provenance/state manifests.
Each document's transport pack is capped12MiB compressed; at most3document
packs plus1failure-metadata pack,48MiB compressed total maximum. Original
ZIPs/members are SHA256/CRC checked; per-file SHA256/size and compressed-pack
SHA256 plus Git blob SHA are recorded before ref publication. No candidates or
operating financial values are published by this collector. Actual source-byte
hashes can only be generated after the authorized source execution; they are
not invented in the proposed code-transfer manifest.

The same GitHub blob/Contents API provides workspace download without Actions
artifact redirects or a DART key. Q3 raw data is not duplicated into the generic
Actions artifact: only safe state/receipt/runtime files are uploaded there.
Before any public pack, both raw files and decompressed ZIP members are checked
for the actual in-process DART/GitHub credential values; a hit refuses transfer.
Request URLs and keys never enter persisted request parameters or logs.

## Durability, budgets and failure behavior

Q3 uses a separate single-use remote ledger
`data/status/dart_q3_three_v1.json`. It consumes1execution and reserves12HTTP
atomically before source HTTP. Original and FY supplemental bytes/history stay
unchanged and are bound as CAS inputs. Both original/FY entrypoints also check
the Q3 day/lease. The existing concurrency group and cancel-in-progress:false
are preserved. The Q3 code checks current active source workflows, source hashes,
original first-review evidence, FY order/budget/history/phase and current KST.
Switching machines cannot create another Q3 execution. The prior local direct
collector has been disabled before key access/lease/HTTP; its zero-use budget is
preserved, not reset or spent. No local execution fallback is authorized here.

Each HTTP intent is persisted BEFORE transport, with an authentication-free
source URL, public request parameters, and UTC intent time. The transport return
records its UTC response-received time; this is collection time, not historic
publication time. Credentials stay separate, and authentication parameters are
rejected before persistence. Responses confirm which intents
actually returned; a killed in-flight request stays conservatively charged and
its outcome is not invented. Each validated original is published and checkpointed
in the SAME remote commit before the next source request. Extra CAS guards bind
the Q3 state/config/code/workflow and FY supplemental state/config, retaining the
original coordinator's source/input guards and non-force ref update.

The source coordinator has a hard600-second deadline from entry, including GitHub
preflight and preservation. New source calls stop with at least120seconds left
for checkpoint/finalization. Normal deadline stops are separate from source
failure. A hard kill or uncertain final commit leaves the durable lease held.
Completed originals can be reopened offline; the consumed execution is not
automatically resumed with more HTTP. HTTPunused is distinct from executable
remaining budget: after this one execution, further execution/call availability
is0 even if fewer than12 calls were used. GitHub control/preservation calls and
kit download are not DART API calls; no source call is excluded from its12 cap.

## Local verification and prepared remote validation

Original fixed kit26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd
verified before calculations. DedicatedisolatedPython used, no Internetpip.
New29Q3 boundary tests plus existing83collection/lease/interruption tests pass.
Actual offline SIGKILL test preserves1lease/4charged requests/1durable original,
then reopens that original with SHA/CRC and rejects a second HTTP execution.
Other cases cover12-call ceiling, deadline, missing public approval, wrong
scope/period/date/issuer/pagination, request intent persistence, failed raw
publication, credential echo including compressed members, read-only validation,
cache reuse, original/FY byte preservation and blob/file recovery tampering.
All source/HTTP data in these tests are explicitly synthetic fixtures, not new
real DART documents or financial/PIT certification. One initial83-test run lacked
the unchanged root update_dart_financials.py in the sparse checkout; adding that
exact original file resolved the environment error without changing its tests.

The same source workflow adds `validate_q3_only:true`: a separate contents:read
job checks out the exact dispatchSHA, restores/verifies the fixed kit, then runs
these112tests without a DART secret, lease or source request. No separate CI index
or driver publication is required; validation code is inside the workflow file
in this manifest. Originald9 remote validation succeeded with108tests. The
Q3-priority/provenance follow-up has112local passes and needs its own exact-SHA
remote validation; the earlier run is not evidence for later code. Publish
with a [skip ci] commit message to avoid the unrelated automatic Internetpip
workflow; run the prepared fixed-kit validation explicitly. Required protection
checks must pass before PR merge; no admin/force bypass is authorized.

## Commands after the corresponding gates and publication approval

Do not invoke the earlier FY-first helper before pending Q3. The current main
guard blocks FY until Q3 has used its approved execution, without reserving FY
calls. FY remains at2116/next2117,20pending. Its preserved10/25expiry then needs
a later finite window before FY can execute; never silently extend or reset it.

After public operating-code approval and branch publication, validate exact
branch code without source HTTP:

```bash
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref ops/q3-three-github-20261024 -f validate_q3_only=true
```

After requiredCI/protection checks and approved minimal PR merge, on a distinct
allowed KST source day only:

```bash
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f q3_approval=q3-three-company-20261024 -f q3_public_preservation=q3-three-public-preservation-20261024
```

After actual preservation, recover at its exact result commit into a NEW folder:

```bash
<FIXED_PYTHON> -I scripts/recover_financial_q3_sources.py --run-id <ACTUAL_RUN_ID> --revision <FULL_PRESERVATION_COMMIT> --output <NEW_Q3_SOURCE_DIRECTORY>
```

The reader verifies outer Git blob and compressedSHA, per-file manifests, ZIPCRC/
member hashes, official page/receipt bindings, and byte-identical repeated metadata.
Unknown paths, changed duplicates and an existing destination are refused. Then
the existing research9.4 source-bound extractor can operate locally with its
immutable2565-ID baseline and six research source pins; no source re-download.
That older immutable ID baseline is for duplicate/amount protection, not a reason
to revert the latest1258PASS/24UV/1283unreviewed decisions or any laterFY20delta.
Financial source controls must independently review current JanSep cumulative
columns, units/signs/definitions and matching FY scope before a provider query.
Publication time, corrections, historical company/security and session evidence
remain independent requirements; never assume pre-open from a date-only filing.

## Actual objective progress in this preparation

Real HTTP/new originals/new candidates/new semanticPASS/newPIT/new strict provider
values/new executable strategy periods: **all0**. Latest candidate ledger remains
2565=1258PASS+24reviewedUV+1283unreviewed. Existing SajoFY4 canary is unchanged.
This preparation removes the need for workspace DART authentication but does not
count authentication/commits/tests as usable data. The next direct data increase
is up to9 Q3 cumulative flow fields for these3 companies, then their actual
field-bound review/PIT/provider checks. The original1946-security population and
whole-strategy readiness gates are not reduced to these three companies.
Financial publicationHOLD,RESEARCH_ONLY,PIT/source/CA/held-return gates remain.

## Owner-approved ordered window renewal

The 2026-10-24 owner approval authorizes Q3 from 2026-10-25 00:00 KST, then the remaining 20 FY documents from 2026-10-26 00:00 KST through 23:59:59 KST. No automatic scheduling is added. The immutable original finite41 config and its budget hash remain unchanged; `config/financial_q3_fy_window_v1.json` separately binds the renewal to that exact approval and frozen receipt order. The runtime requires the original single completed 21-document attempt, preserves its 42 reserved HTTP and all three original executions, and permits only the remaining one 20-document/40-HTTP/600-second FY execution. Both modes share the persisted KST-day/failure/lease checks. A successful Q3 run on the 25th blocks FY that day; the same durable Q3 ledger permits FY on the 26th. Unknown, edited or expired renewal evidence is rejected. A failed Q3 remains held; dates do not reset any lease or budget.

Offline tests cover Q3-before-window/no-network, full synthetic Q3 collection plus next-day FY admission, same-day denial, exact expiry, altered budget/binding rejection, original-ledger immutability, source recovery, and interruption/restart. Synthetic documents do not certify real financial or PIT data. Existing source-owner pins, financial HOLD, PIT 0/6 and runtime kit remain unchanged.

### Manual resume only

After confirming the live shared ledger/day/budget and no active collector, use the existing workflow on main with the following inputs. Authentication remains the existing GitHub environment binding; DART_API_KEY is injected by Actions only. No task has been scheduled by these commands.

Q3, not before 2026-10-25 00:00 KST:
```sh
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f q3_approval=q3-three-company-20261024 -f q3_public_preservation=q3-three-public-preservation-20261024 -f batch_documents=2
```
FY remaining 20, after successful Q3 and not before 2026-10-26 00:00 KST, expires 2026-10-26 23:59:59 KST:
```sh
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f supplemental_approval=finite41-20261023 -f batch_documents=20
```
Each POST is issued once only after live gating; an uncertain dispatch is reconciled by run ID rather than repeated. A green workflow with zero requests/new originals is not a backfill success. Source processing checkpoint remains 20100331002116; next FY receipt is 20100331002117. Q3 uses its own receipt ledger and must not move that FY checkpoint.
