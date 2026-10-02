# DART legacy 2000~2014 — 단계별 인계

## 최신 작업 checkpoint (2026-10-02 UTC)

상위 지침·resume·기존 daily 자동화는 main에 배포되어 실제로 동작한다. 대표 8개 원문 확보 후 첫 source-proven parser guard `legacy-v5-single-amount`를 작업 branch commit `16bf1cb`에 저장하고 local 전체 Strategy DSL **31/31**을 통과했다. 첫 실행의 empty-state coverage 오류도 재현해 배포 전 보완한다. 현재 단계는 **v5 배포·live 재처리·최종 CI 확인**이다. 아래의 단계별 기록과 마지막 checkpoint가 최신 상태이며 이전 수치는 당시 버전의 이력이다. 다음 세션은 원격 main과 현재 parser/source version을 먼저 다시 확인한다.

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
