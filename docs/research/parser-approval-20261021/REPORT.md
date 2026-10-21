# 공개 게시 및 parser 재승인 — RESEARCH_ONLY

## 승인된43파일 게시

사용자가 명시 승인한43파일/17498747바이트/커밋2f5f9d16438dd4fede017a7fe325f60c21154661을 `fix/native-source-boundaries-20261021`에 게시했다. 저장소 Horororong/quant-marcap-runner는 public이다. 최종43파일과 정확한 커밋을 보존하는 중간4커밋의 변경blob을 모두 비밀값·PAT·개인키·AWS키·credential URL/리터럴 secret 패턴으로 검사했다. 검출0, 공개 부적합 제외0이다. 공개 DART 원문 증거, 연구 결과, 코드·회복 메타데이터이며 민감 계좌 자료나 환경 비밀값은 포함하지 않았다.

전송 manifest는 APPROVED_TRANSFER_MANIFEST.json, SHA256은 **bab48693cc5ae3f8a88fcd566debe8aa2289c98dff86baf542dc02b53720240c**다. 원격 branch/head와43개 Git blob SHA/길이 및 tree를 별도로 대조해 PASS했다. 최종43파일 합계와 정확한 SHA 보존에 필요한 동일 경로의 중간history blob47개/17662762raw바이트는 구별했다. main 변경 없이 원래 커밋/조상 관계를 보존했다. 이후 설정·시험·CI·집계 문서 변경은 이번 사용자가 지시한 후속1~5단계의 별도 commit으로 보존한다. 최초 승인 대상2f5f9d1의 내용을 다시 쓰지 않는다.

## 두 차단의 원인과 재승인 판정

실패 시험은 `Limited.test_first_schedule_review_daily_total_and_failure_gates`, `Resume.test_same_day_and_three_attempt_caps_remain_closed`다. 두 시험 모두 기존 config가 허용하는9.2 경로를 새 parser9.3에서 실행할 때 `check_gate`의 parser_version 식별자 일치 검사에서 `UNAPPROVED_PARSER_OR_DIAGNOSTIC_VERSION`으로 멈췄다. source hash 검사는 `run`의 후단이므로 당시 두 오류가 hash check까지 진행됐다고 주장하지 않는다. 그대로 version만 맞췄다면 후단에서 기존 source hash와 달라 거부될 상황이었다.

이는 보호 계약을 통과시키기 위한 예외가 아니라, 새 parser 식별자·실제 source bytes를 검토해 다시 고정해야 하는 정상 재승인 절차다. 원문 경계/부호/단위/기간/불확실 값 차단과 기존 후보·SOURCE_GAP 보존을 확인했다. CJ의 DART literal line-break/장식 표기는 기존 독립 financial_review_gate.normalize 계약에도 있던 원문 표현이다. 새 parser가 두 숫자를 합치거나 다른 열·이전기 금액으로 대체하지 않도록 시험했다.

사용자의 조건부 재승인 지시에 따라 연구 config에서 **두 필드만** 바꿨다.

|항목|이전|새 값|
|---|---|---|
|parser_version|legacy-v9.2-statement-boundary-guard|legacy-v9.3-note-reference-token-guard|
|scripts/legacy_native_financials.py SHA256|3cff54f28e3081a1a014e5e12ad56ed13ea36d2d16e16af7aeef0aa0dd1c2773|4bfb127ac05505e0543952ee8e9d90c7541c031f2751767e247845cae2ced0fb|

나머지5 source hash,6-owner 집합,diagnostic version,실행당100/KST일1회/최대3실행/예약300,문서90초/실행600초,만료시각2026-10-23T23:59:59UTC,first review,격리/중단정책,금융HOLD/backtestFalse/PIT0/6는 동일하다. gate 구현을 삭제하거나 느슨하게 바꾸지 않았다. main의9.2 config/source/state는 변경하지 않았다. 연구 config 승인은 기존57문서를 자동 재처리하거나 옛 후보/상태를 교체할 권한이 아니다. 명시적 old-state migration guard도 유지했다.

이전 두 시험의 기대값/코드는 그대로다. 새9.3 승인 설정을 사용해 정상/일일제한/first review/3회한도를 모두 확인했다. 새 수리 시험의 '옛 승인 설정 거부' 주제는 원래2f5f9d1에서 추출한 정확한9.2 config를 immutable fixture로 고정해 계속 거부하도록 검증했다. 현재 config를 옛 config라고 가정하던 참조만 분리했으며 기존 식별자·거부기대는 유지했다. 추가 시험은 모든 나머지 제한값/5hash/owner집합 동일성과 현재6hash 실제일치를 확인한다. 로컬 관련 suite는 **115/115PASS**이며 이전114=112PASS+2ERROR 기록은 이전 증거 폴더에 그대로 남겼다.

