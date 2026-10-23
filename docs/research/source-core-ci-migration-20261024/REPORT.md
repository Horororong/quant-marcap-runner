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
