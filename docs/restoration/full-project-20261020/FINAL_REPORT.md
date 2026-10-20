# 접근 가능한 전체 프로젝트 snapshot 복원·개발 재개 결과

이 보고서는 최소 실행 환경 복원, 접근 가능한 전체 파일 복원, 금융 정확성/PIT 인증을 구분한다. 기존 최소 복원본과 v1 백업은 변경하지 않았다. 기본 개발 경로는 `/workspace/quant-project-full-20261020/code`, 브랜치는 `restore/full-project-20261020`이다.

## ① 데이터·자료 복원

- 실제 원본 인벤토리: 데이터 **749개 / 1,372,088,236bytes**. 최소 환경과 **6일치 / 743누락 / 0불일치**.
- 원본 데이터749개를 이동·삭제 없이 복사했고 전부 SHA256/길이가 일치했다. 같은 데이터 재수집0.
- 연구 고정 커밋에만 있던 2026공식 확장2개를 Git blob으로 복구했다. 신규 원천 수집이 아니다.
- 연구 입력 데이터 snapshot 합계 **751개 / 1,373,060,882bytes**. 해당 파일별 경로/크기/SHA256은 `evidence/data-manifest-restored.json`에 있다.
- 원본 비 Git 파일 **1,719개** 전량을 데이터와 `../preserved-main/`의 코드·문서·설정·기존 결과970개로 나눠 보존했다. 캐시성/중복 데이터도 삭제하지 않고 manifest에서 분류했다. 전체 원본 파일 hash와 최소 복원본 hash는 외부 evidence에 별도 보존한다.
- KRX1995~2026 **32개 연도 schema** 점검.1995/2000/2010/2021/2026 공통 엔진 로딩 및 Date/Code 중복 검사를 대표 수행했다. 2026확장 포함 마지막 날짜는10/16이었다.
- 등록된 DART loader는2015 FY30,251행/2020 FY21,023행을 로딩했고,2020-04-29의 기존 coverage gate를 통과했다. 이 성공은 금융값·PIT 신규 인증이 아니다.

## ② 차이·미복원 항목

- OS는 현재 Linux x86_64, 전용 kit Python3.12.14와 고정 패키지를 유지한다. 기존 PC의 OS 이미지·시스템 패키지·일시 캐시·사용자 프로필을 확보하지 못해 동일성은 인증하지 않는다.
- 이전 PC 전체 백업 SHA256 `725991950af01331042c74b05b1a52bcb3fc9ebb1502839a2a6fd5eac9844f4d`의 원본 파일은 미확보다.
- 과거 `/workspace/financial-repair`, `/workspace/research-stage*`, 옛 session store 등의 부재 경로를 `unavailable-materials.json`과 전체 절대경로 감사에 기록했다. Git에 보존된 증거는 복원했지만 미확보 세션 폴더/만료 artifact를 복원 완료로 세지 않는다.
- 최소 sparse 환경에는 `web/`가 빠져 있었다. 고정 커밋의 정식 웹 자산을 새 환경에 복구한 뒤 UI를 검증했다. `restored_workspace.py`는 이동 가능한 repo 루트와 명시적인 kit runtime을 사용하며 누락 자산을 실행 전에 보고한다.
- 기존 보조 함수 `krx_backtest_data.load_dart_financial_rows`는 `stock_code`를 요구하지만 실제 원본 shard는 `_stock_code`를 가진다. 원본과 새 파일 hash는 같고, 이 문제는 복사 손상이 아닌 기존 보조 함수/schema 불일치다. 검증된 등록 provider `DartValueFactorAdapter`는 원래 alias를 처리해 통과했다. 금융/PIT 의미를 추정해 보조 함수를 임의 수정하지 않았다. 향후 보조 API를 유지할지/등록 loader로 통합할지 별도 변경으로 다룬다.
- LOCAL DART/KRX 비밀값은 없다. 필요한 이름·설정 방법만 보존한다. 운영 수집은 기존 GitHub workflow secret을 사용했다. 비밀값·토큰·서명 URL은 일반 복구 자료에 넣지 않는다.

