# Stage14 reproduction

Run from repository root. Only original kit26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd;
local dedicated Python /workspace/financial-repair/runtime/.venv/bin/python.
Do not run collector modes again: sources already captured; no pip/price/history API collection.
CI uses the same restored kit, verifies it, then executes only these offline checks plus existing evidence-artifact restoration.

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
/workspace/financial-repair/runtime/.venv/bin/python -I -c 'import runpy,sys;sys.path.insert(0,"docs/research/stage14-celltrion-2019-20261017");runpy.run_path("docs/research/stage14-celltrion-2019-20261017/test_source_formats.py",run_name="__main__")'
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage14-celltrion-2019-20261017/verify_event.py --output /tmp/stage14-event-review-UNUSED.json
cmp /tmp/stage14-event-review-UNUSED.json docs/research/stage14-celltrion-2019-20261017/event_review.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage14-celltrion-2019-20261017/verify_artifacts.py
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage14-celltrion-2019-20261017/preserve.py --originals /workspace/financial-repair/preserved-originals60.zip --output /tmp/stage14-preservation-UNUSED
STAGE13_LEDGER_OUTPUT=/tmp/stage14-independent-ledger-UNUSED.csv /workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage13-stock-dividend-integration-20261017/validate.py --output /tmp/stage14-regression-UNUSED
cmp /tmp/stage14-independent-ledger-UNUSED.csv docs/research/stage13-stock-dividend-integration-20261017/independent_ledger.csv
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage13-stock-dividend-integration-20261017/compare_snapshot.py --output /tmp/stage14-snapshot-UNUSED.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage12-stock-dividend-20261016/compare_krx.py --output /tmp/stage14-prices-UNUSED.json
cmp /tmp/stage14-prices-UNUSED.json docs/research/stage12-stock-dividend-20261016/official_krx/comparison.json
```

Choose unused outputs: commands refuse overwrite. No bare/system Python bypass for calculations/tests.
Do not invoke the old Stage13 preserve.py against modified workflow: its frozen source pins intentionally refer to Stage13.
Stage14 preserve.py inherits the immutable616 controls, freezes Stage13's53files, and adds unchanged engine/contracts to683.
Historical manifests are preserved, not rewritten to make checks pass. Stage14 artifact_manifest.json pins new outputs/source/workflow separately.
The original19-command harness does not skip/defer DART E2E; timeout150 unchanged. Local logs are local_validation/.

Source recovery: source_ci.json lists every actual source run/job/artifact digest. Those artifacts contain exact original
HTTP responses, not new requests. The local source checkpoints are /workspace/research-stage14-20261017/{sources,history,listing,corrected,body}.
source_state.json omits only verbose page snippets from its state derivative (raw state exists in the first artifact).
The original DART member is base64-lossless; strip only terminal LF, decode strict, verify member SHA, decode cp949 and prove roundtrip.
The UTF8 .html is a derivative. Issuer/KSD redacted HTML removes anonymous nonce/session values; its SHA is not the raw HTTP SHA.
KIND kind_body_0.html is unchanged original UTF8 response (659bytes). Source response hashes are in evidence/*_state.json.
No API key/request URL query is stored. API-key echo is scanned across all ZIP members before retention.

Stage14 acquisition history, for reproduction by inspection only:
1. Original proposal20191218800434 + issuer archive/3JS (5 requests).
2. Actual public GET search form page1/page2 then actual2020notice697 (3 requests).
3. KIND search-main + incorrect POST (0byte) + KSD default public form (3requests; no event proof from empty/default).
4. Source-proved corrected KIND POST + its actual viewer + KSD public name lookup (3requests).
   KIND succeeded; KSD pipe-delimited response failed old UI comma parsing. CI39026715582 remains failure.
5. Observed docNo20200421000468 searchContents + returned external URL + exactKSD company POST (3requests).
   These are new routes/parameters, no blind retry. Receipt acptNo20200421000196 differs from docNo; do not manufacture either.

The real-price check uses Stage12's exact official rows and Stage11's independently observed181000 base.
It never derives the base from ChangesRatio. Source identity/date/math assertions and zero-entitlement-new-buyer probe
are component checks, not a completed actual account lifecycle. Missing rights mark triggers the existing atomic engine error;
UNVERIFIED in event_review.json/readiness.json must not be turned into event PASS merely because software assertions exit0.
No actual credit date, rights mark, fractional cash, distribution-tax cash or primary continuous-quantity contract is invented.
The original2019–2020 deciles spec is untouched and not rerun before the required actual-event prerequisite.

Publication uses expected-head GitData without force, verifying the exact native Git tree. Local and remote histories
are retained separately because matching trees started under different commit SHAs. Source checkpoint SHA/run mappings
are in source_ci.json. The final offline CI execution.json reports actual GITHUB_SHA/RUN_ID; the final conversation records
its run/job/artifact conclusion after completion. Main/production gate/data remain untouched.
