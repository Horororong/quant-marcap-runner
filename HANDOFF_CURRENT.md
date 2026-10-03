## 2026-10-03 requested-report kit delivery COMPLETE

Read docs/REPORT_DELIVERY_COMPLETION.md for the final evidence and resume paths.
Verified code: 822c435f4b6148c2832e12370a6ccb324a9e875f; full CI 37157470156 (test + offline CP311/CP312 passed).
Public delivery CI 37158824033 passed; all 24 assets anonymously downloaded with matching full-byte hashes.
Release: https://github.com/Horororong/quant-marcap-runner/releases/tag/quant-report-26e4ec02e569
Kit 26e4ec02e569, original ZIP SHA256 f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784.
Current Work runtime /workspace/attachments/quant-report-kit-822c435f/runtime is already freshly bootstrapped, verified and checked-report tested. Do not reinstall/replay completed work unless integrity or input changes justify it.
Main merge remains separate; preserve ongoing backfill/data updates. Long-history missing data and legacy independent audit remain gaps, not completed investment research.

# Current Strategy DSL handoff

## Custom financial rebalance continuation (2026-10-02 UTC)

Owner requests user-selected financial rebalance timing in the ChatGPT quant
project. New explicit `rebalance.dart_period_policy=latest_disclosed_quarter`
supports selected months 1..12 with last-session signals and unchanged next-close
lag. Default legacy policy preserves April/Q4, October/Q2 and existing strategy
fingerprints. New policy selects the latest disclosed report quarter per code,
with PIT differences/corrections, no cross-scope subtraction and no older-quarter
replacement for missing latest values. Source candidate/dependency completeness
remains mandatory; legacy financial quality is still incomplete.

Machine contract 22 / factor registry 7; local contract and synthetic routing tests
pass, including the unchanged eight strategy fingerprints and a real Samsung
Q1 original-source oracle for May 2020. Full checked NAV and complete remote CI
are required before deployment is declared complete. Local lacks KRX execution
dependencies; do not claim local full E2E. The current remote base is 5d627fe;
local data remains at e0fc32d. See `docs/FINANCIAL_REBALANCE.md` for exact staged
progress and final run/merge evidence. Existing ChatGPT runtime kits require
rebuilding with the new code and actual requested source coverage.

This handoff accompanies the Work continuation on 2026-10-01 (Asia/Seoul).
Read `AGENTS.md` and `BACKTEST_START_HERE.md` before changing or running a backtest.
GitHub refs, PR metadata and checks are authoritative for merge/CI status; this
file is an architectural checkpoint, not a substitute for checking live status.

## Checked-run integration checkpoint

This review unit starts from live main
`71b363ce722c37ace0cdc1466069bafcf19c1604` and integrates, in small commits:

1. PR #23 head `6bbfe22d8fa92383ae57e3d810d9bcd2e9af95cf` by native merge,
   preserving ancestry and shared planned corporate-action exposure checks.
2. Strict input validation from `88553d8e1994ba15a32d4adc3e6e6b7815418d88`.
3. Checked execution lifecycle from `b2d3631b8a2604c4f1ee04bb2283d3bac55caa13`.

The public CLI snapshots input, automatically gates preflight/report readiness,
then publishes validated NAV and CURRENT reports separately with atomic status
updates. Unknown fields, type coercion and malformed dates/numbers fail before
data access. Planned known-event exposure is a data gap before NAV; runtime
held-return/event guards remain enabled. Execution-only NAV is explicitly not a
formal report. Existing result directories are rejected without modification.

Storage update/observation workflows and source data are preserved. Generated
contracts are regenerated from the combined code, never by choosing one side
of a generated-file merge. Tests add checked-entry-point failure boundaries to
the existing strict, shared preflight, lifecycle and real KRX/DART suites.
Require complete final-commit CI before main deployment; inspect current refs
and Actions for actual deployment status.

Next development milestone is the versioned GPT sandbox offline kit, including
checksummed source coverage, pinned environment, Korean capability/DSL guidance,
result export and clean offline replay. Full data/code/package manifest and
arbitrary requested-window CURRENT reporting are still missing. No broad raw
archive/backfill deployment or new factor semantics are included here.

## Git growth review

