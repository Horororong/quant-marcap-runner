# DART legacy 2000~2014 — 단계별 인계

## 최신 작업 checkpoint (2026-10-02 UTC)

**단계 8 main 배포·live 확인 완료.** 기존 fast 예약을 00:30 / 08:30 / 16:30 KST, 회당 최대 2,000건으로 10월 한시 증량했다. 최종 code merge `aa6c8722a0842d717468d855606b7ab76208eac4`의 전체 CI와 validator가 success이며, 배포 확인 100 requests / 100 receipts / rate-limit False를 직접 확인했다. 자동 data commit `07bf21a92d4f33ee8797560a66e4cf9f2b929ff8` 기준 durable processed 1,401 / pending 113,619다. 금융 parser/source는 기존 v5/v1이고 수집·독립 품질 완료는 모두 False다.

이 수치와 commit은 checkpoint이며 원격 main·현재 CI·status를 다시 확인한다. 아래 단계별 기록은 이력을 보존하며 **마지막 단계 8 live 완료 기록**이 현재 재개 지점이다. 다음은 예약 batch 실측과 기존 source evidence를 재사용한 기간·column·단위/음수 guard 및 source adapter 보완이다. 로컬 최신 gzip 동기화 제한도 마지막 기록에 명시했다.

## 최초 인계 checkpoint (2026-10-01, 역사 기록)

현재 단계: **1~4 저장·구현·검증 완료**, **5. main 배포 후 실제 100건 수집 확인 완료**. 6. 대표 원문 증거 확보와 독립 audit 경계 수정 진행 중. 최종 CI/추가 live 확인은 아래 최신 checkpoint를 따른다.
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
2. 최신 bootstrap의 actual request/receipt 수와 normalized/state SHA/row count, 완료된 final code CI를 확인한다. 상위 단계는 재구현하지 않는다. 이미 정상인 현재 버전 receipt는 다시 수집하지 않는다.
3. `docs/audits/legacy/source_probes/*.json`의 원문 excerpt·hash·offset과 audit workflow의 90일 original ZIP artifact를 확인한다. API 014/HTTP 403과 실제 source absence를 혼동하지 않는다.
4. 2000 Q3/2001 Q1/H1/Q3 원문에서 heading, native cell tag, CFS/OFS, unit, current/prior columns, OCF/account aliases를 독립적으로 확인한 뒤 parser 수정과 version invalidation을 실시한다. 동일 parser 재파싱을 정답으로 사용하지 않는다.
5. 저장된 비정상적으로 큰 finite amount의 raw cell과 실제 공시를 대조한다. 독립 expected amount·실제 fixture와 음수 기호/손실 회귀를 추가한다. 백필 완료가 아니라 source-quality 문제 해결을 우선한다.
6. Filing-date query end=2014와 fiscal-period end=2014는 다르다. FY2014의 2015년 접수 공시 누락 가능성, 비12월 결산 변경, historical mapping coverage를 검증하고 필요 구간만 index 확장한다. 180 OK를 전체 2000~2014 PIT completeness로 인증하지 않는다.
7. 독립 source audit를 완료 판정에 연결하고 전체 품질을 검증한다. 각 완료 단계마다 GitHub commit·이 문서 갱신을 남기며, engine/DSL 결과와 전체 Strategy DSL CI를 보존한다.

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

## 단계 5 첫 live bootstrap: 진행 0건 원인 확인 및 수정

- `611eb66`으로 main 배포 완료. Bootstrap run <https://github.com/Horororong/quant-marcap-runner/actions/runs/36951346712>는 Actions **Success**였지만 `legacy_run_docs=0`, `legacy_requests=0`이므로 백필 진척으로 인정하지 않는다.
- 자동 commit `84df0c8`은 coverage/status만 바꿨다. 실제 coverage의 mapped/current durable processed는 115,020/5,993, pending 109,027건이다. v4 6,000 records 중 7건은 현재 index에서 mapped 대상이 아니어서 전체 current-record 수와 대상 coverage가 다르다.
- 원인: `update_filing_index()`의 no-op return에서 `stock_code` dtype을 지정하지 않았다. CSV의 missing code와 앞자리 0 때문에 숫자로 읽힌 code가 6자리 정규식에 모두 실패했다. Stored index 자체는 손상되지 않았으며 API 요청도 없었다.
- 수정: 기존 index 읽기에 `stock_code: str` 명시. 실제 138,540 receipt index를 직접 읽어 leading zeros/100,000건 이상 pending queue 보존을 검증하는 regression을 추가했다. Fast status의 batch limit도 실제 env limit을 반영한다.
- Local parser/resume/automation **27 passed**. 금융적 parsing·version은 변경하지 않았다. 이 수정 commit은 main에 반영하여 새 bounded bootstrap을 확인한다. 성공 판정은 Actions 표시뿐 아니라 receipt state 변경·실제 requests·normalized/state 일치로 한다.

다음은 수정 bootstrap의 live 결과와 최종 CI 확인이며, 이어서 원문 증거 확보와 parser 이상 구간 조사다. 현재 데이터 품질은 계속 미인증 상태다.

## 단계 5 live 수집 확인 및 기존 관측값 보존 (2026-10-02)

