# Stage 8 — 2019~2020 연구 재개 가능성

**분류: RESEARCH_ONLY / 투자 사용 불가 / 공식 PIT 인증 아님.** 기준 원격 commit `cbecba3a5e252f57620da6fdb806e791795f5075`와 내용이 같은 로컬 `bd1da86a3ff5f2120ff728cfbdc3846a920c0a6c`에서 조사했다. 기존 엔진·운영 게이트·시세·기업행위·DART 원문과 감사 결과는 수정하지 않았다. 2007년 KRX 접근을 반복하지 않았다.

## 실제 판단

**제한적인 가격·시가총액 연구는 기존 엔진으로 재개 가능하다. 2019~2020 시가총액 10분위 연구 전체는 현재 자료 상태에서 차단된다. DART 재무 팩터 연구의 사용 승인은 이번 단계에서 부여하지 않는다.**

| 독립 실행 | 원래 저장소 예제 | 실제 결과 | 의미 |
|---|---|---|---|
| 시총 10조 이상·시총 낮은 순 10분위·4월 말 신호 | `config/strategies/kr_equity_size_deciles_research.json`의 기간만 2019~2020으로 확대 | exit 4 / failed / execution / nav_ready=false / report_ready=false | D01 보유종목 091990의 2019-12-27 수익률 불일치로 정상 차단. 승인된 10분위 NAV·성과는 없음 |
| 시총 10조 이상·시총 상위 1종목·1/4/7/10월 말 신호 | 기존 별도 `config/strategies/kr_equity_report_validation_2019_2020.json` | exit 0 / ok / complete / nav_ready=true / report_ready=true | 494일 NAV와 CURRENT 사용자 지정 기간 보고 완료. 연구 실행 경로의 사용 가능성만 확인 |

두 경로를 실행 전에 각각 선정했다. 실패한 10분위에서 종목을 제거하거나 기간을 줄여 상위 1종목 결과로 바꾼 것이 아니다. 두 실행의 기간은 모두 **2019-01-01~2020-12-31**다. 실제 관측일 **2019-01-02~2020-12-30**, 494세션은 기존 XKRX 패키지 달력에서 해당 2개 연도의 전 세션과 일치하며, 요청 기간을 성공시키기 위해 축소한 것이 아니다.

RESEARCH_ONLY는 별도 입력 metadata·제목·기간 라벨·산출물의 용도 표시다. 새 운영 게이트 모드나 기존 게이트 예외를 만든 것이 아니다. `nav_ready`와 `report_ready`는 소프트웨어 산출물 검사를 의미하며, 공식 종목 원장·공개시점·PIT·투자 적합성 인증을 뜻하지 않는다.

## 읽기 전용으로 확인한 기존 기능

- `config/strategy_dsl_capabilities_v1.json`: machine contract 23. KRX 필드, 기술적 지표, DART 공급자를 구분한다. 시가총액 10분위·동일가중·최소 10종목·명시적 비용·다음 세션 체결을 기존 DSL로 표현한다.
- `scripts/strategy_dsl_runner.py` → `scripts/strategy_dsl_run.py`: 입력 snapshot, 기존 shared preflight, 보고 준비도, 실행/보유수익률 검사, 결과 검증을 통과한 산출물만 공개한다. 두 실행은 모두 이 public checked CLI를 사용했다.
- `scripts/strategy_dsl_deciles.py`: 10개 독립 장기보유 포트폴리오를 공통 PROJECT 실행기에 전달한다. 각 분위의 초기자본은 각각 1,000만원이다. 10개를 하나의 1,000만원 계좌처럼 합치지 않는다.
- 실행 엔진 `v2-16-exec-3`, PROJECT `v2-16`, 성과 계산 CURRENT `v2-18`, 기업행위 registry 5. 성과 공식을 새로 작성하지 않았다.
- 기존 `--report-periods` 사용자 지정 기간 보고를 사용했다. 2001년 이후·2021년 이후 등 기본 4기간 보고가 완성됐다고 주장하지 않는다. 실패 진단 HTML과 성공한 오프라인 3차트 HTML은 기존 기능이다.

## 데이터 사용 가능성과 인증 공백

