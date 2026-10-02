# DART legacy 2000~2014 — 단계별 인계

## 최신 작업 checkpoint (2026-10-01)

현재 단계: **1. 지침/main 반영 완료**, **2. 조사 완료**, **3. generic collector의 안전한 resume 구현·로컬 검증 완료**, 4. 기존 daily Actions에 적용·검증 진행.
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

단계 1 commit `e26637b`, 기존 DART 갱신을 보존한 main 통합 commit `3c98f39`, 단계 2 commit `3e571ce`. 단계 3 commit은 이 문서와 함께 저장된다. Daily fast wrapper는 아직 이전 수집 루프이므로 **단계 4 이전에는 새 resume 계약을 daily 실행에 적용했다고 주장하지 않는다.** 백필 완료나 원문 정확성 검증을 선언하지 않는다.
