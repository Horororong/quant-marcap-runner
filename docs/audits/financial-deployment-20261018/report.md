# Bounded financial rollout — candidate, not yet operating deployment

Base main: ffb3b5191dbea73e58c698154184515f8ff49631.
Research source: 0d3669bd45a77d7d7cc03cabcac1fad7963461ff.
This branch contains only financial collection/parser, durability, observability,
scoped CI and independent evidence. No strategy/corporate-action engine is merged.

## New independent primary-source audit

Seed: financial-operational-deploy-independent-20261018-v1. Exclude82 receipts
and77 corporations covering prior22 and original60. Freeze metadata/list before
opening originals/amounts; freeze52 literal cell controls before production output.
Source freeze CI39170886054 succeeded; controls commit1e808baa6d5c338ece84db758bf05cdce6a175e1.
The first attempt39170733793 exited1 before value review because a full artifact
also embeds audit-subset/effective-state.csv. The corrected selector chooses the
unique shallowest full-batch checkpoint; no outcome-based sample replacement.

Twelve distinct new companies,2007/2009, FY/H1/Q3,8 prior full and4 partial.
Industries represented in original bodies include shipping, financial services,
security services, electronics/materials, automotive parts and consumer products.
These are source descriptions, not certified historical industry-master codes.
Formats are native DART XML4.x and1.0, monetary units 원/천원/백만원, positive,
actual negative, quarter/YTD columns, OFS and an explicit separate CFS attachment.

|Sample|Receipt|Original issuer/index label distinction|Amount P/F/U|
|---|---|---|---|
|D01|20070814000143|동북아4호선박투자회사|4/0/0|
|D02|20070814000196|이녹스|4/0/0|
|D03|20070814001171|에스원|3/0/1|
|D04|20071108000069|아구스|4/0/0|
|D05|20070928000284|에이치케이상호저축은행 / current index 애큐온저축은행|3/0/1|
|D06|20070928000036|네오팜|4/0/0|
|D07|20090928000240|아시아퍼시픽12호선박투자회사, OFS plus separately tested CFS|4/0/4|
|D08|20090814002164|하이드로젠파워 / index 삼보오토|4/0/0|
|D09|20090814001843|카엘 / index 젬백스|4/0/0|
|D10|20090814002061|한일이화 / index 서연|4/0/0|
|D11|20090814002153|에이스일렉트로닉스|4/0/0|
|D12|20090814001919|씨앤에스테크놀로지 / index 아이에이|4/0/0|

Amounts46PASS/0FAIL/6UNVERIFIED; period46/0/6; exact originally frozen source
coordinates44/0/8. No rounding tolerance. D03 BS current-column label cannot be
proved by the current grammar; D05 plain 자본 subtotal is not a registered exact
account; four D07 CFS controls are unextracted. They remain missing, never0/PASS.
Two profit values match but were extracted from primary CF reconciliations rather
than the frozen IS coordinates; their coordinate verdict stays UNVERIFIED.
This is not a population error-rate estimate or complete independent certification.

D07 attached CFS auditor date2009-10-26 is later than receipt2009-09-28. The raw
archive's later attachment cannot establish September availability. Other cover
dates are original submission dates only, not proof of official release time.
All12 historical identity, complete amendment-chain and publication/PIT verdicts
remain UNVERIFIED. Source labels retain original issuer spellings separately from
current index labels. No future-dated attachment is admitted to investment input.

Original22 remain regression/recovery candidates, NOT automatically reprocessed
operating records. Original foreign-currency8 stay UNVERIFIED. Expected protected
controls518 and64 overlap; never add them as582 unique observations.

## Collection and financial quality are separate

The rollout selects only never-classified mapped receipts, excluding every older
state/version and historical ERROR quarantine. A parser upgrade cannot requeue
the old population. `collection/` records source durability/hash independently
of `quality/` records parser/version/rejection/UNVERIFIED financial status.
Existing v5 normalized/state/quarantine files are not rewritten. Results are held
as candidates. No full-source-chain or investment certification is inferred.

Initial predeployment configuration: CANARY_ONCE,2 documents (hard ceiling100); schedules cannot collect;
manual entry requires explicit bounded_verification. Both old legacy entry points
share the existing concurrency lock. No modern collection starts after a pause.
No automatic candidate publication and no fallback to v5 or2000 documents.

## Timeout evidence and prevention

Run39153257788 failed its collection step after75 minutes; last explicit log had
900 persisted, later910 rows were committed in ffb3b519. No thread/native stack was
preserved, so the exact previous hang cause remains UNVERIFIED. A read timeout is
not a whole-document deadline; ThreadPoolExecutor shutdown can wait for workers.

New transport uses the original kit plus standard library (no requests install):
connect10s, socket-read15s, response-wall35s,32MiB response bound; at most2 transient
connection attempts, with one2s backoff. Service800 and transient HTTP stop the
batch without permanent quarantine. No URLs, keys or arbitrary response text in
logs. Exact explicit service XML is preserved after checking for credentials.

