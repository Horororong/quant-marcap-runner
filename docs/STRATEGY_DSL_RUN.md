# Checked Strategy DSL execution

Machine contract 20 / run orchestration 1 / preflight 3. PROJECT execution,
registry providers and CURRENT performance retain their existing versions and
formulas. The public runner CLI now uses `run_checked_strategy()` in
`scripts/strategy_dsl_run.py`; Python `run_strategy()` remains the existing
component API for regression/legacy callers.

## One execution command

```bash
# Formal report: actual history for all four CURRENT periods is required.
python scripts/strategy_dsl_runner.py strategy.json

# Explicit short-window research NAV, without formal performance claims.
python scripts/strategy_dsl_runner.py config/strategies/kr_equity_size_deciles_research.json --execution-only

# Compile/inspect only; no run directory or data access.
python scripts/strategy_dsl_runner.py strategy.json --validate-only
```

The execution command snapshots and validates input, runs the shared preflight
including PR #23's known corporate-action gate, checks formal-report date
readiness when requested, then calls the existing top_n/decile execution and
CURRENT postprocessor. A failed preflight never reaches NAV calculation.
Runtime held-return, tradability, cost and verified-event guards still apply;
preflight `ok` is not a historical completeness certificate.

Default runs are separate directories at `results/dsl/runs/{run_id}`. Optional
`--output-dir` names one **new** run directory. Existing directories are rejected
before modifying files, even for a failed prior attempt. Repeating a run creates
a new identity; incidental IDs/timestamps do not change strategy fingerprints,
selections or NAV. The normalized snapshot preserves scenario insertion order
as well as canonical values, retaining existing NAV/audit column order.

The original input is read once. Preflight and execution consume the same
normalized snapshot, so later edits to the original file cannot change a run.
The snapshots, strategy fingerprint and component contract versions are stored.
Full source-data hashes, package versions, code identity and replay verification
remain the following manifest milestone; this run ID is not a complete data pin.

## Status and output contract

CLI stdout is structured JSON with identity, status, phase, readiness flags and
published output paths. Error text also goes to stderr. The persisted
`run_status.json` includes the complete artifact inventory and is updated using
atomic file replacement at stage transitions. CURRENT subprocess output is
captured in `postprocess.log`, keeping stdout parseable.

| Status | Exit | Meaning |
| --- | --- | --- |
| `ok` | 0 | Requested mode completed, including required artifact checks |
| `capability_gap` | 2 | Invalid/unsupported DSL, before data or NAV |
| `data_gap` | 3 | Shared preflight gap or insufficient formal-report date coverage |
| `failed` | 4 | Operational, execution, artifact or CURRENT postprocess failure |
| `interrupted` | 130 | Keyboard interruption; completed-stage flags remain explicit |
| `running` | none | Intermediate persisted state, never returned as completed success |

Phases: `input`, `preflight`, `report_readiness`, `execution`, `postprocess`,
`complete`. Preflight gaps retain their detailed phase as `gap_phase`, and full
diagnostics remain in `preflight.json`. Missing input files are operational
`failed` errors, not missing PIT history. Output-reservation errors have CLI
`phase="output"` and create no status file in the rejected directory.
Unexpected execution errors remain `failed` with their typed error and stage;
the orchestrator does not guess a capability/data classification from text.

`nav_ready` becomes true only after all requested series/dates, finite positive
NAV, fingerprint and mandatory enabled held-return audits are checked, together
with required artifacts (including all ten deciles). `report_ready` becomes
true only after CURRENT outputs contain every requested series in all four
periods and the nine-chart manifest in canonical order.

- Formal success requires both flags. A CURRENT failure after execution leaves
  `status="failed", nav_ready=true, report_ready=false`; validated NAV remains
  available, and partial report files are never published as a complete report.
- Explicit `--execution-only` success has `nav_ready=true, report_ready=false`.
  It describes research NAV, not a completed four-period performance report.
- Input/preflight/readiness/execution failures cannot publish a validated NAV.
  A failed attempt may contain diagnostic files and private partial staging.

```text
<run_directory>/
  run_status.json
  strategy_input.json          # exact original bytes, even on validation failure
  strategy_normalized.json     # created only after successful input validation
  execution_plan.json
  preflight.json
  report_readiness.json        # formal mode
  artifacts/                  # existing engine files, published after validation
    daily_nav.csv
    target_weights.csv
    ...                       # selections, per-decile files, required audits
  report/                     # formal success only
    metrics_CURRENT.csv
    chat_manifest_CURRENT.json
    daily_nav_canonical.csv
    monthly_nav_canonical.csv
    benchmark_statistics_CURRENT.csv  # only with explicit benchmark
  postprocess.log              # when CURRENT runs
  _execution/ or _report/      # private staging can remain after failure
```

Execution/report staging directories are renamed into their published names
only when that stage passes. Execution and report are separate publications;
the status file decides whether the entire requested run succeeded. The report
manifest refers to the stable `artifacts/daily_nav.csv` input path, not a staging
path that disappears after publication. This provides stage-level publication,
not a database transaction or resume/retry service.

## Canonical readiness

`quant_backtest_postprocess.canonical_report_readiness()` uses coverage-verified
session dates, explicit as_of and the **same** CURRENT period-window function
as actual performance. No placeholder NAV, factor values or performance metrics
are invented. The existing period-window policy was extracted into CURRENT's
`standard_period_windows_from_dates()` and reused by its original NAV function.

Formal reporting still requires `book_validation`, `from_2001`, `from_2021`
and `longest`, complete months and exact XKRX sessions. Missing required history
returns a readiness `data_gap` before NAV; the runner never switches modes or
shortens requested dates automatically. Even after readiness passes, actual
NAV and CURRENT report outputs must pass runtime checks.

## Verification

`scripts/test_strategy_dsl_run.py` checks date-policy agreement with CURRENT,
rejected input/preflight, immutable original input, separate deterministic NAV
runs, no overwrite, corrupt/missing artifacts, partial execution, CURRENT
failure/interruption and an actual full synthetic CURRENT report. Artificial
NAV fixtures are software tests, never investment results.

`scripts/test_dsl_run_e2e.py` exercises both public CLI modes on actual KRX data,
compares every component artifact byte-for-byte with the existing runner,
rejects known Jeisys exposure in top_n/deciles and missing historical data
before NAV, and runs actual DART PIT/benchmark/held-return execution.
Both are included alongside all prior tests in the full Strategy DSL workflow.

## Storage and retention

Run directories contain DSL snapshots, NAV, audit and report outputs; they do
not copy the repository's KRX/DART source datasets. Repeated runs still consume
space, especially long histories and ten portfolios. There is no automatic
retention/deletion policy yet. Treat important runs as immutable evidence and
apply an explicit age/size policy to disposable research runs. No old results
were deleted in the collection milestone.

Overwriting a cache or a latest-result pointer can be appropriate. Replacing
an established result in place during execution can lose the prior validated
result if the replacement fails. The checked runner therefore reserves a new
run; a future latest alias should change atomically only after success.