- Code fix `7c7eb39`, 기존 macro 갱신을 보존한 main 통합 `a3e4473`.
- 수정 bootstrap <https://github.com/Horororong/quant-marcap-runner/actions/runs/36951779362>: **Success**, 3m22s. Commit `79b8323`의 보고서에서 **API attempts 100 / receipts 100 / rate-limit False**를 직접 확인했다. 이전 parser receipt의 v4 재처리도 진척에 포함하며 신규 unique receipt 100건 증가라고 주장하지 않는다.
- 실제 결과 대조에서 기존 CSV를 float로 읽고 다시 저장하면서 일부 과거 금액 token의 마지막 자리가 바뀌는 것을 발견했다(1999년 18개 field, 2000년 11개 field). 기존 parser는 큰 문자열을 숫자로 합치는 의심 값도 이미 저장하고 있었다. 원문 확인 없이 이 값 자체를 교정하지 않는다.
- 보존 수정: normalized append 시 기존 관측값은 `dtype=str, keep_default_na=False`로 읽는다. `a3e4473`의 저장 관측값 18,090행을 모든 field의 원래 문자열로 복구하고 **새 관측값 969행은 전부 유지**했다. 이전 parser version도 삭제하지 않았다. 복구는 기존 Git source와 exact textual equality로 검증했으며 history rewrite/delete는 하지 않았다.
- Regression: old scientific-notation amount token·`NA` 문자열의 exact preservation 검사 포함 parser/resume/automation **28 passed**. Financial parser와 version은 그대로다.
- 다음: 같은 기존 audit workflow에서 대표 실패의 원문 ZIP/원문 일부·SHA를 확보하고 reparse consistency와 독립적인 audit를 명확히 분리한다. 전체 CI와 최종 live checkpoint를 다시 기록한다.

## 단계 6 준비: 원문 증거 확보 / audit 경계

- 기존 `audit-legacy-pit.yml`을 재사용한다. 새 schedule은 없고 main의 probe/audit code push 또는 수동 실행에만 동작한다. Daily collector와 같은 lock을 사용하여 중복 API 호출/상태 쓰기를 방지한다.
- 대표 6 receipt(위 초기 이상 구간에서 확인한 NO_METRICS 사례)의 OpenDART 원문 ZIP과 공개 viewer 응답을 확보한다. Probe budget은 모든 retries/viewer calls를 합쳐 36 attempts / 10분 / 0.5초 간격이다. 확장 ZIP 총 20MB, artifact ZIP 합계 40MB, excerpt는 receipt당 최대 40,000 characters로 제한한다.
- 원문 ZIP은 Git에 넣지 않고 기존 audit의 **90일 Actions artifact**에 보관한다. 작은 literal statement excerpt, source character offsets, file/ZIP SHA, encoding, clipped 여부는 Git JSON에 보존한다. 이것은 독립 audit를 위한 증거 준비이며 값의 인증이 아니다. Artifact 만료 전에 실제 fixture/검증 기대값을 만들고 장기 원문 저장 정책을 결정해야 한다.
- `API_014`, viewer HTTP 200/403, 다운로드 성공을 실제 source absence/금융적 정확성으로 인증하지 않는다. 실패 probe를 계속 매일 반복하지 않는다. 재조사는 별도 명시적인 후속 실행으로 관리한다.
- 기존 sample audit의 `audit_ok`를 같은 parser 재파싱으로 True로 만드는 것을 차단했다. 별도 `reparse_consistency_ok`를 제공하고 독립 audit는 `NOT_RUN`/pending, `audit_ok=False`이다. Corrupt input을 조용히 제외하지 않는다. Original amount 기대값 검증은 아직 구현하지 않았으며 재파싱 통과율과 분리한다.
- 기존 음수/손실 회귀 유지. 금융 parser는 아직 `legacy-v4-book`이며 원문 확인 없이 숫자 해석을 바꾸지 않았다. 테스트와 actionlint 후 원격 실행/실제 source 확인 및 최종 전체 CI를 기록한다.

## 실제 원문 확보 checkpoint / capture v2

- Audit run <https://github.com/Horororong/quant-marcap-runner/actions/runs/36952781646>가 기존 lock 뒤에 실행됐으며 commit `2d4e4a3`에 대표 6개 receipt 원문 ZIP SHA/member SHA가 저장됐다. **6개 모두 OpenDART DOWNLOADED, public viewer HTTP 200**이다. 따라서 이 사례의 NO_METRICS를 실제 원문 부재라고 결론낼 수 없다.
- Initial capture의 HTML TABLE 기반 발췌는 6개 모두 0개였다. Original ZIP은 90일 artifact `legacy-original-source-evidence`(258KB)에 보존됐다. 원문 형식 확인을 위해 capture v2에 literal document head·native tag counts·table 외 계정 주변 원문을 추가한다. 원래 format을 추정해 금융 parser를 먼저 바꾸지 않는다.
- v2는 기존 6개의 marker가 없는 source report만 재확보하며, 비정상 raw cell 대표 `20000515000887`(net_income), `20000214000011`(short_term_borrowings) 2개를 더 조사한다. 총 8 receipts / 48 API+viewer attempts / 10분 / Git excerpt 40,000 characters per receipt. Parser version과 별개의 `evidence_capture_version=2`로 수집 증거 변경을 관리한다.
- 현재 v4에서 `abs(amount_krw)>1e20`인 관측값 55개/53 receipts를 진단했다. threshold는 **조사 대상 선정**이며 금액을 바꾸거나 정확성을 판정하는 금융 규칙이 아니다. 예: `raw_amount='751,637 22,35416,940'`이 하나의 net-income 값으로 저장돼 있었다. 실제 공시 원문과 대조해야 한다.
- 같은 parser sample reparse 36개는 100% 일치했지만 structural/reparse consistency는 31/36(86.11%)이고 독립 audit는 **36개 전부 pending / audit_pass 0 / audit_fail 0**이다. 재파싱 성공을 금융 정확성으로 인증하지 않는다.
- `c0c6ac0`의 세 번째 bootstrap commit `2bc35be`: current durable mapped processed 6,293 / remaining 108,727 / 4F 464. Source-quality 완료는 False다. 세 번의 100건은 일부 이전 버전 재처리이며 unique receipt 수 증가와 구분한다.

