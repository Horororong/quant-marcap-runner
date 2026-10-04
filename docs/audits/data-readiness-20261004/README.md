# 데이터 준비 및 독립 감사 · 2026-10-04

이번 범위는 기존 백필 상태, 저장된 1차 원문과 재무 수치 대조, 실행·보고 가능 범위 확인이다. 새 전략·최적화·보고 UI 변경은 없다. 보고 기능은 재현됐지만 데이터 준비·독립 품질검증·실제 전략 검증은 각각 미완료다.

검토용 [draft PR #29](https://github.com/Horororong/quant-marcap-runner/pull/29), 생성 시 remote head `35b19fc5d192a4cf81f3d8e12569180ce97e6172`. 감사 변경은 main에 병합하지 않았다. 로컬 감사 commit `46dbbac`과 remote checkpoint는 commit 생성자/부모가 다르며 33개의 감사 blob SHA는 동일함을 확인했다.

## 확인한 저장소 및 실행 상태

- 시작 시 clean local `work`, main 기준 `40fe72e420f12e069eb1ba07ef712e61684d8a78`. 다른 작업자의 미커밋 변경 없음. 감사 브랜치 `audit/data-source-readiness-20261004`.
- 작업 중 기존 예약 백필 run **37172051500**, job **111346825667**이 성공했다. main은 **4833fb503105d810ea6e8e905d914f1ab3c28632**로 이동했다. 새 수집 요청을 시작하거나 기존 checkpoint를 지우지 않았다.
- `live_state.json`의 최초 스냅샷과 `backfill-job-*.log`의 실제 성공 로그를 구분한다. 새 main의 status/coverage는 `latest_*.csv`에 별도 보존했다. 새 main의 두 binary normalized shard는 이 세션에서 전량 다시 읽지 못했다. 따라서 `coverage_snapshot.json`과 72건 대조는 **40fe72e 파일 기준**이며 새 2,000건의 품질 인증이 아니다.
- 초기 및 이후 GitHub Actions 조회에서 실행·대기 중인 collector는 없었다. 이전 채팅 실행 환경의 로컬 프로세스는 **확인 불가**다. 새 환경에 프로세스가 없다는 사실로 이전 환경 중단을 추정하지 않는다.
- 기존 fast/full/signal/legacy/audit 작업은 `super-value-fast-pit-backfill`, `cancel-in-progress: false`를 사용한다. 구형 `backfill-dart-legacy-quarterly.yml`는 별도 lock이므로 동시에 시작하면 안 된다. 이 감사에서는 모든 수집·dispatch를 추가로 실행하지 않았다.
- PR #28과 main merge d442e07, main CI **37159959636**의 test 및 CP311/CP312 offline replay 성공을 실제 조회했다. PR #27은 이전 open 상태이며 재시도하지 않았다. 새 데이터 커밋을 마지막 코드 CI와 혼동하지 않는다. HANDOFF_CURRENT.md는 CI trigger 대상이므로 감사 브랜치에도 실제 전체 test/sandbox-replay CI가 시작됐다. 최종 head의 check-runs가 모두 완료됐는지는 GitHub에서 별도로 확인한다. 진행 중인 CI를 통과로 표시하지 않는다.

## 백필 및 실제 coverage

| 자료 | 요청/구현 범위 | 실제 확보 및 최신 기준 | 공백/실패·미검증 |
|---|---|---|---|
| KRX 가격·과거 관측 유니버스 | yearly 1995~2026, KOSPI/KOSDAQ | **32 parquet / 15,257,282행**, 1995-05-02~2026-10-01. 전체 파일을 읽고 SHA·시장별 날짜/종목/행수 확인. Date/Code 중복 0 | KOSDAQ은 처음부터 존재하지 않음. 1997-12-26/27 `015545` 종가 2건 없음. 해당일 거래정지/상폐 여부는 추가 원문 필요. 배당·기업행위 전수 검증 아님 |
| legacy DART | 2000~2014 접수 index | index 138,540 / mapped 115,020, 180/180 index 작업. 접수일 2000-01-10~2014-12-30. 최신 main 처리 **11,401**, 대기 **103,619**, 4factor 파싱 **616** | NO_METRICS **8,620**, NO_DOCUMENT **1,570**. FY2014의 2015 접수 index 공백. readable viewer와 native XML의 truncation/깨짐 차이. legacy public provider 미지원, source/PIT 품질 미완료 |
| modern DART full history | 2015~현재, CFS/OFS, FY 및 지원 중간보고 | actual checkpoint **136,914 unique terminal tasks**: OK 93,877 / NO_DATA 43,037. 현재 mapping 4,143행, unmatched 156. 현재 수집 cutoff로 expected 235,352 / pending **98,438**. 실제 원본 shard **184개 / 10,591,081 raw rows**, requested period_end 2015-12-31~2024-09-30, filing 2015-06-24~2026-09-11 | 9월 status의 완료 78,479/잔여 144,393은 stale. terminal NO_DATA는 usable 재무값이 아님. 2015 중간보고 상당 부분은 NO_DATA. 이후 연도·OFS incomplete. actual shard structural 결과는 `modern_shards.json`, 기간별 task 결과는 `modern_task_coverage.csv` |
| recent DART | 2024~2026 rotation | Oct3 300개 기업 시도, offset 900→1200, 오류 0; status records 269,105 | rotation 수치가 전체기간/기업·정정 이력 인증은 아님. 2026FY/미도래 분기는 수집 대상으로 간주하지 않음 |
| 벤치마크 | KOSPI/KOSDAQ/KOSPI200/KOSDAQ150 | KOSPI 1995-05-02, KOSDAQ 1996-07-01, KOSPI200 1995-01-03 시작, 모두 2026-09-17까지. KOSDAQ150 2015-07-13~2026-10-01 | 모두 **가격지수**, 배당 제외. 첫 세 지수는 최신 equity 기간과 불일치. 총수익지수 미확보 |

Baseline mapped pending을 normalized row count와 document SHA까지 독립적으로 확인했다. 손실된 parsed checkpoint는 0건이었다. current state 9,403 중 2개 transport-only receipt가 mapped 요청 집합 밖에 있어 status의 mapped processed 9,401과 차이가 난다. 이를 새 main의 처리 11,401과 혼합하지 않는다.

현대 expected task는 저장된 현재 mapping에 기존 `build_tasks`의 기간·수집 cutoff 규칙을 적용한 계산이다. 과거 신규상장/현재 코드 매핑의 정확성 인증이 아니다. 특히 `current_stock_code`의 기본 first_date를 실제 상장일로 사용하면 안 된다. 수집 cutoff는 실제 공시일 대체값이 아니다.

2026년 기존 표준 `krx_history_audit.py` 실행은 **data_gap(exit 3)**: 고정 calendar 4.13.2의 185 거래일과 실제 양 시장 183일 사이 `2026-06-03`, `2026-07-17` 차이. 공식 휴장 근거를 확인하지 못했으므로 **calendar/source discrepancy**, 확정 가격 누락으로 분류하지 않는다. 444개 종가/참조수익률 차이, 5,534개 내부 관측 공백, 시작/종료 censor 54/76은 검토 후보이며 기업행위를 추정하지 않는다. 원자료·calendar·registry를 수정하지 않았다.

## 독립 재무 검증

성과/NAV 신규 실행 전에 `SAMPLE_PLAN.md`를 commit했다. 기존 실패 조사 자료를 사용한 목적 표본이다. 수익률로 선정하지 않았으며 전체 시장 대표 표본이 아니다.

**8기업 / 8공시 / 72항목**, 원문 기준기간 1999~2000, 일부 fiscal label 2000/2001. 제약·전기기기·중공업·화장품·유통·제분·통신. OFS 46 / CFS 26, 당기 Q1/H1/Q3 누적 및 전기·전전기 연간 비교를 포함했다. 공시 접수일은 2000-02-14~2001-02-13이다.

기존 Actions에 보존된 **DART primary viewer financial sections와 OpenDART native XML**을 실제 내려받아 읽었다. collector를 재실행해 expected를 만든 것이 아니다. viewer artifact 11221241095, native artifact 11205027337. 각 body/member SHA를 기존 capture provenance와 대조했고, 72개 선택 cell의 literal·offset·원문 단위·기간을 `financial_expected.json`에 보존했다. `verify_financial_samples.py`는 collector/financial parser/performance 모듈을 import하지 않고 선택된 단일 숫자를 저장값과 비교한다.

| 주 분류(서로 배타적) | 건수 | 해석 |
|---|---:|---|
| 해당 parser 저장값 없음 | 49 | 현 v5의 6공시는 NO_METRICS. 원문에 값이 있어도 단위 5건은 원문 heading 공란으로 KRW 인증 보류 |
| 저장 기간 불일치 | 18 | 대한제분 v4의 OFS period_end는 1999-12-01이나 원문은 12-31. CFS 9개는 이전 **연간 Jun1999**을 H1 Dec1999로 라벨링. 숫자 일치로 PIT 인증 불가 |
| 금액 불일치 | 3 | 대한제분 단기차입금 여러 숫자 concat, 데이콤 순이익 concat 및 한 부문 매출을 전체 매출로 저장 |
| 항목 의미 불일치 | 2 | 대한제분 보유 채권 **자산**을 사채 **부채**로 분류; 데이콤 사채 `제2회`의 숫자 2를 금액으로 저장 |

저장값 있는 항목은 23개이며 numeric_equal 19 / numeric_unequal 3 / 금액이 아닌 header 1이다. 19개 중 18개는 기간 오류, 1개는 자산/부채 의미 오류다. **완전한 PIT 일치 0 / 정정 chain 인증 0**이다. 72건을 72건 금액 일치 또는 전체 데이터 인증으로 표현하지 않는다.

로컬 `independent-audit-sources.zip`에는 감사 증거와 선택에 사용한 12개 viewer section·2개 native XML 원문을 함께 보존한다. Git에는 전체 원문 대신 선택 cell·SHA·출처를 보존했다. Actions artifact 만료 후에도 이 로컬 archive를 보존해야 full-body 재검증이 가능하다.

`financial_audit.csv/json`에는 기업·코드·접수번호·원문 링크·scope·단위·원문 값·저장 값·저장 parser/기간·공시일·정정 표시·strategy availability·차이 원인을 보존했다. index 접수일과 원문 접수번호 날짜가 일치함을 확인했으나 원문 전체 정정 chain을 확보하지 못했다. 대한제분의 `[첨부추가]`는 정정으로 임의 분류하지 않았다. true 정정 전/후 pair는 이 확보 표본에 없어 검사 미완료다. 공시일이 같다고 정정 이전 시점의 전략 사용 가능성을 인증하지 않는다.

오류는 **보존된 v4 관측값**에서 확인됐다. 현재 public DSL은 이 legacy normalized를 읽지 않으므로 이번 기존 size 예제 NAV를 바꿀 근거가 없다. immutable 관측값을 덮어쓰지 않았다. 현재 source adapter가 readable viewer를 완전하게 수용하지 못하는 문제와 당기/전기·scope·unit guard를 먼저 수정·회귀 검증해야 한다. 임의 값 복구나 v5에 전기 연간값을 공급하는 변경은 하지 않았다. 현 v5의 616개 4factor도 독립 품질 인증된 수치가 아니다.

## 가격·유니버스·기업행위 상태

| 항목 | 구현됨 | 실제 자료로 검증됨 | 자료 부족 / 미지원 |
|---|---|---|---|
| 과거 유니버스 | 해당 날짜 historical KRX panel, 현재 상장목록으로 재구성하지 않음 | 32년 실제 panel 읽기 및 과거 존재/현재 부재 코드 보존 확인 | 관측 first/last는 법적 상장/상폐일 인증 아님. DART identity mapping 전수 미검증 |
| 신규상장·상폐·거래정지 | 양 거래일 tradability/Volume guard, 사라진 보유종목·참조수익률 guard | 기존 예제 494일 실제 execution/held return 통과, 표준 source audit 후보 생성 | 모든 terminal event/정지 사유 원문 미확보. 관측 끝을 상폐로 자동 분류하지 않음 |
| 우선주·스팩·리츠·금융업 | panel에 존재하면 일반 universe에 포함, 명시적 지원 filter만 사용 | 우선주 1997 missing close 2건 확인; registry에 우선주 split 존재 | complete dated 종류/업종 eligibility 없음. PIT 종목유형·업종 제외 조건 미지원/자료 부족 |
| 종가·분할·합병 | 원 종가와 보유주식수 기반, production registry 5. 합병 1건 및 분할 6건 | 기존 source-backed E2E/합병·분할 테스트의 main CI 성공 확인. 이번 size 예제 return guard 통과 | 원문 링크·registry 존재만으로 전체 금융적 정확성 인증하지 않음. 모든 과거 기업행위 미확보 |
| 현금교환 | 공통 cash/share 계약·synthetic 테스트 구현 | actual main CI 테스트만 확인 | 제이시스 287410 actual payment/net tax 근거 미확보, production registry entry 없음. 해당 노출은 차단 |
| 배당·수정주가·TR | 현재 equity path에서 현금배당 지급을 가산하지 않음 | 가격지수 benchmark의 dividend false 확인 | 배당/rights 전수 자료 및 equity 총수익 path 미지원. 현재 경로에 별도 배당 가산이 없어 이 경로의 배당 중복 가산은 없음. 공급자 수정방식 전체 인증 아님 |
| 벤치마크 | 명시 지수 close alignment gate | 실제 CSV 날짜 범위, 기존 size 예제 정확한 날짜 정렬 확인 | price index, TR 비교 불가; latest gap 존재 |

## 실제 백테스트 가능 범위

Capabilities는 표현/실행 계약, coverage는 실제 data manifest다. main에 32년 가격이 있다고 frozen kit에 모두 있다고 가정하지 않는다. 설치 kit는 **KRX 2019/2020/2024**, DART **2019 Q1/H1/Q3/FY + 2020 Q1/H1**, 기존 예제 5개다.

현재 verify 기준: kit `26e4ec02e569…`, source `822c435…`, machine **23**, factor registry **7**, engine **v2-16-exec-3**, PROJECT **v2-16**, CURRENT **v2-18**, corporate registry **5**. 핸드오프의 과거 factor 6 / CURRENT v2-17을 현재 버전으로 사용하지 않는다. 전체 pinned packages·실제 installed verify는 `kit_verify.json`.

| 자산군/조건 | 기간 | 정식 성과 보고 | 검증된 NAV / 차단 구분 |
|---|---|---|---|
| 기존 `kr_equity_report_validation_2019_2020.json`: KOSPI/KOSDAQ, Marcap≥10조, 최대 시총 1종목, 기존 분기 리밸런스/비용/KOSPI price benchmark | **2019-01-02~2020-12-30** | **가능: 명시한 requested period**, CURRENT 표·HTML 생성 | 이번 세션 status=ok, nav_ready=true, report_ready=true, **report_complete=false**. 소프트웨어 경로 검증이며 투자전략/OOS 인증 아님 |
| 같은 예제, 이번 기본 요청 | 책 기간 미지정 / 2000~실제 최신 / 2021~실제 최신 / 가능한 최장~실제 최신 | 네 기간 전체 완료 **불가** | 책 기간 미지정. 실행 예제는 2020 종료, 2000 구간 4,690거래일 부족, 2021 구간 없음. longest는 **예제 NAV 내부 2019~2020**만 보고. 최신 시장 2026까지 확장한 결과로 표현하지 않음 |
| 기존 registered KRX price/size/technical 요인, equal/marcap weighting, supported lag/tradability/costs | 데이터·lookback·보유종목·지수·event guard가 모두 통과하는 지정 구간 | CURRENT requested-period path 지원; **임의 조건/1995~최신 전수 통과 미확인** | kit 기존 decile/split 예제는 verify preflight OK. 이번 새 연구 NAV 실행 없음. 기본 4기간 보고는 별도 자료 gate 필요 |
| 기존 DART standalone-quarter valuation / quarterly ROE·net/OCF margin | kit 예제의 2020-04~2020-11 등, candidate/dependency 전체 수집 및 actual filing gate 조건 | canonical 전체 기간 보고 미완료 | 구현+기존 main 실제 E2E 성공 증거, verify preflight OK. 새 연구모드 동의가 확인되지 않아 이번 NAV 실행 안 함. 독립 원문 품질 인증은 별도 필요 |
| DART 2000~2014 포함 재무 전략 | 2000~최신 등 | 불가 | **data_gap + capability_gap**: legacy source 품질·PIT/재무표 mapping 불완전, public factor source 미지원 |
| 현대 DART 전기간·전유니버스 | 2015~최신 | 일괄 가능 선언 불가 | **data_gap**: pending task, NO_DATA, source/period dependencies·revision evidence 부족 |
| 연간 PER·ROE·TTM, GP-A/NCAV/EV-EBIT, complete dated 업종/종류 제외 | 임의 | 불가 | **capability_gap**. 분기 proxy로 자동 치환하지 않음 |
| ETF/macro/자산배분 Strategy DSL | 임의 | 이번 경로 불가 | **capability_gap**. 별도 기존 프로젝트 산출물을 이 DSL 성공으로 표시하지 않음 |
| equity 배당 TR·제이시스 현금교환·완전한 상폐처리 요구 | 관련 노출 구간 | 현재 전체 인증 불가 | **data_gap / 미지원 계약**을 개별 판별. 종목을 조용히 빼서 통과시키지 않음 |

`status=ok`는 해당 실행 계약이 성공했다는 뜻이다. `nav_ready=true`는 실행 guard를 통과한 NAV, `report_ready=true`는 요청한 준비된 기간의 CURRENT 출력이 있다는 뜻이다. 일부 기간 data_gap이면 report_complete=false다. execution-only의 status=ok/nav_ready=true/report_ready=false는 성과 보고 완료가 아니다. 이 세션은 execution-only를 사용하지 않았다.

## 표준 결과와 검증의 한계

고정 비용 예제, 위 **2019~2020 예제 기간**의 원본 CURRENT CSV 값:

| CAGR | 누적수익률 | 연환산 변동성 | MDD | 최대회복기간 | Sharpe | 초기 $10,000 종료자산 |
|---:|---:|---:|---:|---:|---:|---:|
| 32.2587% | 74.5913% | 28.3240% | -31.8910% | 298 calendar days | 1.1683 | $17,459.13 |

비용: commission 1.5bp, sell tax 15bp, spread 3bp, slippage 5bp. 실제 시장 수수료/충격·해당 기간 세율 타당성의 독립 운용 인증은 아니다. USD는 정규화된 1만 달러 표시이며 KRW→USD 환율 백테스트가 아니다. 무위험률 연 0, 월 환산 `(1+rf)^(1/12)-1`, complete monthly Sharpe/volatility, sample ddof=1, sqrt(12). CAGR actual elapsed/365.2425, 365일 미만 blank. MDD는 daily, 회복 calendar days. 수치는 감사 코드에서 재계산하지 않았다.

원래 report-validation periods 재실행의 metrics/NAV/benchmark statistics는 main browser artifact와 **바이트 단위 일치**. 이번 사용자 시작연도 확인에는 새 period config만 사용했고 기존 전략은 그대로 실행했다. CURRENT 기본 네 기간 경로는 2001 시작 요건 부족으로 **report_readiness data_gap / nav_ready=false / report_ready=false**, diagnostics만 생성했다. 이를 사용자 요청의 2000 시작 보고로 오인하지 않는다.

누적자산·Log2·Drawdown은 기존 표준 HTML에 포함된다. 새 HTML `requested-report/report/report_CURRENT.html`, 공식 export `requested-report-verified.zip`, SHA/bytes는 `export_result.json`. 브라우저 period/cost/legend/sync/mobile 검증 JSON과 PNG는 실제 기존 main CI artifact에서 확인했다. **이번 새 browser rerun은 하지 않았다**. 대화 본문에서 interactive 실행 및 다른 ChatGPT 프로젝트 자동 파일 공유는 지원이 확인되지 않았으므로 미완료다.

## 재현·재개 명령과 보존

워크스페이스 결과 root: `/workspace/quant-audit-20261004`. frozen kit/runtime/원문/원본 결과는 repository 밖에 두었다. 설치는 기존 Actions의 13 upload parts+download ledger를 복원하고 각 digest/full ZIP SHA/CRC를 확인한 뒤 `bootstrap_quant.py`로 **새 별도 runtime**에 수행했다. 인터넷 설치·임의 공급자·proxy 우회 없음. 현재 runtime은 재설치하지 않는다.

```bash
timeout 60 /workspace/quant-audit-20261004/runtime/.venv/bin/python -I /workspace/quant-audit-20261004/runtime/scripts/sandbox_runtime.py verify

timeout 60 /workspace/quant-audit-20261004/runtime/.venv/bin/python docs/audits/data-readiness-20261004/verify_financial_samples.py --repo-root . --source-dir /workspace/quant-audit-20261004/sources --output-dir /tmp/quant-financial-audit-recheck

timeout 180 /workspace/quant-audit-20261004/runtime/.venv/bin/python -I /workspace/quant-audit-20261004/runtime/scripts/sandbox_runtime.py run /workspace/quant-audit-20261004/runtime/config/strategies/kr_equity_report_validation_2019_2020.json --report-periods docs/audits/data-readiness-20261004/requested_periods.json --output-dir /tmp/quant-report-recheck

timeout 60 /workspace/quant-audit-20261004/runtime/.venv/bin/python scripts/export_strategy_dsl_contract.py --check
```

`audit_coverage.py`와 `audit_modern_shards.py`는 현재 checkout의 원자료를 읽는다. 기준 commit이 바뀌면 출력도 바뀌므로 baseline과 latest snapshot을 섞지 않는다. 출력은 같은 폴더에 쓰므로 재확인은 별도 checkout에서 실행한다. 각각 `timeout 180`을 붙인다.

일반 백필은 기존 scheduled main workflow를 유지한다. UTC15:30 일일 실행, 10월에만 UTC7:30/23:30 추가이며 지연될 수 있다. 수동 재개가 필요한 경우에만 Actions의 실행/queued/waiting 및 이전 환경의 collector 상태를 확인하고 같은 기존 lock으로 최신 main에서 실행한다:

```bash
timeout 30 gh run list --repo Horororong/quant-marcap-runner --limit 30
timeout 30 gh workflow run backfill-super-value-fast.yml --repo Horororong/quant-marcap-runner --ref main
```

위 명령은 **재개 절차**이며 이번에 dispatch한 명령이 아니다. 현재 연결에 dispatch 도구가 없고 로컬 API key도 없다. 기존 자동 백필은 실제 체크포인트에서 진행해 성공했다. 별도 collector/lock은 만들지 않는다. 기존 legacy는 3 workers, batch 2,000, request attempts 2,500, submission 3,300초, 0.5초 간격, checkpoint 25, socket 90초×최대 4tries, persistent ERROR 3회 quarantine, step 75분/job 100분의 유한 상한을 사용한다. 날짜·품질 gate를 우회하지 않는다.

## 다음에 수행할 한 가지 작업

今回保存した primary cellsを使って、**readable viewer source adapterの当期期間・scope・unit・numeric-column guardを再現する回帰検証**を既存開発手順で追加する。旧観測を保持し、parser/source version更新と対象 receipt限定再検証・必須CI・必要ならkit再生成を経る。legacy全件の最初からの再収集や新戦略選択は行わない。
