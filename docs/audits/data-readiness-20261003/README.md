# 장기 데이터 준비상태 감사 — 2026-10-03 UTC

장기 백테스트 전체 완료로 판정하지 않는다. 기존 보고 기능과 고정 실행 묶음은 유지됐고, 포함 데이터의 기존 예제는 공식 요청기간 보고까지 실행됐다. 그러나 과거 재무 누락, 독립 수치 대조 미완료, 기업행위 범위와 캘린더 문제 때문에 이를 2000년부터의 투자 검증으로 확대할 수 없다.

## 실제 확인한 저장소와 실행 환경

- 감사 기준 main: `49afdcab324c2b778e21456e70a4e306feec4c0a`. 종료 전 조회 main: `40fe72e420f12e069eb1ba07ef712e61684d8a78`. 사이의 변경은 recent financial batch와 rotation/status 3개 파일뿐이었다. 자동 수집 변경을 덮어쓰지 않았다.
- 작업브랜치: `audit/data-readiness-20261003`. 표본계획 원격 커밋 `56c8020e86e7f1d49e357732913d96a5e435ae96`, 원문·시장 감사 원격 커밋 `59c6cdf55b088b18545e7b2c91a51945f834e693`. 로컬과 원격은 출발 커밋이 다르므로 커밋 ID가 같다고 표시하지 않는다.
- production 코드 7개 파일은 기준 main과 바이트/해시 일치. main CI `37159959636`의 test/CP311/CP312가 success. 이번 변경은 감사 도구·표·기록뿐이다. main 병합이나 새 실행 묶음 생성은 하지 않았다.
- 기존 kit `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`의 107개 고정 파일 verify 정상. 실제 포함 가격은 2019·2020·2024년, 재무는 2019 Q1/H1/Q3/FY 및 2020 Q1/H1이다. 저장소 전체 coverage와 실행 ZIP coverage를 혼동하지 않는다.

## 백필 상태와 확보 범위

마지막 legacy 배치 `37145419881`은 중단/정체가 아니라 정상 완료다. 2,000개 요청/문서, `BATCH_COMPLETE`, rate_limited=false, 25개 단위 체크포인트와 마지막 2,000개 checkpoint 저장을 로그에서 확인했다. 기준 상태는 매핑 115,020건 중 처리 9,401건, 미처리 105,619건, usable-four-factor 313건이다. collection_complete와 quality_complete는 모두 false다. 이전 parser 버전의 성공 건수를 현재 v5 완료 건수에 합산하지 않았다.

종료 전 Actions 조회에는 실행 중인 legacy 배치가 없다. 기존 일일 및 10월 추가 schedule, 공유 concurrency lock, 원격 체크포인트 재개 경로는 유지돼 있다. 새 collector를 중복 기동하지 않았다. UTC 23:30 예정 실행은 조회 시점에 아직 새 run으로 보이지 않아 실행됐다고 주장하지 않는다. GitHub schedule 지연·미실행 가능성 때문에 완료일을 보장할 수 없다. 마지막 배치는 정상 완료됐으므로 중단된 프로세스를 종료하거나 리셋할 사유가 없다.

| 자료 | 실제 확보/확인 | 누락·한계 |
|---|---|---|
| 가격 | 1995-05-02~2025-12-30 파일은 원격 main과 동일. 원격 manifest 최신 2026-10-01 | 로컬 2026 파일은 2026-09-29까지만 있어 최신 main과 다름. 파일 존재는 전 종목/기업행위 인증이 아님 |
| 과거 재무 | legacy 인덱스 138,540건, 매핑 115,020건. 현재 v5 4팩터 파싱 313건 | 105,619건 미처리, 원문 항목 추출 실패 다수. 2014 회계연도/2015 공시 경계도 완전하지 않음 |
| modern 재무 | 최신 state와 historical map으로 다시 산출한 2016~2020 모든 기간의 mapped terminal gate 100% | terminal은 CFS OK 또는 CFS NO_DATA와 OFS terminal을 의미. 수치 유효성/PIT/상폐 전체 유니버스 인증이 아님. 2015 H1/Q3 fallback 없음, 2021 이후 OFS 미수집 다수 |
| 과거 유니버스 | Date/Code 역사 가격 패널에서 관측 종목 사용 | 공시 연결에는 현재 corp map도 보조 사용. 과거 종목코드 재사용·이름·결산기·미매핑 종목 독립 확인 미완료 |

`main-status/dart_full_backfill_status.csv`와 `dart_pit_coverage_by_period.csv`는 9월 23일의 오래된 요약이다. 원본을 보존하고 최신 state로 만든 `modern_period_completion.csv`를 별도로 제공했다. 예: 2021 Q1 1,768/2,536, H1 1,781/2,536 terminal. 2024 Q3 2,017/2,812, CFS 미수집 38건 및 OFS fallback 누락 757건. 최신 원격 수집 상태를 실제 수치의 품질 인증으로 사용하지 않는다.