다음 작업은 capture v2의 실제 원문 구조와 native numeric column/heading/scope/unit을 읽고 독립 기대값을 만드는 것이다. 자료가 없다는 가정이나 숫자 크기를 맞추기 위한 임시 교정은 금지한다.

## 단계 6: 원문으로 재현한 복합 셀 오류 차단 / parser v5

- Capture v2 run <https://github.com/Horororong/quant-marcap-runner/actions/runs/36953686608> **Success**, 8개 원문 evidence는 main commit `610fd4e`에 저장됐다. 직전 code `2b0cbea`의 local 전체 Strategy DSL 검사 **31/31 통과**, 같은 commit의 GitHub CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/36953686599> **Success**(19m14s, Python 3.11/3.12 replay 포함)를 확인했다.
- 데이콤 `20000515000887`의 literal source character 107588–110724에서 `매출액·영업이익·당기순이익`이 한 account cell에, `751,637 22,35416,940`이 한 amount cell에 들어 있다. 표는 1999~1994 연간 사업실적이며 현재 분기 손익계산서가 아니다. v4는 이를 `net_income=7.51637223541694e21 KRW`, statement 빈 값으로 반환했다. 이 source를 직접 재현했으며 `tests/fixtures/legacy_dart/merged_annual_stats_20000515000887.json`에 ZIP/member SHA·offset·원문·독립 거부 기대값을 보존했다.
- `legacy-v5-single-amount`는 완전한 단일 숫자 token만 허용하고 comma grouping을 검증한다. 복합 금액·주석·비율·비정상 grouping을 숫자로 합치지 않으며 standalone dash는 0이 아니라 missing이다. 실제 `0`, decimal, Δ/▲/△/괄호 음수와 손실계정 정규화는 유지한다. Nonfinite 숫자나 단위 환산 overflow는 usable metric으로 인정하지 않는다.
- 등록한 exact account alias와 해당 metric의 명시적인 statement heading이 있어야 후보가 된다. 짧은 substring이나 unknown statement로 사업요약을 현재 재무정보로 승격하지 않는다. 이 변경이 모든 heading/scope/당기 column 오류를 해결했다는 뜻은 아니다.
- Financial parser version 변경으로 이전의 PARSED/NO_METRICS는 v5에서 재처리하며 기존 normalized version 관측값은 그대로 보존한다. 원문 download adapter는 `source_version=opendart-document-v1`로 별도 관리한다. 같은 source adapter의 API 014 `NO_DOCUMENT`는 numeric parser 수정만으로 재요청하지 않는다. 기존 v4에서 source field가 없던 014도 확인된 동일 endpoint이므로 이 범위에 한해 carry forward한다. Source adapter가 바뀌면 그 상태는 재검토 대상이며, API 014는 실제 원문 부재의 인증이 아니다.
- Parser/resume/automation/source-evidence **51 passed**. 실제 source fixture, strict numeric failure boundary, unit overflow, 기존 음수·손실, 정상 데이터 resume, source-version invalidation을 검증했다. Fixture-only 변경도 두 기존 CI에서 검증되도록 paths를 추가했다. 전체 v5 CI와 live 재처리 결과는 다음 checkpoint에 기록한다.
- 네 초기 XML(`20010103000052`, `20010104000076`, `20010213000010`, `20010213000014`)은 원본 UTF-8 내용에 이미 replacement character와 깨진 한글이 있다. Decoder만 바꾸거나 계정명을 추측해 복구하지 않는다. 한글이 읽히는 `20000809000052`, `20000814000085`도 확보한 주 문서에서 재무 계정을 확인하지 못했다. Public viewer 200을 재무 본문 확인으로 해석하지 않고 financial statement/첨부 원문 경로를 다음 단계에서 조사한다.

**현재 완료 단계:** 지침 저장, 안전한 resume·기존 daily 자동화, 실제 300건 수집/재처리, 대표 8개 원문 확보 및 첫 source-proven parser guard. **현재 진행 단계:** v5 전체 regression 후 배포·bounded live 재처리. **다음 단계:** 초기 공시의 재무 본문/첨부 원천 확인 → 기간·scope·unit·당기 column의 독립 기대값 → 필요한 parser 수정·재처리 → FY2014의 2015 접수 coverage와 mapping 검증 → 독립 audit. 2000~2014 수집·품질 검증 완료는 계속 False이며 legacy 실행 capability는 공개하지 않는다.

