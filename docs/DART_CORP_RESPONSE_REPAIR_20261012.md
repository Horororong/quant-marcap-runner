# DART company-code response repair · 2026-10-12

## Confirmed failure

Actual fast run **38079743270**, job **114294012340**, exited **1** on
2026-10-10 after persisting legacy checkpoints through 1,475 receipts. The modern
phase's `load_all_dart_corps()` opened `corpCode.xml` response bytes directly with
`zipfile.ZipFile`, raising `BadZipFile: File is not a zip file`. The response body
and HTTP status were not retained, so the exact server-side status cannot be
claimed. Earlier failures also included connection timeouts at this endpoint.
Completed legacy data were preserved by the workflow's existing always-run
publication; the combined fast status was stale because it was written only
after successful modern execution.

Primary format/status contract:
[OpenDART company-code guide](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018).
Normal output is a ZIP containing XML. Error responses include API status codes;
020 is quota, 010/011/012/901 are authentication/access failures. Maintenance or
unknown response content does not prove a transient communication failure.

## Fix and scope

`dart_corp_code.py` validates archive members, XML and nonempty company-code
rows before returning data. Non-ZIP XML errors are classified; malformed HTML,
truncated archives, empty/invalid company lists and ambiguous XML members fail
explicitly rather than becoming empty mapping success. Raw response messages,
request URL queries and credentials are excluded from errors.

Only transport timeout/connection errors and HTTP 500/502/503/504 are retried,
with a maximum of **3 attempts**, 60-second request timeout and 1/2-second
backoff. Quota (API020/HTTP429), access errors, maintenance responses, unknown
API errors and invalid payloads are not repeatedly requested in the same run.
No indefinite retry, cache fallback, changed collection periods or fabricated
financial values. The modern loader translates quota/authentication into its
existing typed exceptions and retains status/attempt metadata. The active recent
financial refresh uses the same helper and retains its listed-stock filter.
The inactive legacy quarterly workflow is not changed or launched.

The fast wrapper atomically publishes current completed legacy counts and
sanitized modern failure information **before exiting nonzero**. A potentially
partial modern count is unknown (blank), not falsely zero/completed. Legacy quota
and fatal-service gates still stop subsequent modern calls. Durable per-task
state, original financial rows, parser versions, source quarantine and shared
writer locks are unchanged. The 4,021 quarantined errors and 15,918 source-gap
receipts were not cleared or blindly retried. Those are separate source-quality
and receipt-specific investigations, not resolved by this transport change.

## Actual local validation

The original runtime remained available at
`/workspace/scratch/laa-recovery/runtime/.venv/bin/python`.
`sandbox_runtime.py verify`: actual **exit0/statusok**, original kit
`26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`.
No package installation, kit manifest changes or ambient Python test fallback.
The kit does not include requests/pytest/yaml; local tests use explicit controlled
transport doubles and execute the actual changed loader/wrapper function bodies.
Existing CI's real-module collector regressions provide the integration checks.

**18 unittest regressions pass**: valid ZIP/DataFrame contracts, XML-member
selection, transient recovery/retry exhaustion, permanent/quota stop, credential
redaction, malformed/archive/company-list rejection, actual loader exception
translation, recent-loader behavior, success counters, and persisted legacy
counts/current failure status. The same invalid non-ZIP boundary is reproduced
offline; no specific response body is represented as the original failed call.

Generated DSL contract check: **PASS**, contracts unchanged. Initial invocation
with `-I` could not import `execution_contract` (exit1); corrected the module
search path explicitly for this checkout under the same dedicated Python and
reran successfully. No dependency or interpreter substitution. `git diff --check`
passes. Frozen kit remains unmodified; no investment backtest was run.

Relevant source hashes match live main **44ca6d57962cd1b1906fbb144cdb62db4cac52c5**.
Changes are isolated in `/workspace/scratch/dart-repair`, leaving the earlier
LAA worktree and artifacts intact. Publish only the reviewed source/test/docs/CI
files on top of current main; do not replace remote data with local older data.
The existing Strategy DSL workflow includes the new tests and trigger paths.
Full final-head CI must pass before deployment is claimed.

## Exact resume

```bash
timeout 60 /workspace/scratch/laa-recovery/runtime/.venv/bin/python -I /workspace/scratch/laa-recovery/runtime/scripts/sandbox_runtime.py verify
/workspace/scratch/laa-recovery/runtime/.venv/bin/python -I tests/test_dart_corp_code.py
```

Saved local logs: `/workspace/scratch/dart-repair-tests.stdout.log`,
`/workspace/scratch/dart-repair-tests.stderr.log`,
`/workspace/scratch/dart-repair-kit-verify.json`.
The original failed remote job log remains accessible on GitHub. No duplicate
collector or rerun has been launched. Preserve existing schedules/checkpoints;
next production use should resume through the existing shared lock.

This fixes response handling and failure reporting, not financial numeric/PIT
certification or proof that the external endpoint will never fail again.
