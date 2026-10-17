# 한국 주식 연구 실행

이 경로는 **RESEARCH_ONLY**다. 보존 시세·시총·기술 지표를 사용하며 투자 PIT
승인, 실제 증권계좌 재현, 배당을 모두 복원한 총수익률을 의미하지 않는다.
`Net`은 설정한 거래비용 차감 후이며 배당 관련 세후 성과가 아니다.

## 전용 Python과 단일 실행 경로

원래 offline kit을 복원하고 `sandbox_runtime.py verify`를 통과한 Python을
사용한다. 인터넷 설치는 필요하지 않다. 아래 `$PY`는 그 전용 Python이다.

```bash
$PY -I scripts/research_workbench.py capabilities
$PY -I scripts/research_workbench.py inventory
$PY -I scripts/research_workbench.py check --strategy config/strategies/research_size_deciles_2019_2020_v1.json --diagnose-panel
$PY -I scripts/research_workbench.py run --strategy config/strategies/research_size_deciles_2019_2020_v1.json --report-periods config/reports/research_2019_2020.json --output-dir /tmp/new-decile-run
```

출력 디렉터리는 새 경로여야 한다. `check`의 준비 판정은 실행 보증이 아니다.
실제 선정·보유 수익률·유동성·기업행위·비용 검사는 기존 PROJECT가 수행한다.
검증된 일별 NAV만 CURRENT로 넘어가며 지표·차트는 기존 CURRENT가 계산한다.
일반 거래일 1bp 검증, 미등록 기업행위 차단, 금융 DART PIT 게이트는 유지된다.

## 제한된 한국어 문법

완전한 자유문장 해석기로 표시하지 않는다. 다음 명시적 항목 문법과 등록된
팩터 별칭을 지원한다. 미지원·중복·누락 항목은 전체 요청을 거부한다.
`translate`는 DSL만 생성하고, `run`은 같은 DSL 검증·준비도·엔진·보고를 실행한다.

```bash
$PY -I scripts/research_workbench.py run --request '기간:2019-01-01~2020-12-31;시장:코스피·코스닥;필터:시가총액>=10조원;팩터:시가총액 낮은;포트폴리오:10분위;리밸런싱:4월말;체결:1거래일뒤종가;비용:수수료1.5bp,매도세15bp,스프레드3bp,슬리피지5bp;벤치마크:코스피' --research-model-from config/strategies/research_size_deciles_2019_2020_v1.json --report-periods config/reports/research_2019_2020.json --output-dir /tmp/new-korean-run
```

주식배당 연구 계약은 `--research-model-from`으로 명시적으로 선택한다.
정의되지 않은 계약을 자동 선택하거나 기존 금융 게이트를 면제하지 않는다.
JSON DSL의 다중 팩터 기능은 기존 경로로 사용하며, 위 한국어 인터페이스는
현재 단일 등록 팩터, 상위 N개/10분위, 지정 월말, 다음 세션 종가만 해석한다.

## 연구 계약 v1

- 사실: 원공시 배정률·권리 기준일, 공식 배당락 효력일·기준가격,
  확인된 승인 결과와 공식 추가상장일. 사실 파일 SHA256을 DSL에 고정한다.
- 평가 모델: 조건부 권리 수량 × 당일 기초주식 종가 × 명시한 계수.
  기본 계수1.0은 명목 주식등가 장부 관례이며 시장 관측값·승인 확률이 아니다.
  0.9 시나리오를 별도로 실행하며 유리한 성과를 보고 사후 선택하지 않는다.
- 승인 전에는 조건부로 남는다. 공식 공개 날짜만 아는 경우 다음 관측 거래일에
  인식한다. 이후 승인 결과를 과거 확정 사실로 소급하지 않는다.
- 연속수량·비례 배정·배당세 전 가상 계좌다. 개인계좌 단주 매각대금,
  원천징수, 실제 입고일·수량은 복원하지 않는다. 정수 계좌 계약은 그대로다.
- 승인 후 공식 추가상장일 종가에 가상 정산한다. 실제 계좌 입고 사실이라고
  주장하지 않는다. 1세션 지연 시나리오가 별도 계약으로 존재한다.
- 권리는 거래·매수 재원으로 사용할 수 없다. 기존 주식을 매도해도 권리는
  남고 배당락 이후 신규 매수자는 해당 사건 권리를 받지 않는다.
  정산 시 권리→주식 전환만 하며 소득·수수료를 중복 인식하지 않는다.
- 확인되지 않은 2020년 말 사건의 2021년 승인·상장일을 만들지 않는다.
  이 사실 카탈로그의 미완료 생애주기는 2020-12-31까지만 지원하며,
  그 이후까지 해당 권리를 보유하는 실행은 추가 사실이 없으면 차단된다.

직접 공식 기준가격을 확인한 사건은 그 관측 기준가격을 사용한다. 산식으로
새 기준가격을 만들지 않으므로 당시 규정 전문·반올림을 추정할 필요가 없다.
기준가격 대비 `ChangesRatio`와 배당권리 포함 경제적 수익률은 별도 검사다.
실제 계좌 과세·단주·입고 인증에는 추가 증거가 필요하며 연구 모델이 이를
대신 인증하지 않는다.

## 결과와 기간별 준비도

`run_status.json`의 `status/nav_ready/report_ready`를 먼저 확인한다.
`artifacts/`에는 선정·체결·일별 NAV·권리·현금·비용·시장가격 검증이,
`report/`에는 CURRENT 지표 CSV·기준자산10000·벤치마크·자체 포함 HTML이 있다.
HTML은 기간·비용·분위 선택, 누적자산·로그2축·드로우다운을 공유한다.
KOSPI 비교는 배당 미포함 가격지수다. 짧은 기간에 정의되지 않는 지표는
CURRENT 계약대로 비어 있으며 신규 계산기로 채우지 않는다.

기간별 인벤토리는 파일 메타데이터만 증명한다. 법적 상장 상태·완전성·PIT를
인증하지 않는다. `check`는 실제 전략의 거래일·팩터 lookback·벤치마크를
검사하고 `--diagnose-panel`은 전체 패널 후보를 실제 보유 노출과 구분한다.
기간·전략을 바꾸면 다시 이 경로를 거쳐야 한다. Stage15에서 전체 실행한
예시는 2019~2020 시총10분위, 2020년 3-1 모멘텀 상위3, 2024년 시총 상위1이다.
어느 예시의 성공도 모든 종목·기간·DART 재무 전략의 승인이 아니다.