The recent-storage fix is ported independently from tested commit
`155d08a3f4c6233168105a7baee05721050a40d4` onto main checkpoint
`b763c5ca903d652a815bbdbff6df978843a45c86`. It fixes rotation filename drift,
deterministic CSV/gzip output and timestamp-only churn while preserving real
rotation state, correction updates and existing files/history. It was deployed
at `9356fd3d05fc2c964f566283904fb7567cf36171`; full CI passed at
https://github.com/Horororong/quant-marcap-runner/actions/runs/36930068580
and its first main observation succeeded at
https://github.com/Horororong/quant-marcap-runner/actions/runs/36931922233.
That storage port did not deploy strict-input/orchestration, which are now in
the separate integration above. Broad-source archives remain separate.
Read `docs/GIT_STORAGE_AUDIT_20261001.md` for the audit.

Four-week read-only growth observation uses
`config/git_storage_baseline_20261001.json` and
`.github/workflows/observe-git-storage.yml`. Reports go to 90-day Actions
artifacts, never recurring Git commits; weekly full-history downloads stop
after October 29. See `docs/GIT_STORAGE_OBSERVATION.md` for metric limitations
and `docs/GPT_SANDBOX_ROADMAP.md` for the user's Codex-development/GPT-sandbox
execution goal, missing deployment units and the proposed offline-kit milestone.

The integration also preserves automatic backfill checkpoint
`8784c9aaab277a82c1b74ffda0bd3163c8892c79` (October 1 21:16 UTC): five new
2024 financial shards, historical mapping and collection state updates. The
storage changes do not revise those observations. Validate the final combined
commit against this current dataset, not only the earlier b763c5c snapshot.

## Goal and architecture

User goal: a Korean strategy request produces a Strategy DSL JSON and runs on
one generic engine, without creating strategy-specific Python for each request.

Korean request -> generated capabilities and JSON Schema -> deterministic aliases
-> Strategy DSL -> compiler/preflight -> registry providers -> target weights
-> PROJECT v2-16 execution -> daily NAV -> CURRENT postprocess.

The AI translation layer must inspect capabilities first. A complete arbitrary
Korean-language compiler/service is not implemented yet. Unsupported requests
must identify the missing capability instead of mapping to a similar strategy.

- Execution: `scripts/quant_backtest_template_PROJECT_v2-16_CURRENT.py`,
  execution engine `v2-16-exec-3`.
- Canonical metrics/charts: `scripts/quant_backtest_template_CURRENT.py`
  (currently `v2-17`) and `scripts/quant_backtest_postprocess.py`.
  The execution and performance template versions are distinct; do not rename
  one to pretend it has the other's implementation.
- Strategy schema: `1.0`; machine contract `20`; input-validation contract `1`; run orchestration `1`; factor registry `6`;
  preflight contract `3`; history-audit contract `1`; market-normalization contract `1`; corporate-action registry `5`.
- Generated contracts: `config/strategy_dsl_schema_v1.json` and
  `config/strategy_dsl_capabilities_v1.json`. Regenerate with
  `python scripts/export_strategy_dsl_contract.py --write`; CI uses `--check`.

## Review units and resumption

PRs #7-#19 are merged. The canonical-performance main commit is
`ba6c3772a57de3276f31f23247395d1877b13b73`. PR #18 full CI passed:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36824544209
Its own main workflow also passed:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36825497414
Check live refs/checks again before merging further work.

Canonical performance v2-17 is merged: PROJECT delegates metrics to CURRENT;
exact daily calendar checks, Sortino, Calmar, complete-month win rate and explicit
benchmark statistics retain the four periods and nine charts. See
`docs/CANONICAL_PERFORMANCE.md` for compatibility and verification scope.

PR #19's tested head is `2585d24a26a88c9d4707e1beb79ec2a228cafb7c`; full CI
passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36831237355
It is merged on main at `b39d06ced5c85b17deb10747811d91f8a9364af3`.
PR #21 is merged at `aae1bdde220aac2d519fcf845e544bb1f9fecebc`. Its full tested-head
CI passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36837202267
and main CI passed at https://github.com/Horororong/quant-marcap-runner/actions/runs/36839116922.
That milestone fixes KOSDAQ GLOBAL classification and restores 46,753
pinned original observations across 2022–2026, without revising existing values
or extending stored windows. SourceMarket preserves then-observed membership.
Machine contract 15 and market-normalization version 1 expose this boundary.
See `docs/KRX_MARKET_NORMALIZATION.md` and its complete repair evidence. Require
full current-head CI, including both real public modes and existing DART/KRX
E2Es, before merge. Check live refs; never force-push main.