## v5 배포 직전 추가 경계 검증

- `16bf1cb`의 local 전체 Strategy DSL **31/31 통과**. 실제 DART PIT·KRX top-N/10분위·공통 CLI·CURRENT·기업행동·held-return을 포함한다. 최신 main의 source evidence 데이터 변경은 이후 normal merge로 보존한다.
- 새 source-version coverage 필드가 아직 state 파일이 없는 첫 실행에서 `KeyError('parser_version')`를 내는 것을 별도 재현했다. Empty state의 명시적인 columns를 보완하고, API 호출·가짜 완료 없이 pending/품질 미완료를 보고하는 회귀를 추가했다.
- 기존 v4 raw amount 19,444행을 오프라인 비교했다. 단일 numeric token 16,563행 중 3행은 괄호와 음수기호가 함께 있어 v4가 double flip하던 사례다(`20000330000422` 두 손익, `20000330000363` 자본). v5에서는 음수 표기를 다시 양수로 뒤집지 않는다. 나머지 허용 numeric token의 수치는 동일했다. 기존 관측값은 수정하지 않으며 두 공시 원문 금액·unit·column의 독립 audit는 아직 pending이다. 숫자 token 회귀와 공시 정확성 인증을 구분한다.
- 거부 token 2,881행에는 dash/missing·비정상 grouping·복합 금액 등이 포함된다. 이 중 과거 `abs(amount_krw)>1e20` 관측값 57행의 raw token은 거부된다. 이 수치는 전체 receipt를 정확하게 다시 해석했다는 인증이나 모든 대형 금액 오류를 해결했다는 뜻이 아니다.
- 추가 sign/empty-state 회귀 후 전체 legacy 관련 pytest와 generated-contract/actionlint를 다시 실행한다. Main 배포 후 실제 requests·v5 state/normalized의 SHA/row count와 이전 버전 모든 field의 textual equality, 최종 GitHub CI를 확인해 마지막 checkpoint에 기록한다.

## 단계 6 v5 배포·live 검증 완료 / 재개 확인 (2026-10-02 UTC)

- 원격 GitHub API로 main `df1ef362617d2fc9d89064dec56a7cf852cfe9a2`와 로컬 HEAD의 일치를 확인했다. 작업 트리는 깨끗했고 v5 재배포·bootstrap을 반복하지 않았다. Code integration은 `993e13fb1abac8da05d2c9ea43808c2a13566f13`이다.
- 해당 code의 전체 Strategy DSL CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/36957000605>에서 test 및 Python 3.11/3.12 sandbox replay **모두 success**를 직접 확인했다. Legacy pytest는 로그상 **55 passed in 2.66s**. Parser validation <https://github.com/Horororong/quant-marcap-runner/actions/runs/36957000579>도 success다. Data-only `df1ef36`에는 별도 전체 CI가 자동 실행되지 않았으므로 code CI와 data commit을 구분한다.
- Live bootstrap <https://github.com/Horororong/quant-marcap-runner/actions/runs/36957000576>는 success이며 저장된 보고서의 **100 requests / 100 receipts / rate-limit False**를 확인했다. `993e13f` 대비 실제 receipt 변경 100건은 **NO_METRICS 68 / PARSED_PARTIAL 16 / PARSED_4F 16**이다. 신규 unique receipt 100건으로 해석하지 않는다.
- Parsed 32 receipts의 v5 normalized **581행**은 state의 document SHA와 metric_rows에 전부 일치한다. 직전 normalized **92,449행의 모든 field 문자열·중복 multiplicity가 그대로 보존**됐고 v5 581행만 추가됐다. State의 빈 source_version column 추가는 재처리 건수로 세지 않는다. 검증 snapshot: `docs/audits/legacy/v5-live-checkpoint-20261002.json`.
- 현재 mapped 115,020 / durable processed **1,301** / pending **113,719** / 4F **16**. Compatible source-only NO_DOCUMENT는 전체 state 1,203건(그 중 mapped 1,201)이다. V4 6,293을 v5 유효 데이터로 합산하지 않는다. Collection/quality complete는 모두 False, 독립 금융 audit는 아직 NOT_RUN이다.

### 무출력 대기 조사 및 bounded 재개

