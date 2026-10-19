# 실행·검증

검증된 kit의 PY만 사용한다. 인터넷 pip 설치/임의 버전 변경은 없다.
운영 데이터/원래 전략은 변경하지 않으며 결과는 RESEARCH_ONLY다.

```bash
"$PY" -I "$RUNTIME/scripts/sandbox_runtime.py" verify
"$PY" -I -m unittest discover -s tests -p test_financial_record_readiness.py -v
"$PY" -I -m unittest discover -s scripts -p test_research_incident_groups.py -v
"$PY" -I -m unittest discover -s scripts -p test_factor_code_refactor.py -v
"$PY" -I -m unittest discover -s scripts -p test_dart_snapshot_selection.py -v
"$PY" -I -c 'import runpy,sys;sys.path.insert(0,"scripts");runpy.run_path("scripts/test_research_planned_readiness.py",run_name="__main__")'
"$PY" -I -c 'import runpy,sys;sys.path.insert(0,"scripts");runpy.run_path("scripts/test_dart_dsl_super_value.py",run_name="__main__")'
"$PY" -I docs/research/source-readiness-20261019/reproduce.py --check
"$PY" -I scripts/research_workbench.py issues --saved-run "$EXISTING_FULL_PERIOD_RUN" --output "$NEW_ISSUE_OUTPUT"
```

CLI accepts saved preflight.json or readiness_incidents.json, avoids duplicate
envelopes, and never executes a new NAV to summarize old diagnostics. Full-period
issues/fingerprints and source SHA are in planned_symptoms pack/manifest. Raw
10136→key9926 and distinct-context episode9934→work-item5258 are separate metrics.
No group becomes a registered corporate action. An executed holding is never
inferred from the later potential path after an unresolved order/event.

reproduce.py uses immutable ZIP10, DART6reply, KRX4reply and one exact DART primary
section packs, checks their compressed/member/response SHA and original source
coordinates, independently normalizes equity with Decimal, and invokes the
existing common factor arithmetic. It uses the entire actual2010-04-30 observed
tradable cross-section for readiness counts, not two selected tickers as a
replacement universe. The existing provider coverage is invoked and its exact
partial-universe refusal retained. No provider/gate is patched for the diagnostic.

original named-primary attestation is record_attestations.json, limited to the
specific primary OFS equity at2010-04-30. Later dates/full correction history,
late CFS bytes/metrics, other fields and investment certification are excluded.
Same-day rejection, actual late attachment lower bound, future scope closure,
synthetic correction version order and missing-current no-stale-fallback are
tested separately. Missing evidence returns UNVERIFIED rather than financial0.

Source runs already completed:
- DART6 replies: code4d7cd140566b5e84b209c5e68ed6bb0f0e9f8f82 /39201336629
- KRX4 replies: coded438c6c6acbab2ede4679fef650f439d51b968f6 /39209874603
- DART1 exact node: code762ba9ed2dd05a9f08a342e525c33802dec8e127 /39210830639

All source jobs are retired to their completed SHA/attempt1. Do not repeat them.
Final CI uses markers [financial-backfill] [long-backfill] [source-readiness]:
existing financial22/518/64/60, existing2026 numerical pins/Korean JSON/independent
book/browser, plus actual source/readiness/current DART E2E. The 2026 rerun is
strictly preservation of an existing successful example, not new multi-security
completion or a substitute for the blocked original25year requests.

No new long strategy NAV is claimed. The next inputs are the exact official
rights/transfer/exchange/listing/cash documents listed in report.md. Keep the
original full periods, populations, selection, execution, costs and1bp guard.
Do not change goldens, exclude tickers, shorten dates, invent rights values or
reinvest unreceived proceeds. Candidate CI failure and operational use approval
are separate from arithmetic success.

The current code intentionally extracts the same factor arithmetic into a helper.
The OLD code-byte preservation manifest is not rewritten. Full financial replay
uses the explicit one-code-file equivalence contract:

```bash
"$PY" -I docs/audits/backfill-accuracy-20261018/validate.py --check \
  --approved-code-refactor docs/research/source-readiness-20261019/factor_refactor.json \
  --originals "$ORIGINALS60" --runtime "$RUNTIME" --output "$NEW_FINANCIAL_OUTPUT"
```

The original source/goldens are retained. The AST verifier rejects changed
equations, provider gates or any undeclared module change, then the unchanged
preservation owner checks848 exact original pins +1 explicitly declared new code
pin, as well as original60/518/64. Temporary derived manifest and the code-only
transition proof are stored separately; no historical manifest/data is replaced.
Without this explicit option, the original849-byte contract remains strict.
