# Codex development, GPT sandbox natural-language backtests

## Target and boundaries

User target: develop/configure the reusable system in Codex and ask ordinary GPT
with Python/file tools to run backtests in natural Korean. A separate web service
or bespoke strategy Python is not a prerequisite for this workflow.

Codex/GitHub owns versioned code, source collection, validation and release.
GPT interprets a request using frozen machine capabilities, emits Strategy DSL,
and invokes the same engine/CURRENT path in its sandbox. Numerical results come
from executable code, never from the language model's arithmetic.

Codex files, installed packages and GitHub secrets are not automatically shared
with a GPT chat sandbox. Sandbox network/package access, upload limits, RAM,
Python version and CPU/runtime limits must be checked for the actual session.
Another chat's conversation/process state is not visible to this repository.

## Facts at the storage integration checkpoint

Main checkpoint was `b763c5ca903d652a815bbdbff6df978843a45c86`: machine contract
16, registry 6, preflight 2, execution v2-16-exec-3, canonical performance v2-17.
The storage integration preserves those runtime contracts. Read current generated
capabilities/refs again when starting subsequent development.

Already in main:
- KOSPI/KOSDAQ historical PIT KRX adapter and generic PROJECT execution.
- Registered raw KRX fields, four fixed momentum definitions and three fixed
  volatility definitions; filters/ranks, top-N and ten-decile equal weighting.
- Seven DART factors: book-to-price, standalone-quarter earnings/cashflow/sales
  yields, quarterly ROE/net margin/OCF margin. DART signals are limited to April
  and October, with actual filing-date guards, CFS-first/OFS fallback and coverage.
- t+1-or-later close execution, explicit fixed-bps cost scenarios, exact sessions,
  verified event registry, enabled held-return guard and CURRENT performance.
- Generated capabilities/schema and real DART/KRX/execution regression CI.

The checked-run integration subsequently brings these existing review units
together on the current data checkpoint (machine 20, input validation 1,
preflight 3, run orchestration 1):
- Strict shared DSL input validation: commit `88553d8e1994ba15a32d4adc3e6e6b7815418d88`.
- PR #23 known-event planned-exposure preflight: head
  `6bbfe22d8fa92383ae57e3d810d9bcd2e9af95cf` (native merge preserves PR ancestry).
- Checked one-command run lifecycle: commit `b2d3631b8a2604c4f1ee04bb2283d3bac55caa13`.

Still separate: broad collection/checkpoint/source-archive work, commit
  `2e6f95c85422629b26ef48ef57ae81ae247a9fba`. Deploy this separately, after
  measuring raw ZIP sizes and planning persistence; default Git archiving could
  sharply increase storage. No backfill source/archive deployment is part of
  the checked-run integration.

## Gaps and dependency order (assessment)

| Priority | Gap | Required outcome |
|---|---|---|
| Completed prerequisite | Strict-input/shared preflight/checked lifecycle integration | Unknown conditions are rejected; one command produces explicit readiness/status; full CI and real-data regression are required before deployment |
| 2 | No portable sandbox distribution or complete reproducibility manifest | Versioned offline kit: code/capabilities/DSL, checksummed data, pinned packages/wheels, bootstrap, replay manifest and result export |
| 3 | Formal CURRENT reporting assumes four standard periods | Add an explicit requested-window research report contract in CURRENT, retaining existing four-period behavior; do not demand invented 2001 history for a valid 2015-start study |
| 4 | GPT interpretation needs a bounded, reviewable contract | Korean prompt-to-DSL guide/harness with registered aliases, visible interpretation, unsupported/ambiguous-case regressions and no approximation |
| 5 | Data completeness is uneven; legacy is not connected to public financial providers | Independently verify mappings, original/corrected filings, period/source coverage, CA/payment evidence and PIT bridge; publish usable ranges per capability |
| 6 | Broad raw collection is not a broad validated factor catalog | Annual/TTM period-defined provider, then growth/quality/ROIC etc.; independent formulas, actual availability, completeness and generated-contract tests |
| 7 | More historical universe/execution definitions are needed | Verified then-known industry/SPAC/preferred/IPO/status classifications; historical taxes/liquidity/quantity/cash and validated dividends/events |
| 8 | Research output and resource scaling are limited | CURRENT rolling/OOS/walk-forward/factor diagnostics, column/period-limited loading and measured sandbox runtime/RAM budgets |

Data collection and coverage/CA verification run in parallel with interface work.
Request completion or parser label PARSED_4F is not investment-usable PIT
coverage. Generic PER/ROE must not silently mean an existing quarterly factor.
Unsupported accounting periods and timing are capability gaps; missing required
source history is a data gap. Unknown event evidence continues to block affected
holdings without removing them from historical universe.

## Proposed next development milestone: offline sandbox kit v1

Prerequisite: the checked-run integration described above, with full CI on the
deployment commit. Package one **unchanged supported engine path** for a fresh sandbox.
Do not start by adding an unrestricted natural-language parser or many factors.

Concrete deliverables:
1. Code archive with `SANDBOX_START_HERE.md`, machine contracts, registered aliases
   and a single checked runner. No secrets, backfill scheduler or source downloads
   are required during a backtest.
2. Dataset manifest pinning commit/snapshot, source paths, byte SHA256, row schema,
   actual coverage and engine/registry/normalization versions. Separate code/data
   parts to stay within the actual upload limits; verify every supplied part.
3. Pinned dependencies and an offline install path for explicitly supported
   Python ABI/platform versions. Fail clearly on mismatch; never assume that a
   package installed in Codex exists in the sandbox.
4. A small Korean starter instruction: inspect capabilities, return unsupported
   definitions explicitly, emit and explain the DSL, then validate/preflight/run
   it. Ask only for material ambiguity such as accounting period or execution.
5. Results archive containing original/normalized DSL, manifest, readiness/status,
   daily NAV, selection/trade/event audits and CURRENT outputs when ready.
6. Clean-environment replay test with network disabled: same kit/DSL yields the
   same fingerprint, selections and NAV as the existing real DART/KRX golden
   runs. Missing/corrupt data, wrong package/runtime and unsupported requests
   fail before publishing a valid result.

Start with the real short-window DART/KRX E2E range already validated. Label
execution-only NAV as research NAV. It does not prove a full 2001-present report.
Expand dates/factors only when coverage and execution evidence are verified.
Requested-window canonical reporting is the following small contract change.

## Intended chat flow

```text
Codex develops/tests -> GitHub collects/verifies data -> versioned sandbox kit
  -> upload/load in GPT Python sandbox once per snapshot
  -> Korean request -> capability/ambiguity check -> Strategy DSL
  -> strict validation -> preflight -> generic engine -> validated daily NAV
  -> CURRENT report for explicitly supported mode -> export results + manifest
```

Initial setup can require loading code/data parts. After that, supported requests
should need only the natural-language strategy. A new Codex/main commit does not
silently update an existing GPT sandbox; load a new pinned kit when refreshing.
GitHub source collection remains persistent outside disposable chat sessions.
No requirement to transfer a GitHub DART API secret into the sandbox.

Long full-market/decile studies may exceed sandbox limits. First measure the
supported range; if resource constraints prevent execution, report the failure
and required resources rather than trimming the requested universe/period.
A remote job service is an optional later execution alternative, not the initial
implementation requirement for the user's chosen workflow.
