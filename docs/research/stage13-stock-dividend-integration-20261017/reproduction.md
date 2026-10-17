# Stage13 再現 및 인계

브랜치 fix/financial-accuracy-20261014, 시작 원격c20e09aa705c96bfe67139c4aea27c15e347a5da.
로컬 원래56395108c4c689f19d7d26182e148ca3e1e8d6a9와 tree동일이었다.
로컬/원격 부모 이력이 다르므로 Git Data 게시 시 전체 tree 일치를 확인하고 원격
expected_sha lease/일반 fast-forward만 사용한다. 원래 로컬 커밋/ZIP/원문은 보존한다.
공식 자료 checkpoint 원격a7842f2c9401a421d71aeb13665a8bb6a5393c72는
로컬6fa95ab84207713d30a95f2941ec6dbe42a47728와 tree b94443f8576912f7fc9518f22ab78b1f92402795가 같다.
이 checkpoint CI39007075828은 원문 검증 거부로 failure다. 최종 엔진 CI와 혼동하지 않는다.

## 환경과 실행

전용 Python `/workspace/financial-repair/runtime/.venv/bin/python`,
원본 kit_manifest `/workspace/financial-repair/runtime/kit_manifest.json`,
kit26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd.
새 세션의 복원은 기존 restore_kit_only.py + bootstrap_quant.py의 고정된 원래 kit/
번들 wheel만 사용한다. 인터넷 pip/임의 버전/시스템 Python 계산 우회 금지.
현재 checkout 소스를 scripts 경로로 넣되 Python/패키지는 전용 kit를 사용한다.

