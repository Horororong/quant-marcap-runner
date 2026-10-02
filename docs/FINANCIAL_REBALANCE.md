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

## 단계 2: 구현·로컬 검증

- DSL machine 22 / factor registry 7. Explicit latest_disclosed_quarter 정책을 provider, 공통 top-N/10분위 선정, preflight coverage 및 offline kit source selection에 연결했다. 기존 policy 기본값·8개 strategy fingerprint와 기존 Q4/Q2 수식을 보존한다.
- 새 policy의 provider는 dart_report_year / dart_report_period / dart_available_date / dart_fs_div를 선정 감사에 남긴다. 신규 보고서에 등록된 계정이 전혀 없는 경우도 receipt marker를 보존해 과거 완전 분기로 잘못 fallback하지 않는다.
- 로컬 bounded 검증: 새 정책 unit/integration 경계 14개, kit 경계 14개, strict validation 271 invalid cases 및 기존 8 fingerprint, factor registry·aliases·PROJECT synthetic integration, generated-contract check 통과. 삼성전자 원문 receipt 20200515001451의 4 IFRS Q1 계정을 snapshot 수식과 독립적으로 읽어 2020-05-29 값과 직접 대조했다. 전체 source candidate/dependency gate도 통과했다. KRX 실거래 NAV는 로컬 pyarrow/exchange_calendars 부재로 아직 검증하지 않았다. 기존 decile execution local 검사는 exchange_calendars 부재로 실패한 사실을 구분한다.
- Generated contracts는 executable builder로 생성했다. 캘린더 라이브러리는 실제 session 검사 함수에서 import해 contract export/DSL-only 검사가 데이터 실행 의존성을 설치하지 않아도 가능하다. 실제 session guard는 동일한 라이브러리와 함수로 유지한다.
- CI에 새 5월 real original-source/checked NAV 검사를 추가했다. 기존 전체 suite와 clean offline Python 3.11/3.12 replay를 유지한다. 새 source/실거래 실행 테스트 process timeout 840초, step 15분, faulthandler 60초마다 stack 출력, 전체 test job 45분으로 제한했다. 기존 60초 pytest limits는 유지한다. CI 시작·완료·실거래 PASS 여부는 이후 checkpoint에 기록한다.
- 첫 GitHub commit 요청은 사용자가 실수로 취소했다고 명시한 뒤 재개했다. 계약 commit 0ceb9d0c77f1e1db8da52ac3fe17c4735b91a504, branch feat/financial-custom-rebalance. 데이터/백필 workflow/API 요청은 변경하지 않았다.

다음: 구현 PR의 모든 required CI 확인 → native merge → main CI 확인. 아직 main 배포 완료로 소개하지 않는다.

## ChatGPT에서 요청하는 예

> 재무 팩터 리밸런싱을 3·6·9·12월 마지막 거래일로 해줘. 각 종목은 그날까지 공시된 최신 분기의 수치를 사용하고 최신 보고의 결측을 과거 분기로 대체하지 마. next-close 1거래일 지연으로 실행해줘. 필요한 데이터가 부족하면 정확한 data_gap을 알려줘.

매월은 months=[1,2,3,4,5,6,7,8,9,10,11,12], 5·11월 반기는 [5,11], 매년 7월은 [7]이다. 선택한 월 외에 신호를 임의 추가하지 않는다. 예시 파일 config/strategies/kr_equity_dart_custom_month_research.json은 **시총 10조 이상 대형주 10개**라는 명시적 연구 유니버스에서 2020년 5월 신호를 검증하기 위한 짧은 실행 예다. 사용자의 다른 시장·종목 조건에 이 필터를 자동 부과하지 않는다.

ChatGPT용 runtime kit는 새 code commit과 요청에 필요한 whole-period shards로 다시 빌드·verify/replay해야 한다. 기존 kit에 이 기능이나 새로운 연도가 자동으로 설치되지는 않는다. 기본 배포 kit의 3개 starter coverage가 임의의 월·기간을 보장하지 않는다. 월 중 특정 날짜/공시 이벤트, 연간·TTM 정의, legacy 2000–2014 품질 인증은 별도 미완료다.

