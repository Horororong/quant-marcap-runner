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


## 첫 실제 관찰 완료와 제한 예약 승인

PR43 main 코드f754b3eeb17493bd3254303e3a2ec52990f76ac7의 실제 CI39248507369는
기존110원문/199독립통제/22회귀/518·64·60 보호 후 첫 실제 수집을 실행했다.
HTTP 전 lease/100목록 commit5d6413f83dfda342f29b756e95a221e6fff3b572,
selection SHA ed377b007fa475fa7a5c03baa643a67eda765d43f899837440c161e63b74e401.
20100331001758~20100331001937의 고정100문서를510.693초에 처리했다.
4F84/부분1/SOURCE_GAP14/EXTRACTION_FAILED1, 추출85문서/1363후보다.
모든 ZIP100의 SHA·CRC와 source/quality manifest를
f391dc01355b4eeb26ee0f209fa97e5f5ef43900에 실제 보존했다. source pack5개를
Git tree에 연결하여 단순한 도달 불가 blob/일시 artifact만 남기지 않았다.
새 후보의 운영 금융값 게시0, 미검토 후보는 계속 HOLD다. 정상 수집과 숫자
정확성·PIT는 서로 다른 상태다. 첫 source job도 실제 SUCCESS다.

100문서 모두 원문 ZIP이 있으며 원문 아카이브 손상0/서비스·공통 guard failure0다.
SOURCE_GAP14문서에는15개의 XML markup 오류 member가 있었고 정상 본문이
있어도 보수적으로 해당 archive 전체를 격리했다. 세 표본의 실제 본문 값이
있음을 독립 확인했으므로 실제 재무자료 부재라고 부르지 않는다.01822는
primary table header 거부로 미추출,01875는 BS2009-03-31과 연간IS2009-12-31
표기의 차이가 있어 부분 추출이다. 이 문서의 새 검토2항목은 보수적으로
UNVERIFIED로 고정했으며 원문 날짜를 수정하지 않았다.

결과 전 고정 primary20와 사전 정의 상태별 보강3, 합계23문서의 OFS 자본총계/
당기순이익46개를 raw Grid로 먼저 확인했다. 합병단순합산·부문표·배당 요약·EPS·
전기 열은 택하지 않았다. 원/백만원 요약을 혼합하지 않고 primary 원 단위를
사용했다.01857의9개월FY(2009-04-01~12-31)는12개월로 늘리지 않았다.
controls SHA1c00ca6209151ed99929a51b8d50b3a70223ac76ead12ebf0df1dbefb165555a를
후보 금액을 열기 전에 동결했다. 결과38 PASS/0 FAIL/8 UNVERIFIED,
coverage38 PASS/6 FAIL/2 UNVERIFIED다. 전체 문서 PIT/1363개 정확성 통과가
아니다. 외화·다른 연도·CFS/CF 전체 정확성도 새로 인증하지 않는다.

문서/필드별 정상 거부는 다른 정상 문서 수집을 막지 않는다. 반면 미승인 파서/
진단 코드, 원문 SHA·CRC·공통 schema, API800/제한·통신 실패·worker/기한/lease
문제는 중지 조건이다. 다음 source 실행 전에도 첫 검토의 exact controls/원문/
manifest를 재현하고 승인된6개 source-owner hash와 parser/진단 버전을 확인한다.
매 문서 단계·마지막 내구성 checkpoint·경과시간을 비밀값 없는 live log로 남긴다.
예약 승인은 source-only이며 금융 자동 게시 HOLD와 투자PIT0/6은 바꾸지 않는다.

관찰3회 중 실제 완료1회/100문서다. 남은2회는 아직 실행되지 않았다. 승인 PR의
필수 CI/first artifact 검증 후 main의 READY_NEXT가 적용돼야20·21일05:17 KST의
한 회/일 실행을 검토한다. 새 관찰에서도100문서·90초/문서·600초/수집,3회/
예약300 상한을 유지한다. 출처/의미 검증 U가 있다는 이유만으로 전체 원문 수집을
영구 금지하지 않으며, 발견한 판정 가능한 금융 오류가 있으면 관련 경로를 중지한다.

원래314파일 중 recent_01500_01799는 작업 시작 전 ff9ae7c 현대 수집 커밋에서
변경됐다. 이번 최소 패치는 최신314개를 그대로 보존했고 원래 legacy 상태33MB도
그대로다. 과거98a5f7 기준과 이번 작업 중 변경을 혼동하지 않는다.
