# Bounded100 source validation reproduction

Use only the original verified kit Python. Never install internet dependencies.
The original main source was98a5f706b56ba23c4d10731050c14be0405c4da2; production
parser remains legacy-v9.1-primary-source-metadata and quality remains
financial-quality-v1-source-linked-not-PIT. The independent review contract is
independent-source-review-v1. No parser version retroactively relabels v5 data.

The reviewed source packs, their compressed SHA256, original Git blob IDs and
collection run are in source_manifest.json. Each pack contains exact original
ZIP bytes and the initially collected subjects; independent raw source grids do
not open production row amounts. Controls are frozen before comparison and
their source-cell/account/header evidence is executable. Human financial meaning
is an explicit control input, not authenticated by running a second parser.

Offline checks (replace PY with the dedicated verified Python path):

```bash
"$PY" -I /path/to/pinned/runtime/scripts/sandbox_runtime.py verify > runtime.json
"$PY" -I -m unittest discover -s tests -p 'test_financial*.py' -v
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-validation-100-20261019 --check
"$PY" -I scripts/financial_operating_evidence.py
"$PY" -I scripts/financial_review_views.py docs/audits/financial-validation-100-20261019 --output /tmp/fresh-independent-raw-views
```

The source grid viewer verifies original pack/ZIP/member identity and emits raw
header/row views. It is not an independent semantic adjudicator. Financial review
controls must establish current period, account, unit, scope, and source member;
an exact decimal match alone cannot promote any PIT or historical mapping flag.
Amount normalization is exact in KRW; no rounding tolerance or FX is inferred.

Initial authorized collection commands ran only in authenticated Actions, after
fixed-kit preservation CI. Freeze selects100 NEVER-classified mapped receipts,
excluding all historical v5 states/quarantine and durable prior10. It fixes the
literal list and SHA before HTTP; seed financial-validation-100-20261019-v1 fixes
the primary20 by SHA256(seed|receipt), with the preregistered extraction/state
augmentation. The order is receipt date then receipt number, without replacement.

```bash
"$PY" -I scripts/financial_validation_batch.py freeze --plan /tmp/validation100/batch_plan.json
"$PY" -I scripts/financial_validation_batch.py collect --plan /tmp/validation100/batch_plan.json --output /tmp/validation100 --chunk 0
```

These are historical collection commands, not instructions to rerun HTTP. The
five chunks have20 fixed documents each,90 seconds/document and600 seconds/chunk.
A failed chunk stops subsequent chunks; original bytes and durable checkpoints
precede completion. An Actions retry or existing output is refused. A consumed100
ledger blocks another100; the next scale needs a new explicit decision. The old
first10 operational canary is consumed and HOLD remains closed independently.

Original collection, parser extraction, independent verification and reviewed
publication are separate ledgers. Collection SOURCE_GAP does not establish actual
financial absence. An unsupported CFS source is not reconstructed from OFS.
Conflicting current amounts are held instead of selecting or averaging versions.
Missing subjects remain UNVERIFIED even when a human can identify a source cell.

The first10 result/status, published8 and held43 remain immutable baselines. A
new review transition, if present, is stored separately with exact field scope;
it does not erase earlier holds or certify a correction chain. New reviewed
financial rows use their own batch metrics directory and stay ineligible for
investment backtests. Legacy v5 normalized files, state and3998 service-error
quarantine are neither reset nor rewritten.

The old queue selector rebuilt a72028-receipt union for every index row. The
one-time blocked set preserves selection/order and avoids that quadratic work:
100000 synthetic index rows/72028 old receipts select100 in0.045 seconds locally;
a separate3000-row old/new comparison is byte-semantically identical. The first
live freeze's observed delay is retained rather than omitted from timing.

Fixed-kit CI also repeats original22 financial controls and518/64/60 preservation.
CI success is reported separately from document/field PASS/FAIL/UNVERIFIED. The
historical Stage6 investment PIT result remains0/6. A review subset is not a
population accuracy estimate, full-document PIT certificate or strategy approval.

Workflow review: dedicated financial CI and finite collection restore pinned
wheels only. Legacy-schema and broad Strategy-DSL internet-install jobs retain
their existing deployment-prefix/fixed-kit-marker guards. No such installer is
executed for this task. Other legacy/manual workflows still have internet
installers outside this scope; they are not described as migrated or executed.

## Explicit v9.2 correction and fresh holdout

The100 HTTP collection remains the exact v9.1 snapshot. Original source packs,
initial controls and before_v91 results stay immutable. Current parser version
is legacy-v9.2-statement-boundary-guard (approved exact SHA in
parser_candidate.json); quality/PIT flags do not change. Isolated title tables
reset inherited statement/scope and unsupported following headers stay closed.

Fresh post-fix20 selection and50 controls (40 financial,10 document-only) are in
postfix_holdout_plan.json/postfix_controls.json. They are disjoint from initial28
and were frozen in134378b329a3be789c5049a91845a6a549b5cb0a before candidate output.
The initial28 are now regression evidence for this fix. Controls are not replaced.

```bash
"$PY" -I scripts/financial_validation_replay.py docs/audits/financial-validation-100-20261019 --output /tmp/new-candidate-replay
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-validation-100-20261019 --check
```

Replay110 = authorized100 plus original10, HTTP0, readonly original ZIP cache.
Each of the six small offline runs uses the same90/600-second bounds. Raw worker
results/progress retain execution clocks. The versioned comparison snapshot
removes only state.updated_at_utc and sorts JSON keys, preserving every financial
value, period, scope, source hash and coordinate. CI compares decompressed exact
canonical bytes and separately audits frozen semantic/literal controls.

The original22 validator remains unchanged in its historical checkout. The
candidate runner extension pins the approved9.2 source hash and compares all88
financial-control CSV rows to original values. Only the revised_parser metadata
column changes9.1 to9.2; summary and every other field remain equal. The original
historical proposal apply/rollback checks its original9.1 hash, independently of
the candidate9.2 hash. This fixes audit-version coupling without replacing any
financial expectation. The local first wrapper exit1 and successful final-stage
recheck are recorded in local_regression_recovery.json; final CI reruns the full
command, rather than treating that original exit1 as success.

The new100 financial publication is82 reviewed fields/21 documents. A separate
prior10 transition releases3 BS/IS fields; it does not select the conflicting
OCF. Original global8 metrics and43 observations/statuses remain byte-identical.
New per-field review metrics are in the reviewed_batches namespace and stay
backtest_eligible=False. Publication file hashes are checked by the CI gate.