PR #22 is merged at `b4c2b4ab7a6fec794766b447dc9470372dcab539`.
Its tested head `587733f7c3e1c5497d36cbb74b8bcb78b4a5bbca` passed all 30
workflow lifecycle steps at:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36847851288
Its own main CI and subsequent data-update workflow passed at:
https://github.com/Horororong/quant-marcap-runner/actions/runs/36849922237
https://github.com/Horororong/quant-marcap-runner/actions/runs/36849922248
The continuation base is `f77a4543d6e58e01c78bf234cc9347784b7b0e73`.

PR #23 adds known-event planned-exposure preflight, initially machine
contract 17 / preflight 3, with no NAV/metric change. It is included in the
checked-run integration above; the combined machine contract is 20. Relevant known gaps invoke
shared PIT selection and exact lag, including all ten deciles; unaffected
strategies retain their historical universe. Timing/lineage and real KRX
positive/negative tests are in `scripts/test_corporate_action_preflight.py`.
Require full current-head CI including that new step and existing DART/KRX
E2Es before deployment. Read live PR/checks for current status.
See `docs/CORPORATE_ACTION_PREFLIGHT.md` for scope.

Repository: https://github.com/Horororong/quant-marcap-runner

## Supported contracts

- PIT KOSPI/KOSDAQ equity universe; selected-month, last-session rebalance;
  equal-weight cross-sectional percentile ranking; explicit fixed-bps costs.
- Portfolio selection defaults to `top_n` with a positive integer position
  count. `deciles` partitions the full post-filter finite-factor universe into
  ten balanced contiguous groups; position count is omitted/null. D01 is best,
  D10 worst; tied scores are split explicitly by zero-padded Code order. Fewer
  than ten eligible codes fails at execution. Every bucket is a separate
  long-only portfolio with independent initial capital, same PROJECT execution
  and costs. CURRENT remains the sole metrics/chart path. Full policy and
  output schemas are in `docs/STRATEGY_DSL.md` and generated capabilities.
- KRX panel factors: market cap, amount, volume, close, shares as registered.
- DART value factors: standalone-quarter earnings/cashflow/sales yields,
  book-to-price. Profitability: `quarterly_roe`, `quarterly_net_margin`,
  `quarterly_ocf_margin`. Positive denominators only. April/October signals
  only; actual filing-date PIT; CFS first, OFS fallback; completeness gate.
- Momentum uses decimal exchange `ChangesRatio` compounded over fixed windows:
  3-1 = 63 lookback minus latest 21; 6-1 = 126 minus 21;
  12-1 = 252 minus 21; 12-0 = 252 with no skip.
- Volatility: sample standard deviation of the latest 63/126/252 decimal daily
  `ChangesRatio` observations multiplied by sqrt(252), including signal day.
  Missing per-code observations produce NaN, never fabricated zero returns.
- Optional benchmark: explicit source `index` plus symbol KOSPI, KOSDAQ,
  KOSPI200 or KOSDAQ150. Uses `data/indices/{symbol}.csv` Close on exact strategy
  dates; first date normalized to 1.0. This is a price index without dividends,
  not a total-return index. Preflight checks raw source prices without NAV.
- Verified merger continuity currently includes Korean Paper 002300 ->
  Haesung Industrial 034810, ratio 1.6661460, successor listing 2020-07-13.
  Verified split: EcoPro 086520, five shares per old share, trading resumes
  2024-04-25 after suspension 2024-04-09..24. Evidence and independent test
  are in `docs/HELD_RETURN_VALIDATION.md`. Registry version 4 also includes BYC
  001460 and BYC preferred 001465, each ten shares per old share, resuming
  2024-04-17; Namyang common 003920/preferred 003925 ten-for-one on 2024-11-20;
  APR 278470 five-for-one on 2024-10-31. See
  `docs/CORPORATE_ACTION_RECONCILIATION.md`. The registry is incomplete.

## Non-negotiable correctness rules

1. No fabricated missing history, future observations, current-universe
   reconstruction of historical membership, or silently shortened periods.
2. No filing data before its actual availability date; no post-signal values
   in factors. A close-t signal executes no earlier than a later session close.
   Existing positions/cash earn their returns through the execution date.
