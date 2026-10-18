# 재현·게시·보존

## 환경

저장소 Horororong/quant-marcap-runner, 브랜치 fix/financial-accuracy-20261014.
시작 remote b37c0cf636e5fd80d001cf6d5c907cbf209eede8의 실제 성공 CI는39106746295다.
전용 Python은 `/workspace/financial-repair/runtime/.venv/bin/python`이다.
기존 kit_manifest와 sandbox_runtime.py verify 통과를 확인한 이 Python만 사용한다.
requests/PyYAML 미포함이며 인터넷 pip·버전 변경·시스템 Python 대체를 하지 않는다.

```bash
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I docs/research/long-multi-backfill-20261018/validate_continuation.py --check --output /tmp/continuation-new-run
"$PY" -I docs/research/multi-asset-20261018/validate_multi.py --output /tmp/multi-new-run
"$PY" -I docs/research/long-execution-20261018/validate_long.py --check --output /tmp/long-new-run
"$PY" -I docs/research/stage15-research-environment-20261017/validate_environment.py --check --output /tmp/baselines-new-run
"$PY" -I docs/research/stage16-continuous-research-20261018/validate_continuous.py --check --baselines /tmp/baselines-new-run --output /tmp/continuous-new-run
node scripts/verify_research_dashboard.cjs /tmp/continuation-new-run/json/report/report_CURRENT.html /tmp/continuation-browser
```

각 출력 폴더는 존재하지 않는 새 경로여야 한다. 이미 완료된 폴더를 덮어쓰거나
같은 실패를 수정 없이 재실행하지 않는다. 도구가 새로운 세션을 반환하면 해당
세션의 종료코드와 실제 summary를 확인한다. 마지막 명령 종료만으로 앞선 명령을
성공 처리하지 않는다. 모든 실행 결과는 원본 데이터나 main 상태를 변경하지 않는다.
각 프로그램의 명령·종료코드·로그는 출력 commands.json에 보존된다.
`validate_multi`의 종료0은 미해결 전체 요청들의 예상 exit3·NAV 미발행을 검증한다는
뜻이다. 그 전략들의 백테스트 완료를 의미하지 않는다.

## 지금 사용할 새 예제

```bash
"$PY" -I scripts/research_workbench.py inventory --output /tmp/inventory.json
"$PY" -I scripts/research_workbench.py check --strategy config/strategies/research_size_top1_2026_asof1016_v1.json --output /tmp/ready2026.json
"$PY" -I scripts/research_workbench.py run --strategy config/strategies/research_size_top1_2026_asof1016_v1.json --report-periods config/reports/research_continuous_2025.json --output-dir /tmp/actual2026
```

동일 한국어 요청은 validate_continuation.py의 REQUEST 상수에 보존했다.
`--research-model-from`에 동일 DSL을 명시한다. 선정표의 사용자 정의 팩터 열 이름만
정규화해 값 전체를 정확히 비교하고, 비중/NAV/성과는 바이트 단위로 비교한다.
성과는 CURRENT만 계산한다. 개인 계좌·배당세·현금배당 총수익/PIT 인증이 아니다.

## 공식 원천·변환

`config/research/official_source_extensions_v1.json`은 원본 parquet/지수 CSV SHA,
압축 전 CSV SHA·행수·유효기간·원문 응답 SHA를 묶는다. 전송 파일은 gzip 후 base64다.
`verify_official_sources.py`는 원문 JSON과13,808주식행의 OHLC·거래량·거래대금·등락·
등락률·시총·주식수138,080숫자 및 KOSPI17행을 독립 Decimal로 대조한다.
모든 STK/KSQ 원문 행이 변환 결과에 존재해야 한다. 순위는 당일 전체 Marcap 내림차순/
Code 순서의 파생값이며 공식 순위라고 표시하지 않는다. SourceMarket 원문을 보존하고
KOSDAQ GLOBAL만 기존 시장 정규화 계약에 맞춘다. 원문에 없는 ChangeCode/UpDown/Comp는
빈 값이며 실제 관측값을 만든 것이 아니다. Change는 CMPPREVDD_PRC의 별칭이다.
기존 base 필수 열만 투영한 뒤 공통 로더가 별도 확장을 합친다. 같은 날짜의 원본
관측이 존재하면 덮어쓰기 대신 실패한다. 일반 거래일1bp 검사는 유지된다.

