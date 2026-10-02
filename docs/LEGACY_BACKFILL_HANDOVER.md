# DART legacy 2000~2014 — 단계별 인계

## 최신 작업 checkpoint (2026-10-01)

현재 단계: **1. 지침/main 반영 완료**, **2. 조사 완료**, **3. generic resume 검증 완료**, **4. 기존 daily Actions 연결·전체 CI 검증 완료**. 5. main 배포와 실제 100건 bootstrap 확인 진행 중.
기준 main: `7be2003c18998f6b12747a0e187a0b40cf6ad7d6`. 이 값은 checkpoint이며 다음 세션에서는 원격 상태를 다시 확인한다.

`PROJECT_CHARTER.md`는 소유자의 지속적인 상위 지침이며 `AGENTS.md` 필수 읽기에 연결했다. 이후 단계별로 구현·검증·GitHub commit·인계를 남긴다.

## 저장 자료에서 직접 확인한 진행 상태

- `legacy_filings.csv.gz`: 공시 138,540건, 6자리 종목코드 매핑 공시 115,020건.
- Index task state: 15년 × 4개 calendar quarter × Y/K/E = 180개 OK. 공시 검색 완료와 원문/데이터 품질 완료는 다르다.
- `dart_legacy_backfill_state.csv`: 13,345개 receipt. 현재 `legacy-v4-book` 6,000건; v3-book 6,000, v1 748, v2 597건.
- 모든 버전 합계: PARSED_4F 3,488 / PARSED_PARTIAL 3,012 / NO_METRICS 5,577 / NO_DOCUMENT 1,239 / ERROR 28 / RATE_LIMIT 1. **이 수치를 현재 버전의 검증된 coverage로 사용하지 않는다.**
- 마지막 저장 update: `2026-10-01T21:16:51.529396+00:00`.
- 현재 v4 6,000건의 status: NO_METRICS 2,526 / PARSED_PARTIAL 1,865 / NO_DOCUMENT 1,185 / PARSED_4F 424. 현재 버전의 4F는 424건이며 3,488건이 아니다.
- Normalized 90,551행 중 v4 17,546행. 현재 v4 PARSED_4F/PARTIAL 상태의 receipt별 `metric_rows`는 저장된 v4 행 수와 전부 일치했다. 현재 저장 checkpoint 자체의 행 수 불일치는 발견되지 않았다. 원문 금액 정확성을 뜻하지 않는다.
- 2000 Q3의 모든 버전 합계 4F 0건, 2001 Q1/H1/Q3도 매우 낮음. 실제 원문 대조 전 source-data 부재로 결론내리지 않는다. 비12월 결산 회사는 report 제목 연도와 fiscal-year label이 다를 수 있다.
- 현재 public factor provider는 `full_history`를 읽는다. legacy 데이터가 검증된 실행 capability로 통합되었다고 주장하지 않는다.

## 실제 존재하는 자동화와 확인한 위험

- `backfill-super-value-fast.yml`: 매일 `30 15 * * *` UTC, 기존 modern+legacy collector 실행. Legacy 6,000건/6 workers이며 현재는 전략용 signal cutoff에 따른 공시 subset을 처리한다.
- `backfill-dart-legacy-2000-2014.yml`: 수동 실행, 전체 legacy collector. 위 일일 실행과 concurrency group이 달라 중복 실행 가능.
- `backfill-dart-legacy-quarterly.yml`: 수동 실행, 별도 구형 `data/financials/legacy` 경로. 현재 `legacy_2000_2014`와 혼동하지 않는다.
- 현재 generic/fast legacy 처리기는 futures 전체를 제출하고 마지막에만 normalized/state를 저장한다. timeout/cancel 중간 진행 유실 위험이 있다. Index도 상태 OK와 데이터 저장 순서를 점검해야 한다.
- `validate-legacy-parser.yml`은 syntax/schema 검사만 수행하며 기존 parser pytest를 실행하지 않는다.
- `audit_legacy_pit_sample.py`의 fresh reparse는 동일 parser를 사용한다. 현재 `audit_ok`는 독립적인 원문 금액 audit 증거가 아니다.
- GitHub API 접근은 현재 환경에서 403이지만 HTTPS Git fetch/push는 작동한다. 로컬 DART secret은 없으며 GitHub secret의 값은 읽거나 복사하지 않는다. 기존 Actions 실행으로 live 검증을 진행해야 한다.
- DART 공개 viewer(`dsaf001/main.do?rcpNo=20000814000085`)도 이 환경에서 HTTP 403을 반환했다. 대표 원문 접근은 Actions 환경에서 별도로 확인할 필요가 있다. 접근 거부를 원문 부재로 기록하지 않는다.