## 후보/미검증 집계

기존871개/848PASS/23미검증은 보존했다. unchanged9.3source bytes에 대한57문서 실제 원문 회귀와 신규9개 독립 원문행 의미 대조 증거를 재사용했다. 원문 회귀 전과 후의871개 key와 비교 대상 금융·출처 필드 변경/삭제0,원래저장결과 불일치0,SOURCE_GAP9유지다. 소스코드는 재승인 과정에서 바꾸지 않았다.

원문행 의미PASS848+신규9=857,검토후미검증23,미검토0,중복0으로 **오프라인 제안 집합880개**다. 신규9개는 STC CFS8/CJ CFS자산1이며 전부 원문행 의미PASS/PIT미검증/게시HOLD다. 실제 수집 장부871을880으로 덮어쓰지 않았다. 전체880의 PIT/전체 공시·첨부 추출 완전성도 미인증이다.

12→23 증가의 값별 경로·금액·원문 라벨·사유는 UNVERIFIED_12_TO_23.md와23건 JSON에 있다. 증가11개는 기존 미검토에서 새로 발견한 정의 문제이며,새 숫자 후보 추가/기존PASS재분류/이전12판정변경은 각각0이다. 신규 parser9개는 증가11개와 별개다.

## 고정 kit 최종 CI

기존 manual driver를 parser suite로 확장해 동일 공식 고정 kit을 사용한다. driver와 checkout대상은 별개이며 CI에서 target_sha 전체40자리와 gitrev-parseHEAD 일치를 assert한다. 실제115시험,6source hash,새10경계시험 및old계약거부,880unique 집계와 원문 증거 hash,generated DSL 계약을 검사한다. 계산/시험은 공식bootstrap의 dedicatedPython-I만 사용한다. Internet pip/의존성 갱신은 없다. 변경 없는 브라우저/130전체 통합/751데이터 감사는 반복하지 않는다.

이 문서와 설정을 포함하는 최종 불변 commit을 대상으로 dispatch하며, 최종 결과는 GitHub Actions run/job log와 exact target의 commit-status로 기록한다. 실제run URL/checkout SHA/result/log hash는 작업 종료 시 `/workspace/quant-parser-approval-20261021/FINAL_STATUS.md` 및 새 로컬v8 증분의 최종 영수증으로 보존한다. CI_CONTRACT.json에 driver·범위·kit 식별정보가 있다. 이전305cbCI39540516627과 새 parser CI를 구별한다.

## v7의 원격 보존 범위

이번 branch 게시로 v7의 `delta/`16개 코드·시험·보고·검증결과 파일은 정확한2f5f9d1커밋으로 원격 보존됐다. parent01731c7와 앞선v6의 Git 변경도 조상 관계로 보존된다. Git clone/fetch로 해당 코드·증거를 다시 확보할 수 있다.

v7 ZIP118024바이트/SHA256d19147a72ff5c1e65c26f560266593054eed2e4681fed4cb38a30904f885fe16,checksum/VERIFICATION/FINAL_STATUS,`code-delta.bundle`,payload CODE_STATE/RESUME/runtime-verify/MANIFEST 등 백업 전용 파일을 release asset이나 별도 remote artifact로 업로드한 것은 아니다. Git에 있는 코드·증거 보존을 ZIP 파일 업로드 성공으로 세지 않는다. v7 완전 아카이브의 원격 보존/다운로드 검증은 미실시다. 이번 후속 CI/runtime evidence는 별도로 생성되는 새 기록이다.

기존v5 draft419190338 원격검증은 완료 상태를 재사용했다. v1~v7는 변경/재전송하지 않았다. 기존751data/전체 원본/kit은 이전 원격복구 출처를 계속 사용한다. 모든 원본 없이 remote-only전체 복원 시험을 새로 했다고 주장하지 않는다.

## 실제 HTTP와 다음 위치

수집 실행 전 live main9.2의 state/config/일일제한/예산을 확인하고 gate가 닫혀 있으면 dispatch하지 않는다. main9.2 운영 수집과 연구9.3승인/CI는 별도다. 현재 live증거는 LIVE_GATE.json에 있다. checkpoint20100331002054는 완료이고 다음2062/2063,pending43,기존2/3실행·예약200/300이다. KST날짜가 바뀐다는 이유로 한도/전역계정quota를 복구됐다고 가정하지 않는다. 금융HOLD·PIT0/6·품질/게시제한은 그대로다.

금융 의미 미검증23건은 새 개념 정의/원문 근거가 있을 때만 재판정한다. main에는 이번 연구 branch를 병합하지 않는다. 다음 운영 반영은 최소 source/config 범위의 별도 검토 대상이며 이번 승인은 main병합을 포함하지 않는다.