## ③ 기존 개발 지점과 반영

- 복원 기준이며 연구 브랜치 마지막 상태: **b5aaa7f01c17f77527c07baa36f27415de9aba31**, `fix/financial-accuracy-20261014`.
- 시작 시 운영 main: **55e8efcb02e1021f57448131df5e411eafca2ab9**. 연구와main은 각각84/51개 커밋으로 분기돼 있었다. 두 원본 작업 트리의 미커밋 변경0. 원격 전체 브랜치 refs와 전체 경로 차이를 보존했다.
- 운영main의 최신 유한 수집/HOLD 코드·설정·재무 후보는 `preserved-main` snapshot으로 보존했으며 연구 코드에 무조건 병합하지 않았다.
- 복원 필수 변경: **9b1eeb22741bd1919454ed1d9feb2550061754dc**.
- 신규 사용자 기능: **acdba7c4a66656d4bebac46fb202a666ab38848b**, **609ca9d209c5eb31a99e1eb63206450070278509**. 저장 결과/비교 카드에 당시 전략·자료 hash·비용·실행ID를 연결했다. 편집 중 조건이나 현재 파일로 과거 결과 기준을 바꾸지 않는다.
- 새 개발 브랜치에 GitHub 지속 게시했다. 원격/로컬 commit 및 tree가 정확히 일치한다. 최초 게시의 SHA차이는 전송 코드가 commit message 끝 개행을 제거한 것이었고, 원인을 SHA 재구성으로 입증해 고쳤다. 본래 개발 내용을 수정해 SHA를 맞추지 않았다.

## ④ 기존 회귀 기준

전체 데이터와 경로 복원 뒤 고정 JSON 세 전략을 한 차례 재실행했다.2024 top1244거래일,2020 momentum top3248거래일,2019~2020 deciles494거래일이다. 기존 **130개 파일 bytes/SHA256 정확히 일치**, 기존 비교기가 허용한9개 plan/preflight 계약 확장 통과,12개 volatile envelope는 byte 일치를 주장하지 않는다. 입력·fingerprint·선정·비중·NAV·CURRENT 기준을 교체하지 않았다.

모멘텀의 보고 설정에 포함된 추가2019년 gap은 그대로이며 요청한2020전체는 성공했다. 운영 금융/PIT·기업행위·1bp held-return·기간/모집단 gate를 완주 목적으로 바꾸지 않았다. UI 변경은 성과 계산/엔진/입력 파일을 건드리지 않았고 기존 저장 run260개 파일도 재열기 전후 동일했다.

## ⑤ 자동 수집

- fast workflow의 최신 run39483682418은 schedule 이벤트였지만 `bounded-canary.if`가 명시 marker push 또는 bounded dispatch만 허용한다. job steps0으로 skipped였으며 실행 로그가 생성되지 않은 상태다. cron은 active이나 이 workflow의 스케줄로 수집을 시작하지 않는 정책이다.
- 실제 유한 수집 workflow는 `backfill-dart-legacy-2000-2014.yml`, KST05:17 cron과 같은 공유 concurrency를 사용한다.1회100/최대3회/총300/KST하루1회/90초 문서/600초 전체, 원문 저장 뒤 checkpoint, CAS/lease, source hash 및 독립 첫검토 gate를 확인했다. 관련 소규모5시험은 통과했다.
- READY_NEXT, 기존 예약100, 첫 검토 통과, 중복 실행0, 다음100건 선정/소유 코드hash를 확인하고 **기존 예산 안에서1회** run **39504052321**을 재개했다.
- 결과: **RUN_WALL_BUDGET**로600초 예산 중단, 원문/체크포인트 **57건 보존**,48 PARSED_4F 후보/9 SOURCE_GAP, 후보871개, 새 금융값 게시0. 예약100건을 성공100건이라고 세지 않는다.
- 상태는 **HOLD_FAILURE**, 마지막checkpoint **20100331002054**. 예약은 총200/300으로 기록됐으며 같은 원인 재실행·예산 확대·HOLD해제는 하지 않았다. 다음 승인된 유한 재개 설계는 중단 checkpoint와 미수집43건/남은100 예약 한도를 구분해야 한다.
- 원격 원문 게시 commit **a9da665e77eb06e09232c9fa1b382b1e3ea31d4f**.5개 source pack을 Git blob에서 다시 확보했고 원본57 ZIP CRC·238개 파일 hash를 검증해 `../continuation/39504052321`에 보존했다. 새 후보는 연구 입력751개에 자동 승격하지 않았다.
- 실제 step 로그도 확보했다. 실행 결과 failure를 숨기지 않는다. 기존 백테스트 입력·보호값·운영 PIT와 자동 금융값 게시 HOLD는 유지한다.