Each common-collector document executes in a subprocess with90s wall budget;
whole run budget600s.15s heartbeats retain receipt, stage, elapsed time and last
durable checkpoint. Timeout/signals terminate then kill bounded workers, retain
pending receipts and stage artifacts, exit nonzero and keep publication HELD.
Checkpoint success requires original-file SHA equality and durable result bytes.

## Validation and CI boundaries

Actual fixed-kit financial/rollout tests plus service/phase/source tests execute
in financial-deployment.yml. Candidate files are overlaid onto the immutable
research audit checkout only in CI temporary storage; its original controls,
518/64,60 sources, and88 audit controls are not replaced. Audit CSV/summary bytes
must match checked evidence. New12 audit remains independent of production parser.

The old broad Strategy DSL workflow installs Internet dependencies absent from
the immutable kit. For this explicitly scoped financial branch/commit marker,
it does NOT run that installer. Its skipped jobs are NOT counted as PASS. The
dedicated financial CI runs actual parser, transport, source audit, protection and
DSL contract checks. Full unrelated engine/pytest dependency coverage is UNVERIFIED;
no engine behavior is changed or newly certified by this deployment.

## Reproduction and rollback

Use only verified kit .venv/bin/python -I. Run unittest discover for
test_financial*.py, test_dart_service_status.py, test_fast_backfill_phase_policy.py,
test_legacy_document_quality.py. Replay and audit commands appear in the workflow;
they are separate programs and source literals are immutable inputs.

Predeployment live HTTP plan is exactly two preserved prior800 candidates,
20041112000277/20041112000279, in separate output; no old quarantine reset.
Stop at first service/rate-limit failure. Do not retry it blindly.

The preceding sections are predeployment checkpoints, not the final operating state. At that checkpoint rollout was NOT yet merged or operating-verified. Merge only
after required scoped CI and live HTTP checks have actually passed. On failure,
leave canary/schedules/publication held. Revert code independently from any later
data commit; keep candidate raw artifacts/quality state for inspection. A rollback
must retain bounded HOLD workflows/config, never restore the old2000/v5 schedule.
After operating collection, independently review the source cells before a separate
quality_v9-only publication commit. Scale-up requires separate explicit judgment.

Long multi-security completion is unchanged; no substitute single-stock runs.
Investment PIT0/6 and all operating PIT gates remain unchanged.

## Failed candidate runs retained; corrections are not successful deployment

Candidate bbef9262 CI39171683518 failed. Fixed-kit financial tests passed, but
the isolated DSL export command needed an explicit scripts import path. A runpy
entrypoint with that path fixes invocation without changing the DSL/export owner.
The live worker stopped before making HTTP because Python3.12 HTTPSHandler lacks
the private _check_hostname attribute. The fix passes only the verified default
SSLContext; an actual urllib opener-dispatch regression now covers that boundary.
No network/service retry is justified by this local adapter error; the corrected
transport is a separately versioned attempt and no prior quarantine was modified.

An overlooked automatic validate-legacy-parser workflow39171683542 installed
Internet dependencies before failing old v5 assertions. This violated this task's
installation constraint; the run is not a fixed-kit test or PASS. Main and the
immutable local kit were untouched. Its trigger is now guarded for this scoped
release, as is broad Strategy DSL CI. No further Internet installation is allowed.

Its three parser failures are explicit contract changes: old v5 version literal,
unheaded negative money without proved period, and publishing NaN candidates.
tests/test_legacy_dart_parser.py is migrated to standard unittest, preserving
all numeric/alias/source protections, requiring dates for valid loss extraction,
testing refusal of unheaded/NaN values and preventing implicit v5 replay. It runs
in the dedicated fixed-kit CI; no original source fixture/oracle is overwritten.

## Verified predeployment checkpoint

Candidate8b1c845dfc332faea88382f1f414602cdbbad4b2/run39171975276 completed
SUCCESS. Actual fixed-kit financial61, legacy parser10, service5, phase5 and
source-quality6 tests, DSL contract check, independent12 source replay/audit and
original22/518/64/60 protection all executed. Recreated audit CSV/summary bytes
matched. Broad/schema skipped workflows are not counted as successful tests.

Live authenticated shadow2 completed in18.545seconds. Both prior800 receipts now
returned original ZIPs, but each has independently recorded malformed XML:
20041112000277 mismatched tag and20041112000279 invalid token. Both are SOURCE_GAP,
0 published monetary rows, not NO_METRICS or financial PASS. The original3998
quarantine manifest/state is unchanged. This demonstrates the actual fixed-kit
HTTP route and correct distinction between prior service outage and current
document damage, not financial accuracy of those documents.

Raw shadow transfer Git blob a04e3097e3e23753df03e2dbb54a46c898db2d59,
compressed SHA256 d36e7c5056d2c51053a83e01439c1c4bfa142d468537bf75655a3daaba805cfc.
Artifacts:12152837621 financial-shadow-live-HTTP and12153515057 bounded-financial-
fixed-kit-validation. PR39 is separate from the research branch and remains
unmerged until its final head CI completes. Final log instrumentation adds
explicit UTC/connect/read stages without changing source parsing/HTTP semantics.
Operating checkout is pinned to the trigger SHA, not a moving main ref.