- 중단된 호출은 GitHub 조회·pytest·추가 network 권한을 요청하는 shell 실행을 `Promise.allSettled`로 묶었다. 모든 호출 종료 전 출력이 반환되지 않아 한 작업의 대기가 전체 결과를 가렸다. 정확히 어느 미완료 호출에서 대기했는지는 중단 당시 trace가 없어 단정하지 않는다.
- 재개 환경에서 `timeout -k 5s 45s python -u -m pytest tests/test_legacy_dart_parser.py -vv -s -o faulthandler_timeout=15`는 즉시 **No module named pytest**로 종료됐다. 살아 있는 pytest/pip 프로세스가 없고 설치 대상 `/tmp/legacy-test-deps`도 없다. 이것은 테스트 실행/통과의 증거가 아니며, pytest 자체의 90분 hang으로 재현되지 않았다. 원격의 동일 suite는 위 2.66초 통과가 직접 증거다.
- 이 환경에는 pytest/requests/beautifulsoup4/pyarrow가 부족하다. 의존성 설치를 요청한 추가-network shell 호출도 완료 결과를 반환하지 못했다. 설치 성공을 가정하거나 동일 설치를 무기한 재시도하지 않는다. Local Git/gh network도 sandbox socket/proxy 단계에서 실패했다. GitHub 조회와 원문 artifact 다운로드는 연결된 GitHub connector로 수행했다.
- 이후 shell 명령은 process timeout + 짧은 yield를 쓰고, 원격 도구 조회 결과는 개별 출력한다. 의존성이 준비되면 테스트 파일을 하나씩 `timeout -k 5s 60s python -u -m pytest <file> -vv -s -o faulthandler_timeout=15`로 실행한다. 15초 stack dump와 마지막 test node를 보존하고, 60초 timeout 시 해당 node만 분리해 조사한다. 의존성 없는 실패를 test hang으로 분류하지 않는다.
- 현재 다음 단계는 이미 확보된 원문 artifact의 viewer 목차에서 재무 본문 경로를 확인하는 것이다. API 재수집·금융 parser 변경 없이 기존 source evidence부터 조사한다.

## 단계 7: 초기 재무 본문 경로 확인 및 제한된 evidence capture

- 기존 run `36953686608`의 artifact `11205027337`을 내려받아 ZIP/member/viewer SHA를 기존 Git report와 대조했다. 새 OpenDART 원문 요청은 하지 않았다. 6개 viewer 모두 `3. 재무제표`와 `4. 연결재무제표`의 rcpNo/dcmNo/eleId/offset/length/dtd를 실제 응답에 포함한다. 12개 주소와 literal pointer block은 `docs/audits/legacy/initial-financial-body-routes-20261002.json`에 저장했다. Viewer 목차 존재를 재무 금액 확인으로 해석하지 않는다.
- **6개 중 5개**의 내려받은 XML은 `</DOCUMENT>` 없이 중간에서 끝나고 strict XML parse가 `no element found`로 실패한다. `20010213000010`만 구조상 완결되지만 UTF-8 원문에 replacement character가 39,374개 있다. `20010103000052`, `20010104000076`, `20010213000014`에도 각각 22,691 / 7,797 / 12,692개가 이미 원문에 있다. 읽을 수 있는 두 초기 XML도 잘린 원문이었다. 이 자료만으로 source absence 또는 parser의 금융적 정확성을 인증할 수 없다. Viewer offset은 별도 원문 경로 값이므로 변환된 UTF-8 ZIP의 byte/character offset과 같다고 가정하지 않는다.
- 기존 `audit-legacy-pit.yml` 안에서 별도 `capture_legacy_viewer_sections.py`로 **이미 확인한 12개 financial-body 주소만** 요청한다. OpenDART ZIP/main viewer를 다시 수집하지 않는다. 동일 lock, 새 schedule 없음, retries/redirect 없음, 최대 12 requests / 300초 / 0.5초 간격 / 요청당 socket timeout 20초. Body별 2MB·전체 12MB로 제한한다. Step 7분, audit job 55분으로 기존 probe/reparse와 checkpoint·artifact publish 여유를 보존한다.
- 원문 bytes를 runner artifact에 먼저 저장하고 개별 section report를 atomic checkpoint한다. 성공·실패 모두 저장된 report는 자동 재요청하지 않는다. HTTP 403/429 또는 transport failure는 뒤따르는 요청을 중단한다. Deadline·byte budget·빈/실패 응답은 정확성 또는 부재 인증이 아니다. 90일 raw artifact와 Git의 SHA/literal excerpt를 유지하며 독립 금융 audit는 NOT_RUN이다.
- 새 capture는 stdlib와 기존 CollectionControl만 사용한다. Local bounded transport regression **8 tests passed in 0.007s**, 세 workflow YAML parse와 diff check 통과. 금액 parser/version·provider·실행 capability는 변경하지 않는다. 기존 두 CI의 pytest는 파일별 60초 process limit, 15초 stack dump, verbose node 출력을 적용해 무출력 무기한 대기를 방지한다. 새 capture regression은 별도 30초 limit이다.
- 다음은 feature의 전체 GitHub CI 통과 후 main 반영 → 같은 audit workflow의 실제 section HTTP/raw SHA/원문 확인이다. 실제 scope·unit·당기 column·OCF 기대값은 그 원문을 읽은 뒤에만 등록한다. FY2014의 2015 접수 coverage와 historical mapping은 후속이며, 백필/독립 품질 완료는 계속 False다.

## 단계 7 live 완료: 원문 금융 본문 확보 및 독립 기대값 checkpoint