| 자료 | 실제 보존·확인 범위 | 인증되지 않은 부분 |
|---|---|---|
| `data/krx_equities/yearly/marcap-2019.parquet` | 555,287행, 2,341코드, 시장별 246세션. Date+Code 중복 0; Close/Volume/Marcap/ChangesRatio 공란 0 | FinanceData/marcap를 거친 보존 자료. 공식 원응답과 전 종목 대조·법적 상태·기업행위 완전성 미인증 |
| `data/krx_equities/yearly/marcap-2020.parquet` | 580,252행, 2,426코드, 시장별 248세션. 동일 필드 공란·키 중복 0 | 위와 같음. 값이 있다는 사실은 수정주가·정지·상폐·권리락 처리 인증이 아님 |
| 실제 실행 패널 | 두 시장 합계 1,135,539행, 전체 구간 2,443개 고유코드, 시장별 494세션 | 현재 상장종목으로 거르는 생존 필터는 사용하지 않았다. 하지만 과거 원천에서 이미 누락된 상폐·소멸 종목까지 완전하다는 증거는 없음 |
| `data/indices/KOSPI.csv` | 494개 실행일과 정확하게 정렬되는 KOSPI 종가 가격지수 | 배당 포함 총수익지수 아님. 이번에 KRX 원응답을 새로 받아 대조하지 않음 |
| `config/kr_corporate_actions.csv` | 2019년 등록 0건, 2020년 한국제지→해성산업 합병 1건. 2024년 등록들은 해당 기간 밖 | 등록이 적거나 조회 구간의 known-gap 목록이 비었다고 실제 기업행위가 없었다고 판단하지 않음 |
| `data/financials/full_history/`의 2019·2020 자료 | 파일 존재와 기존 DART provider/PIT completeness 경로가 있음을 확인 | 이번 단계에서 공시 원문 숫자·정정·실제 공개시점·역사적 종목 연결을 인증하지 않았고 실행에 사용하지 않음 |

기존 [KRX Open API 공식 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)의 2010-01-04 이후 제공기간에는 2019~2020이 포함된다. **제공기간은 다운로드 성공·현재 권한·역사적 PIT 인증이 아니다.** 현재 환경에는 KRX 인증 binding이 없고 KRX 호스트는 터미널 허용 목록에 없다. 이번에는 API 호출·새 수집·2007 접근 재시도 없이 보존 자료만 사용했다. 실제 API 이용승인과 시점별 원응답 대조는 별도 필요하다. 데이터 재배포/상업적 사용권 역시 공개 저장소라는 이유만으로 인증하지 않는다.

Source SHA256, 크기·필드·날짜·공란 수는 `evidence/input_inventory.json`에 있다. 날짜 일치 검사는 exchange_calendars **4.13.2**와의 정합성 검사이며, 새로 확보한 KRX 공식 거래일 원본 인증이 아니다.

## 실행 전에 확정한 연구 기준

1. **유니버스/생존편향:** 과거 각 신호일의 KOSPI·KOSDAQ 관측값으로 선택한다. 현재 회사명·현재 상장목록·기간 말 생존 여부로 과거 종목을 거르지 않는다. 공통 기준은 신호일 시총 ≥10조원과 양의 가격·거래량이다. 전체 소형주 효과 연구가 아니며 우선주를 제거하는 추가 규칙도 없다.
2. **가격·기업행위:** 저장된 Close를 사용한다. 포괄적 수정주가·배당 재투자·권리락·상폐 회수액을 임의 복원하지 않는다. 기존 검증 registry만 적용하며 보유수익률을 원자료 ChangesRatio와 1bp 한도로 대조한다. 미등록 행사/불일치/보유 중 결측은 중단한다.
3. **신호/체결:** 신호일 종가 정보 → 최소 다음 거래 세션의 종가 체결이다. 체결일까지의 수익은 기존 보유분에 귀속하고 새 비중으로 소급하지 않는다. Top1 최초 신호 2019-01-31 → 체결 2019-02-01, 2020-04-29 → 2020-05-04. 나머지는 `evidence/top1-schedule.csv`에 있다. 첫 매수 전에는 현금이며 이 기간도 2년 보고에 포함한다.
4. **비용:** 원래 예제의 무비용 기준과 고정비용 시나리오를 유지했다. 매수·매도 양쪽에 commission 1.5bp + effective spread 3bp + slippage 5bp, 매도에 추가 sell tax 15bp다. 시장충격 비용은 0, 대규모 거래 체결 가능성·실제 역사적 세율을 검증한 가정이 아니다. 따라서 실제 투자 순수익/총수익으로 해석하지 않는다.
5. **결측:** 시장 날짜/벤치마크 누락은 preflight에서 차단한다. 유한한 팩터 교집합을 사용하고 임의 forward-fill·0 수익률 대체·다른 종목 proxy를 사용하지 않는다. 거래정지 여부를 결측만으로 추정하지 않는다. 검증된 등록 행사 이외의 보유 공백은 엔진이 차단한다.
6. **DART 분리:** 두 입력의 factor_sources는 오직 `krx`, 외부 provider coverage는 비어 있다. 미인증 DART 재무값을 투입하지 않았으며 `dart_value_factor_adapter.py`의 역사적 코드 연결·수집 완료/PIT 경로와 운영 source gate를 우회하거나 수정하지 않았다.