`official_calendar_corrections_v1.json`의 KRX 현물 공고
20260520000117/20260520000121은 이전에 확보한 원문을 그대로 재사용한다.
검증 마지막 거래일은2026-10-16이며 미래 날짜/미거래일을 채우지 않는다.
Bio 공식 원문은 sources/bio__*.gz.b64,원래 URL/HTTP/content-type/원문 SHA는
sources/bio__state.json.gz.b64에 있다. 추정으로 생성한 기업행위 레코드는 없다.

## main 감사 재현

main snapshot은78ab49df4b25e0b71df0fc4366fcc7f5d0a179a9,
legacy 게시 데이터는5fd6583ca89de0dfa887deda0221852b448c04d5다.
`main_snapshot_manifest.json`으로 main의 실제 코드/상태 파일을 식별한다.
`backfill_published_snapshots.json`은 각 실행의 실제 게시 SHA와 그 시점 상태를
저장한다. 취소 실행에는 새 게시 SHA를 만들어 넣지 않았다.

신규 배치 원문 증거는 성공39085773974의 기존 artifact12122416836에 있다.
복원한 원래 ZIP은199816317바이트,
SHA256 `6faea3647a128da272d76aa0d315f4bdb93c7e46ba4554a8314add2d5b8f2f65`다.
추가 금융 수집은0회다. 공식 GitHub API302→서명된 저장소200으로1회 복원했고,
Authorization을 외부 저장소에 넘기지 않았다.8MB 별도 기존 subset12122461579는
SHA256 `326c0ad9baeedc2c326d62e85e04c94fa7b105a0f9f73abe75a4750f09f1dae5`다.
전체 원문을 Git에 중복 저장하지 않는다. 아티팩트 만료 전 원본 보관 정책은 별도 필요하다.

선정 규칙은 sample_plan.json/선정된 selection에서 확인한다. 금액 원문을 보기 전에
seed long-multi-backfill-20261018-v1을 고정했다. 신규16건+별도 과거 격리4건이다.
원문 literal grid와 각 원문 ZIP/member SHA는 sources/main_evidence-recovered__*에
보존했다. source_grids 전송은 원래 gzip-base64에 다시 gzip-base64를 적용했으므로
2단계로 복원해야 한다. verify_independent_audit.py가 이 단계를 명시적으로 수행한다.
이 프로그램은 기존 financial parser/aliases/selection 함수를 import하지 않는다.
독립 수동 통제값과 좌표,현재 금액·기간·단위·부호를 비교한다. 전체 원문 감사의
대체물이 아니라 정확한32개 통제값의 재현과 근거 추적을 위한 프로그램이다.

## 실패와 복구

- 첫 source CI39118387151: download-artifact의 반복 다운로드가 실패했다. 같은
  Action을 무조건 다시 돌리지 않고 공식 API의 bounded 복원으로 바꿨다. 원래 실패
  로그와 job 결론은 남아 있다. 이 Action의 내부5재시도는 우리가 만든 추가 루프가 아니다.
- 같은 최초 실행의2026수집은 DateOutOfBounds로 API 요청 **0회**에 실패했다.
  Jan1로 만든 XKRX 달력의 첫 세션 Jan2와 요청범위 경계가 원인이었다.
  달력 구성 시작을 이전12월로 고친 뒤 recovery39118810337에서26개 응답을 확보했다.
  이미 성공한 Bio7응답은 재다운로드하지 않았다.
- continuation-rights39119336267: 원래 상태3998/4021의 maintenance census 성공,
  신주인수권 시세 API는1회401로 실패. 새로운 재시도/추정값은 없다.