## Final bounded operating result (supersedes earlier candidate checkpoints)

PR39 merged as63ad9b8fe26ff619dafd11935619ca7f61be530b, preserving ETF
update8be3b098. Final PR39173902344 and push39173899179 passed on90fb122.
Main financial CI39174955538 passed at the actual merge SHA.

The first operating plan was fixed at10 untouched pending receipts, within the
user100-document ceiling, before any operating values. Actual run39174955546
SUCCESS,10/10 processed in45.497seconds:3PARSED_4F,7SOURCE_GAP,51 structural
observations, zero service/rate/worker errors. It was transport/checkpoint success,
not financial acceptance of all candidates. No original v5 state/financial data
was rewritten and3998 old service-quarantine records remain untouched.

Independent operating primary controls:16 unique fields,12 source amount/period/
unit/scope/coordinate PASS,0FAIL,4CFS UNVERIFIED because unextracted. Publication
acceptance is narrower:8 fields accepted and8 controls held. Only OFS core4 each
for20100331001578 (original 고려반도체시스템, current index 코세스) and20100331001582
(사조산업) are source-verified for publication. Their original auditor primary
statements also agree. Other28 non-core structural observations and all15 rows
from the source-conflicting bank remain in the original artifact, not the posted
metrics (43 total candidate rows held). No CFS value is replaced with an OFS value.

Receipt20100331001580 main primary CF reports2,274,870,860원, while its auditor
primary CF reports2,274,103,227원 for the same2009FY OFS period. The main CF profit
reconciliation also differs from its IS by767,633원. These are confirmed source
discrepancies; authoritative version/amount remains UNVERIFIED. No parser answer
was changed to pick a favorable source. All15 bank candidates are HELD.

Seven archives have strict source-integrity failures, often in an attachment.
Their main bodies can visibly contain financial tables. SOURCE_GAP means the
archive failed current integrity requirements, not that financial items are absent.
Exact members/reasons/hashes are in operating_source_gaps.json and original ZIPs.

Source artifact12153773795, size1444872, zipSHA551dfea8895c871c9fa9affc2412fa7f99a8245482b4083173820e758b2172d3.
Public raw/candidate transfer blob aad8c5f8f42afa33fafe14c3bba9dbe0c43b451d,
compressedSHA b7f743566098c248907a2c2a1bc7bd790a08e8b6e22ca6e5561ce45bb2f4bd68.
The immutable operating ZIPs, typed controls, quality checkpoints and8 posted
fields are rechecked by scripts/financial_operating_evidence.py in actual CI.
That independent checker imports no production parser or account aliases.

Collection/quality checkpoints are separate; next unclassified receipt is after
20100331001585, with10 exact source receipts durable in quality_v9/collection.
New untouched queue38961 is prior38971 minus these disjoint10; old v5 snapshot
counts remain labeled v5. Old wrapper CSVs are explicitly superseded, not current
success evidence. data/status/dart_legacy_rollout_status.json is the current view.

The closing configuration is HOLD. No automatic collection or automatic data
publication resumes, and no v5/2000 fallback exists. Scope expansion requires a
separate decision, including malformed-source handling, attachment/version
conflicts, CFS coverage and explicit source financial acceptance.

Every posted row keeps original member/archive SHA, field coordinates, source
units/dates, parser and quality versions. Identity, complete amendment chain and
official availability remain UNVERIFIED; backtest_eligible=False, PIT0/6. These
are exact-source financial observations, not complete investment-certified data.
Original22 common-collector replay produced331 candidates, with80P/0F/8U across
88 controls. The8FX controls were not promoted.518/64/source60 protection remains
separate from the new small-sample source audit. No new long multi-security run
completed in this task; the prior rights/succession/source blockers remain.

Reproduction in the same verified kit:
```bash
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I scripts/financial_operating_evidence.py
"$PY" -I -m unittest discover -s tests -p 'test_financial*.py' -v
"$PY" -I -m unittest discover -s tests -p test_legacy_dart_parser.py -v
```
Replay source12 and old22/518/64/60 commands are pinned in the workflow. The8-field
publication uses the fixed operating_controls.json; changing those controls after
comparison is forbidden. Code rollback and explicit data withdrawal are distinct.
Keep HOLD policy while reverting code; preserve original artifacts and add a
withdrawal record for any invalid posted observation instead of deleting evidence.

One forbidden Internet installer ran in initial failed schema CI39171683542.
It affected its ephemeral runner only; it is not fixed-kit or accuracy evidence.
Both legacy installer triggers were corrected for this scoped release. Final
scoped runs use the original pinned kit and no internet pip. Broad skipped jobs
are not reported as PASS. Actual final SHAs, run states and publication readback
are reported separately after the closing data/HOLD PR finishes.
