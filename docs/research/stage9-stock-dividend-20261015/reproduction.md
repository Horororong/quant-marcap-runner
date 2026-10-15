# Stage 9 재현·재개 절차

- Repository: Horororong/quant-marcap-runner
- Branch: fix/financial-accuracy-20261014
- Remote baseline: ab4850193da1cd8bd4137a35ab978eb5f166f550
- Local baseline: 07d0f882d6e54929159fb1711c0e372f85a94e43
- Identical baseline tree: 7546db07b2930aa98627df6bd7b8e6ed5047f6ec
- Date: 2026-10-15 UTC
- Python: /workspace/financial-repair/runtime/.venv/bin/python
- kit_manifest: /workspace/financial-repair/runtime/kit_manifest.json
- Kit ID: 26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd
- This folder contains audit observations and a read-only arithmetic probe, not an event registry or a new backtester.

## Actually executed

From /workspace/quant-marcap-runner:

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify > /workspace/research-stage9-20261015/runtime-verify.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage9-stock-dividend-20261015/inspect_arithmetic.py /workspace/research-stage9-20261015/arithmetic.json
```

Both commands exited 0. Runtime verification status is ok. No internet installation or alternate Python.
The small arithmetic result was copied byte-for-byte into this folder. To reproduce without replacing preserved evidence, run the second command with a fresh output path, then compare with arithmetic.json.
The probe reads only the Stage8 3-row CSV. Decimal precision is 40.
It generates no NAV, metrics, strategy selections, registry records or official price certification.

Integrity observations in preservation.json were obtained by SHA256:
Stage8 manifest files, source parquets/inputs, protected financial results and pinned original-source archive.
Existing result files were also compared to their baseline Git blobs.
This is preservation verification, not another financial parsing/replay/independent audit.

## Official sources and access result

source_observations.json records exact URLs, document identifiers, accessible sections and limits.
stage9_details.csv separates ten official-evidence checks (2 PASS, 0 FAIL, 8 UNVERIFIED).
PASS applies only to the later proposed rate and fractional cash method.

Used approved web open/find/search and the explicit related-publication link in the 2020 AGM decision.
Searched bounded company/event terms for the declaration, ex-dividend notice, official price,
AGM result and delivery/listing; no bulk API collection.
The 2019 KIND wrapper lacks the original document body in accessible extraction.
KRX law open returned the tool acquisition error '(400) Timeout fetching'; the source-server HTTP status was not observed.
No retries of that request. A later or derivative rule is not substituted.
No full official HTTP response bytes were obtained; local summaries and their hashes must not be represented as raw official evidence.

Managed cloud networking policy was inspected using the cloud-environment-runtime skill:
restricted/enforced; KIND, KRX law, KRX data and DART are absent from terminal allowed hosts.
No runtime credential binding is configured. Approved web access to the supplied KIND external pages works.
No terminal bypass or new credential was used.
A first local path lookup used /workspace/financial-repair/review, which does not exist.
The actual preserved location is /workspace/financial-repair/evidence/review and the archive
/workspace/financial-repair/preserved-originals60.zip; no restore or download was needed.

## Guard and model findings

Read:
- scripts/corporate_action_registry.py (supported event types)
- scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py (event normalization, return guard, execution ordering)
- scripts/cash_share_exchange.py and docs/CASH_SHARE_EXCHANGE.md
- docs/HELD_RETURN_VALIDATION.md and docs/CORPORATE_ACTION_RECONCILIATION.md

No stock_dividend event/stock-entitlement lifecycle exists.
Immediate 1.05 equivalent gross holder arithmetic misses preserved -0.92% by 5.6125654bp.
54600 gives a rounded percentage match but is still an unverified base hypothesis.
Aggregate share-count and per-eligible-holder ratios are distinct; no tick rounding rule is selected.
The report proposes only the minimum contract needed after evidence acquisition.

## CI and unchanged execution

Inspected .github/workflows/test-strategy-dsl.yml and financial-accuracy-revalidation.yml triggers/branch guards.
No workflow changed or dispatched. No API/financial recollection, unit regression or E2E rerun.
The new docs/research/stage9-stock-dividend-20261015 paths do not match those workflow push filters.
Repair-branch pip-disabling guard remains unchanged.

No decile rerun: source/economic handling preconditions are not satisfied.
Retain the original Stage8 execution status, exit 4 and first 091990/2019-12-27/1bp failure.
Do not use a top1 result, shorter period, exclusion, override, relaxed tolerance or forward-fill as replacement.

## Exact resume boundary

First secure the original KIND 20191217000478 body/amendments, the 091990 ex-dividend official notice and price/base tape,
the then-effective KOSDAQ cash-market Article 17/appendix/tick rule, actual AGM result,
stock credit/additional-listing and fractional-cash records. Public access or purchasing requirements remain unresolved.
Do not infer actual delivery from an intended listing date.

Only after independent evidence review, implement a generic stock-entitlement lifecycle if justified,
test original holders, post-ex buyers, sale-before-credit and credit without double gains,
retain independent 1bp reference-price validation and separate holder-value ledger checks,
then rerun the unchanged Stage8 deciles_research_only.json for all 2019–2020.
No execution command is issued in this stage because its required preconditions fail.

Original Stage1–8 evidence and financial/PIT judgments remain unchanged; Stage6 investment approval stays 0/6.