## 다음 세션 / 다음 단계

1. 원격 main/작업 branch/Actions 상태와 이 문서의 최신 변경을 확인한다.
2. Generic legacy 및 fast wrapper의 안전한 incremental checkpoint, parser-version별 resume, rate-limit/deadline 동작을 재현하고 테스트한다. 이미 정상인 현재 버전 receipt는 다시 수집하지 않는다.
3. 기존 daily workflow를 재사용하여 중복 실행 방지·시간/API 예산·항상 checkpoint 보존·완료 후 no-op을 검증한다. 새 중복 scheduler는 만들지 않는다.
4. 단계별 commit 후 실제 Actions의 저장된 진행을 확인한다. GitHub API 제한으로 확인하지 못한 실행을 성공으로 보고하지 않는다.
5. 2000 Q3/2001 Q1/H1/Q3 대표 원문을 확인한 뒤에만 parser 수정과 version invalidation을 실시한다. 원문 fixture와 독립 expected amount, 음수 기호/손실 회귀 테스트를 추가한다.
6. 독립 source audit를 완료 판정에 분리하고 전체 품질을 검증한다. 실행 engine/DSL의 기존 정상 결과와 전체 Strategy DSL CI를 보존한다.

## 단계 3: generic collector resume 계약

- 동시에 worker 수만큼만 제출한다. 기본 25 receipts마다 data → state 순서로 checkpoint하고 종료 시 남은 완료 결과를 flush한다. SIGTERM/SIGINT는 새 작업 제출을 멈춘다. SIGKILL은 cleanup이 불가능하므로 마지막 checkpoint 이후 최대 24개 완료 receipt와 진행 중 worker 작업은 재요청될 수 있다. 이미 저장한 정상 receipt는 재요청하지 않는다.
- Index는 query task마다 공시 데이터를 먼저 저장한 뒤 OK를 기록한다. 이미 OK인 전체 index는 API 요청·remapping·gzip 재생성 없이 재사용한다.
- Requests budget은 index pages와 document download 및 retry를 포함한다. 기본 2,500 attempts / 3,300초 / 요청 시작 간격 0.5초이며 env로 명시적으로 설정한다. Deadline 뒤 in-flight 요청의 종료를 기다릴 workflow 여유 시간이 필요하다.
- `DEFERRED`는 로컬 예산/중단이며 원문 부재가 아니다. API 020은 RATE_LIMIT로 저장하고 신규 요청을 중단한다. ERROR 3회는 자동 재시도 보류이며 실패 상태를 보존하고 다른 receipt는 계속 처리한다. Parser version이 바뀌면 이전 오류 횟수를 물려받지 않는다.
- 현재 version의 PARSED 상태를 skip하려면 normalized row count와 document SHA가 상태 기록과 일치해야 한다. 이전 parser version metric은 보존한다. **Financial parser는 변경하지 않아 `legacy-v4-book`을 유지한다.**
- 기존 deterministic CSV writer를 `scripts/csv_storage.py` 공통 소유자로 옮겨 recent와 legacy에서 재사용한다. 동등한 데이터/상태 timestamp만 변경되면 기존 bytes를 보존한다.
- 수집 완료 표시는 `COLLECTION_COMPLETE_REVIEW_REQUIRED`이며 `quality_complete=False`다. 같은 parser의 reparse나 4F 유무를 독립 audit로 인증하지 않는다.
- 검증: parser+resume pytest **18 passed**, 기존 recent storage **9 passed**(실제 저장 317,165행 deterministic 검사 포함), generated DSL contract 검사. 저장소 데이터는 수정하지 않았다. 실제 live Actions 검증과 전체 DSL CI는 다음 단계에서 수행한다.
- 재검증 명령: `python -m pytest tests/test_legacy_dart_parser.py tests/test_legacy_backfill_resume.py -q`, `python scripts/test_dart_recent_storage.py`, `python scripts/export_strategy_dsl_contract.py --check`.

