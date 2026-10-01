# BACKTEST START HERE

이 파일은 ChatGPT/코딩 에이전트가 백테스트 요청을 받을 때의 진입점이다.

## 사용자에게 요구할 단계 없음

사용자가 전략과 조건을 주고 "백테스트해줘"라고 하면 아래 절차를 에이전트가 수행한다. 사용자가 데이터 확인, 지표 계산, 그래프 생성 단계를 따로 지시할 필요가 없다.

## Strategy DSL 우선 경로 (v1)

전략이 `scripts/strategy_dsl.py`의 지원 범위로 표현 가능하면 새 전략별 Python 스크립트를 만들지 않는다.

1. 먼저 `config/strategy_dsl_capabilities_v1.json`에서 요청한 팩터·시장·리밸런싱·체결 규칙이 지원되는지 확인한다. 자연어 팩터명은 `natural_language_factor_aliases`와 `natural_language_direction_aliases`만 사용해 canonical factor/direction으로 변환한다. 등록되지 않은 표현이나 회계기간 정의가 다른 PER/PCR/PSR 등은 임의 근사하지 않고 capability gap으로 중단한다.
2. `config/strategy_dsl_schema_v1.json` 계약에 맞춰 자연어 조건을 `config/strategies/*.json` Strategy DSL로 변환한다.
3. `python scripts/strategy_dsl_runner.py <strategy.json> --validate-only`로 스키마/실행계획을 다시 검증한다.
4. `python scripts/strategy_dsl_preflight.py <strategy.json>`를 실행한다. `capability_gap`이면 전략 표현력 문제, `data_gap`이면 PIT 원자료/완결성 문제로 구분하고 실행하지 않는다.
5. preflight가 `ok`일 때만 같은 JSON을 범용 러너로 실행해 목표비중과 일별 NAV를 만든다.
6. 성과/위험지표와 채팅 차트는 기존과 동일하게 `quant_backtest_postprocess.py`만 사용한다.
7. DSL이 지원하지 않는 팩터/자산/체결 규칙이면 임의 근사하지 않는다. 반복 사용 가능한 기능은 DSL/어댑터를 확장하고, 특수 체결이 필요한 경우에만 별도 엔진을 둔다.
8. 같은 Strategy DSL JSON + 같은 데이터 + 같은 엔진/registry 버전은 항상 같은 결과를 내야 하며, `strategy_fingerprint`와 execution plan의 버전 필드를 재현성 키로 사용한다.

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
  --title "<strategy title>" \
  --book-start YYYY-MM-DD \
  --book-end YYYY-MM-DD \
  --output-dir results/<strategy>
```

`--series`는 실제 NAV 열 이름에 맞춰 조정한다. CSV에 `NAV` 또는 `NAV_*` 열만 있다면 생략 가능하다.

## 단일 계산원

- 전략 로직: 전략별 스크립트
- 성과/위험 계산: `quant_backtest_template_CURRENT.py`
- 표준 산출물: `quant_backtest_postprocess.py`
- 채팅 표시: `chat_manifest_CURRENT.json`

같은 데이터와 같은 전략이면 모델의 사고 수준과 무관하게 같은 성과 수치가 나와야 한다.
