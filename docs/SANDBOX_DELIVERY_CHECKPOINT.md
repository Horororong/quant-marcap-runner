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


## 단계 2 완료: 실제 ZIP 생성·양 ABI offline replay (2026-10-02 UTC)

- 원격 source commit `b350b61e4db0c626e8533645a1a76d61d6ba0ae6`, PR #27, CI run `37075642412`.
- Kit ID `ee212da3e4a71bb7fa2261b45771156e2bf49b563419c8e639db45449cf694db`; `quant-sandbox-ee212da3e4a7.zip`, **291308667 bytes**.
  전체 SHA256: `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`.
- **CPython 3.11/3.12 모두 성공**. 각 ABI에서 4예제 **83개 artifact**가 원본 checked
  runner와 byte-identical이다. 두 ABI 간 fingerprint·NAV SHA256도 모두 일치한다.
  6개 missing/corruption/readiness 경계도 모두 통과했다.
- 12개 24MiB download segment와 ledger를 실제로 내려받았다. 전달 artifacts는
  30일 보관한다. 전체 Strategy DSL test job은 아직 실행 중이며 success로 기록하지 않는다.
- 다음: 저장된 ledger의 모든 SHA/길이로 ZIP 복원·무결성 검증, 로컬 offline
  bootstrap/verify, 전체 CI/PR 최종 확인, 실제 ZIP 링크 전달.
- Machine checkpoint: `docs/audits/sandbox-delivery-checkpoint-20261002.json`.


## 단계 3 완료: 다운로드 ZIP 복원·로컬 설치·전체 CI (2026-10-02 UTC)

- 12개 download segment의 길이·SHA256을 전부 직접 대조하고 원래 ZIP을 복원했다.
  전체 **291,308,667 bytes / SHA256 `533530e8ab97192574f53fc05cd6125abd3452e5978abdae9c08c512c78e2587`**가
  원격 생성 ledger와 일치한다. ZIP CRC/중복·안전한 이름, bootstrap, 모든 내부 part 및
  code/data/wheel archive의 길이·SHA256도 통과했다.
- 실제 파일: `/workspace/attachments/quant-sandbox-delivery/quant-sandbox-ee212da3e4a7.zip`.
  Binary는 Git에 저장하지 않는다. 새 workspace라면 machine checkpoint의 artifact IDs와
  `download_manifest.json`을 사용해 이 ZIP을 복원한다. 임의로 재생성/재백필하지 않는다.
- 현재 로컬 CPython 3.12에서도 **IP socket/DNS를 차단한 상태로** 다운로드 ZIP의
  bootstrap 설치와 isolated `sandbox_runtime.py verify`를 실제로 실행해 모두 통과했다.
  원격의 양 ABI 4예제 replay를 로컬에서 중복 실행하지 않았다.
- 원격 source `b350b61e4db0c626e8533645a1a76d61d6ba0ae6`의 전체 CI **`37075642412` success**:
  test `111064819455`, 3.11 `111064819139`, 3.12 `111064819425` 모두 success다.
  원문 quarter oracle, 기존 DART/KRX/top-N/10분위/CURRENT/legacy regressions를 보존했다.
- ZIP은 코드·원본 데이터·고정 wheel과 4예제를 포함한다. CPython 3.11/3.12 Linux
  x86_64 glibc≥2.28용이며, 가격 연도는 2020/2024, DART는 예제용 2019/2020 기간이다.
  연구 NAV와 정식 CURRENT report readiness를 구분하고 필요한 자료가 없으면 data_gap이다.
- 사용자 전달 준비 완료. 다음은 PR #27 native merge와 원격 main 상태를 별도 기록하고
  이 실제 ZIP의 다운로드 링크를 제공하는 것이다. 생성 source revision은 이후 docs/main
  commit과 구분하며 이미 검증한 kit ID/bytes를 변경하지 않는다.