## 단계 4: 기존 daily workflow의 안전한 인계

- 새로운 scheduler 없이 `backfill-super-value-fast.yml`의 기존 `30 15 * * *` UTC 일일 실행을 재사용했다. Fast wrapper도 generic collector의 **전체 mapped receipts** 큐를 쓰며 정정공시·특정 전략 cutoff 외 공시도 수집한다.
- Daily와 수동 legacy, 공통 modern 데이터에 쓰는 full-history 및 super-value signal 작업이 기존 `super-value-fast-pit-backfill` concurrency group을 공유한다. `cancel-in-progress: false`로 진행 중 수집을 취소하지 않는다.
- Daily legacy: 2,000 docs / 2,500 request attempts / 3 workers / 55분 API 제출 deadline. Index 6 tasks, request start interval 0.5초. Modern 기존 수집도 유지하되 legacy 다음에 최대 1,000 tasks / 3 workers로 수행한다. 단일 계정의 전 workflow 공통 quota는 중앙화하지 않았으며 API 020은 즉시 중단한다.
- Main code push는 100 docs / 150 attempts / 10분 제출 예산으로 한 번 live 검증한다. Push paths는 code/workflow뿐이므로 data commit이 무한 실행을 만들지 않는다. 두 legacy entry point는 main에서만 실행하고 실행 시 최신 main을 checkout한다.
- Collector step timeout(75분 daily, 65분 manual)보다 job timeout을 길게 두어 commit 여유를 확보한다. Collector 실패 뒤에도 `always()`로 coherent checkpoint를 commit하며, publish 실패 시 14일 recovery artifact로 normalized+state를 보존한다. Artifact는 Git storage와 별도이고 기존 history/data는 삭제하지 않는다.
- 전체 queue가 소진되면 legacy의 API/document 요청은 no-op이다. 오류 보류·NO_METRICS/NO_DOCUMENT와 독립 audit 미완료는 완료로 인증하지 않는다. Daily schedule 자체는 modern 잔여 catch-up을 계속 지원하므로 그 완료 여부와 정상 운영 전환도 별도 확인한다.
- `validate-legacy-parser.yml`과 전체 Strategy DSL CI에 실제 pytest를 연결했다. 로컬 parser/resume/automation **26 passed**, 변경한 여섯 workflow **actionlint 통과**. Auth/service 오류는 DEFERRED로 기록하고 신규 요청과 뒤따르는 modern API 작업도 차단한다.
- 다음: 전체 CI 통과 후 main에 반영하고 push bootstrap의 실제 Actions 결과·state 증가·원문 접근을 확인한다. API 접근 제한 때문에 GitHub 성공을 추정하지 않는다. 2000 Q3/2001 Q1/H1/Q3 원문 증거를 확보한 뒤에만 parser 수정한다.

## 배포 전 검증 checkpoint (2026-10-02)

- 구현 commit `3d8e044e7c280b367e8370d818ec6de88683b8eb`.
- Local Strategy DSL workflow의 실행 검사 **31/31 통과**. 실제 DART Super Value PIT, real KRX/decile/held-return, CURRENT 성과, strict DSL, CLI lifecycle 및 recent deterministic storage 포함.
- 같은 구현 commit의 GitHub 전체 CI **Success**: <https://github.com/Horororong/quant-marcap-runner/actions/runs/36945219803> (19m15s). Python 3.11/3.12 sandbox replay matrix 포함.
- 다음은 검증된 code를 main에 non-force fast-forward push하고 bootstrap의 실제 run, committed state의 증가와 dataset/state 일치를 확인하는 것이다. 실패하면 기존 checkpoint/14일 recovery artifact에서 재개하고 이 문서를 갱신한다.

단계 1 commit `e26637b`, 지침 main 통합 `3c98f39`, 단계 2 `3e571ce`, 단계 3 `1d44474`, 단계 4 `3d8e044`. **이 checkpoint 작성 시점은 구현 main 배포 전이다.** 백필 완료나 원문 정확성 검증을 선언하지 않는다.
