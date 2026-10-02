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

### 첫 원격 실거래 검사 경로 수정

- 구현 remote commit 901a3631ce390557f3c139e26478268fd390c0c1 / PR #26. CI 37019745246에서 새 14개 회귀와 실제 삼성전자 원문 oracle가 통과했다. 실제 checked 실행은 status=ok / nav_ready=True / report_ready=False였고 10개 종목의 Q1/PIT 선정과 유한 양의 NAV까지 확인했다.
- 테스트가 기존 publisher에서 저장하지 않는 artifacts/execution_schedule.csv를 읽어 FileNotFoundError로 실패했다. 실행 실패나 hang이 아니었다. 60초 stack dump는 report_snapshots의 원자료 처리 위치를 보여 주고 전체 실제 실행은 약 142초 뒤 정상 반환했다.
- 체결 지연 검증을 삭제하지 않고, 실제 공통 run_strategy를 그대로 호출하는 transparent wrapper로 engine_result.execution_scenarios.gross.execution_schedule을 확인하도록 수정했다. 수정 commit의 전체 CI와 기존 실데이터 회귀를 다시 확인한다. 첫 실패 run을 성공으로 기록하지 않는다.

### Native crash를 구분한 bounded 진단

- 다음 CI 37020801380 / code 4a24ff82972890f6c4fdc82b9fe4e75ffefa4fb7은 input/기존 KRX 회귀와 새 14개 경계·삼성전자 원문 oracle 이후 첫 timed stack 출력 중 pandas/core/dtypes/generic.py 위치에서 exit 139 (Segmentation fault)로 종료됐다. 840초 timeout이나 보통 assertion 실패가 아니다. 로그만으로 native crash의 근본 원인을 인증하지 않는다.
- 비동기 timed frame inspection을 제거하고 30초마다 persisted run_status의 phase와 monotonic 경과시간을 출력한다. Fatal crash의 faulthandler는 유지한다. External timeout 840초/step 15분, 기존 pytest 60초 process limit/15초 stack dump, 모든 PIT·NAV·t+1 assertions는 유지한다.
- 실패 CI의 numpy 2.5.3은 기존 offline lock의 2.4.6과 달랐다. CI test job도 기존 cp312 sandbox requirements의 exact versions/SHA hashes로 계산 환경을 설치하여 offline replay와 맞춘다. pytest/requests/bs4/lxml/YAML은 보조 테스트 의존성으로 설치한다. Numpy 차이가 원인이라고 단정하거나 정상 결과를 위해 검증을 삭제하지 않는다. 이 수정의 전체 CI를 다시 확인한다.

## ChatGPT에서 요청하는 예

> 재무 팩터 리밸런싱을 3·6·9·12월 마지막 거래일로 해줘. 각 종목은 그날까지 공시된 최신 분기의 수치를 사용하고 최신 보고의 결측을 과거 분기로 대체하지 마. next-close 1거래일 지연으로 실행해줘. 필요한 데이터가 부족하면 정확한 data_gap을 알려줘.

매월은 months=[1,2,3,4,5,6,7,8,9,10,11,12], 5·11월 반기는 [5,11], 매년 7월은 [7]이다. 선택한 월 외에 신호를 임의 추가하지 않는다. 예시 파일 config/strategies/kr_equity_dart_custom_month_research.json은 **시총 10조 이상 대형주 10개**라는 명시적 연구 유니버스에서 2020년 5월 신호를 검증하기 위한 짧은 실행 예다. 사용자의 다른 시장·종목 조건에 이 필터를 자동 부과하지 않는다.

ChatGPT용 runtime kit는 새 code commit과 요청에 필요한 whole-period shards로 다시 빌드·verify/replay해야 한다. 기존 kit에 이 기능이나 새로운 연도가 자동으로 설치되지는 않는다. 기본 배포 kit의 3개 starter coverage가 임의의 월·기간을 보장하지 않는다. 월 중 특정 날짜/공시 이벤트, 연간·TTM 정의, legacy 2000–2014 품질 인증은 별도 미완료다.

## 단계 3: main 통합 및 검증 상태

