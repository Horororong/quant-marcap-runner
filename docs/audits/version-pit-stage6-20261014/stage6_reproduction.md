# 재현과 안전한 재개

기준 remote SHA `9c35c36eb7a106065668beb8aef367811342c009`, 수집 remote SHA `c209a8f9b84a9de5afddbdcd4d3136d8533beb46`. 로컬의 commit 부모/작성자 차이로 commit SHA는 다르지만 remote 수집 tree `e91c4ac5d9832cace2be15b83fab9c1cbe9a018f`와 로컬 tree가 일치함을 확인했다. 결과 commit SHA·CI 실행 ID는 해당 브랜치 commit 및 실행 기록/체크포인트를 참조한다. `main`은 대상이 아니다.

## 동일 환경

```bash
cd /workspace/quant-marcap-runner
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/version-pit-stage6-20261014/test_stage6.py
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/dart-history-stage5-20261014/verify_responses.py
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/version-pit-stage6-20261014/audit_versions.py --output /tmp/stage6-review
```

kit ID `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`, source revision `822c435f4b6148c2832e12370a6ccb324a9e875f`, kit manifest SHA256 `a396ca2750bd55939b6915a90522a61a301e7b17ad095a6d8f4f422efa2a6018`, CPython 3.12/Linux x86_64. 표준 라이브러리와 고정 pandas/pyarrow/exchange_calendars를 사용했으며 정확한 버전은 `evidence/runtime-verify.json`에 보존했다. 인터넷 pip 또는 시스템 Python으로 감사 계산을 실행하지 않는다. CI의 시스템 Python은 동일 kit 운송과 기존 bootstrap에만 쓰이며, 계산과 DART 호출은 verify 이후 전용 Python으로 실행한다.

`source_manifest.json`에 12개 `.zip.b64`의 전송 SHA, **복원된 원본 ZIP SHA**, 원본 XML 회원 SHA를 기록했다. 감사 프로그램은 base64를 strict decode하고 ZIP SHA/CRC와 XML SHA를 모두 검사한다. 원문을 수정하거나 다시 다운로드하지 않는다. 새 DART 6건의 아티팩트 `11908710722` / run `38592615003` / SHA `38faf537dc9fa158146fe58072bf548be56a01983d910b792b51fea9234f1a15`도 별도로 보존했다. `evidence/response_manifest.json`의 API `raw/` 경로는 아티팩트 안의 경로이고, 저장소 재현은 `source_manifest.json`의 전송 파일을 사용한다.

현재 `collect_documents.py`는 보존된 6개 파일을 검증한 뒤 **0요청**으로 종료한다. 수집 완료 marker를 재사용해 다운로드하지 않는다. 5단계 응답 22개는 `docs/audits/dart-history-stage5-20261014/results/raw/`에 있다. 신규 `list.json` 호출이 필요하지 않다.

## 기존 60건 금융 재검증

