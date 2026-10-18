# Reproduce the explicit long execution experiment

Use only the verified dedicated offline-kit interpreter. Local execution used
`/workspace/financial-repair/runtime/.venv/bin/python`; exact kit identity and
package versions remain in the Stage16 runtime verification and CI artifact.
No network, pip or source collection is needed for validation.

```bash
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I scripts/research_workbench.py examples
"$PY" -I scripts/research_workbench.py check \
  --strategy config/strategies/research_size_top1_2001_2025_deferred_v1.json \
  --output /tmp/long_readiness_new.json
"$PY" -I scripts/research_workbench.py run \
  --strategy config/strategies/research_size_top1_2001_2025_deferred_v1.json \
  --report-periods config/reports/research_continuous_2025.json \
  --output-dir /tmp/long_run_new
"$PY" -I docs/research/long-execution-20261018/verify_long_ledger.py \
  --run /tmp/long_run_new --output /tmp/long_independent_new
```

Every output path must be new. Old successes, failures, original inputs and
financial audit files must not be replaced. The command uses CURRENT for all
metrics and interactive reporting; the independent ledger is an audit only.

Full fresh release validation, identical to the additional CI job:

```bash
"$PY" -I docs/research/long-execution-20261018/validate_long.py \
  --check --output /tmp/long_validation_new
```

It executes the JSON and controlled Korean full25year requests, checks all
new numeric pins, independent raw-source selections/orders/quantity/cash,
the actual original2019–2020 ten portfolios through selected projection,
old numeric pins, source response hashes, frozen Stage16 evidence and
518/64/original60 preservation. No requests are made by this validator.
The old financial regression job additionally replays original DART E2E,
all original successful strategies and frozen151file comparisons.

Korean input uses the explicit opt-in model flags; without them the original
fixed-lag strategy remains blocked:

```bash
"$PY" -I scripts/research_workbench.py run \
  --request '기간:2001-01-01~2025-12-31;시장:코스피·코스닥;필터:시가총액>=10조원;팩터:시가총액 높은;포트폴리오:상위1개;리밸런싱:4월말;체결:1거래일뒤종가;비용:수수료1.5bp,매도세15bp,스프레드3bp,슬리피지5bp;벤치마크:코스피' \
  --research-model-from config/strategies/research_size_top1_2001_2025_deferred_v1.json \
  --execution-contract-from config/strategies/research_size_top1_2001_2025_deferred_v1.json \
  --report-periods config/reports/research_continuous_2025.json \
  --output-dir /tmp/korean_long_new
```

The controlled factor label differs (`size` versus `Marcap`); selections must
match exactly after that registered label mapping, with no numeric tolerance.
NAV, target weights, metrics and canonical NAV must match byte-for-byte.

In CI, `explicit-long-research` runs alongside the existing
`stock-dividend-regression` on a `[stage16] [long-research]` commit.
Preinstalled Chromium runs `scripts/verify_research_dashboard.cjs` against
the completed full25year HTML. It is not installed from the network.
Artifacts retain full reports, daily ledgers, orders, controls and screenshots.
Local Chromium remains blocked by the sandbox; no repeated local launch or
network workaround is part of this reproduction.

Do not rerun the source collector. Its completed one-attempt job is pinned
to remote `370c1fff064dcaa04be66f7374003864635fd2c1`; the four original
responses and SHA256 are already preserved under `evidence/` and
`source_manifest.json`. The bounded Actions job39087969598 made4public
requests with0retries. The subsequent implementation commit is remote
`0acfed11e5a4af6ded40319807dd47b48aab9d2a`.
