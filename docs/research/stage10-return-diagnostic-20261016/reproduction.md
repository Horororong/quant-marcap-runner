# Reproduce Stage10 without NAV or data writes

Baseline: `6dfa430128b37cd49990232acf43f2882fcf20dc` on `fix/financial-accuracy-20261014`.
Read the handoff, Stage8 report, Stage9 report/followup, AGENTS/PROJECT_CHARTER and source contracts first.
Read-only inspection imports the current repository scripts using the original verified kit's dedicated Python.
It does not run the checked backtest, generate NAV, or bypass its failed guard.

In this session the original release was restored with the existing bounded helper:

```bash
python docs/audits/version-pit-stage6-20261014/restore_kit_only.py --output /workspace/scratch/37dc2d194953/runtime
python /workspace/scratch/37dc2d194953/runtime/kit-parts/bootstrap_quant.py --parts-dir /workspace/scratch/37dc2d194953/runtime/kit-parts --destination /workspace/scratch/37dc2d194953/runtime/installed
/workspace/scratch/37dc2d194953/runtime/installed/.venv/bin/python -I /workspace/scratch/37dc2d194953/runtime/installed/scripts/sandbox_runtime.py verify
```

Run from repository root with that verified Python, in a NEW output directory:

```bash
/workspace/scratch/37dc2d194953/runtime/installed/.venv/bin/python -I docs/research/stage10-return-diagnostic-20261016/diagnose.py --output /tmp/stage10-review
/workspace/scratch/37dc2d194953/runtime/installed/.venv/bin/python -I docs/research/stage10-return-diagnostic-20261016/verify_results.py
```

The second command independently checks the committed `results/` and writes this directory's `verification.json` only.
The first refuses an existing output directory. Compare its deterministic CSV/JSON hashes with `artifact_manifest.json`.
Use the same interpreter/kit/package versions; substitute only absolute local runtime paths on another machine.
No internet pip, collector, runtime code change or registry update is needed. Current repository code SHA
and installed original-kit source SHA are different on purpose: kit supplies pinned dependencies, current repo supplies diagnostic inputs/builders.

Outputs:

- `results/membership.csv`, `partition_audit.csv`, `schedule.csv`: complete original selection and timing.
- `results/planned_holding_observations.csv.gz`: every expected prior-held code/day with arithmetic and classification.
- `results/planned_holding_mismatches.csv`, `planned_top20.csv`, `planned_by_code.csv`, `planned_by_date.csv`: all4 held candidates.
- `results/target_only_observations.csv`: new-at-close cases without prior return exposure.
- `results/panel_mismatches.csv`: full316 comparable >1bp cases (includes held4).
- `results/panel_numeric_mismatches.csv`: full535 arithmetic cases including219 UNVERIFIED nontrading boundaries.
- `results/panel_unverified.csv.gz`: all41,822 first observations/nontrading boundaries, without forced returns over gaps.
- `results/missing_planned_observations.csv`: explicit left-join missing-held-row audit (0).
- `results/registered_events_in_period.csv`, `history_coverage.json`, `execution_plan.json`, `input_sha256.json`, `summary.json`.
- `case_evidence.json`: limited primary-source observations, each proof's boundary, all exact causation UNVERIFIED.
- `verification.json`, `runtime_verification.json`: actual checks, distinct from full regression tests or CI.

Initial diagnostic ran once to inspect unclassified candidates; a final run added primary-evidence labels and compressed large CSVs deterministically.
No input or candidate arithmetic changed. Initial verification's unbounded production-gap probe encountered an assertion:
the production tracer correctly keeps an unresolved gap active for later bucket purchases. The probe was corrected to cap each case at
its event day, preserving pre-close semantics; all final checks then passed. No engine, gate, source or threshold was altered.
The initial failure is an audit-tool validation failure, not a new production defect or a hidden ignored test.

Existing 518/core64 results and original60 controls are SHA-preserved, not re-certified by this arithmetic diagnostic.
Full original60 archive retrieval/replay and full engine E2E were intentionally not repeated.
Final CI must be queried for the exact published SHA; docs-only path filters/skipped jobs never mean tests passed.