3. No generic PER/PCR/PSR/ROE substitution with standalone-quarter definitions;
   no ambiguous momentum skip convention chosen silently.
4. No generic held-stock NaNs replaced with zero. Suspension/merger continuity
   is allowed only for explicitly verified events and recorded in audit output.
5. No benchmark filling/interpolation. Unsupported definitions are capability
   gaps; missing or malformed source data are data gaps.
6. Strategy/provider code produces weights and daily NAV. Metrics and chat
   charts come only from CURRENT postprocess. Preserve the four standard
   analysis periods; a short execution E2E is not full-history validation.
7. Preserve working main, use a PR for each feature, require the complete CI
   including real-data execution E2E before merging a code feature.

## Verification and practical scope

Workflow: `.github/workflows/test-strategy-dsl.yml`. It includes syntax,
contract sync, aliases, preflight, benchmark cases, momentum, volatility,
provider extension, corporate-action continuity, synthetic PROJECT execution,
real DART PIT selection/formulas and real-data execution E2E. The decile tests
add independent partition/balance/disjointness, JSON Schema/runtime agreement,
provider-backed filter/rank sharing, no-lookahead, missing-factor intersection,
small-universe failure, t+1/cash timing, exact costs, blocked/missing prices,
verified successor continuity and no new partial outputs on execution failure.

Real DART/execution regression uses 2020-04-01 through 2020-11-30. This verifies
that path, not a full 2001-present performance report. Technical provider tests
use deliberately synthetic panels for independent formulas and no-lookahead;
never present their NAV as an investment backtest.

Runnable benchmark example: `config/strategies/super_value_dart_benchmark_dsl.json`.
Validate, preflight, then run with `--execution-only` for its explicitly short
research window. Request canonical performance only with actual source history
sufficient for the required standard periods.

Real KRX decile regression/example:
`config/strategies/kr_equity_size_deciles_research.json`, 2020-04-01 through
2020-05-08, explicitly signal-date Marcap >= KRW 10 trillion. It validates
narrow-window selection, t+1, equal initial holdings, exact cost deductions,
benchmark dates and artifacts against an independent raw-price oracle.
It does not claim broad-universe/full-history investment performance.

## History-audit checkpoint

Source diagnostics and reproducible commands are in `docs/KRX_HISTORY_AUDIT.md`.
The original 2020/2024 snapshots and pre-repair reconciliation remain archived.
The new snapshots in `docs/audits/krx-history-2024-repaired` and
`docs/audits/corporate-actions-2024-repaired` record the repaired 2024 source
hash, 657,429 observations and 2,797 codes. Both markets have all 244 sessions.
There are 257 >25bp price/reference candidates: six match consistent registered
splits and 251 remain unmatched. There are zero internal observation gaps and
140/52 censored starts/ends. These are source observations, not proven losses,
corporate-action counts or a completeness certificate.

Code 287410's former 89-session gap was a KOSDAQ GLOBAL ingestion omission.
The repair restores those actual rows and its 207 observations. Its later cash
exchange has verified legal completion and delisting, but actual payment and
applicable net proceeds remain unverified. The new generic cash-only contract is tested with synthetic payment
evidence; no production cash registry entry exists. The known gap blocks affected
holdings from 2024-10-23 instead of inferring receipt or excluding the stock.
See `docs/CASH_SHARE_EXCHANGE.md` and primary evidence there. The Aug 19 tax
disclosure is historical guidance, not proof of actual deduction or universal
net receipt. No production event or automatic tax model is added.

Public DSL runners now require ChangesRatio source data and validate each
pre-rebalance held asset's effective return against ChangesRatio/100 within
1bp before NAV/cost calculation. Missing/non-finite references or unresolved
differences fail; no automatic substitution by exchange returns. First buys
are cash beforehand; sells still require the prior holding's return to pass.
Verified merger disposal values have explicit override audits. Split event
returns are still reference-checked; wrong ratios do not bypass the gate.
Per-scenario/decile audits record checks and explicit override counts.
Low-level direct engine calls retain an optional reference matrix for backwards
compatibility and explicitly report enabled=false when it is absent.

The 25bp source-diagnostic threshold is distinct from the 1bp execution guard.
Neither certifies whole-market events, dividends or total returns. Rights,
spin-offs, unsupported events, missing sources and remaining history still need
verified handling. Do not silently exclude stocks that would fail the guard.

## Next development sequence