## 차단된 10분위의 정확한 장애

run_id `20261015T123642486413Z-7b0ecac6`. 입력 검증·preflight·보고 준비도는 통과했으나 실행에서 다음 원문 오류로 exit 4가 발생했다.

```text
D01: decile execution failed; no price gaps are filled: held-return reference check failed: date=2019-12-27, assets=['091990'], tolerance_bps=1.0. Missing/non-finite or inconsistent returns require verified source/event data; no automatic corrections.
```

보존 원자료에서 091990 셀트리온헬스케어의 Close는 2019-12-26 **57,300**, 12-27 **54,100**, 12-27 ChangesRatio는 **-0.92%**다. 단순 가격수익률은 약 **-5.584642%**, 차이는 **466.464223bp**로 1bp 한도를 초과한다. 가격 또는 기준수익률 오류인지, 주식배당/권리락 등 사건인지 이번 자료만으로 확정하지 않았다. 행사 비율을 역산해 생성하거나 주식분할로 임시 등록하지 않았다.

실패 신호의 후보 모집단은 2019-04-30 33종목, 2020-04-29 26종목이었다. 최소 모집단 부족이 원인이 아니다. 두 신호의 계획 체결은 2019-05-02, 2020-05-04지만 **완료된 10분위 체결/성과 인증은 아니다.** 실패한 사적 staging이 존재할 수 있으나 승인된 `artifacts/daily_nav.csv`는 없다. `evidence/deciles-run_status.json`, `deciles-execution.log`, `deciles-blocking-source-rows.csv`를 근거로 남긴다.

## 성공한 별도 Top1 연구의 범위

run_id `20261015T123651947431Z-34058acb`, fingerprint `6a600e61130b3c6cb53e26ce86fb88ec993214041946880dc86719c757307955`. 사전 선택한 기존 Top1 규칙의 실제 선택은 8개 신호 모두 **005930 삼성전자**였다. 특정 종목을 하드코딩한 입력이 아니다. 보유수익률 검사는 비용 시나리오별 471관측에서 활성화됐고 verified override는 0이다. 494일 NAV·기준지수·CURRENT 보고가 함께 검증됐다.

이 성공은 이 규칙·구간에서 기존 기능을 사용할 수 있다는 증거다. 10분위 전체, 다른 종목, 모멘텀/변동성, 다른 기간, 미래 수익, 초과수익 가설의 검증으로 확대하지 않는다. CURRENT의 요청기간 보고를 생성했지만 알파·OOS·전략 선정 검증은 하지 않았다.

주요 검토 산출물:

- `evidence/top1-daily_nav.csv`: 실제 494행 연구 NAV
- `evidence/top1-metrics_CURRENT.csv`: 기존 CURRENT가 계산한 연구 지표. 배당 미반영·가상 고정 비용 기준이며 투자 성과 인증이 아님
- `evidence/top1-selections.csv`, `top1-schedule.csv`: 선택과 공통 실행기의 일정 근거
- `evidence/top1-run_status.json`, `top1-preflight.json`, `top1-return_reference_audit.json`: 실행/보고/날짜/보유수익률 검사 범위
- 전체 로컬 실행과 오프라인 HTML: `/workspace/research-stage8-20261015/top1-run/report/report_CURRENT.html`

HTML 제목과 보고 기간 라벨은 RESEARCH_ONLY·투자 사용 불가로 표시했다. 이 설명 문서가 출처·검증 범위·미해결 위험을 포함하는 연구 보고서다. HTML의 표준화 $10,000은 비교 표시이며 환율 변환이나 추가 납입이 아니다. 큰 내장 Plotly HTML과 전체 임시 실행 디렉터리는 Git에 복제하지 않고 해시/경로를 매니페스트에 남긴다.

