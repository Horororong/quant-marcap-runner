# 검증 subset 게시와 문서별 격리 수집

기존 source-readiness 독립 통제199 PASS/53문서를 별도 source-linked 관측으로
게시한다. 기존93개와 필드·문서 중복0, 충돌0이다. 보류28개와 coverage27 FAIL/
1 UNVERIFIED는 held_fields.json에 보존한다. 문서 전체 PIT·투자 승인은 아니다.
기존v5/314파일/옛상태/518/64/60/성공 NAV와 기존93개는 수정하지 않는다.

문법9건은 문서 전체 격리, 숫자·기간·scope·단위가 독립 입증된 다른 문서는
진행 가능하다. CFS member/version 미인증과 OCF 충돌은 해당 source/field 보류다.
같은 문서 안의 영향이 분리되지 않으면 문서 전체를 보류한다. 출처 해시/공통
schema 검증 실패, 서비스 오류800/HTTP/worker/시간 한도/lease 충돌은 전체 중지다.
미추출은0이 아니며 실제 재무표 부재/정정 이력 인증으로 바꾸지 않는다.

신규 계약 limited-source-observation-v1은100문서/회, KST 하루1회, 최대3회/
예약300문서,90초/문서·600초/실행을 고정한다. 기존2000경로와 v5/현대 fallback은
없다. 매회 HTTP 전에 selection·20개 primary 검토 규칙·소비 lease를 main에
보존한다. 이후 원문·후보·격리·품질 manifest와 SHA를 durable blob+git tree에
연결한 뒤 최종 checkpoint를 commit한다. 게시 실패면 RUNNING lease가 남아
후속 실행을 차단한다. 재실행 attempt도 거부하며 실패 접수번호를 교체하지 않는다.

원문 수집과 금융값 게시 ledger는 다르다. 신규 후보는 전부 미검토 HOLD이고
자동 metrics 게시가 없다. 첫 실행 후 WAIT_FIRST_REVIEW 상태에서 멈추며 독립
원문 통제가 끝난 뒤에만 나머지2회 예약이 허용된다. schedule은05:17 KST,
만료2026-10-24 08:59:59 KST다. 미실행 회차는 성공이 아니다. 제한 관찰 종료 후
자동 대량 복귀는 없다. 원래 config/financial_backfill_rollout.json의 HOLD는
구형 canary/legacy 경로에 계속 적용되며 새 제한 계약과 혼동하지 않는다.

동시 main 현대재무 커밋은 보존한다. 커밋 직전 main과 원문 queue·상태·코드
blob SHA를 확인하고 non-force ref 갱신을 사용한다. 다른 커밋과의 충돌만1회
검사 후 통합하며 통신/권한 실패를 반복하지 않는다. 최신 실행·게시 상태는
data/status/dart_legacy_limited_resume_v1.json과 해당 Actions를 따른다.

첫 실제 실행·독립 감사·예약 활성화 결과는 실행 후 별도 실행 근거에 기록한다.
계획과 코드 통과만으로 수집 완료·금융 정확성·전체 인증을 선언하지 않는다.

롤백은 자동 수집을 먼저 HOLD하고 이 최소 패치만 revert한다. 새 source-linked
관측은 기존값을 덮어쓰지 않았으므로 증거와 게시 ledger를 보존한다. v5 대량
수집으로 자동 복귀하거나3998격리를 초기화하지 않는다.