- PR #26 최종 code `140bbdfaa8a0974229092667580e8998868d8af3`의 전체 CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/37022042125> **test / sandbox replay 3.11 / sandbox replay 3.12 모두 success**를 직접 확인했다. 실제 새 5월 checked NAV는 30초 heartbeat와 함께 약 197초 뒤 통과했다. Q1 PIT/10개 선정/유한 양의 NAV/2020-06-01 체결/정식 report_ready=False를 확인했으며, 기존 4·10월 DART·실제 KRX·CLI와 8개 fingerprint 회귀도 모두 통과했다.
- Native merge `573b6bdc91af6d713b55364e2072fe23d2fd507f`의 tree `e48820095ee8ee5e39fc95b78a5dfb6745cd24e0`가 feature의 검증된 tree와 **정확히 동일**하다. Main의 기존 데이터·수집 일정과 legacy 품질 상태를 보존했다. 새 기능은 main에 통합됐고 자동 main CI의 완료 상태를 추가 확인 중이다.
- 최초 exit 139의 native 원인을 독립적으로 규명했다고 주장하지 않는다. 고정 numpy/pandas 계산 환경과 periodic frame inspection 대신 persisted-phase heartbeat를 사용하는 최종 run은 segfault 없이 전체 통과했다. 동일한 수치·PIT·체결·source completeness 검증을 유지했다.
- Machine checkpoint: docs/audits/financial-rebalance-checkpoint-20261002.json. 마지막 main CI 결과와 최신 commit은 이 문서의 다음 checkpoint에서 확인한다. 기존 ChatGPT runtime kit는 새 code와 실제 선택 기간의 source를 넣어 재생성해야 하며 자동으로 변경되지 않는다.

## 최종 완료: main CI·데이터 갱신·재개 인계

- Main code `573b6bdc91af6d713b55364e2072fe23d2fd507f`의 전체 CI <https://github.com/Horororong/quant-marcap-runner/actions/runs/37055474711> **test / sandbox replay 3.11 / sandbox replay 3.12 모두 success**로 종료한 것을 직접 확인했다. 실제 custom May checked NAV와 기존 DART/실데이터/CLI 마지막 PASS 로그를 확인했다. 신규 source/PIT/체결 검증과 기존 8개 fingerprint가 main에서도 통과했다.
- `scripts/execution_contract.py`가 기존 Update quant data의 push path에 들어 있어 <https://github.com/Horororong/quant-marcap-runner/actions/runs/37055474556>가 함께 실행됐고 **success**였다. 기존 KRX/current-year, public market/macro, recent DART 갱신을 보존했다. 후속 data-only 최신 commit은 `94cabcd4d000bb46eaed87bed8fcf2164f029a95`이다. Merge 이후 변경 파일을 직접 비교해 코드·DART full_history·KRX 2020/2024·KOSPI는 바뀌지 않았음을 확인했다. 현재 2026 자료·다른 지수/FX/macro·recent DART/status가 갱신됐으며, 이 후속 data-only commit에 별도 전체 CI가 있었다고 주장하지 않는다.
- Legacy 상태도 다시 직접 읽었다: durable **1,401 / pending 113,619**, collection/independent quality 완료 모두 False, parser/source version은 그대로다. 이 기능 작업에서 legacy 정상 receipt·원문 capture를 다시 수집하거나 처리 완료를 품질 인증으로 승격하지 않았다.
- 완료 기능: 선택 월 1..12의 마지막 거래일, monthly/quarterly/semiannual/annual 월 목록, 명시적 latest_disclosed_quarter, PIT 차분·정정·scope·최신 보고 결측 guard, provider/선정/coverage/kit 연결, generated contracts와 전체 CI. `rebalance.dart_period_policy`를 생략하면 기존 4·10월 정의를 유지한다.
- 월 중 특정 일자·공시 직후 일정, annual/TTM 팩터, noncalendar fiscal mapping 인증, legacy 품질 완료는 후속이다. 다운로드 가능한 새로운 GPT kit ZIP을 이 기능 작업에서 생성했다고 주장하지 않는다. **ChatGPT 퀀트 프로젝트에 적용하려면 이 버전과 실제 요청에 필요한 source를 넣어 kit build/verify/offline replay 후 첨부·설치해야 한다.** 기존 kernel/kit를 조용히 수정하거나 GitHub main의 코드가 ChatGPT에 자동 설치됐다고 소개하지 않는다.
- Local implementation commit은 `ab62836f098269180fa2b02451982b6ad7b95d87`다. 최신 remote gzip/2026 데이터의 binary 전달 제한과 local KRX 실행 의존성 부재를 구분하며, local이 최신 main과 같다고 주장하지 않는다. 이 최종 인계와 machine checkpoint는 local에도 mirror하고 별도 commit한다. 재개 시 GitHub main·최신 상태/CI를 다시 직접 확인한다.

**다음 작업:** 사용자의 구체적인 리밸런싱 월·전략·기간에 맞는 GPT offline kit 구성·실제 다운로드/설치 전달. 특정 일자/공시 event 규칙을 요청하면 별도 DSL 일정 계약과 거래일·PIT 회귀로 확장한다. 기존 legacy 자동 수집·확보 원문의 source/당기 기간·단위·loss guard·독립 audit 후속은 legacy handover의 순서를 따른다.
