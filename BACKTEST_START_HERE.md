# BACKTEST START HERE

이 파일은 ChatGPT/코딩 에이전트가 백테스트 요청을 받을 때의 진입점이다.

## 사용자에게 요구할 단계 없음

사용자가 전략과 조건을 주고 "백테스트해줘"라고 하면 아래 절차를 에이전트가 수행한다. 사용자가 데이터 확인, 지표 계산, 그래프 생성 단계를 따로 지시할 필요가 없다.

## Strategy DSL 우선 경로 (v1)

전략이 `scripts/strategy_dsl.py`의 지원 범위로 표현 가능하면 새 전략별 Python 스크립트를 만들지 않는다.

1. 먼저 `config/strategy_dsl_capabilities_v1.json`에서 요청한 팩터·시장·리밸런싱·체결 규칙이 지원되는지 확인한다. 자연어 팩터명은 `natural_language_factor_aliases`와 `natural_language_direction_aliases`만 사용해 canonical factor/direction으로 변환한다. 등록되지 않은 표현이나 회계기간 정의가 다른 PER/PCR/PSR 등은 임의 근사하지 않고 capability gap으로 중단한다.
2. `config/strategy_dsl_schema_v1.json` 계약에 맞춰 자연어 조건을 `config/strategies/*.json` Strategy DSL로 변환한다.
3. `python scripts/strategy_dsl_runner.py <strategy.json> --validate-only`로 스키마/실행계획을 다시 검증한다.
4. `python scripts/strategy_dsl_runner.py <strategy.json>`를 실행한다. 공통 경로가 입력 snapshot, shared preflight, 표준 보고 기간 준비도, NAV 실행, CURRENT 후처리를 자동 수행한다. 원자료 준비도만 별도 조회하려면 `strategy_dsl_preflight.py`를 사용할 수 있다.
5. `run_status.json`의 `status`, `phase`, `nav_ready`, `report_ready`를 확인한다. `capability_gap`이면 전략 표현력 문제, `data_gap`이면 PIT 자료/표준 기간 문제다. `failed`이면 실패 단계와 오류를 확인한다. 표준 보고 성공은 두 readiness 플래그가 모두 true여야 한다.
6. 기본 결과는 `results/dsl/runs/<run_id>/artifacts/`의 NAV·감사 자료와 `report/`의 CURRENT 성과표·차트다. 명시한 `--output-dir`은 새 실행 디렉터리여야 하며 기존 결과를 덮어쓰지 않는다. 짧은 연구 NAV만 요청하면 `--execution-only`를 명시하고 표준 성과 보고로 소개하지 않는다. 상세 계약은 `docs/STRATEGY_DSL_RUN.md`를 따른다.
7. DSL이 지원하지 않는 팩터/자산/체결 규칙이면 임의 근사하지 않는다. 반복 사용 가능한 기능은 DSL/어댑터를 확장하고, 특수 체결이 필요한 경우에만 별도 엔진을 둔다.
8. 같은 Strategy DSL JSON + 같은 데이터 + 같은 엔진/registry 버전은 항상 같은 결과를 내야 하며, `strategy_fingerprint`와 execution plan의 버전 필드를 재현성 키로 사용한다.

preflight와 범용 실행은 요청기간의 XKRX 거래일을 각 요청시장과 정확히 대조한다.
시장 전체 날짜 누락은 중단한다. 이는 종목별 기업행동 이력의 완전성 인증이 아니다.
preflight 계약 3은 관련된 미확인 기업행위가 있으면 실행과 같은 PIT 팩터·선정
함수를 사용하고 실제 체결 지연에 맞춰 양의 목표비중 보유 계획을 추적한다.
행사일 종가 매도로 그 이전 보유를 소급 제거하지 않는다. 해당 노출은
`data_gap`, `phase="corporate_actions"`, `ready_for_execution=false`로 중단하며
종목·분위·선정일을 `corporate_action_audit`에 기록한다. 관련 알려진 공백이
없으면 원자료 검사만 수행한다. NAV·비중 드리프트·비용·성과는 계산하지 않으며,
`ok`도 미등록 행사나 실제 가격 경로의 완전성 인증은 아니다.
상세 범위는 `docs/CORPORATE_ACTION_PREFLIGHT.md`를 따른다.
장기 실행의 원자료 검토에는 `docs/KRX_HISTORY_AUDIT.md`의 감사 절차를 사용하고,
확인 후보를 전략 필터나 기업행동으로 자동 적용하지 않는다.
시장 정규화와 검증된 과거 관측값 복원은 `docs/KRX_MARKET_NORMALIZATION.md`를
따른다. `KOSDAQ GLOBAL`은 코스닥에 포함하며 당시 원본 구분은 `SourceMarket`에
보존한다. 현재 구성종목으로 과거 유니버스를 재구성하지 않는다. 실행계획의
`krx_market_normalization_version`도 재현성 키에 포함한다.
등록 분할과 원자료 대조에는 `docs/CORPORATE_ACTION_RECONCILIATION.md`의 명령을
사용한다. 종목코드·일자가 같은 행사도 자료와 일치해야 하며, 모든 후보를 보존한다.