## ⑥ 사용자 기능

실제 Chromium에서 자연어 조건 입력→해석/명시적 확인→준비도→공통 PROJECT→CURRENT→수수료 변경→결과 비교→전략 저장/불러오기/JSON 재실행을 통과했다. 수정 후 서버를 새로 띄워 **기존 저장 결과 다시 열기**와 자료/비용 기준 표시도 확인했다. 현재 편집 비용9.5bp와 저장 결과 비용1.5bp가 명확히 구분됐고 재계산/저장 파일 변경0이었다.390x844 viewport도 확인했다.

미지원 손절/레버리지와 모호한 조건은 실행 전에 거부한다. 원래 장기 다종목207940 차단도 계속 data_gap이며 성공 NAV를 남기지 않는다. 언어/web 시험12개 통과. 임의 자유문장 모델은 연결하지 않았다. 현재는 등록된 제한 한국어/JSON이며 외부 모델 연동, 실제 휴대폰 외부 접속·호스팅은 미검증/미제공이다. 로컬 브라우저 검증을 공개 서비스 배포로 소개하지 않는다.

## ⑦ 다음 작업·실행

1. 새 기본 개발 브랜치에서 저장된 사용자 결과와 manifest를 사용한다. 완료된 세 전략·v1 kit/백업을 무조건 재실행하지 않는다.
2. 수집은 HOLD_FAILURE 상태와57원문/871후보에 대한 독립 검토·중단 위치를 먼저 확인한다. 가드·예산을 늘리거나 무시하지 않는다.
3. 기존 보조 재무 API/schema 불일치의 처리 경로와 임의 자유문장/외부 모델 입력 계약은 각각 별도 범위로 개발한다. 등록 provider와 기존 금융 gate를 우회하지 않는다.
4. 다른 새 세션에서는 기존 v1의 고정 kit과 이번 증분 복구 자료를 사용한다. 데이터751개는 새 브랜치의 고정 커밋에도 보존돼 있으며 manifest로 검증한다. 증분은 동일 v1 kit/data를 다시 전송하지 않는다.

```bash
cd /workspace/quant-project-full-20261020/code
export QUANT_PINNED_RUNTIME=/workspace/quant-restore-b5aaa7f/runtime
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/restored_workspace.py layout
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/restored_workspace.py web --store /workspace/quant-project-full-20261020/user-store --port 8765
```

백업 원본·데이터 복사·금융 정확성 인증·최종 연구 목표 달성을 각각 판단한다. 이번 완료 범위는 **접근 가능한 전체 프로젝트 snapshot과 선언한 실행/사용자 흐름의 복원·검증 및 저장 결과 provenance 기능 재개**다. 기존 PC 전체 이미지, 금융/PIT 전체 인증, 모든 장기 다종목 전략의 완주를 완료로 선언하지 않는다.