- Feature `a02386d08cd2974dd004019efa95bfd8195625be`의 전체 CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/36988758296>는 **test + sandbox replay 3.11/3.12 모두 success**. Parser validation <https://github.com/Horororong/quant-marcap-runner/actions/runs/36988758249> 로그에서 파일별 **19 / 22 / 7 / 7 passed**, 새 stdlib capture **8 passed**를 직접 확인했다. PR #24는 native merge `56b13f38d0185c015d7f1473a396d8e7afdd6e57`로 main에 반영됐다. Backfill push trigger에 해당하는 변경은 없어 이미 완료한 bootstrap을 반복하지 않았다.
- 실제 audit <https://github.com/Horororong/quant-marcap-runner/actions/runs/36994245000> **Success**. 이전 OpenDART source probe는 1초 no-op이었고, 확인된 viewer section만 **12 attempts / 12 HTTP 200 responses / BATCH_COMPLETE**로 확보했다. Main 자동 commit `6411d24f952a757322722d9461c5109cd2f338bc`에 12개 report와 v5 reparse summary가 있다. 기존 normalized/state/금융 parser는 이 audit에서 변경되지 않았다.
- Raw artifact `11221241095`, SHA `63416ef30250a6d65e470cc2030fa9af11b7a1b997510212b09d39b3412205df`, 만료 **2026-12-31T10:13:08Z**. 다운로드한 모든 response의 길이·SHA를 report와 직접 대조했다. **12개 모두 strict UTF-8로 읽히고 source replacement character는 0개**다. 실제 재무제표 heading·계정·기간·단위를 원문에서 확인했다. 이것은 source 경로/내용 확보이며 전체 금액 인증이 아니다. Snapshot: `docs/audits/legacy/financial-body-live-checkpoint-20261002.json`.
- 저장된 12개 report와 실제 URL fingerprint로 resume를 실행하고 네트워크 호출을 금지한 opener를 사용해 **0 requests / 0 report rewrites**를 확인했다. Raw HTML은 Git에 넣지 않았다. 이미 받은 source ZIP·viewer TOC·section을 재확보할 이유는 없다.
- 독립 기대값 `docs/audits/legacy/daewoo-current-period-expectations-20010103000052.json`은 **원문 CRLF를 보존한 strict UTF-8 character offsets**, SHA, literal heading/row와 금융적 해석 경계를 담는다. 대우중공업 OFS의 2000-09-30 자본총계 `(-)4,316,453,759,135`원, 2000-01-01~09-30 누적 매출액 `3,150,518,514,093`원, 누적 당분기순손실 `(-)3,423,467,689,539`원을 원문에서 각각 확인했다. 기존 parser의 재계산에서 기대값을 만들지 않았다. Full receipt audit나 normalized ingestion 인증은 아직 0건이다.
- 원문으로 다음 경계를 재현했다. (1) v5의 정확한 parse_number AST는 source의 `(-)4,316,453,759,135`를 NaN으로 거부한다. (2) `당분기순손실` account cell에는 주당손실 `(-)9,834원`도 있어 금액 column과 구분해야 한다. (3) 해당 CF section은 FY1999의 `(-)198,014,822,042`원을 보여 주므로 이를 **현재 2000 Q3 OCF로 승격하면 안 된다**. 당기 column은 왼쪽 제38기, 오른쪽 제37기는 전기 연간이다. 이 발견만으로 다른 곳에 current OCF가 없다고 인증하지 않는다.
- 같은 v5 재파싱 sample **28/28 수치 일치**, structural + reparse consistency **26/28 (92.86%)**지만 독립 full audit는 **pending 28 / pass 0 / fail 0**이다. Structural gap은 `20000215000011`의 net_income unit, `20000324000148`의 depreciation/long_term_borrowings unit 및 환산 검사다. 현재 mapped durable **1,301/115,020**, pending **113,719**; collection/quality complete는 계속 False이며 legacy 실행 capability는 공개하지 않는다.
- FY2014의 읽기 전용 boundary snapshot도 저장했다: `docs/audits/legacy/fy2014-filing-boundary-20261002.json`. Index 접수일은 **2000-01-10~2014-12-30**, 2015 접수는 0건이다. FY2014 label은 216건(현재 mapped 158)이며 회사별 추정 결산월을 사용하는 metadata이다. 이 건수를 fiscal-year-2014 completeness로 인증하지 않는다. 비12월 결산 변경과 미래 기간의 결산월 mode가 과거 label에 영향을 주는 현재 assign_fiscal_periods 계약도 원문과 대조해야 한다.
- Local generated-contract 재검사는 missing `exchange_calendars`로 즉시 실패했다. Local pytest와 이 의존성 실패를 테스트 hang이나 통과로 기록하지 않는다. Generated contract·기존 DART/KRX/top-N/decile/CURRENT 검증은 위 전체 원격 CI에서 확인했다. 새 capture 테스트와 실제 no-op/source SHA 검증은 현재 환경에서 제한시간 내 직접 실행했다.

**현재 완료:** v5 배포·100건 live checkpoint 검증, 무출력 대기 진단·bounded 파일별 CI, 6개 초기 공시의 12개 읽을 수 있는 금융 본문 확보, 첫 독립 current-period 기대값 보존. **다음 단계:** 확보된 artifact/기대값을 재사용하여 source adapter의 완결성/인코딩 검증 및 viewer fallback 계약 → source-backed `(-)`/loss alias·unit·당기 기간/column 회귀 → parser/source version 변경과 필요한 receipt만 live 재검증 → fiscal mapping·FY2014 2015 접수 index 확장 → 독립 audit. 새 본문을 기존 parser에 단순히 통째로 공급하면 전기 연간 CF·별도 과거 table이 현재 분기 값으로 오인될 수 있으므로 당기 기간/column guard를 먼저 재현·검증한다. 이전 normalized 관측값과 원문 증거는 보존한다.

