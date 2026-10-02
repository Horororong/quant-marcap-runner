# 재무 팩터 사용자 지정 리밸런싱

## 단계 1: 상태 확인과 계약 (2026-10-02 UTC)

- 소유자가 ChatGPT 퀀트 프로젝트에서 재무 팩터 리밸런싱 시점을 직접 지정하도록 확장 요청했다. 기존 4·10월 정의를 조용히 바꾸지 않는다.
- 원격 main `5d627feaf8532e33963af047785ca78aeb1ffdc5`, 마지막 code merge `aa6c8722a0842d717468d855606b7ab76208eac4`의 전체 CI `37002403185` success를 직접 확인했다. 최신 legacy durable 1,401 / pending 113,619이며 금융 품질 완료는 False. 완료된 백필·원문 capture는 반복하지 않는다.
- 로컬 HEAD는 clean `e0fc32db5e5bfc9d6e175f1daa4a985f2b82ae8f`다. 최신 main의 gzip은 GitHub connector UTF-8 제한으로 수신할 수 없어 로컬과 원격이 동일하다고 주장하지 않는다. 변경은 원격 main tree를 기반으로 필요한 코드·문서만 반영하고 데이터 변경을 보존한다.
- 현재 범위: `rebalance.months` 1..12 선택 + 월 마지막 거래일, 명시적 `rebalance.dart_period_policy=latest_disclosed_quarter`. 기존 생략/default는 `legacy_april_october`이며 기존 normalized JSON/fingerprint와 Q4/Q2 계산을 유지한다. 매월/분기/반기/연간은 월 목록으로 표현한다. 월 중 특정 날짜·공시 이벤트 일정은 이 단계의 미지원 범위다.
- 새 정책은 최근 종료된 4개 분기를 후보로 하여 종목별로 signal_date까지 공시된 최신 보고분기를 선택한다. 최신 보고의 필수 계정이 없다는 이유로 과거 완전한 분기로 대체하지 않는다. Q1은 단독 분기, Q2/Q3은 당분기 IS 또는 누적 차분, Q4는 FY-Q3이며 CF는 누적 차분이다. 실제 공시일 이후의 정정·차분 operand는 사용하지 않는다. CFS/OFS를 섞어 차분하지 않는다.
- 후보 및 차분 의존 period 전체의 기존 historical-map/terminal-state/raw-shard 완결성 gate를 유지한다. 필요한 collection이 미완료면 data_gap으로 중단한다. 최신 분기의 필수 값 누락은 factor NaN으로 유지하며 기존의 명시적 결측 교집합 규칙을 따른다. 후보 4분기보다 오래된 자료를 자동 승격하지 않는다.
- Local pip는 20초 process limit/retries 0에서 즉시 실패했다. pytest/exchange_calendars/pyarrow가 없는 상태를 pass로 기록하지 않으며 동일 명령을 무기한 기다리지 않는다. 직접 가능한 pandas 회귀와 syntax를 먼저 검사하고 generated-contract·전체 real-data E2E·Python 3.11/3.12 sandbox replay를 원격 CI에서 확인한다.

현재: 계약 checkpoint 저장. 다음: provider/DSL/kit source-selection 연결, quarter/filing/fallback/fingerprint 회귀, 실제 2020년 5월 PIT 검증, generated contracts, 전체 CI 후 PR merge 및 사용법 기록.