1. Verify live main and full current-head CI for the known-event preflight milestone.
2. Continue exact primary-source investigation of the 251 unmatched 2024 price
   candidates and remaining years. For 287410, verify actual cash-exchange
   actual payment and applicable net-proceeds evidence. The distinct cash
   receivable/payment contract now exists; replace the blocker with a reviewed
   executable entry only after evidence and actual proceeds/timing tests in both
   public modes. Do not reuse a stock split or merger approximation. Preserve
   all audit candidates and never use future survival as a strategy filter.
   The event registry, dividends and full historical coverage remain incomplete.
3. Expand factors with explicit accounting-period definitions (annual/TTM,
   quality/growth) and supported portfolio/asset contracts through registries.
4. Add a tested Korean request compilation interface using generated schema,
   preserving ambiguity/gap behavior. Benchmark total-return support requires
   a separate verified source and explicit return-basis contract.

Deciles, market-session validation and held-return checks are present. An arbitrary-language
compiler/service and complete historical corporate-action coverage are still
outstanding.

Annual/rolling performance and evaluated OOS reports remain follow-up work;
this milestone does not claim full-history corporate-action correctness.

## Offline sandbox distribution follow-up

The additive sandbox delivery contract is machine **21**, kit **1**; underlying
factor registry **6**, preflight **3**, execution **v2-16-exec-3** and CURRENT
**v2-17** remain unchanged. Read `SANDBOX_START_HERE.md` and
`docs/GPT_SANDBOX_ROADMAP.md` for current entry points and exact starter coverage.
Builder uses the shared preflight's actual signal dates when selecting DART
periods and technical warm-up years, including partial calendar-month windows.

Local evidence: 14 distribution boundary tests; clean offline CPython 3.11 and
3.12 real-source replays, each with all 73 artifacts byte-identical to the source
checked runner (DART 11, decile 53, verified split 9). Missing coverage, unresolved
Jeisys event in both selection modes, formal-report readiness, wrong packages and
missing kit sources are checked. No data/history deletion or collection-workflow
change is part of this delivery. Required complete CI has the existing full test
job plus both sandbox replay matrix jobs; verify live final-commit results before
integration. Generated kit archives are local ignored outputs, not Git data.

Next milestone: explicit requested-window research reporting in CURRENT. The
starter kit currently publishes validated short-window NAV, not new metrics or
an unrestricted natural-language compiler.
# Standing project instructions and legacy ownership (2026-10-01)

Read `PROJECT_CHARTER.md` immediately after `AGENTS.md`. The owner requires staged
GitHub commits and durable progress at each completed stage. Current priority is
safe resume and existing scheduled automation for the 2000–2014 legacy DART
backfill, followed by original-source parser investigation and independent audit.
The current stage, measured progress, workflow risks and exact next steps are in
`docs/LEGACY_BACKFILL_HANDOVER.md`. Earlier checkpoints below are historical.

## Legacy v5 live continuation (2026-10-02 UTC)

Remote main was verified at `df1ef362617d2fc9d89064dec56a7cf852cfe9a2`.
V5 deployment and its bounded 100-receipt bootstrap are complete; do not repeat
them. Code `993e13f` passed the full Strategy DSL CI (test and both sandbox replay
jobs) at <https://github.com/Horororong/quant-marcap-runner/actions/runs/36957000605>;
legacy pytest passed 55 tests in 2.66s. The subsequent data-only main commit had
no separate full CI run. Live verification preserves all 92,449 preceding
normalized rows literally and confirms 581 v5 rows against 32 parsed state
records. Mapped durable coverage is 1,301/115,020, pending 113,719; collection
and independent financial quality remain incomplete.

The interrupted local multi-tool call is not evidence of a pytest hang. An
isolated 45-second bounded parser test exits immediately because pytest is
missing; dependency installation did not complete. Do not wait indefinitely or
claim a local pass. Use per-file 60-second process limits, verbose node output
and 15-second faulthandler dumps after installing the required dependencies.
Inspect the existing original-source artifact/viewer pointers next; do not
re-download captured source merely because the session resumed. Full evidence
and continuation commands are in `docs/LEGACY_BACKFILL_HANDOVER.md`.