저장소 루트에서 모두 새 출력 경로를 지정한다:

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage13-stock-dividend-integration-20261017/validate.py --output /tmp/stage13-new-validation
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage13-stock-dividend-integration-20261017/compare_snapshot.py --output /tmp/stage13-new-snapshot.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage13-stock-dividend-integration-20261017/preserve.py --output /tmp/stage13-new-preservation --originals /workspace/financial-repair/preserved-originals60.zip
```

validate.py는18개 실제 테스트 파일+생성 계약 검사19개 명령을 각각 isolated child/
150초 상한으로 실행한다. skip/defer 옵션 없음. 로그·실제 코드·시간·SHA를 저장하고
하나라도 실패하면 종료1이다. CI execution.json은 GITHUB_SHA와 Run ID를 기록한다.
pytest는 원래 kit에 없어 실행하지 않았다. unittest 및 기존 executable test 경로는 실행했다.

대표 독립 두 계좌 합성 장부를 저장하려면 기존 파일 없는 경로를 지정한다:

```bash
STAGE13_LEDGER_OUTPUT=/tmp/stage13-new-ledger.csv /workspace/financial-repair/runtime/.venv/bin/python -I -c 'import runpy,sys;sys.path.insert(0,"scripts");runpy.run_path("scripts/test_stock_dividend_execution.py",run_name="__main__")'
cmp /tmp/stage13-new-ledger.csv docs/research/stage13-stock-dividend-integration-20261017/independent_ledger.csv
```

이 CSV는 실제 사건/투자 결과가 아니다. fixed-bps 비용 계약 아래 수량·현금 oracle의
대표12일×Gross/Net24행이다. 나머지 실패 경계/복수 사건은 같은 시험 파일에서 검증한다.

## 실제 DART 병목과 native 진단

원래 명령은 scripts/test_dsl_execution_e2e.py를 -I child에서 runpy로 실행하는 것이다.
합성 자료로 교체하거나 삭제하지 않았다. 수정 전 cProfile 실행은 exit0이었고
profile_summary.txt에416,500,169호출/255.313초와 report_snapshots238.067초를 보존했다.
프로파일 원본 dart-before.prof는 외부 작업 경로에 있고 대용량 이진 프로파일은 Git에 중복 저장하지 않았다.
수정 전 정확한 adapter 바이트는 baseline_dart_adapter.py.txt에 있다. compare_snapshot.py는
실제2019Q3원자료64보고서/630행에서 같은 Python으로 전후 결과를 정확 대조한다.
타이밍은 환경 부하에 따라 달라지므로 pass 기준이 아니다. 회계 수치 정확 일치가 기준이다.

변경 전 최소 입력8회 no_timer exit0과 timer exit139의 실제 로그/소스는 diagnostics에 있다.
원래 조사에서는 CPython3.12.14, pandas3.0.6, pyarrow25.0.1에서 반복 비동기 스택 덤프만
추가했을 때 native fault를 관측했다. 손실된 전체 E2E 스택의 저수준 결함 바이너리는 미확인이다.
**알려진 비동기 타이머 재현을 일반 회귀/CI에서 재실행하지 않는다.**
기록된 native_minimum.py.txt는 조사 증거이며 자동 테스트가 아니다. 공급자 수준 추가 진단이
필요한 경우 별도 프로세스에서만 검토하고, 원래 git show의 로컬 baseline SHA 대신 보존된
baseline_dart_adapter.py.txt를 읽으면 원격에서도 같은 변경 전 코드를 확보할 수 있다.
안전한 동기 프로파일링/단계 로그는 이용할 수 있으며 의존성 변경은 필요하지 않았다.

## 공식 자료와 금지된 재수집

이전 Stage12 metadata98 및 KRX8응답/12field PASS는 원래 경로/manifest를 재사용한다.
compare_krx.py는 재수집 없이12필드를 독립 대조한다. CI에서 출력 JSON 바이트 cmp를 한다.
새 prices/list 호출0, 새 문서 요청은 미조회20201228900943 하나뿐이다.
CI39007075828/job117321614615 HTTP200/INVALID_DOCUMENT_XML/exit2.
상태 artifact12091442461 및 official_notice_attempt/run_state.json이 근거다.
안전 검증 실패 원문 바이트/원문SHA 없음; 문서 형식/내용을 인증할 수 없다.
동일 API 요청을 다시 실행하지 않는다. bounded-stage13-notice job은 완료 SHA와
run_attempt=1에 고정되어 최종 게시에서 수집0회다. 기존 Stage12 수집도 retire 상태다.

## CI와 보존

기존 `.github/workflows/financial-accuracy-revalidation.yml`의 stock-dividend-regression은
커밋 메시지 `[stage13]`와 브랜치/path 조건에서 실행한다. 기본 workflow의 인터넷 설치
경로/자동 데이터 갱신은 사용하지 않는다. 새 검증기 실제19개 명령, 원본64보고서 정확
전후 대조, 합성 장부 바이트 cmp, 기존 공식 KRX 비교 바이트 cmp,616개 보존 핀과
기존 verify_preserved60.py의 고정 원문/replay60 artifact 복원 검사가 있다.
GH_TOKEN은 artifact 읽기에만, 키는 과거 bounded capture의 격리 env에만 사용한다.
운영/PIT 게이트나 운영 registry CSV는 변경하지 않았다.

Stage12 frozen source manifest는 옛 코드의 기록이므로 새 구현에 덮어쓰지 않는다.
새 preservation_manifest는 기존 자료565개+옛 adapter 보존본1개+Stage12파일50개를 고정한다.
원래 adapter 소스만 의도적으로 변경됐으며 옛 바이트를 따로 보존했다. implementation_sha256.json은
현재 변경 소스의 핀이다. 금융518/64 및 원문60 검증은 보존 확인이며 신규 금융 인증이 아니다.

최종 게시 후 원격 커밋·변경 파일·tree를 읽고 해당 SHA의 실제 Actions Run/Job/아티팩트를
조회한다. skip을 PASS로 세지 않는다. 최종 SHA의 CI 결과는 최종 채팅 보고가 현재 상태다.
다음 작업은 실제 현물 원문/규정/권리평가/계좌입고·상장/단주·세무 근거 확보이며,
그 전까지 실제4사건/원래2019~2020전략 실행은 차단한다. 합성 통과를 투자 인증으로 바꾸지 않는다.