범용 실행은 보유종목의 유효수익률을 `ChangesRatio/100`과 1bp 허용범위에서
NAV 반영 전에 검증한다. 미확인 불일치·보유 참고수익률 누락은 중단한다.
등록된 분할은 주식 수 비율로 보정하되 보정값도 검증한다. 합병 처분가치의
명시적 예외는 감사에 기록한다. `return_reference_audit.json`에서 검증 활성화와
예외를 확인한다. 상세 정의는 `docs/HELD_RETURN_VALIDATION.md`를 따른다.

팩터 10분위 연구를 요청하면 같은 JSON에서 `portfolio.selection="deciles"`,
`portfolio.weighting="equal"`로 지정하고 `number_of_positions`는 생략/null로 둔다.
일반 상위 N종목 전략의 기본값은 `selection="top_n"`이다. 10분위는 필터와
팩터 결측 교집합 적용 후 전체 유효 종목을 D01(우수)~D10(하위)으로 나눈다.
각 분위는 독립된 자본으로 동일 체결·비용 규칙을 적용한다. 10종목 미만이면
중단하며, 실제 성과지표는 공통 일별 NAV를 CURRENT 후처리에 전달한다.
짧은 실행 경로 검증은 `--execution-only`로 명시하고 장기 성과로 보고하지 않는다.

## 강제 실행 순서

1. `scripts/quant_backtest_template_CURRENT.py`를 읽고 CURRENT 버전을 확인한다.
2. 프로젝트 저장 데이터와 전략 조건으로 **일별 NAV**를 계산한다.
3. 전략별 코드에서는 CAGR, MDD, Sharpe, 회복기간, 채팅 차트를 다시 계산하지 않는다.
4. 일별 NAV를 `results/<strategy>/daily_nav.csv`로 저장한다.
5. 반드시 `scripts/quant_backtest_postprocess.py`를 사용해 표준 성과표와 채팅 payload를 생성한다.
6. `metrics_CURRENT.csv`의 4개 기간 결과를 보고한다.
7. `chat_manifest_CURRENT.json`의 render_order를 따라 **2001 3개 → 2021 3개 → 최장 3개, 총 9개 차트**를 표시한다.
8. 차트 표시용 Drawdown만 축약하며, MDD/회복기간 계산은 전체 일별 NAV를 사용한다.
9. 필요한 원자료가 없으면 수치를 임의 생성하지 말고 누락 데이터와 막힌 지점을 명시한다.

## 표준 명령

```bash
python scripts/quant_backtest_postprocess.py \
  --daily-csv results/<strategy>/daily_nav.csv \
  --series NAV_Gross,NAV_Net,NAV_Benchmark \
  --market-calendar XKRX \
  --benchmark-series NAV_Benchmark \
  --title "<strategy title>" \
  --book-start YYYY-MM-DD \
  --book-end YYYY-MM-DD \
  --output-dir results/<strategy>
```

성과분석 CURRENT는 v2-17이다. 한국주식 DSL은 `--market-calendar XKRX`를
자동 전달하며 일별 NAV 거래일 누락/추가 시 정식 보고서 생성을 중단한다.
다른 자산은 실제 NAV 생성 캘린더를 지정한다. 캘린더 생략 경로는 기존 휴리스틱과
명시적 월별 fallback을 유지한다. `--benchmark-series`는 실제 벤치마크 열이 있을
때만 지정하고, 없으면 위 예시에서 제거한다. 배당을 포함하지 않은 지수 NAV를
총수익 지수로 해석하지 않는다. 지표 정의와 호환성은 `docs/CANONICAL_PERFORMANCE.md`를 따른다.

`--series`는 실제 NAV 열 이름에 맞춰 조정한다. CSV에 `NAV` 또는 `NAV_*` 열만 있다면 생략 가능하다.

## 단일 계산원

- 전략 로직: 전략별 스크립트
- 성과/위험 계산: `quant_backtest_template_CURRENT.py`
- 표준 산출물: `quant_backtest_postprocess.py`
- 채팅 표시: `chat_manifest_CURRENT.json`

같은 데이터와 같은 전략이면 모델의 사고 수준과 무관하게 같은 성과 수치가 나와야 한다.

## Cash exchange evidence boundary

Read `docs/CASH_SHARE_EXCHANGE.md` for cash-only exchanges. A planned payment or
delisting date is never actual receipt. The generic contract keeps unpaid claims
in NAV but outside settled Cash; insufficient settled cash rejects execution.
Known unresolved events in `config/kr_corporate_action_gaps.json` stop affected
holdings without historical-universe exclusion. Jeisys actual payment remains
unverified, as do applicable net proceeds, and has no executable registry entry.

## GPT Python sandbox distribution

For offline GPT use, read [SANDBOX_START_HERE.md](SANDBOX_START_HERE.md). The kit
pins a clean code commit, original source hashes and Python 3.11/3.12 Linux
wheel locks. Use its isolated Python and `scripts/sandbox_runtime.py`, which
wraps the same checked DSL runner; it does not compute separate performance.
Starter coverage is explicitly limited and every new DSL still needs preflight.
