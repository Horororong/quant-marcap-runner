# quant-marcap-runner — Repository Agent Instructions

This repository is a reproducible quantitative-research and backtesting system.

## Owner's failure-recovery instruction (2026-10-06)

On command/tool failure, inspect the last verbatim error, actual exit code (or
explicit absence of one), and completed steps before choosing recovery. Only
transient communication failures receive bounded retries; do not repeat the
same failure without fixing its cause. Locate the original dedicated Python and
kit_manifest, and require `sandbox_runtime.py verify` before calculation. No
internet pip, arbitrary package changes, or ambient/system Python calculation
fallback. Preserve completed collection/backfill/commits and resume incomplete
steps only. Distinguish attempted commands from actual verified outputs. Do not
hide failures by changing data, periods or formulas. If blocked, persist the
error, completed scope, preserved artifacts/checkpoint and exact resume command.
The original kit's stdlib-only bootstrap may restore its pinned offline runtime;
it does not authorize strategy execution outside that verified runtime.

Read `PROJECT_CHARTER.md` before other project documentation. It preserves the
owner's standing project instructions, including the legacy DART backfill and
independent source-audit requirements. Follow it in every new task/session.

The long-term target architecture is:

Korean natural-language strategy request  
→ supported-capability inspection  
→ deterministic Strategy DSL  
→ validation / preflight  
→ registered factor and data providers  
→ generic execution engine  
→ daily NAV  
→ canonical performance postprocess.

The goal is to support new strategies primarily through reusable DSL capabilities, registries, providers, and configuration rather than creating a new strategy-specific Python backtester for every request.

---

## 1. Required reading order

Before modifying or running the backtest system, read:

1. `AGENTS.md`
2. `PROJECT_CHARTER.md` (standing owner instructions)
3. `BACKTEST_START_HERE.md`
4. `HANDOFF_CURRENT.md`
5. `PIPELINE.md`
6. `docs/STRATEGY_DSL.md`
7. documentation relevant to the task
8. the actual implementation and tests

For performance/reporting work, also read:

- `docs/CANONICAL_PERFORMANCE.md`

For KRX historical-data work:

- `docs/KRX_HISTORY_AUDIT.md`
- `docs/KRX_MARKET_NORMALIZATION.md`

For held-return / corporate-action work:

- `docs/HELD_RETURN_VALIDATION.md`
- `docs/CORPORATE_ACTION_RECONCILIATION.md`
- `docs/CASH_SHARE_EXCHANGE.md`

`HANDOFF_CURRENT.md` is a checkpoint, not live GitHub state.  
Always verify the current branch, commit, PR and CI status before relying on handoff metadata.

---

## 2. Source of truth hierarchy

For current behavior, prefer:

1. executable code and generated contracts
2. automated tests
3. current CI
4. current design documentation
5. `HANDOFF_CURRENT.md`
6. historical comments or legacy strategy scripts

Do not change version identifiers or documentation merely to make inconsistent implementations appear compatible.

When documentation and implementation disagree, investigate the discrepancy and make the contract explicit.

---

## 3. Strategy DSL first

For a Korean-equity strategy request, inspect:

`config/strategy_dsl_capabilities_v1.json`

before implementing anything.

Natural-language translation must use registered capabilities and aliases.

Generated machine contracts:

- `config/strategy_dsl_schema_v1.json`
- `config/strategy_dsl_capabilities_v1.json`

They are generated from code.

Regenerate/check them using:

```bash
python scripts/export_strategy_dsl_contract.py --write
python scripts/export_strategy_dsl_contract.py --check
```

Do not manually introduce schema/runtime drift.

If a requested strategy is already representable by the DSL, do not create a new strategy-specific Python backtester.

Create or modify reusable capabilities instead when functionality is expected to be reused.

Unsupported definitions must remain explicit capability gaps.

Never silently map an unsupported strategy to a merely similar supported strategy.

---

## 4. Standard DSL execution path

The normal Strategy DSL workflow is:

1. inspect capabilities
2. generate Strategy DSL JSON
3. validate the JSON
4. run preflight
5. execute only if preflight succeeds
6. produce daily NAV
7. pass daily NAV through canonical postprocessing

Validation:

```bash
python scripts/strategy_dsl_runner.py <strategy.json> --validate-only
```

Preflight:

```bash
python scripts/strategy_dsl_preflight.py <strategy.json>
```

A failure must preserve the distinction between:

- `capability_gap`
- `data_gap`

Do not bypass preflight merely to obtain a numerical result.

---

## 5. Determinism and reproducibility

The same:

- Strategy DSL
- source data
- engine version
- registry versions
- normalization contracts

must produce the same result regardless of the reasoning model or conversation that initiated the run.

Preserve and use strategy fingerprints and execution-contract versions.

Do not allow LLM reasoning to perform hidden numerical calculations that belong in deterministic code.

Investment metrics reported as backtest results must come from the repository's executable calculation path.

---

## 6. Point-in-time correctness

Point-in-time integrity is non-negotiable.

Never:

- use future observations
- use filing information before its actual availability date
- reconstruct a historical universe from today's listed securities
- silently drop delisted/disappeared securities
- fabricate missing history
- silently shorten the requested period
- convert missing held-stock returns to zero
- forward-fill unsupported source gaps merely to keep a backtest running

For accounting data, fiscal-period end is not sufficient evidence of availability. Use actual filing-date availability according to the repository contract.

For KRX equities, use historical PIT panel data from the repository rather than current constituent lists.

`KOSDAQ GLOBAL` historical normalization must follow the repository's market-normalization contract and preserve original source classification where required.

---

## 7. Signal and execution timing

