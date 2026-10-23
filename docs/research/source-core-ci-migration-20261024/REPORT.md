# Source-core CI owner migration repair — RESEARCH_ONLY

Approved public code: cc817d6d030e1980bb6e159a3c0efa52ab23611d.
Separate approved driver: 2bdbaff396c65e08cf5471fd32cbeca5ccd5c401;
workflow SHA256 5df75fd7a4d2cda98a70cc604bd9d0549eaa9eb5dbcf5b49c1eb1814a27583a4.

Remote run https://github.com/Horororong/quant-marcap-runner/actions/runs/40030239278
FAILED. Exact-target assertion and fixed-kit bootstrap/verify succeeded. The
source-core step failed; the subsequent SBM/migration step was skipped. GitHub
annotations expose exit1 only; one normal job-log API download was unavailable
and was not retried or routed around. Remote traceback bytes were not obtained.

The same source-core command sequence reproduced a failure locally at the final
protected-owner hash assertion. Fresh source80, preview80, identity40 and all
strict data/readiness comparisons succeeded before that assertion. The old five
pins are historical9.3: parser SHA4bfb127... and config SHA7a537780... differ from
the explicitly reviewed9.4 migration. The other three protected pins match.
This is a reproduced integration-check defect, not evidence of changed monetary
values. It is not claimed to be an independently downloaded remote traceback.

The repair preserves the old pin file. It permits exactly the parser and approval
config to differ only when (1) the preserved9.3 config fixture hashes to the old
config pin, (2) its source pin equals the old parser pin, and (3) the existing
`check_native_source_review_evidence.check` validates the full explicit migration,
old/new versions, exact source hashes, config limits, original candidate values,
180 source regressions, independent new source controls and unchanged other
source owners. Its returned source hash must equal the actual module hash.
Any additional protected-owner difference or missing migration evidence fails.
The returned metadata says five owners **checked**, not five unchanged.

Seven new boundary tests PASS, including actual migration validation, unrelated
owner changes, wrong old fixture/parser pins, missing migration and wrong final
source binding. The failed source-core check now passes locally using the fresh
source80/provider80/identity40 reproduction. No old expectation or pin was
rewritten. No financial/PIT/provider/collector/engine/UI code is changed.

These three repair files are subsequent to the exact162-file approval. They are
LOCAL_ONLY pending a new exact public-transfer approval. No new driver is needed;
reuse2bdb... with `target_sha=<repair commit>` and `suite=source_core` after approval.
Do not cite the local seven tests as successful remote CI. Do not rerun the old
failing SHA without a cause correction. Evidence and exact publication/readback
receipts remain in /workspace/quant-publish-q3-20261024.

## Follow-up expressly authorized on2026-10-24KST

The user authorized both the prepared3-file repair and directly necessary
follow-up code/tests/evidence for this same CI failure. The earlier pending
approval statement applies historically; this issue-scoped follow-up does not
need another approval merely because its file count or SHA changes. It does not
publish the later unrelated68-field audit, new raw sources or main changes.

The old native module hash protects statement-boundary, current-period, scope,
unit/sign and extraction behavior. The old approval-config hash protects its
explicit parser/source authorization and all finite-operation limits. They
changed because the independently reviewed9.4 parser recognizes the exact
attached-audit-note reference without terminating SBM's primary statement. The
old9.3 pins and approved fixture remain unchanged. No general acceptance of
changed hashes was introduced.

Additional protection:19 exact file SHA256 anchors are taken from the already
approved immutable cc817 commit, including historical owner pins/fixtures, the
before/after module/config relationship, source-transfer manifest, source80
financial/identity reference bytes, old audit manifests and the9.4 migration,
replay and independent controls. Mutable proof plus a simultaneously rewritten
hash is insufficient. The complete existing migration verifier still runs after
these byte checks and verifies versions, zero changes/losses, raw-member source
bindings and config limits. The old owner dictionary cannot be replaced with
current hashes to bypass this route.

Fifteen boundary cases now include actual parser+config+after-hash rewriting,
financial controls with a matching rewritten proof hash, source-transfer
manifest changes, wrong before/after links, missing or contradictory migration
and historical-pin tampering. These are included in the existing selected native
boundary test family through unittest's load_tests hook, so the unchanged driver
runs the original118 cases plus15 additional cases=133. The previous arbitrary
current-hash direct-call test was tightened to reject an unbound replacement;
no existing118 test was removed or weakened.

## Actual remote result for final repair code

Final validated code **ff195aa31db153f8fd042ad170a937150c092df4** published
fast-forward after3ea, six net CI-issue paths/32,560 bytes, no secret hits.
All remote file SHA256 and the full Git tree matched. No0f7f audit, new source
bytes, main merge, financial publication or PIT relaxation was included.

[Fixed-kit CI40034805026](https://github.com/Horororong/quant-marcap-runner/actions/runs/40034805026)
**SUCCESS**, created2026-10-23T22:37:26Z/completed22:38:51Z. Unchanged separate
driver2bdbaff396c65e08cf5471fd32cbeca5ccd5c401; workflow dispatch input and
mandatory exact-target assertion bind checkout toff195... . Both source-core and
subsequent source-reference/migration/SBM steps succeeded. The selected native
family includes original118 cases plus15 tamper/migration cases=133; source-core
also runs11 identity/extension cases, source80/canonical80/identity40, actualSBM15
source controls/core4 previews,160 financial as-of field/signal checks and the
generated contract check. Historical2277+273 preservation evidence is pinned and
validated; this is not a new180-document parser replay. All non-admissions stay
blocked; these tests grant no new PIT certification. No Internetpip or DART calls.

This result/evidence-only append may have a later Git SHA thanff195... . It is
not another code change or another CI run; the exact tested code SHA remains
ff195... . The prior failedcc817 run is retained as historical failure evidence.
