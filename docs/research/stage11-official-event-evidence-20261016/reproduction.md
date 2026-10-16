# Stage11 재현 및 복구 경계

기준 브랜치 fix/financial-accuracy-20261014.
원격 기준/확인 HEAD 5be8b720784f0f9a3817bdaee3fc2685a6905dc3,
원격 트리88675418f8cc7045590a65538057acb46e49982c.
시작 로컬 c8fb84cbd121c68e7cf2e678ceb03c8c8ca2858d는 직전 Stage9후속과 같은 트리였고 Stage10은 없었다.
기존 로컬 커밋과 파일은 삭제하지 않았다.

## Stage10 전체 확인

GitHub 전용 fetch_file에서 정확한 기준 SHA의 파일26개를 UTF8/base64로 읽고,
Git blob SHA1과 manifest25개 bytes/SHA256을 검증한 후 존재하지 않던 경로에만 복구했다.
JSON/보고서·재현절차·두 Python 코드 전체를 읽었다.
모든 CSV/gzip CSV를 전부 스캔하여 행/상태를 확인했다. stage10_review.json 참조.
diagnose.py 및 verify_results.py는 실행하지 않았으며 verification.json을 덮어쓰지 않았다.
대형 기존 표를 새 Stage11 커밋에 중복 게시하지 않는다.
원격 기준+새 파일로만 새 tree를 만들고 복구된 로컬 baseline tree가 원격과 같음을 확인한다.

## 환경과 실제 실행

원래 Python /workspace/financial-repair/runtime/.venv/bin/python,
kit_manifest /workspace/financial-repair/runtime/kit_manifest.json,
kit ID26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd.
새 인터넷 설치/의존성 변경 없음.

저장소 root에서 실제 실행:
```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify > /workspace/research-stage11-20261016/runtime-verify.json
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage11-official-event-evidence-20261016/calculate.py --output /workspace/research-stage11-20261016/calculations.json
```
둘 다 exit0. runtime status ok. 계산 결과를 이 폴더 calculations.json에 바이트 그대로 보존했다.
이는 기존4개 행의 Decimal40자리 산술이며, 선정/엔진/백테스트/NAV/성과를 실행하지 않는다.

재현 시 calculate.py의 --output은 새 경로로 지정한다. 기존 경로는 덮어쓰기를 거부한다.
결과의 SHA256을 artifact_manifest.json 및 보존 calculations.json과 대조한다.
스크립트는 Stage10 CSV의 기존 manifest를 먼저 확인하고 정확히4개 사건인지 검사한다.
배정률은 evidence.json의 기존 공식 이력에서 온다. 새 공식 기준가1개만 사용한다.
알 수 없는 기준가3개는 null로 남긴다. 가격·등락률 역산으로 기준가를 생성하지 않는다.
경제적 수익률은 실제 권리 입고/평가/현금 근거가 없으므로 항상 UNVERIFIED이며,
가정 등가가치 계산과 공식 기준가+2차 종가의 혼합 대조를 구분한다.

## 공식 원문/재사용 근거

evidence.json은 정확한 URL, 문서 식별자, 장·절·표·날짜·짧은 원문 셀 및 한계를 기록한다.
E11-01의 적용일과 셀트리온 기준가181000은 본문에서 직접 읽었다.
E11-02는 기존 Stage10 E10-01의 자본금 변동 및 OFS22 이익잉여금과 XI.2의 새 문맥 확인이다.
이미 Stage9~10에서 확인된 배당률/HC 승인/발행 이력은 해당 기록을 재사용한다.
후대 문서의 사실을 과거 신호일 정보로 사용하지 않는다.

웹 검색30개, 직접 open2개, find6개로 제한했다(access_log.json).
이전 실패 RefBon URL 직접 호출0, DART/KRX API0, 새 수집 코드0.
2020 KIND 뷰어는 본문 부재로 종료했고 반복 호출하지 않았다.
공식 원본 HTTP 파일/응답 SHA는 확보하지 못했다. 로컬 작성물 SHA를 원본 SHA로 표현하지 않는다.
부분 검색 실패를 공식 자료 부재로 단정하지 않는다.

## 판정/보존/CI

stage11_details.csv:4건×14항목=56,12P/0F/44U. 신규 공식 판정4개는CT2019에 한정한다.
공식 가격 원장 정확성0건 인증, 완전 사건 해소0/4, 투자 승인0/4, Stage6 PIT0/6 유지.
engine/script/config/data와 기존 감사 자료를 기준 tree/기존 SHA로 보존 확인했다.
518/64는 보존된 기존 결과이며 재파싱/재인증이 아니다.
원문60 기존 통제와 이전 실제ZIP/member 검증 기록을 유지했으며 새 수집·재감사를 하지 않았다.

financial-accuracy-revalidation.yml 및 test-strategy-dsl.yml 경로/브랜치 조건을 읽었다.
새 Stage11 docs/research 경로는 두 CI의 push 필터에 해당하지 않는다.
CI dispatch, collector dispatch, 새 회귀 테스트/10분위 실행 없음.
게시 직전 remoteHEAD를 다시 읽고 예상 기준과 일치할 때만 expected_sha/force=false로 갱신한다.
게시 뒤 ref/commit/tree/compare 및 actions/runs?head_sha=정확한SHA를 읽어 실제 반영과 CI 상태를 확인한다.
운영 게이트와1bp 허용오차를 변경하지 않는다.

정확한 재개점은 남은 공식 배당락/가격 원장, 유효 현물 규정/호가 이력,
권리 기준일과 입고·추가상장·단주 증거의 확보다.
이 자료 없이 새 이벤트를 등록하거나 주식배당을 stock_split으로 변환하지 않는다.