## 독립 원문 점검 결과

성과 계산 전에 커밋한 `SAMPLING_PLAN.md`에 따라 기존 캡처 원문을 전수 확인했다. 제약/오류 위험을 선택한 표본이며 임의 무작위 표본이 아니다. 6개 회사, 6개 접수번호, 12개 HTML 본문에서 당기 별도 30개 및 전기 연결 연간 15개, 총 45개 재무 셀을 점검했다. 기업·종목·기간·항목·접수번호/URL·원문 literal·단위·scope·저장 상태·차이·해시·위치를 `financial_audit.csv`에 기록했다. 감사 도구는 수집 parser를 import하지 않는다.

**저장 수치 독립 일치 인증은 0건이다.** 당기 30개는 최신 원격 receipt state가 모두 `NO_METRICS/metric_rows=0`이라 저장값을 빈칸으로 기록했다. 최신 원격 normalized gzip의 실제 행을 내려받아 확인하지는 못했다. 로컬 retained normalized에서 해당 6개 receipt 행이 0개임은 별도로 확인했지만, 일부 파일 해시가 main과 달라 최신 수치 부재의 물리적 증거로 대체하지 않는다. `normalized_snapshot_limits.json`을 따른다.

전기 연결 연간 15개를 당기 분기로 대체하지 않았다. 비츠로테크 5개 항목은 원문 단위 미기재, 대구백화점 BS 3개는 괄호 부호 맥락 미확인으로 환산값을 인증하지 않았다. 피어리스 당기순손실의 label과 대우중공업 `(-)` 및 피어리스 `△` 표기를 기록했다. 소스 숫자 45건을 봤다는 사실을 45개 저장 수치가 맞는다는 주장으로 바꾸지 않는다.

공시일 6건은 실제 main viewer 제목과 catalog 날짜를 대조했다. 전체 정정 이력·장중 공시시각·과거 결산기·전략에서 사용 가능한 날짜는 미확인이다. usable date는 빈칸으로 남겼고 PIT 인증은 false다. 원문 실제 기준기간은 1999/2000에 집중되며 다년도·현대 공시·정정공시 대표성 확보는 **차단됨**이다. shell DART 접근은 환경 proxy 연결 오류(exit 7)로 막혔으며, 기존 캡처만 재사용했다. GitHub native 조회는 가능했지만 binary 원격 normalized 다운로드는 차단됐다.

## 가격·유니버스·기업행위

`market_action_audit.csv`는 구현/실제 자료 검증/자료 부족/미지원 구분을 유지한다. 현재 상장목록만으로 과거 투자 유니버스를 생성하는 경로는 확인되지 않았다. 하지만 factor finite intersection에 따른 제외는 존재하므로 과거 금융정보 누락을 조용히 전체 유니버스 완전성으로 취급하지 않는다.

- 원가격 및 등록된 split/share exchange가 실행 경로에 반영되고, 보유 중 1bp return-reference 검사가 존재한다. 기존 실제 자료 검증은 2024년 split 6개와 주식 교환 1개 범위다. 전체 기업행위를 인증한 것이 아니다.
- 현금 교부 contract는 구현됐지만 production 등록 0개다. 제이시스메디칼 실제 지급일/수수료 후 지급액 등이 없어 해당 보유 노출은 data_gap이다. 배당·권리·전체 상폐 cash flow와 합병 단주 현금 처리도 부족/미지원이다.
- 거래가능성은 Close>0, Volume>0 등을 사용한다. 모든 거래정지·가격제한폭에서 실제 주문 체결 가능성을 인증하지 않았다. 원행을 삭제하거나 원가격을 덮어쓰지 않았다.
- 사용한 KOSPI/KOSDAQ/KOSPI200 벤치마크는 가격지수로 배당 제외이며 최신 종료일 2026-09-17. KOSDAQ150은 2026-10-01까지다. 총수익지수로 표시하지 않는다. 배당 현금을 자동 가산하지 않으므로 배당 중복 반영을 실제로 인증한 것도 아니다.
- XKRX 4.13.2와 관측 시장일의 차이가 1995/1996/1998 및 로컬 2026에서 나타났다. 선거/휴일·KOSDAQ 개장 전 구간의 calendar 적용 문제가 가능하다. KRX 1차 달력 접근은 **차단됨**으로, 실제 거래일 가격 누락인지 calendar 오류인지 확정하지 않았다. 캘린더 readiness를 완화하거나 행을 보간하지 않았다.

## 확정 가능한 실행 범위