로컬 originals40 `/workspace/financial-repair/evidence/review`, holdout20 `/workspace/financial-repair/heldout20/review`. 기존 원문 SHA/CRC 검증을 포함한다. 아래 명령은 **각 명령의 종료코드 0과 결과 파일을 확인한 뒤 순서대로** 실행한다. 서로 의존하는 replay와 revalidate를 병렬 실행하지 않는다.

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/financial-repair-20261014/replay60.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --runtime /workspace/financial-repair/runtime --output /tmp/stage6-replay60
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/financial-extraction-stage3-20261014/revalidate.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --replay /tmp/stage6-replay60 --output /tmp/stage6-financial
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/financial-extraction-stage3-20261014/forensic_compare.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --before-replay /workspace/financial-repair/stage3/restored-before-ci/replay60 --before-audit /workspace/financial-repair/stage3/restored-before-ci/results --after-replay /tmp/stage6-replay60 --after-audit /tmp/stage6-financial --output /tmp/stage6-financial
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/financial-repair-20261014/assert_regressions.py --replay /tmp/stage6-replay60 --output /tmp/stage6-financial/original_regressions.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/financial-extraction-stage3-20261014/assert_stage3.py --replay /tmp/stage6-replay60 --results /tmp/stage6-financial
```

Stage2 before 원본은 이미 보존된 `/workspace/financial-repair/stage3/restored-before-ci`를 썼다. 없는 경로를 임의 생성하거나 새로운 baseline으로 대체하지 않는다. `evidence/preservation_verification.json`에는 60개 replay SHA와 결과 8개 SHA가 있고 모두 기존 결과와 bytes equality를 검증했다. Stage4 재실행 결과 4개도 동일했다. 소스 60개는 `preservation60.json`, 이전 결과·운영 파서·Stage5 증거 및 2007 시세 103개 파일은 `preservation_inputs.json`에 핀했다.

## CI 및 장애

원래 workflow `.github/workflows/financial-accuracy-revalidation.yml`만 사용한다. branch/path 제한, read-only contents/actions, no workflow_run chaining, fixed-kit 검증을 점검했다. `[stage6-dart-doc-proof]`는 run_attempt 1에서만 6건 조회한다. `[stage6-krx-proof]`는 별도 공개 KRX 조사 최대 3요청이며 DART key를 받지 않는다. `[stage6-evidence]`는 보존 원문 독립 감사·테스트만 실행한다. 해당 특수 commit에서는 아티팩트 egress 장애가 확인된 기존 60건 restore job을 skip하며, 그 사실을 CI 판정에서 숨기지 않는다. marker 없는 기존 run은 원래 financial restore를 계속 사용한다.

첫 실패 run `38592204895`, job `115949696398`, HTTP 503 `Egress is over the account limit.`, exit 1. 원인 수정 없는 rerun 금지. 동일 kit release만 복원한 새 job의 성공 run `38592615003`, job `115951116574`; 12개의 당시 transport 테스트와 6개의 실제 호출 완료. 이후 새 27 테스트는 현 증거 기반 정책/전송 검사까지 추가한다.

최신 테스트 로그는 `evidence/test-logs/`, 로컬 수집·재대조·PIT 실행은 `/workspace/financial-repair/stage6/`에 보존했다. 최초 로컬 재대조 실패 exit 1은 `evidence/revalidation-initial-failure.log`, CI 실패 원문은 `evidence/initial-ci-failure.log`이다. GitHub blob 도구 중단 2회는 HTTP/exit 미반환이며 같은 도구를 재시도하지 않았다. lossless 텍스트 운송으로 원본 archive SHA를 유지했다.

최종 보고서와 새 감사 코드의 remote 게시는 완료되지 않았다. 원격은 마지막 확인 SHA `c209a8f9b84a9de5afddbdcd4d3136d8533beb46`이다. 대용량 tree 요청은 45초 미응답, 예상 tree GET 404이며 commit/ref 갱신은 하지 않았다. 이 작업의 local commit/tree가 실제 완료 산출물이다. 현재 브랜치의 local commit을 승인된 전송 경로 또는 작은 Git 객체 단위로 게시할 때 원격 최신 head를 다시 읽고 expected_sha lease로 갱신한다. 전체 2 MB tree 또는 중단된 blob 도구를 그대로 재시도하지 않는다. `[stage6-evidence]` commit 메시지로 게시하면 기존 artifact egress 복원과 새 네트워크 수집을 생략하고 고정 kit·원문 12개·154 테스트·정책 36개 및 결과 bytes identity부터 실행한다. DART 6건 수집은 보존 cache에서 0요청이므로 다시 받을 필요가 없다. 별도 KRX 공개 조사도 아직 실행하지 않았으며 `[stage6-krx-proof]`는 현재 API 역사 응답을 다시 조회하지 않는 최대 3요청 조사에만 쓰인다.

공식 거래일 파일 또는 증권 식별 근거를 나중에 확보하면 기존 자료를 덮어쓰지 말고 신규 evidence manifest에 URL/접수번호/시간/bytes SHA를 추가한 후 별도 판정한다. 일반 weekday 연산이나 패키지 달력만으로 `official_calendar=True`를 설정하지 않는다. 새 자료가 없으면 0/6 투자 승인 상태를 유지한다. 2,000건 재처리와 main 병합은 이 재현 과정에 포함되지 않는다.