## 필요한 최소 작업과 가능한 전략 범위

- **즉시 재개 가능:** 검증한 2019~2020 기존 대형주 Top1 가격·시총 연구. 새 엔진/파서/운영 게이트 수정 없이 별도 DSL·요청기간 설정과 연구 용도 표시만 필요했다. 다른 가격 기반 전략은 개별 preflight와 실행 guard를 통과해야 하며 이번 성공을 자동 적용하지 않는다.
- **10분위의 첫 최소 작업:** 091990의 2019-12-27 공식 시세·기준가/권리락·주식배당/상장주식수 변동 증거를 확보해 불일치 원인을 확인한다. 원천 오류라면 출처를 보존한 교정 검토, 기업행위라면 기존 registry/지원 event contract에 의미상 맞게 표현 가능한지 검토한다. 새 엔진부터 만들지 않는다. 이 한 건 해결이 전체 10분위 성공을 보장하지 않으며 다음 보유 구간의 guard도 계속 적용한다.
- **기술적 팩터:** DSL 등록은 확인했지만 이번 실행 범위 밖이다. 필요한 과거 lookback·기준수익률·기업행위 정합성부터 확인해야 한다.
- **DART 재무 팩터:** 자료 파일 존재/수집 완료/숫자 보호값 통과와 공개시점·버전·역사 매핑 인증은 구분한다. 이번에는 사용하지 않았고 기존 gate를 계속 유지한다. 별도 금융 원문/PIT 검증 전 투자 연구 입력으로 승인하지 않는다.
- **실제 투자 또는 공식 인증:** 가격 원응답 대조, 당시 종목 원장/거래상태, 생존편향·기업행위·배당/상폐 처리 완전성, 역사적 비용/시장충격, OOS 등 별도 과제가 남는다. API 제공기간이나 연구 소프트웨어 성공으로 대체할 수 없다.

## 재현과 보존

새 입력은 이 디렉터리의 `deciles_research_only.json`, `top1_research_only.json`, `report_periods.json`이다. 원래 두 예제는 변경하지 않았다. 실제 명령, exit, run_id, fingerprint, 사용 계약 버전은 `research_status.json`에 있다. 저장소 전용 Python `/workspace/financial-repair/runtime/.venv/bin/python`, 원래 kit `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`의 verify를 통과한 환경에서 실행했다. 새 테스트나 인터넷 pip 설치는 없다.

public CLI를 새 결과 디렉터리에서 그대로 사용한다. 이 환경의 isolated Python에서는 sibling import를 위해 아래처럼 기존 scripts 경로만 추가했다. 사용자 정의 실행/성과 계산을 끼워 넣지 않았다.

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I -c 'import runpy,sys; sys.path.insert(0,"scripts"); sys.argv=["scripts/strategy_dsl_runner.py","docs/research/stage8-2019-2020-20261015/top1_research_only.json","--repo-root","/workspace/quant-marcap-runner","--output-dir","/tmp/stage8-top1-reproduction","--report-periods","docs/research/stage8-2019-2020-20261015/report_periods.json"]; runpy.run_path(sys.argv[0],run_name="__main__")'
```

10분위는 입력을 `deciles_research_only.json`으로, 출력을 별도 새 디렉터리로 바꾸면 같은 오류를 재현한다. 기존 실패 디렉터리에 덮어쓰거나 실패를 성공으로 바꾸지 않는다. 단순 경로 조사 중 존재하지 않는 `data/krx_equities/status.json`을 읽어 exit 1이 있었고, 코드에 정의된 실제 상태 경로 `data/status/krx_equities_status.csv`를 확인했다. 이는 실행 데이터 누락이나 preflight 실패가 아니다.

입력 시세·지수·원래 전략·행사 registry SHA는 실행 후에도 동일했다. 기존 tracked 파일의 diff는 없고 새 연구 산출물만 추가했다. 기존 2007 감사, 금융 보호 518/518·핵심 64/64, 원문 60건, Stage6/7 결과와 운영 PIT gate는 보존했다. 과거 인증 수치를 재실행하거나 승격하지 않았으며 투자 PIT 승인 0/6은 그대로다. main 병합·대량 백필·새 자료 수집은 하지 않았다.