아래 정식 보고는 공식 CURRENT 요청기간 계약 1의 소프트웨어 보고 가능성이다. 투자전략 채택·OOS·현실적 비용·전체 데이터 인증과 구별한다. 정식 보고 행의 날짜는 실제 거래일 범위다. 기존 NAV 예제 행은 DSL 요청 구간이며, 휴장일을 실행 거래일로 인증하지 않는다.

| 분류 | 기존 전략 조건/기간 | 실제 근거 |
|---|---|---|
| 정식 요청기간 보고 확인 | KOSPI/KOSDAQ, 시총 10조 이상 중 시총 1위 1종목, 동일비중, 1/4/7/10월 말 신호·다음 종가, 2019-01-02~2020-12-30 | 이전 checked 보고 보존 및 이번 preflight 재확인. zero/fixed_cost 비교, KOSPI 가격지수 |
| 정식 요청기간 보고 확인 | 분기 EP/CFP/SP + BP, 20종목 동일비중, 4/10월 말 신호·다음 종가, 2020-04-01~2020-11-30 | 이번 checked 전 단계 성공. 일별 NAV SHA가 기존 CP311/312 검증과 동일. 기존 all-zero 비용. 365일 미만이므로 CAGR 계산 불가 |
| 기존 검증 NAV만 | size decile 2020-04-01~05-08, 사용자 선택 5월 재무 2020-05-01~06-02, 등록 split 예제 2024-03-01~04-26 | 기존 CP311/CP312 replay 근거. 이번 execution-only 재실행이나 성과지표 추가 없음 |
| data_gap | 2000년 재무, 2016년 4월 재무, 2021년 10월 재무 | 최신/로컬 state 기반 실제 preflight 실패. 필요한 과거 공시 또는 OFS fallback 누락 |
| data_gap | 기존 kit의 2000년 가격 요청, 기본 4기간 보고 요청 | checked fail-closed exit 3. 가격 파일 또는 2000년대 일별 NAV 없음. 요청을 줄이지 않음 |
| data_gap | 1998년 / 최신까지의 로컬 2026 가격 요청 | calendar/source coverage 실패. 로컬 최신 파일 차이와 benchmark 종료일 문제 별도 |
| capability_gap | 연간 PER, 연간 ROE, TTM earnings yield, 미국 ETF | 실제 compile 실패. 분기 proxy나 한국 주식으로 대체하지 않음 |

저장소 size 2000 및 재무 2017 진단은 preflight만 통과했다. NAV/기업행위/공식 보고를 실행하지 않았으므로 확정 정식 보고 범위에 넣지 않았다. 장기 금융 전략 전 구간이나 단순 가격 전략의 임의 기간 전체를 한 번에 인증하지 않는다. `backtest_scope.csv` 및 `preflight_matrix.json`을 참고한다.

## 검증·보존·수정

kit verify 정상, 요청기간 보고 회귀 5개 테스트 정상, generated machine contract 정상, 원문/상태 변경 fail-closed 감사 경계 3개 정상. 소프트웨어 테스트(합성 NAV 포함)는 데이터 인증과 분리한다. 실제 포함 KRX/DART checked 금융 실행 결과 `report_ready=true`, `report_complete=true`. 이전 NAV 해시 `cea3c5b9274b4a5d457cb993d3f9740617cb821a30e63ef3cd96f8003776db21`과 동일하다.

이번 수정은 최신 state에서 coverage를 독립 산출하고, 45건의 원문 기대값·해시 검증 도구와 가능/차단 범위를 저장한 것이다. 첫 감사 실행의 캡처 status 이름 가정을 실제 `HTTP_RESPONSE_CAPTURED`로 수정했다. 첫 checked 시도는 기간 config 생성 전 실행돼 입력 오류(exit 4)였고 파일 생성 후 새 결과 디렉터리에서 성공했다. 실패 로그도 보존했다. 큰 GitHub blob 응답이 JSON이 아닌 CSV라는 전달 형식을 확인해 읽기 처리를 수정했다. 이 작업 중 발견한 생산 parser 추출 실패, 캘린더 차이, PIT 한계는 증거가 부족한 상태에서 변경하지 않았다.

기존 원자료, 체크포인트, fixed kit/manifest, registry, readiness gate는 수정하지 않았다. 보고 코드를 다시 만들거나 browser 검증을 반복하지 않았다. 정확한 실행 명령은 `REPRODUCE.md`, 로그 해시/결과는 `evidence_ledger.json`에 있다. 다음 작업 하나는 **기존 6개 공시의 viewer 본문 fallback 계약을 원문 fixture로 검증하는 것**이다. 당기 열·scope·단위·부호를 확인하고 전기 연간 OCF를 분기 값으로 가져오지 않는 조건을 먼저 통과시킨 뒤 parser 변경 여부를 판단한다.