Initial source inspection now preserves twelve financial-body viewer routes
from the existing six-response artifact. Five downloaded native XML members
are truncated; the remaining member is structurally complete but already has
replacement characters. The additive bounded section capture uses the existing
audit workflow/lock, makes no repeated ZIP/TOC requests, and never certifies
financial amounts from HTTP success. Its eight offline transport tests pass
under a 30-second process limit. Require complete feature CI before main
integration, then inspect actual section evidence and record the live result.
Legacy pytest in both existing CI workflows now runs each file with a 60-second
limit and a 15-second faulthandler dump. See the legacy handover for budgets,
resume rules, exact source hashes and the remaining independent-audit scope.

## October legacy collection acceleration (2026-10-02)

The owner requested an October queue-processing target. The existing fast
workflow now proposes three bounded 2,000-receipt batches per day: 00:30,
08:30 and 16:30 KST. Extra batches run legacy only and skip dependencies/API
work when automatic pending is zero or actual start is November 1 KST or later.
Daily modern collection and all existing request/deadline/checkpoint/lock
boundaries remain intact. The 113,719 pending receipts imply at least 19
full-capacity days; this is capacity arithmetic, not observed throughput or
independent financial-quality completion. Gate boundary tests pass locally;
require complete feature CI and live main confirmation before deployment is
recorded as complete. Follow the final section of the legacy handover for
actual commit/run IDs and the remaining parser/source/independent-audit work.
# 사용자 실행 묶음 전달 — 진행 checkpoint (2026-10-02)

최신 사용자 요청은 실제 `quant-sandbox-*.zip` 전달이다. 현재 기준 원격 main은
`61250b33d84b02338bef4037f19169b336bb2185`; 기존 리밸런싱 전체 CI는 success다.
기존 3예제+custom May, CPython 3.11/3.12, 고정 wheels와 원본 데이터를 묶는
기존 CI의 명시적 export 경로를 준비했다. 생성·offline replay·다운로드는 아직
미완료다. `docs/SANDBOX_DELIVERY_CHECKPOINT.md`부터 재개하고 완료한 기능·백필을
반복하지 않는다. 최신 legacy processed 3,401/pending 111,619이며 품질 완료는 False다.


## 단계 2 완료: 실제 ZIP 생성·양 ABI offline replay (2026-10-02 UTC)

- 원격 source commit `b350b61e4db0c626e8533645a1a76d61d6ba0ae6`, PR #27, CI run `37075642412`.
- Kit ID `ee212da3e4a71bb7fa2261b45771156e2bf49b563419c8e639db45449cf694db`; `quant-sandbox-ee212da3e4a7.zip`, **291308667 bytes**.
  전체 SHA256: `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`.
- **CPython 3.11/3.12 모두 성공**. 각 ABI에서 4예제 **83개 artifact**가 원본 checked
  runner와 byte-identical이다. 두 ABI 간 fingerprint·NAV SHA256도 모두 일치한다.
  6개 missing/corruption/readiness 경계도 모두 통과했다.
- 12개 24MiB download segment와 ledger를 실제로 내려받았다. 전달 artifacts는
  30일 보관한다. 전체 Strategy DSL test job은 아직 실행 중이며 success로 기록하지 않는다.
- 다음: 저장된 ledger의 모든 SHA/길이로 ZIP 복원·무결성 검증, 로컬 offline
  bootstrap/verify, 전체 CI/PR 최종 확인, 실제 ZIP 링크 전달.
- Machine checkpoint: `docs/audits/sandbox-delivery-checkpoint-20261002.json`.


## 단계 3 완료: 다운로드 ZIP 복원·로컬 설치·전체 CI (2026-10-02 UTC)

- 12개 download segment의 길이·SHA256을 전부 직접 대조하고 원래 ZIP을 복원했다.
  전체 **291,308,667 bytes / SHA256 `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`**가
  원격 생성 ledger와 일치한다. ZIP CRC/중복·안전한 이름, bootstrap, 모든 내부 part 및
  code/data/wheel archive의 길이·SHA256도 통과했다.
- 실제 파일: `/workspace/attachments/quant-sandbox-delivery/quant-sandbox-ee212da3e4a7.zip`.
  Binary는 Git에 저장하지 않는다. 새 workspace라면 machine checkpoint의 artifact IDs와
  `download_manifest.json`을 사용해 이 ZIP을 복원한다. 임의로 재생성/재백필하지 않는다.
