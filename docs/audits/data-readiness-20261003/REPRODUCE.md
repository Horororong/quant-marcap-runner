# 재현 명령

현재 설치된 고정 환경을 사용한다. source/manifest를 직접 수정하지 않는다. 각 명령은 유한 timeout이며 실패 결과 디렉터리도 지우지 않는다. 아래 output 경로는 기존 결과와 충돌하지 않는 새 경로다. 동일 로그의 반복 조회나 전체 백필 재시작은 필요하지 않다.

```bash
cd /workspace/quant-marcap-runner
QUANT_RUNTIME=/workspace/attachments/quant-report-kit-822c435f/runtime
QUANT_PY="$QUANT_RUNTIME/.venv/bin/python"
QUANT_AUDIT=docs/audits/data-readiness-20261003
QUANT_EVIDENCE=/workspace/attachments/data-readiness-20261003
timeout -k 5s 30s "$QUANT_PY" "$QUANT_RUNTIME/scripts/sandbox_runtime.py" verify
timeout -k 5s 60s "$QUANT_PY" scripts/export_strategy_dsl_contract.py --check
timeout -k 5s 120s "$QUANT_PY" scripts/test_requested_period_report.py
timeout -k 5s 60s "$QUANT_PY" "$QUANT_AUDIT/verify_primary.py" \
  --primary-dir "$QUANT_EVIDENCE/primary" \
  --state "$QUANT_AUDIT/main-status/selected_legacy_state.csv" \
  --viewer-zip /workspace/attachments/c15f0ef0-f065-4deb-a0cf-2cc18e723fd9/legacy-original-source-evidence.zip \
  --output-dir /workspace/attachments/primary-audit-reproduction-20261003
timeout -k 5s 180s "$QUANT_PY" "$QUANT_RUNTIME/scripts/sandbox_runtime.py" run \
  "$QUANT_RUNTIME/config/strategies/super_value_dart_benchmark_dsl.json" \
  --report-periods "$PWD/$QUANT_AUDIT/financial_periods.json" \
  --output-dir /workspace/attachments/checked-financial-reproduction-20261003
```

위 `primary` 디렉터리는 기존 `legacy-financial-body-evidence.zip`에서 추출한 12개 HTML이다. 출처 보고서는 저장소에 있고 본문 SHA와 viewer SHA를 검사한다. 새로운 실행환경에서는 결과 묶음의 `raw/primary`를 사용하고 원래 viewer ZIP 경로를 묶음의 `raw/legacy-original-source-evidence.zip`으로 지정한다. 본문 파일이 없으면 실행 실패가 정상이다.

14개 조건 진단의 exact command/종료코드/경과시간은 `preflight_matrix.json`에 있다. 각각 child timeout 60초, 전체 420초로 실행했다. 이 command 배열은 shell 문자열에 합치지 않고 subprocess 인수 배열로 실행한다.

```bash
timeout -k 5s 420s "$QUANT_PY" "$QUANT_AUDIT/replay_preflight.py" \
  --python "$QUANT_PY" --repo "$PWD" \
  --output /workspace/attachments/preflight-reproduction-20261003.json
```

실제 실패 경계 명령도 다음 기록과 같다. 각각 exit 3이 기대 결과이며 NAV/성과 보고를 생성하지 않았다.

```bash
timeout -k 5s 60s "$QUANT_PY" "$QUANT_RUNTIME/scripts/sandbox_runtime.py" run \
  "$QUANT_RUNTIME/config/strategies/kr_equity_report_validation_2019_2020.json" \
  --output-dir /workspace/attachments/four-period-gap-reproduction-20261003
timeout -k 5s 60s "$QUANT_PY" "$QUANT_RUNTIME/scripts/sandbox_runtime.py" run \
  "$PWD/$QUANT_AUDIT/inputs/size_2000.json" \
  --report-periods "$PWD/$QUANT_AUDIT/financial_periods.json" \
  --output-dir /workspace/attachments/kit-missing-year-reproduction-20261003
```

마지막 명령은 2000년 입력에 2020년 보고 config가 붙어 있으나 가격 preflight에서 먼저 실패한다. 따라서 이 결과는 **고정 kit 2000년 가격 부재 차단만** 증명하며 요청기간 일치 검사 통과를 증명하지 않는다. 이를 보고 기능 통과로 해석하지 않는다.

새 DART 접근은 `curl --connect-timeout 5 --max-time 10`에 timeout 15초를 적용했으나 환경 proxy connect 실패(exit 7)였다. Git fetch timeout 60초는 같은 원인 exit 128. 이미 확인한 차단을 재시도하지 않았다. GitHub native connector를 사용해 ref/tree/state/완료 job 로그를 읽었다. 한 원인에 대한 수정 후 재실행은 2회를 넘기지 않았다.
