# Git 저장공간 감사와 1차 개선 (2026-10-01 UTC)

## 확인 기준과 제한

직접 확인한 사실과 운영 예측을 구분한다. 조사 기준은 전체 이력이 있는
feature checkout `2e6f95c85422629b26ef48ef57ae81ae247a9fba`이며, 원격 main은
`b763c5ca903d652a815bbdbff6df978843a45c86`, PR #23은 open,
head `6bbfe22d8fa92383ae57e3d810d9bcd2e9af95cf`였다. 선행 feature의
[최종-head Strategy DSL CI](https://github.com/Horororong/quant-marcap-runner/actions/runs/36885642627)는 Success였다.
이 변경은 `feature/deterministic-dart-storage`에서 작업한다. main 변경,
원자료 삭제, Git history rewrite, force push, LFS 변환은 수행하지 않는다.

크기는 MiB/GiB(2진 단위)다. HEAD 파일 합계, 파일시스템 크기, Git pack의
실제 저장 크기는 서로 다르다. `git rev-list --objects --all`,
`git cat-file --batch-check`, `git verify-pack -v`로 현재 clone의 모든 ref에
도달 가능한 blob을 조사했다. GitHub 서버의 전체 내부 저장량/청구량을
조회한 것은 아니다. packed delta의 크기를 포함해 측정했으며, 모든 버전의
파일 크기를 단순 합산한 수치를 실제 pack 크기로 주장하지 않는다.

## 1. HEAD와 working tree

HEAD 전체 파일 합계는 1,305,501,956 bytes, **1.216 GiB**다.

| 경로 | HEAD 파일 합계 |
|---|---:|
| data/ | 1.136 GiB |
| data/krx_equities/ | 555.31 MiB |
| data/krx_equities/yearly/ | 526.29 MiB |
| data/financials/ | 553.58 MiB |
| data/financials/full_history/ | 328.04 MiB |
| data/financials/recent_batches/ | 194.96 MiB |
| data/krx_equities/derived/ | 29.01 MiB |
| results/ | 78.22 MiB |

작업 디렉터리는 테스트 캐시 등으로 HEAD보다 약간 크다. 특히 Git의 기본
quoted Unicode 경로를 그대로 문자열로 집계하면 results 합계가 75.08 MiB로
작게 나온다. `git -c core.quotePath=false ls-tree -rl HEAD`로 교정했다.

가장 큰 파일은 marcap-2025.parquet 24.26 MiB, 2024 23.75 MiB,
2023 23.03 MiB, 2022 22.07 MiB다. 2026 파일은 18.50 MiB다.
results의 상위 파일은 60_40_template_v28 chat payload 12.58 MiB,
v29 payload 12.49 MiB, permanent_portfolio_v29 payload 11.97 MiB,
두 dashboard HTML 6.75/6.62 MiB다.

## 2–3. 실제 blob과 반복 버전

Git pack은 `git count-objects -vH` 기준 약 **1.21 GiB**다. 도달 가능한
blob 3,839개의 pack 내 압축/delta 저장분 합계는 1,305,154,412 bytes다.
loose objects 약 704 KiB, commit/tree/pack index 등이 별도로 있다.

| 분류 | 고유 blob | 전체 버전의 논리 크기 | 실제 packed blob 저장분 |
|---|---:|---:|---:|
| KRX yearly parquet | 46 | 760.54 MiB | 529.57 MiB |
| KRX 2026 parquet | 11 | 161.37 MiB | 30.85 MiB |
| DART financials 전체 | 331 | 606.52 MiB | 569.19 MiB |
| DART recent_batches | 36 | 194.96 MiB | 194.85 MiB |
| results | 736 | 약 141 MiB | 약 39.92 MiB |

경로 분류는 `rev-list`가 해당 blob에 붙인 경로로 집계한다. 같은 blob은
여러 경로/commit에서 공유될 수 있어 경로별 집계는 GitHub 청구 분류가 아니다.

pack에서 가장 큰 blob은 현재 2025 parquet의 20.05 MiB이며, 같은 경로의
이전 blob도 19.67 MiB를 차지한다. 현재/이전 2024 blob은 19.74/19.34 MiB,
2023은 19.27/18.87 MiB다. 2022–2025의 추가 버전에는 기존 KOSDAQ GLOBAL
역사 복원 작업이 포함된다. 이는 필요한 자료 변경이므로 불필요한 중복으로
삭제하거나 취소할 대상이 아니다. CSV/HTML/JSON은 Git 압축과 delta가
상당히 효과적이지만, recent gzip은 거의 원래 압축 크기 그대로 저장된다.

## 4–5. recent gzip 재생성과 실제 주요 원인

직접 읽은 recent 파일 36개의 이력에는 **각 경로당 blob이 한 개씩** 있다.
따라서 현재 이력만으로 "같은 파일이 gzip timestamp 때문에 매일 새 blob이
됐다"고 단정할 수 없다. 같은 경로의 이전/다음 gzip 비교 대상은 0쌍이다.

그러나 기존 writer는 pandas `compression='gzip'`으로 현재 gzip mtime과
파일명 FNAME을 저장한다. 실제 header에서도 이 값들을 확인했다. ThreadPool의
`as_completed()` 순서로 CSV 행을 쌓고 첫 결과에서 컬럼 순서가 정해지므로,
같은 원자료의 재수집에서 행/컬럼 순서도 바뀔 수 있다. 이 동작은 테스트에서
시간·경로·행·컬럼을 바꿔 재현하고 새 writer로 차단했다.

**더 큰 사실:** 기존 rotation은 마지막 배치에서 처음으로 wrap하며
`(start + batch_size) % total`을 다음 시작점으로 사용한다. 회사 수가 300의
배수가 아니면 다음 회전 시작이 0이 아니고, offset 기반 파일명이 계속
추가된다. 실제 `00000_00299`, `00269_00568`, `00238_00537` 같은 서로
겹치는 배치가 함께 남아 있다. 회사 목록 크기 변화도 배치 소속을 바꾼다.

36개 파일의 전체 7,618,049행을 CSV의 모든 필드/값으로 비교하면 고유 행은
2,623,596행이다. 약 **65.6%가 완전히 같은 행의 반복**이다. 원자료에 없는
값을 채우거나 공시/금액을 무시해서 만든 중복 판정이 아니다. CFS 응답이 있는
고유 종목은 2,355개, 파일별 종목 출현 합계는 6,721회다. 이 통계가 과거
snapshot을 삭제해도 된다는 뜻은 아니다.

## 6. KRX current-year 영향

2026 parquet은 2026-08-31~10-01에 11개 blob, 논리 크기 합계
161.37 MiB이나 실제 pack 저장분은 **30.85 MiB**다. 두 base blob이
각 15.44/14.93 MiB이고 나머지는 대부분 수 KiB~수백 KiB delta다.
"매 갱신마다 18.5 MiB가 그대로 누적"이라고 해석하면 과장이다.

실제 새 거래일/역사 정정은 저장해야 한다. 현재 writer는 snappy parquet을
통째로 쓰며, derived wide CSV와 status/manifest의 수집 시각도 갱신한다.
데이터가 같을 때도 status만으로 commit할 가능성이 있다. 이번 1차 범위에서는
KRX writer/자료를 변경하지 않는다. 장기 예산은 delta 효과를 확정할 수 없으므로
연 26회 × 20–26 MiB ≈ **0.51–0.66 GiB/년**을 current-year parquet의
보수적 full-version 시나리오로 본다. 완료 연도 추가분/derived/수동 실행은 별도다.
현재의 delta 효과가 지속되면 실제 저장은 훨씬 작을 수 있다.

## 7. DART 연간 증가 예측과 개선 효과

9월 23일 이후 새 배치 12개의 평균 크기는 5.113 MiB다.
일 1회 + biweekly 26회 = 연 391회에서 같은 양을 저장한다고 가정하면
**1.95 GiB/년**이다. 공개된 현재 workflow가 매일 모든 회사를 수집하는
것은 아니며, 한 번에 최대 300개 회전 수집이다. 일부 날짜의 추가 실행도 있어
이 값은 운영 예산 시나리오이지 확정 성장률이 아니다.

이번 변경은 목록 끝에서 짧은 마지막 배치 후 next_offset=0으로 돌아간다.
현재 3,933개 회사/300개 배치에서는 14개 배치 경계가 반복된다. 기존 offset에서
그대로 재개하고 첫 tail 이후 0으로 정렬하므로 한 회사를 영구 누락시키지 않는다.
기존 파일은 일괄 재작성하거나 삭제하지 않는다.

신규/변경 CSV는 모든 컬럼과 행을 고정 정렬하고 LF, UTF-8 BOM,
gzip mtime=0, FNAME 없음, compresslevel=9로 저장한다. 같은 CSV 필드/값이면
구 gzip 파일의 원래 bytes까지 보존한다. 실제 금액/공시일/추가 필드 변경은
별도 변경으로 저장된다. 코드/금액/빈 값/`NA` 텍스트를 숫자나 결측으로
해석하지 않으며 새로운 dedup 규칙을 적용하지 않는다. 기존 API 수집과
`drop_duplicates(..., keep='last')` 선택 계약은 유지한다.

**판단:** 회사 목록·배치 크기·조회 연도·원자료가 고정된 재수집은 새 대용량
blob을 만들지 않는다. 새 경계 14개가 모두 추가되는 최악의 초기 적응 예산은
평균으로 약 72 MiB이며, 이후 동일 재수집의 큰 blob 증가분은 0이다.
이를 연 391개 완전 신규 파일 모델과 비교하면 초기 경계 정착분에 대한
감소는 약 96%다. 이는 "전체 저장 증가를 항상 96% 줄인다"는 주장이 아니다.
실제 신규/정정 공시 비중, 연도 이동, 회사 목록 변화가 있는 상황의 감소율은
배포 후 2–4주 측정해야 한다. 압축 라이브러리/패키지 버전 변경에도 실제 CSV
내용 비교로 동일 파일을 유지한다.

## 8. generated results

HTML/dashboard/chart JSON은 일별 NAV + CURRENT/postprocess + 고정된 환경으로
재생성 가능한 presentation 산출물이다. 매번 전부 Git에 commit해야 재현성이
성립하는 것은 아니다. `update-market-data`, 여러 개별 backtest workflow와
`run-marcap`의 broad `git add results/`는 장기적으로 재생성 파일까지 수집한다.

추천 최소 보존 묶음은 전략 JSON, code/engine/provider 버전, 데이터 SHA256
manifest, 일별 NAV, 필요한 selection/trade/기업행동 감사, canonical metrics,
실행 status다. NAV만으로 전략/원자료 재현이 증명되지는 않는다. 실행 환경과
입력을 고정한 manifest는 아직 완성되지 않았으므로 모든 과거 presentation을
이미 완벽히 재현할 수 있다고 가정하지 않는다.

향후 **새 산출물**은 artifact 또는 release에 발행하고 explicit allowlist로
Git staging하는 것이 좋다. .gitignore만 추가해도 이미 추적 중인 파일은 계속
commit되므로 workflow staging도 함께 수정해야 한다. 기존 파일 untrack/삭제나
results retention/GC는 이번 변경에 포함하지 않는다.

## 9. Actions artifact와 Git storage

`actions/upload-artifact`의 ZIP은 별도의 Actions storage다. 그 내용을 `git add`
한 경우에만 Git blob도 생긴다. 양쪽에 저장하면 두 곳 모두 용량을 사용한다.
artifact를 삭제해도 Git blob은 줄지 않고, Git 파일을 지워도 과거 blob은 남는다.

artifact에는 보존기간/만료와 계정별 저장 요금·접근 권한이 있다. 현재 historical
failure recovery artifact는 90일이며 **영구 원자료 저장소가 아니다**. per-run
status/디버깅 자료에 적합하다. 정확한 비용/허용기간은 repository 공개 여부,
계정 요금제와 설정을 확인해야 한다.

공식 참고:
- [Actions storage/billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Artifacts retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
- [Large Git files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)

## 10. 1년/3년 최대 리스크

개선 전 recent 모델만 더하면 현재 Git pack 약 1.21 GiB에서
1년 뒤 약 **3.17 GiB**, 3년 뒤 약 **7.07 GiB**다. KRX/backfill/원문 ZIP/
results는 제외했다. 정기 업데이트와 일회성 backfill 증가는 구분해야 한다.

주요 리스크는 (1) 이동하는 배치 경계 + 압축 재생성, (2) broad full-history/
원문 ZIP 보관, (3) 진짜 값 변경도 통째로 기록하는 parquet/gzip,
(4) presentation 자동 commit, (5) status만 바뀌는 commit과 clone/CI 비용이다.
새 historical collector의 immutable 원문 JSON/ZIP은 checksum으로 같은 bytes를
중복 저장하지 않지만, 현재 Git 보관을 기본으로 한다. 원문 ZIP이 아직 수집된
크기로 검증되지 않아 연간 증가량은 산출할 수 없다. 대규모 원문 수집이 가장
큰 미확정 리스크이며, 첫 1만 건의 평균/상위 크기부터 측정해야 한다.

## 저장 대안 비교 (판단·제안)

| 대안 | 장점 | 단점·비용 | 재현성 | Codex/CI 접근 | 이전 난이도 |
|---|---|---|---|---|---|
| 현 Git + deterministic 출력 | 기존 checkout 그대로, commit으로 snapshot 고정 | 모든 실제 압축 버전 유지, clone 커짐; Git 호스팅 한도/CI 전송 비용 | 현재 방식 유지, 원자료 함께 있음 | 가장 단순 | 낮음, 이번 구현 |
| Git LFS | code clone 가벼워짐, pointer SHA로 파일 고정 | 변경 때 전체 LFS 객체 증가; storage와 다운로드 quota/요금, LFS 도구 필요 | pointer+객체 보존/가용성이 전제 | checkout LFS 설정, 인증·quota 필요 | 중간; 앞으로의 파일 전환도 가능, 과거를 줄이려면 별도 승인된 rewrite 필요 |
| GitHub Releases | 버전별 immutable 운영 snapshot, Git 이력 밖; public 다운로드 간단 | 운영상 삭제/교체 막아야 함, asset당 2 GiB 미만; 일반적으로 Actions/LFS 별도 quota와 다른 정책 | 고정 release/asset ID+SHA256 manifest 필수 | public은 간단, private은 token 필요 | 중간, 분할·다운로드·checksum loader 필요 |
| Actions artifacts | CI 결과/실패 복구 쉽게 연결 | 만료; Actions storage 정책/요금, 영구 source로 부적합 | 보존기간 동안만 보장 | run ID+auth 다운로드/복구 필요 | 낮음(보고서), 높음/부적합(영구 원자료) |
| 별도 object storage | 원문 ZIP/장기 version 확장, content-address/lifecycle 지원 | 월 저장+요청+전송 비용, 인증·백업·권한 관리 필요 | immutable object key+hash, 보존/백업 계약이 전제 | CI secret/OIDC, Codex read 권한·fetch 설정 필요 | 중~높음; adapter를 로컬 cache 경로 뒤로 유지할 수 있음 |
| data-only Git repo | code 개발/clone과 데이터 소유권 분리 | 데이터 repo의 압축 history 문제는 남음; 전체 저장 비용 감소 아님 | 데이터 commit pin+hash로 유지 | 두 repo checkout/token 필요 | 중간; canonical 로컬 디렉터리 공급 유지 |

정확한 청구 단가는 특정 provider/계정이 정해진 후 확인한다. LFS는 gzip/parquet
버전 증가를 자동 dedup하지 않으므로 첫 선택으로 권하지 않는다. Release도
hash 없는 `latest` URL만으로 재현성을 보장할 수 없다.

## 실행 순서

1. **즉시:** 이번 작은 writer/rotation/status 변경만 적용한다. 기존 자료와
   이력은 보존한다. daily/biweekly 스케줄, API 범위, 교정 공시 갱신은 유지한다.
   상태 CSV의 updated_at_utc는 마지막 실질 상태 변경 시각이다. 실행마다의
   checked_at_utc와 changed_paths는 runner temp의 JSON으로 artifact에 남긴다.
   next_offset/실제 오류/회사 수 변화는 commit하므로 완전 동일 데이터라도
   회전 진행을 보존하는 작은 commit이 계속 생길 수 있다.
2. **1–3개월:** code/data/environment hash 실행 manifest → 실제 증가량과 ZIP
   pilot 측정 → 새 results staging allowlist+artifact/release → receipt/company
   기반 immutable 데이터 chunk와 dataset manifest를 설계한다. offset 소속 회사
   변경에 따른 churn을 없애려면 안정된 회사 식별자로 partition해야 한다.
   KRX derived를 필요할 때 재생성하고 status-only Git commit도 별도 검토한다.
   다른 데이터 updater/backfill의 timestamp 계약을 이번 방식으로 무작정
   바꾸지 않는다. task-state timestamp는 재개/최신행 선택에 쓰일 수 있다.
3. **3–5 GB 접근 시:** code Git + 작은 dataset manifest, verified snapshot은
   versioned Releases(간단한 배포) 또는 object storage(대량 원문)로 분리하는
   방식을 우선 비교한다. 새 자료부터 이중 기록→hash/행/PIT/E2E 대조→read-only
   loader 전환→복구 연습을 한다. dataset pin, checksum, offline cache,
   CI/Codex 접근과 백업을 확보한 뒤 다음 단계로 넘어간다. 기존 Git history를
   줄이는 작업은 별도 승인 대상이며 자동 수행하지 않는다.

## 변경과 검증 경계

변경 파일은 최근 writer, 두 production workflow, 신규 regression test,
Strategy DSL CI 연결, 이 감사 문서와 운영 문서다. daily workflow의 push는
main으로 제한하여 feature push가 실 API 갱신을 실행하지 않게 한다.
manual/schedule/main 동작과 기존 staged diff commit gate는 유지한다.

신규 9개 regression은 exact CSV 값/빈 값/leading zero/문자 NA, gzip header,
시간·파일명·행/컬럼 순서, legacy byte 보존, 실제 공시/금액 변경, 중복행 수,
atomic failure/corruption, 모든 회사 회전 coverage, 실제 Git no-change commit
경계와 artifact heartbeat를 검증한다. 실제 stored DART 317,165행도 포함한다.
전체 Strategy DSL CI의 29개 check에는 기존 DART/KRX/top-N/decile execution,
held-return/corporate actions, CURRENT와 generated-contract 회귀가 유지된다.

이 환경에는 DART API key가 없어 live DART 수집은 하지 않았다. 기존 실제 저장
자료로 output determinism을 검증한다. engine/provider/성과 계산 코드는 수정하지
않으며, 실제 원자료와 기존 backtest NAV/선정 결과 대조도 별도로 수행한다.
