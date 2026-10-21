# Research and bounded collector integration2026-10-21

RESEARCH_ONLY. Restoration is closed in its previously verified scope. No751-file rehash or large v1/v2/v3 retransmission is performed. Remote-only full restoration remains untested.

## Explicit ancestry and integration scope

- Research1872467ae3d31f5c17617a1791b1e48ed812c11e has parent5bb0523bb192598c51923549a21fd5a87ae87366.
- Collector4cb7014693f554b22151b6ea36b5f628e0ad3cd1 has parentf2c6e7da032eec086d9bb8ffc86460489b9a0819, whose parent isa9da665e77eb06e09232c9fa1b382b1e3ea31d4f.
- Live main9d000150badd662bb48813eebeb9f5ead7c756cd; PR45 was head4cb/base9d, draft/mergeable at the recorded observation. Common ancestor of187/4cb is3e9c42a1d3e028874eefb84c958a65d23083d088 (89research and55operating-side commits).
- Newintegrate/research-collection-20261021 is a child of187. It selectively imports the collector dependency closure from4cb (integration-paths.json,18paths), including the previously absent coordinator, source adapter, approved config, workflow and tests. All six approved source-owner hashes match the existing limited-observation configuration. It is NOT a whole-main merge and4cb itself is NOT a Git ancestor. Inclusion is established by exact path/hash provenance and combined executable tests, not a fabricated merge parent.
- Existing research engine, user implementation and751 research data objects remain unchanged. Main's newer operating status/data files remain on main; they are not replaced with the older research snapshot. The frozen operating-state test fixture is not a live ledger or a research input.
- Follow-up minimal operating commit34b2728878a562b22fa8b75645c944df51ee4b78 (parent4cb) fixes only the legacy safety tests/isolated fixtures and documents their contracts. Its changed test/fixture bytes are also in the integration. PR45 remains a minimal main-target collector PR. A separate integration PR targetsrestore/full-project-20261020, in accordance with PROJECT_CHARTER's prohibition on merging all research into main.

## Validation and limitations

-66collection tests PASS:24legacy plus42existing coordinator/limited-resume/SIGKILL/corp-code tests. Language6+web6 PASS, generated contracts synchronized. Prepared-readiness7 tests and standalone actual preflight/known-corporate-action smoke PASS.
-Actual browser: language→explicit preview→preflight→common engine/CURRENT→cost edit→comparison→save/reopen; three requested strategy NAV hashes preserved; independent books and changed-cost Net behavior pass. Local access is loopback; phone/public hosting and external model are not provided.
-Strict130 regression uses exact original strategy/report inputs throughscripts/test_frozen_integration.py. UI translation produces distinct IDs/metadata and decimal textual forms, so comparing every UI artifact directly to an original-input run is invalid. A trial such comparison found different book strings/source-input digests despite identical NAV; no exception or tolerance was added. The separate original-input runner preserves those strict pins.
-12old envelopes remain UNVERIFIED against original bytes. SeeGATES_AND_COMPARISON.md andenvelope-12-verdicts.json; current840metric/14155point consistency evidence is retained separately.
-ActualHTTP2 blocked before HTTP by liveONCE_PER_KST_DAY; checkpoint20100331002054 completed, next2062/2063, no state reset. No request/duplicate/new candidate was produced.
-Semantics8→13PASS (+5),1additional reviewedUNVERIFIED account definition,857unreviewed. Numeric/sign/unit871 remains a different claim. All871PIT and full-document extraction completeness remain unverified, published0.

The previous automatic Internet-pip CI ran on disposable GitHub hosts. Its failures/artifacts are excluded from pinned-kit evidence, and none of its environments/kits were promoted into this runtime or dependencies. This integration changes no requirement/lock/runtime dependency file, and approved source hashes and sandbox_runtime verification remain exact. Follow-up commits use[skip ci] to suppress the old installer workflows; explicit fixed-kit workflow_dispatch validates the immutable integration target. Local original-input regression:130 exact files,9 explicit contract files,12 original envelopes still unverified. Final remote result/driver/target will be recorded separately in the versioned integration handoff; local PASS is not remote success.

## Commands

```
cd /workspace/quant-project-full-20261020/code
export QUANT_PINNED_RUNTIME=/workspace/quant-restore-b5aaa7f/runtime
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I "$QUANT_PINNED_RUNTIME/scripts/sandbox_runtime.py" verify
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I -c 'import sys,unittest;sys.path[:0]=[".","tests"];s=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n)for n in ["test_legacy_backfill_resume","test_financial_rollout","test_financial_limited_resume","test_financial_batch_resume","test_dart_corp_code"]);r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(not r.wasSuccessful())'
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/test_frozen_integration.py --output /NEW/EMPTY/OUTPUT
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/test_research_workspace_e2e.py --output /ANOTHER/NEW/EMPTY/OUTPUT
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/restored_workspace.py web --store /workspace/quant-project-full-20261020/user-store --port 8765
```
Use a new output directory for every test; completed baselines are never overwritten. CI uses the same official kit, no Internet pip, exact checkout verification; OS/CPython patch level may differ from the local recorded runtime.