- 현재 로컬 CPython 3.12에서도 **IP socket/DNS를 차단한 상태로** 다운로드 ZIP의
  bootstrap 설치와 isolated `sandbox_runtime.py verify`를 실제로 실행해 모두 통과했다.
  원격의 양 ABI 4예제 replay를 로컬에서 중복 실행하지 않았다.
- 원격 source `b350b61e4db0c626e8533645a1a76d61d6ba0ae6`의 전체 CI **`37075642412` success**:
  test `111064819455`, 3.11 `111064819139`, 3.12 `111064819425` 모두 success다.
  원문 quarter oracle, 기존 DART/KRX/top-N/10분위/CURRENT/legacy regressions를 보존했다.
- ZIP은 코드·원본 데이터·고정 wheel과 4예제를 포함한다. CPython 3.11/3.12 Linux
  x86_64 glibc≥2.28용이며, 가격 연도는 2020/2024, DART는 예제용 2019/2020 기간이다.
  연구 NAV와 정식 CURRENT report readiness를 구분하고 필요한 자료가 없으면 data_gap이다.
- 사용자 전달 준비 완료. 다음은 PR #27 native merge와 원격 main 상태를 별도 기록하고
  이 실제 ZIP의 다운로드 링크를 제공하는 것이다. 생성 source revision은 이후 docs/main
  commit과 구분하며 이미 검증한 kit ID/bytes를 변경하지 않는다.


## 최종 전달 상태 / 중단된 원격 호출

실제 ZIP은 환경 재시작 후에도 보존됐다. 전체 SHA256을 다시 대조해 일치했다.
다운로드 파일: `/workspace/attachments/quant-sandbox-delivery/quant-sandbox-ee212da3e4a7.zip` (278 MiB).
GitHub 반영 호출은 `user cancelled MCP tool call`로 중단됐다. 직접 재조회한 PR #27은
**open / merged=false**, main은 `61250b33d84b02338bef4037f19169b336bb2185`다.
원격 main 반영 완료로 표시하지 않는다. 취소된 merge는 자동 재호출하지 않는다.
생성·전체 source CI·양 ABI 4예제 재현·ZIP SHA·로컬 offline 설치/검증은 완료됐으며
해당 실제 파일을 사용자에게 전달한다. 완료한 생성/검증/백필을 다시 실행하지 않는다.

## 모바일 다운로드 복구 (2026-10-03)

사용자의 모바일 screenshot에서 작업환경 경로의 다운로드 실패를 확인했다.
기존 ZIP을 재생성하지 않고 전달-only run `37080822925`에서 복원·SHA/CRC 검증해
artifact `11259265188`로 올렸다. 실제 HTTPS 다운로드와 내부 원본 ZIP 처리법은
`docs/MOBILE_SANDBOX_DOWNLOAD.md`를 따른다. 기존 test/sandbox replay는 skipped다.
취소된 PR #27 merge는 재호출하지 않았다. 이전 workspace 경로를 다운로드 링크로
반복 제공하지 않는다.


## 최종 완료: 실제 익명 다운로드 검증

- 전달 구현 commit `6d99daeff656042277bf75abff7adf73ce2a6f2d`, run `37081967124` / job `111084242487`
  **success**. Test/sandbox-replay jobs는 **skipped**다. 생성/백테스트/패키지 재현/백필을
  다시 하지 않았으며, 취소된 PR #27 merge도 재시도하지 않았다.
- 공개 release `quant-sandbox-ee212da3e4a7` (ID `402239704`, draft=false),
  원본 ZIP asset ID `606780546`, **291308667 bytes**.
- **Authorization header 없는 실제 GET**이 HTTP **200**을 반환했고, 전체 다운로드
  SHA256 `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`가 원본과 일치했다.
- 최종 고정 다운로드 주소: https://github.com/Horororong/quant-marcap-runner/releases/download/quant-sandbox-ee212da3e4a7/quant-sandbox-ee212da3e4a7.zip
  로그인이나 단기 서명 URL이 필요 없다. Actions artifact의 30일 만료와 별도인
  공개 release asset이다. 기존 workspace/서명/artifact 링크를 최종 전달로 재사용하지 않는다.
- 이 파일은 안쪽 ZIP wrapper가 없는 원래 실행 ZIP이다. ChatGPT 퀀트 프로젝트의
  Python 실행 가능한 대화에 **그대로 첨부**하고 기존 bootstrap/verify를 사용한다.
- Machine checkpoint: `docs/audits/public-sandbox-download-checkpoint-20261003.json`.
