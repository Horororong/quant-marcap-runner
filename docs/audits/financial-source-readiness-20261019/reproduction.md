# 재현

최초 원격 main0cb8efc2dd1b58951b1e7183c1661977ca3b5cdc,
연구51358f619278811435fc622d296952638073d740을 실제 조회했다.
공식 증거 코드4d7cd140566b5e84b209c5e68ed6bb0f0e9f8f82 /
[성공 CI39201336629](https://github.com/Horororong/quant-marcap-runner/actions/runs/39201336629),
job117894750603이다. 이 수집 job은 완료 SHA로 봉인했고 다시 실행하지 않는다.

전용 kit SHA26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd,
Python3.12 고정 의존성만 사용한다. 아래 PY는 검증된 kit의 .venv/bin/python이다.

```bash
"$PY" -I "$RUNTIME/scripts/sandbox_runtime.py" verify
"$PY" -I -m unittest discover -s tests -p 'test_financial*.py' -v
"$PY" -I -m unittest discover -s scripts -p test_legacy_document_quality.py -v
"$PY" -I scripts/financial_validation_replay.py docs/audits/financial-validation-100-20261019 --output "$NEW_OUTPUT"
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-validation-100-20261019 --check
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-source-readiness-20261019 --check
"$PY" -I scripts/financial_source_readiness_audit.py docs/audits/financial-source-readiness-20261019 --check
```

NEW_OUTPUT는 존재하지 않는 별도 경로다.90초/문서·600초/실행을 유지하고6개의
유한 replay에서110원문을 재사용하며 HTTP fallback은 없다. 출력
subjects_v92.json.gz.b64의 해제 JSON bytes를 이 폴더 subjects_quality_v3와 대조한다.
파서9.2는 그대로이므로 과거 출력 파일 이름도 바꾸지 않는다. 판정 대상 데이터의
source_diagnostic_version은v3로 명시되어 v2와 혼동하지 않는다.

review_plan.json→controls.json이52건, fresh10_plan→fresh10_controls가 후속10건이다.
생산 파서 결과를 기대값으로 사용하지 않는다. 숫자 출처는 원문 ZIP SHA/memberSHA,
물리 table/row/column, 당기 계정·기간·단위와 연결된다. 원문과 이전 산출물은
financial-validation-100/source_manifest의 기존 여섯 pack을 참조한다.
source_manifest는 새 shadow subject만 참조하며 과거 manifest를 바꾸지 않는다.

보호 검증은 기존 financial_candidate_regression.py 경로에서 이번
legacy_document_quality.py까지 audit-reference에 명시적으로 복사한 뒤 실행한다.
기존 parser_candidate.json과22/518/64/60 통제는 재동결하지 않는다. CI artifact의
protected-financial-audit/commands.json, protected.json, provenance_delta.json과
canonical-source100-replay-NO-HTTP의 실제110재실행을 확인한다. CI 미실행/skip은
보존 성공으로 계산하지 않는다.

원문 SHA·소비 체크포인트·93게시 파일 해시는 reconciliation.json에 있다.
신규1701후보·199통제 PASS는 운영 데이터의 자동 게시나 backtest 승격이 아니다.
보호 ZIP/원문·구형 재무·상태 파일을 덮어쓰지 않는다. 공식 API를 다시 호출할
필요 없이 publication-proof pack의6응답과 state를 SHA 검증 후 재사용한다.
