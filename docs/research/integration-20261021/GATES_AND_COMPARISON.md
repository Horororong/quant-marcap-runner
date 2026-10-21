# Comparison and collection boundaries —2026-10-21

All results RESEARCH_ONLY. No existing151-file baseline pin, tolerance, input, strategy, cost, trade, weight, NAV or performance expectation is updated.

|Frozen files|Count|Verdict/meaning|
|---|---:|---|
|Strict original bytes|130|Final integrated exact original-input executions are compared with unchanged151-file manifest; selection/weights/fills/books/NAV/CURRENT/strategy/fingerprint are NOT exceptions.|
|Execution plans|6|Only three version fields change: exec5→10, CA7→9, DSL25→30. All other plan fields must equal originalJSON. No trade/cost/result differences are permitted.|
|Preflight|3|Structured planned-readiness contract, annual source/calendar checks, selected exposures and source/control hashes replace the old source-only envelope. Distinct planned codes33/3/1 are not a reduced universe. Full yearly signal cross-sections are scored before selected-code diagnostics. Source missing, calendar mismatch, unknown corporate actions, missing held quotes/reference returns, insufficient population and untradable original execution remain blockers. Runtime engine still applies1bp held-return, actual liquidity, cost, PIT and CURRENT gates.|
|Old envelopes|12|UNVERIFIED before/after field comparison: original bytes not locally available through currently supported transfer. Per-file currentSHA/size/schema and substantive-field warnings inenvelope-12-verdicts.json. Not labelled harmless timestamp/path/ID changes.|

Nine fullJSON diffs remain in../post-restore-20261020/nine-contract-differences.json andcomparison-exceptions-21.json. No planned-readiness or engine implementation change was made in this integration. Independent prepared-readiness seven tests, actual preflight smoke and known-event top-N/decile test preserve rejection boundaries. Older broad comparator preflight checks do not by themselves prove every field equivalent.

Existing independent CURRENT payload evidence:840 metric fields and14,155 displayed longest-period NAV points match the byte-pinned canonical CSV exactly(tolerance0). That evidence does not prove old HTML/chat/log/status fields equal. Retain existingrendered-envelope-audit.json separately. Missing old originals remain a limitation, not an exception certifying them.

## Real two-document attempt

At2026-10-21T03:30:40.685772UTC(KST2026-10-21 12:30), actual main9d000150badd662bb48813eebeb9f5ead7c756cd and its state/config were read. Same-KST-day parent39504052321 already exists. Production check_recovery_gate returnedONCE_PER_KST_DAY before lease, source HTTP or state mutation. HTTP0,new originals0,new candidates0,duplicates added0,stopONCE_PER_KST_DAY; checkpoint remains20100331002054 and is in completed_receipts. It is not a retry target. Next reserved sources20100331002062/02063, pending43. Existing reservations200/300, executions2/3; a continuation consumes the third execution but reserves0additional documents. Daily reset is KST midnight(UTC2026-10-21 15:00), not UTC midnight or token expiry. No actual DART account-wide remaining API quota is exposed in this ledger; do not claim an unmeasured quota.

HOLD_FAILURE not reset. PublicationHOLD, backtest_eligibleFalse, investmentPIT0/6 retained. No repeated dispatch was issued against the known closed gate. A successful future constrained execution may clear onlyRUN_WALL_BUDGET execution failure; financial certification remains separate. Existing main-only workflow/lease/source-input CAS means research integration cannot silently operate main. PR45 must first be reviewed/applied; an integration-branch dispatch is not a supported way to bypass that restriction.

Future explicit dispatch(on updated main only, after live state/gate/source review):
```
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=2
```
Do not run the above until main contains the reviewed collector change and the daily gate actually permits it. After exactly2documents, inspect requests, new sources/candidates, unique keys, checkpoint and exit reason; no fourth execution is authorized under the current three-execution ceiling. Offline SIGKILL/restart proves durable sources/candidates are reused, but does not stand in for the currently blocked liveHTTP test.