- 로컬 collector import: requests 누락,exit1. phase-integration.log 보존.
  실제 함수 AST+transport double+원래 writer로 범위를 좁혀 시험했다. 전체 import는
  UNVERIFIED로 남겼으며 인터넷 설치로 가리지 않았다.
- 로컬 최초 continuous 재현: 예전 exec6/registry8을 가진 오래된 baseline 폴더를
  공급해 현재 exec10/registry9 계약 비교가 실패했다. 기준값을 수정하지 않고 현재
  코드로 Stage15 전체를 fresh-baselines에 재현한 후 그 결과를 공급했다.
- 준비도v2 변경 후 generated_contracts 검사 실패: 생성 capability가 오래된 것을
  정확히 검출했다. 공식 export --write 후 --check,새 출력 폴더에서 원래 검증을 재개했다.
- Git diff --check의 보존 CSV CRLF/원문 인용 공백은 코드 오류와 구분한다.
  원문·기존 숫자 바이트를 고쳐 숨기지 않고 code/config는 별도로 검사했다.
- 로컬 Chrome: setsockopt EPERM/SIGTRAP. 추가 권한 요청은 사용자 취소이며
  실제 브라우저 실행/결과가 없었다. 같은 요청을 반복하지 않고 최종 CI에서 확인한다.

원본60ZIP `a7dfb0cc7764e21b9cc660f33d47a811e54785823d1beefadb93a54a486123c7`,
기존 Stage6 ZIP `b5b9d9b1b57632455ffcb27f5e2d28dc3c043b2154a76e29cba5e2f8fbc671a7`
및 기존 커밋은 보존한다. 원본 데이터·원문·운영 PIT 게이트는 변경하지 않는다.

## 게시와 CI 계약

GitHub Git Data API로 tree를 만든 뒤 native git tree와 SHA가 정확히 일치하는지
검사한다. 원격 최신 HEAD를 parent/expected_sha로 사용해 force=False로 이동한다.
원격 commit/file 목록을 다시 읽어 확인한다. 로컬과 원격 commit의 author 메타데이터로
commit SHA가 다를 수 있으므로 tree/file 일치를 별도로 검증한다. history rewrite는 없다.

최종 메시지 marker는 `[long-backfill] [stage16] [long-research] [multi-asset]`다.
실제 검증 job은 long-backfill-continuation/stock-dividend-regression/
explicit-long-research/multi-asset-research/continuous-baseline-research의5개다.
수집 job들은 과거의 정확한 SHA에만 한정되어 최종 검증 때 새 원문 API를 호출하지 않는다.
스킵된 기본 Strategy DSL workflow는 PASS로 세지 않는다. 최종 job의 실제 SHA·상태·
명령·브라우저 PNG/JSON·산출물은 해당 Actions artifact에서 확인한다.

## 최종 업로드 결함의 후속 최소 수정

첫 최종 CI39128696160 /83d07aa4738f82570a8784392b6dbcb3adee4097의
long-backfill-continuation117679175133은 계산·32금액 판정 재현·192세션 JSON/한국어·
독립576장부일·Chrome 실제 상호작용 단계는 성공했으나 artifact 업로드 단계가 실패했다.
원문 오류는 `test_fast_backfill_phase*.py.log`의 `Asterisk *` 파일명 거부다.
이 job를 PASS로 표시하지 않는다. 테스트 검색 패턴을 변경하지 않고 로그 basename만
안전한 ASCII와 원래 이름 SHA8로 만든다. commands.json에 실제 log_file을 기록하고
아티팩트의 모든 파일 이름을 검사한다. 로컬 원래 전체 명령을 새 폴더에서 다시
실행해 숫자 해시·원문 판정이 그대로이고 금지 문자가 없음을 확인했다. 이 후속 커밋은
원문 수집·원자료·전략·수익률·허용오차·금액 판정을 바꾸지 않는다. 실패 증거는
results/ci_39128696160_upload_failure.json에 보존했다.