Do not introduce same-close look-ahead.

Information observed at a close cannot be assumed executable at that same close unless the contract explicitly proves it was available before execution.

Existing positions and cash must earn the appropriate return through the execution date according to the execution engine.

Rebalance dates, signal dates and execution dates must remain explicit and testable.

---

## 8. Missing data

Missing data is not permission to invent data.

Never replace missing observations with:

- zero returns
- estimated prices
- fabricated accounting values
- silent interpolation
- an unrelated proxy

unless an explicit, documented contract authorizes that exact treatment.

If required data is missing, either:

- classify it as a data gap,
- add a proper reusable collection path,
- or use an explicitly identified exploratory proxy whose limitations are clearly separated from canonical results.

---

## 9. Corporate actions and held-return validation

Corporate actions must be evidence-based.

Do not infer split, merger, exchange or cash consideration treatment simply because a price discontinuity resembles an event.

Only verified events may enter executable production registries.

Known unresolved corporate-action gaps must block affected execution according to the repository contract rather than being hidden through universe exclusion.

Held-stock effective returns must satisfy the repository's reference-return validation contract before NAV is accepted.

Do not bypass a failed return guard simply to obtain a complete backtest.

---

## 10. Performance metrics have one canonical owner

Strategy/provider/execution code should produce portfolio weights, execution outputs and daily NAV.

Do not implement duplicate CAGR, MDD, Sharpe, Sortino, Calmar, recovery-period or chart logic in strategy-specific code.

Canonical performance is owned by:

- `scripts/quant_backtest_template_CURRENT.py`
- `scripts/quant_backtest_postprocess.py`

The PROJECT execution template and CURRENT performance template serve different purposes.

Do not rename or version-bump one merely to pretend the implementations are identical.

Always inspect the current contract/version constants rather than assuming a version from old conversation history.

---

## 11. Backtest output

Canonical backtests should preserve:

- daily NAV
- gross/net distinction where applicable
- explicit costs
- requested benchmark definition
- exact analysis periods required by CURRENT
- canonical metrics output
- canonical chat/report payload

Do not present a short E2E test window as a long-horizon investment-performance study.

Synthetic test NAV is test evidence, not an investment result.

A price-index benchmark must not be described as a total-return benchmark unless the source contract actually includes distributions.

---

## 12. Costs

Transaction costs must be explicit.

Do not silently assume zero cost when evaluating an investable strategy if the strategy contract requires costs.

Commission, taxes, spread, slippage and market impact must follow explicit Strategy DSL / execution assumptions.

When changing cost handling, add exact regression tests for NAV impact.

---

## 13. Tests are part of the implementation

Every reusable feature change should include tests covering its failure modes and contract boundaries.

Relevant test areas include:

- DSL schema/runtime agreement
- aliases
- preflight
- factor providers
- no-lookahead
- missing-data handling
- PIT DART behavior
- universe filtering
- rebalance timing
- transaction costs
- decile partitioning
- benchmark alignment
- KRX session coverage
- market normalization
- corporate actions
- held-return validation
- PROJECT execution
- canonical performance

Do not weaken or delete a correctness test merely because a new implementation fails it unless the underlying contract is intentionally changed and documented.

---

## 14. CI

The primary Strategy DSL workflow is:

`.github/workflows/test-strategy-dsl.yml`

Before considering an engine/DSL/data-contract feature complete:

1. run the most relevant local tests
2. run generated-contract checks
3. run applicable integration/E2E tests
4. verify the complete required CI on the final commit

A narrow unit-test pass is not sufficient evidence that a backtest-engine change is safe.

Real-data E2E failures must be investigated rather than replaced with synthetic-only validation.

---

## 15. Change discipline

Preserve a working `main`.

Prefer small, reviewable changes with clear contracts over large rewrites.

Before changing architecture:

1. locate the current owner of the behavior
2. identify dependent contracts
3. identify regression tests
4. make the smallest coherent change
5. test it
6. update generated contracts/documentation if necessary
7. verify regression behavior

Do not duplicate an existing subsystem without first determining whether the proper solution is to extend it.

Avoid adding compatibility hacks that permanently create two sources of truth.

---

## 16. Repository data first

Before obtaining external data, check whether the required dataset already exists in the repository.

Relevant sources include:

- `data/krx_equities/yearly/`
- `data/financials/`
- `data/indices/`
- `data/fx/`
- `data/macro/`
- ETF/proxy stores and their registries

Existing repository PIT data should be preferred for reproducible research.

If a reusable dataset is genuinely missing, integrate it through an appropriate collection pipeline rather than downloading an untracked one-off file solely for a single backtest.

Never commit API secrets.

---

## 17. Natural-language interface goal

The eventual user experience should allow requests such as:

> 코스피·코스닥에서 시가총액 하위 종목을 고르고 모멘텀과 가치지표를 합산해 상위 20개를 분기마다 리밸런싱해서 백테스트해줘.

The system should determine whether this is supported by inspecting machine-readable capabilities.

If supported:

natural language  
→ deterministic canonical interpretation  
→ Strategy DSL  
→ validation  
→ preflight  
→ generic execution  
→ canonical results.

If unsupported:

return the exact missing capability or data requirement.

Do not guess.

---

## 18. Definition of done

A feature is not complete merely because code executes.

It is complete when:

- its contract is explicit
- deterministic behavior is preserved
- PIT/no-lookahead requirements are satisfied
- failure behavior is explicit
- required tests exist and pass
- generated contracts are synchronized
- relevant documentation is updated
- existing supported strategies still pass regression checks
- required CI passes on the final code state

Correctness and reproducibility take priority over producing a backtest number.