### 최종 code CI와 원격 인계

- Main code merge `56b13f38d0185c015d7f1473a396d8e7afdd6e57`의 전체 Strategy DSL CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/36994244906>는 **test / sandbox replay 3.11 / 3.12 모두 success**로 종료된 것을 직접 확인했다. Main parser validation <https://github.com/Horororong/quant-marcap-runner/actions/runs/36994244925>도 success다. Local에 부족한 pytest/exchange_calendars 등은 원격에서 설치해 실제 계약·전체 E2E를 검증했으며, local 실행 실패를 pass로 바꾸지 않았다.
- 뒤따르는 `6411d24`와 이 checkpoint는 evidence/status/documentation 변경이다. 금융 parser·normalized/state·DSL contract의 마지막 code state는 위 검증된 merge와 같다. Workflow가 source report/data-only commit에 전체 CI를 다시 실행하지 않는다는 것을 현재 run 목록과 paths에서 확인했다. 완료한 bootstrap·원문 확보·전체 코드 검증을 임의로 재실행하지 않는다.
- 다음 세션은 `AGENTS.md` → `PROJECT_CHARTER.md` → 이 문서의 마지막 checkpoint부터 읽고 원격 main·CI를 직접 확인한다. `docs/audits/legacy/viewer_sections/*.json`, `daewoo-current-period-expectations-20010103000052.json`과 artifact `11221241095`를 우선 재사용한다. 새 capture를 다시 실행해도 저장된 12개 section은 no-op이다. Parser/source version을 바꾸기 전 독립 기대값과 기간·scope·단위·실제 numeric column 회귀를 먼저 작성한다.

## 단계 8: 10월 한시 수집량 증량 (구현·검증 checkpoint)

- 소유자의 10월 안 처리 요청에 따라 기존 fast workflow만 재사용한다. 기준 원격 main은 `6b7912e291826c57c361eac009728b90a38e8eba`; 기존 일일 예약 실행 `36921413786`과 v5 push 실행 `36957000576`의 success를 직접 확인했다. 현재 대기량은 113,719건이다. 기존 예약은 UTC 15:30이며 실제 Actions 시작은 지연될 수 있다.
- 기존 **00:30 KST**에 **08:30 / 16:30 KST** 두 배치를 추가한다. 회당 최대 2,000건으로 **하루 최대 6,000건**, 총 legacy 요청 예산은 최대 7,500회(배치당 2,500회, retries 포함)다. 실제 API 계정 한도는 조회하지 못했으며 다른 DART 작업도 같은 키를 사용한다. API 020 중단과 다음 실행 resume를 유지하며 설정 상한을 실측 처리량으로 주장하지 않는다.
- 추가 배치는 modern tasks 0으로 기존 modern 수집량을 세 배로 늘리지 않는다. 기본 daily/manual의 modern 1,000 tasks와 push의 legacy 100건 검증은 유지한다. Workers 3, 요청 간격 0.5초, 제출 deadline 3,300초, checkpoint 25건, collection step 75분/job 100분, 공유 writer lock과 cancel-in-progress false는 그대로다.
- `legacy_schedule_gate.py`는 최신 main checkout 직후, dependencies/API 실행 전에 추가 배치를 판정한다. 자동 pending 0이거나 실제 시작일이 **2026-11-01 KST 이후**이면 setup/install/collector/publish를 전부 건너뛴다. 지연된 October trigger도 만료 후 수집하지 않는다. 누락·손상 status와 알 수 없는 추가 schedule은 실패로 종료해 API 요청을 하지 않는다. 추가 cron 자체도 10월만 예약한다(`30 7,23 * 10 *`). 다음 해 10월의 재발 예약은 날짜 gate가 수집을 차단하며 기본 일일 운영은 유지한다.
- Local stdlib 경계 테스트 **6 passed**: KST 만료 직전/직후, queue 소진, 기본 daily/push/manual 보존, status 누락/손상, 알 수 없는 cron/naive datetime. 세 workflow YAML parse, syntax compile, git diff check 통과. 기존 automation regression에 schedule/gate/modern 예산 경계를 추가했다. 두 기존 CI는 새 gate 회귀를 30초 이내 실행하며 기존 파일별 pytest 60초 제한도 유지한다.
- 113,719 / 6,000은 **최소 19일(57개 full batch)**이다. 10월 3일부터 세 배치를 전부 처리하면 10월 21일 전후가 이론적 queue 처리 예상이다. 실측 일일 처리량·API 제한·Actions 지연·parser/source version 변경에 따른 필요한 재처리를 반영하지 않은 best case다. **10월 말은 수집 목표이며 금융적으로 검증된 최종 완료를 보장하지 않는다.** Parser/source adapter·FY2014 범위·독립 audit는 별도 미완료다.
- 다음: feature PR의 전체 CI + legacy validator를 확인하고 main으로 normal merge → 제한된 live push 결과와 실제 요청·pending 감소를 기록한다. 배포 전 이미 완료한 source evidence·독립 기대값·정상 receipt를 재수집하지 않는다.

