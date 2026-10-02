# 실행 묶음 전달 checkpoint — 2026-10-02

사용자 요청: ChatGPT 퀀트 프로젝트 대화에 직접 첨부할 실제 `quant-sandbox-*.zip`.
ZIP 생성 완료를 안내만으로 대신하지 않는다. 생성 파일은 Git에 넣지 않는다.

## 단계 1 완료: 현재 상태 확인·생성 경로 준비

- 원격 main `61250b33d84b02338bef4037f19169b336bb2185`를 직접 확인했다.
  최신 코드의 전체 CI `37055474711`과 후속 fast backfill `37058140267`은 success다.
  기존 재무 리밸런싱 구현·원문 확보·백필은 반복하지 않는다.
- 최신 legacy status는 현재 버전 processed **3,401**, pending **111,619**,
  usable4F **247**, collection/quality complete **False**다. 이 자료는 kit의
  공개 재무 provider에 통합하지 않는다.
- 기존 builder/bootstrap/checked runner와 Strategy DSL CI를 확장했다.
  기본 CI의 3예제 profile은 보존하고, 명시적인 전달 실행에서만 기본 3개와
  custom May 예제를 묶는다. KRX 2020/2024 원본 연도 패널, DART 2019 Q1/H1/Q3/FY
  및 2020 Q1/H1 원본 shard, 코드 map/state, KOSPI와 검증된 기업행동을 포함한다.
- CPython 3.11/3.12용 hash-locked wheel을 함께 넣는다. 두 ABI 각각 깨끗한
  venv와 libc socket/DNS guard 아래에서 네 예제의 모든 artifact를 원본과 비교한다.
- 각 subprocess는 900초, replay step은 1,750초 process limit/30분 step limit,
  job은 40분이다. 무출력 무기한 대기를 반복하지 않는다. 원본/재생 시작·소요시간을
  출력하고 실패 시 captured stdout/stderr를 보존한다.
- 기존 CI에 명시적 export 입력과 전달 branch gate만 추가했다. 추가 schedule,
  API 수집, 새 백테스터는 없다. 검증 성공 후 ZIP을 최대 32개의 24MiB download
  segment로 보관하고 전체/segment 길이·SHA256을 ledger에 기록한다.
- Local: kit failure-boundary **14 tests passed (1.037s)**, syntax/YAML parse,
  `git diff --check` 통과. 실제 offline replay는 GitHub Actions에서 실행할 예정이다.
  Local 부족 의존성/network 실패를 통과로 표시하지 않는다.

## 현재/다음 단계

현재 단계: 변경사항 commit → 원격 Actions 실제 생성·양 ABI 전체 검증.
그 후 native PR/CI 상태와 kit ID, 고정 source commit, 전체 ZIP SHA/크기,
artifact IDs·만료를 기록한다. 전달 segment를 내려받아 각 SHA/길이를 대조하고
ZIP을 복원한 뒤 전체 SHA와 member 무결성을 확인하여 대화에 다운로드 링크를 준다.
실제 검증·다운로드 전에는 ZIP 전달 완료로 표시하지 않는다.
