# 사용자 지정 기간 공식 보고 · CURRENT v2-18

## 단계 1 — 표준 계산과 화면 구현 (2026-10-03 UTC)

시작 시 원격 main `12aaa86dbef54aa846f7afa6b2145094c407a09b`를 확인했다.
최근 fast backfill/최근 재무 갱신 Actions는 success다. Legacy는 7,401건 처리,
107,619건 대기, 품질은 `INDEPENDENT_SOURCE_AUDIT_REQUIRED`다. 수집기·예약·자료를
이 보고 작업에서 변경하지 않는다. 기존 PR #27의 취소된 merge도 재시도하지 않는다.

CURRENT `calculate_metrics(requested_period=True)`가 사용자 기간의 공식 지표를
계산한다. PROJECT v2-16 / execution v2-16-exec-3와 전략 fingerprint는 유지한다.
성과 계약 v2-18, machine contract 23, run contract 2, 요청 보고 계약 1이다.
기존 4기간/9차트 payload와 기존 지표 정의는 유지하고 3차트 HTML 화면을 추가한다.
새 화면은 같은 CURRENT payload의 표·종료자산·일별 배수·낙폭만 표시한다.
화면 JavaScript에는 투자 지표 계산이 없다. Plotly를 HTML에 내장해 오프라인으로
hover·범례·구간 선택·확대·축소·반응형을 제공한다.

요청 기간은 `id`, 선택적 `label`, `start`, `end`의 객체 배열이다. 날짜는 정확한
YYYY-MM-DD이며 start의 `longest`, end의 `latest`만 특별값이다. latest는 **검증된
NAV의 마지막 관측일**이며 현재 날짜나 데이터가 없는 끝 날짜로 바꾸지 않는다.
최대 32기간, 중복 ID·알 수 없는 필드·잘못된 날짜는 실패한다.

일별 캘린더는 정확히 일치해야 한다. 기간 시작 직전 관측 NAV를 1로 재기준화하고
그 기준일을 차트에 $10,000으로 넣어 첫 선택일 수익을 보존한다. 최초 관측에서
시작하는 기간은 원본 NAV=1의 초기자산 행이 있어야 한다. 임의 상수배 정규화나
결측 제거·시작일 이동·보간으로 통과시키지 않는다. NAV를 여러 기간으로 잘라
보고하며 각 기간마다 포지션을 초기화해서 전략을 다시 실행하는 계약은 아니다.

요청 보고의 CAGR는 실제 기준일~종료일/365.2425로 계산하며 365일 미만은 표시하지
않는다. 변동성/Sharpe는 완결된 거래소 월 수익률 2개 이상에서만 계산한다.
부분 시작·종료월은 통계에서 제외하지만 누적수익·종료자산·일별 위험에서는 유지한다.
MDD/회복기간은 전체 일별 NAV (2관측 이상), 회복기간은 달력일이며 미회복도 포함한다.
짧은 표본은 탐색/실행 검증으로 표시하며 장기 투자 검증으로 소개하지 않는다.
월 rf=(1+연 rf)^(1/12)-1, 표본 ddof=1, 연환산 sqrt(12), 기본 연 rf=0이다.

표·3차트는 같은 종료 거래일을 쓴다. 기준자산 $10,000은 NAV 표준화 비교값이며
한국 주식의 실제 환율을 반영하지 않는다. 추가 납입 없음. 가격지수 벤치마크는
배당 미반영. 비용·세금은 DSL 시나리오 가정이며 실제 모든 과거 세율 인증은 아니다.
로그 차트는 실제 logarithmic 축과 2의 거듭제곱 눈금을 쓴다. 0.5/0.25배도 지원하고
hover는 배수·달러 비교값을 보인다. 낙폭 축약은 표시 전용이며 MDD는 축약 전 계산한다.

로컬 검증: 기존 canonical 지표 독립 공식·v2-15 기준 회귀·4기간 CLI/9차트 검사 통과.
새 합성 NAV 검사 4개는 표본·독립 기간별 공식·첫 거래일·로그 눈금·표/차트 종료값·
결측/날짜/범위·오프라인 HTML을 확인한다. 합성 자료는 소프트웨어 테스트일 뿐이다.
다음 단계: checked lifecycle/kit CLI 연결, 실제 자료 실행·기존 NAV 회귀·브라우저 검증,
전체 원격 CI, 새 clean-source kit 생성·bootstrap/verify·공개 전체/분할 다운로드.

## 단계 2 — checked 실행 연결과 실제 NAV 검증

단계 1 원격 commit `8b8aa51e7fb2f5dd0a524c5710294ef685e7d76c`, 로컬 `ac08b1d`.
`strategy_dsl_runner.py`와 `sandbox_runtime.py run`의 새 `--report-periods` 옵션은
입력 기간을 snapshot하고, 실행 전 CURRENT 날짜 준비도를 점검한 뒤 기존 shared
preflight/기업행동/held-return guards로 NAV를 만든다. 기존 execution-only와 동시에
요청하면 실패한다. 기존 기본 정식 4기간 readiness는 변경하지 않는다.

요청 기간의 최소 하나가 준비되면 나머지 gap을 그대로 등록한 부분 보고를 만든다.
`report_ready=true`는 준비된 기간만 공식 계산·검증한 보고라는 뜻이다.
`report_complete=false`와 `period_readiness`로 전체 요청 완료 여부를 구분한다.
모든 요청 기간이 gap이면 실행 전에 `data_gap`이며 보고 수치를 만들지 않는다.
실패·gap에는 `diagnostic_CURRENT.html`을 남기고 지표를 추가하지 않는다.
보고 staging은 기간/캘린더/벤치마크/전체 NAV/metrics/HTML의 embedded payload를
CURRENT 결과와 대조한 후에만 publish한다. Postprocess subprocess는 300초 제한이다.

실제 로컬 KRX 대형주 10분위 checked 실행 성공: 2020-04-01~2020-05-08.
Fingerprint `fc1db45bda8afee95fb05681c4500176ebcb4fc699094de182e89da6b17873c8`,
전체 daily NAV SHA256 `fcba76a621a97095396fefad9695f19d363b79eb791fc9a3d6c0bfead20d4c32`.
기존 ee212da3e4a7 묶음의 검증 ledger와 byte-identical이다. Cost/selection/execution
수식을 바꾸지 않았으며 performance/machine version metadata만 달라진다.
2020년 5월의 정확한 하위기간은 직전 NAV 기준으로 보고한다. 2000/2010/2021 기간은
gap으로 남고 CAGR/Sharpe 등 표본 부족은 null/계산 불가 표시다. 이는 실행 및
보고 검증이며 장기 투자 가설의 검증은 아니다.

기존 checked lifecycle 회귀와 kit 실패 경계, 새 합성 검사 5개를 수행한다.
로컬 Chromium은 sandbox의 setsockopt 차단으로 시작하지 못했다. 이를 브라우저
검증 통과로 주장하지 않는다. CI에는 pinned Playwright 1.57.0을 사용한 실제 HTML
기간/표/3차트·종료값·로그축/hover 값·비용/벤치마크·공통 zoom·범례·모바일 너비
검사를 추가하고 실제 report HTML/PNG/검증 ledger를 artifact로 보존한다.
두 ABI의 offline kit E2E에도 새로운 기간 보고/원래 NAV 일치/결과 export 검사를
추가했다. 다음: 최종 원격 CI와 실제 브라우저 결과 확인, 새 묶음/공개 전달.