## 단계 8 live 완료: 10월 한시 증량 main 배포·수집 확인

- Feature commits `3adb7d354280001643e7243ae947afe2be100318`, `e0fc32db5e5bfc9d6e175f1daa4a985f2b82ae8f`는 PR #25로 normal merge `aa6c8722a0842d717468d855606b7ab76208eac4`에 반영했다. 최종 feature 전체 CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/37000310336>와 validator <https://github.com/Horororong/quant-marcap-runner/actions/runs/37000310360> 모두 success였다. 전체 test + sandbox replay 3.11/3.12, legacy pytest 56개 및 별도 gate 회귀 6개를 확인했다.
- 병합 직전에 recent DART 자동 commit `23bdabcbfa6da63ec722e4b8e1632dd85e8db718`이 갱신된 recent gzip과 rotation/status를 main에 저장했다. 이를 normal merge로 보존했다. 따라서 main의 데이터 tree는 feature snapshot과 다르며, main 전체 CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/37002403185>에서 **test + sandbox replay 3.11/3.12 모두 success**를 별도로 확인했다. Main validator <https://github.com/Horororong/quant-marcap-runner/actions/runs/37002403064>도 success다. 수집 대상·금융 parser/source/DSL/provider/capability 변경은 없고 source 품질을 처리 건수로 인증하지 않는다.
- 실제 배포 확인 <https://github.com/Horororong/quant-marcap-runner/actions/runs/37002402985> success; GitHub 보고서와 내려받은 artifact에서 **100 selected / 100 completed / 100 requests / BATCH_COMPLETE / rate_limited False**를 대조했다. Modern tasks는 0이다. 25/50/75/100건 checkpoint가 실제 로그에 남았다. 원래 100건을 재배포하여 반복 수집한 것이 아니라 durable receipt를 제외한 다음 pending 100건을 처리한 것이다.
- 자동 데이터 commit `07bf21a92d4f33ee8797560a66e4cf9f2b929ff8`에 이 결과가 저장됐다. Durable processed는 **1,301 → 1,401**, automatic pending은 **113,719 → 113,619**, 4F 표기는 16 → 31이다. 새 100건의 분류는 NO_METRICS 74 / PARSED_PARTIAL 11 / PARSED_4F 15다. Collection/quality complete는 계속 False이며 독립 금융 정확성을 뜻하지 않는다. 이 단계에서 전체 normalized 과거 field/row를 새로 독립 대조했다고 주장하지 않는다.
- Artifact `11223389756`의 실제 ZIP SHA256은 `528ae547a40f7b3d67462e9996e267db325fe7b50e6bcbad00f9b76ebff08b16`, 만료 2026-10-16T11:44:58Z다. Machine checkpoint: `docs/audits/legacy/october-capacity-checkpoint-20261002.json`. 금융 원문 12개 section과 기존 독립 기대값은 재수집하지 않았다.
- **배포된 예약:** 매일 00:30 KST, 10월 중 추가 08:30 / 16:30 KST. 각 최대 2,000건, 하루 최대 6,000건으로 동일 shared lock 안에서 실행된다. 추가 두 배치는 legacy only이며 pending 0 또는 2026-11-01 KST 이후 실제 시작이면 API·설치·publish를 건너뛴다. GitHub scheduling 지연을 감안해야 하며 현재까지는 100건 배포 확인만 실측했다. 113,619건은 최소 57개 full batch / 19일; 10월 3일부터 full capacity이면 10월 21일 전후다. 10월 말은 현재 대기열 처리 목표이며 요청 한도·deadline·필요한 version 재처리·FY2014 범위 확장은 예측을 바꾼다.
- **Local/GitHub 상태 구분:** sandbox Git fetch는 proxy 8080 연결 실패로 즉시 종료됐고 connector의 repository fetch/blob는 gzip을 UTF-8로 읽을 수 없어 거부했다. 로컬 work HEAD는 테스트한 `e0fc32d`에 clean 상태로 유지하고, 최신 recent/normalized gzip을 받지 못한 채 main과 같다고 주장하거나 데이터를 추정 재생성하지 않았다. Main code·live 상태·최종 인계는 GitHub가 SSOT다. 다음 세션은 GitHub의 최신 handover/status/CI를 먼저 읽고, Git 전송 경로가 준비되면 fetch/normal fast-forward로 로컬도 맞춘다. 로컬의 1,301 상태를 최신 진행량으로 쓰거나 이미 처리된 100건을 반복하지 않는다.

**다음 단계:** 첫 세 예약 배치의 실제 processed 증가·requests·stop reason·API 020 및 ERROR quarantine을 관찰해 평균 일일 처리량으로 10월 예측을 갱신한다. 동시에 기존 재무 본문·독립 기대값을 재사용하여 source adapter 완결성/인코딩 및 당기 기간/column·단위·음수/loss guard를 검증·보완하고 필요한 receipt만 reprocess한다. Source/parser version이나 FY2014 index 범위를 바꾸면 이 19일 capacity 예상은 다시 계산한다. 독립 금융 audit와 품질 기준을 만족하기 전 legacy 실행 capability를 공개하지 않는다.
