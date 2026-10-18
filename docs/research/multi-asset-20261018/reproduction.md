# Reproduce without modifying original evidence

Branch: `fix/financial-accuracy-20261014`. Read the live final SHA and CI rather
than interpreting a historical handoff as current evidence. No main merge.

Use only the existing pinned offline kit, CPython3.12.14, pandas3.0.6,
numpy2.4.6, pyarrow25.0.1, exchange_calendars4.13.2. No internet installation,
dependency upgrade, system-Python execution fallback or raw-data replacement.

```sh
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I docs/research/multi-asset-20261018/validate_multi.py --output /workspace/multi-asset-fresh
```

Choose a NEW output directory. The orchestrator refuses to overwrite completed
results. It checks frozen211 evidence files, immutable predeclared DSL hashes,
source-response hashes,10 relevant test commands, generated contracts, both
demerger components (including all10 public decile helpers and top-N), two new
dividend components, complete original2019–2020 JSON/Korean runs and independent
raw-source ledger, exact2020 technical projected NAV, ALL full-period requests,
and the preserved strict original LG rejection. Expected exit3 from a blocked
request is asserted as a rejection, never counted as successful execution.

Individual request (full years, no exclusions):

```sh
"$PY" -I scripts/research_workbench.py run --strategy config/strategies/research_size_deciles_2019_2025_event_deferred_v2.json --report-periods config/reports/research_continuous_2025.json --output-dir /workspace/deciles-2019-2025-fresh
"$PY" -I scripts/research_workbench.py issues --saved-run /workspace/deciles-2019-2025-fresh --output /workspace/decile-issues.json
```

The three broad2001–2025 DSL paths are pinned in `predeclaration.json`; remove
no securities, dates or costs. The original10T filter remains untouched; its
separate broad-universe experiments have their own names/fingerprints.

Common owners: `execution_scheduling.py`, PROJECT target-weight execution,
`research_spinoff.py`, stock-dividend subledger, selected observation preparation,
planned readiness and CURRENT/postprocess. Technical ranking always precedes
observation projection on the complete historical cross-section. The original
source-asset order is retained ONLY for the legacy floating-point reduction of
zero-padded contributions, not for survivor/price-availability filtering.

The legacy full-panel/projected momentum difference was4.44e-16 normalized NAV.
It was resolved by reproducing the original summation layout, without changing
pins/tolerance/selection/formulas. Exact old CSV SHA256 comparison is mandatory.

Recovery evidence: first dividend oracle attempt failed with
`KeyError: Timestamp('2022-01-31 00:00:00')`, exit1. That signal is a holiday.
The engine already schedules the next observed session; the independent oracle
now finds it using `searchsorted(..., side='right')`, preserving the original
signal and allocation, with no invented weekday or strategy-date change.
Original failed local output/logs are preserved outside the repository.
Legacy DART ZIP `.xml` members contain CP949 HTML; strict source-format detection
is used, not forced XML or silent decoding. Original archives/hashes are kept.

All official acquisition has ALREADY completed. Final validation makes ZERO
DART/KRX requests. Do not rerun retired source jobs. Source state and hashes are
under `evidence*/state.json`. Acquisition runs and limitations are in report.md.
The unsuccessful bounded2001 source run returned HTTP200 but no candidates:
exit1 is preserved, not proof that a historical action did not exist.

Final CI commit markers: `[stage16] [long-research] [multi-asset]`.
Four actual verification jobs must finish: stock-dividend-regression,
explicit-long-research, multi-asset-research, continuous-baseline-research.
The last job consumes the first job's SAME-RUN fresh artifact, preserving all
old continuous assertions outside the near20minute original job. No timeout
increase, removed checks or old-baseline substitution. Source jobs are retired
to their exact successful acquisition SHAs. Skipped source jobs are not tests.

Retained artifacts: stage16-continuous-research, explicit-long-research,
multi-asset-research and continuous-baseline-research; they include full
preflight/output/logs/runtime verification and browser proofs. Read the actual
run and commit rather than assuming a marker or successful upload proves tests.
