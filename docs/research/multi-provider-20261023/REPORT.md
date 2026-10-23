> **최신 보완(2026-10-23KST): v12 전송 완료.** 현재 GH_BACKUP_TOKEN으로 인증·기존 draft 업로드·4assets 실제 다운로드·ZIP SHA/CRC/41payload 일치 PASS. 새 권한/토큰 교체 불필요. 아래 PENDING_AUTH 진단은 당시 이력이다. 최신 증거: `docs/research/auth-delivery-20261023/REPORT.md`, `/workspace/quant-auth-recheck-20261023/FINAL_STATUS.md`. 승인된 동일 v12는 다시 전송하지 않는다.

# 다종목 재무 연결·모집단 대조·인증 재개점 — 2026-10-23

모든 결과는 **RESEARCH_ONLY**다. 금융 게시 HOLD, PIT0/6, source coverage,
기업행위·held-return·no-lookahead 계약은 유지한다. 완료된 전체 복원·751파일
해시 감사·130비교·UI 브라우저·29b CI·대용량 백업 전송은 반복하지 않았다.

## 승인된 연구 코드 게시

공개 연구 브랜치 `fix/native-source-boundaries-20261021`은
`29b6c4a2c277f6b2070e4bf70da54899f9fe4bcf`에서
**`589a3ea2aa7dd3aa23f961aab7a8e75e1b1ac574`**로 fast-forward했다.
별도로 질문한 중간 f8f2e62·7691fd2의 게시에 사용자가 “다 해라”로 승인했다.
중간 범위는 최종 경로 43개/880,628바이트이고, 그 뒤 승인 범위는
31개/1,064,712바이트다. HANDOFF 등 3개 경로가 겹쳐 전체 고유 경로는 71개다.
네 커밋의 역사상 파일 버전은 76개/2,030,672바이트이며, 최종 파일 수와 다르다.

|전송 manifest|SHA256|
|---|---|
|중간 43경로|1cb88495e47179ed0531b53be3e598670aae19b0530408561bee7f733b3b4df6|
|후속 31경로|0975b2067fb40401ffb0c966edbda27a64b8368c04102e2d5a2545f8998fa705|

모든 변경 버전의 비밀값 검사 0건. 원격 커밋·tree의 정확한 Git SHA와
3개 파일의 실제 다운로드 바이트/SHA256를 확인했다. 강제 push·main 변경·새
driver·CI 색인 게시는 없었다. [원격 커밋](https://github.com/Horororong/quant-marcap-runner/commit/589a3ea2aa7dd3aa23f961aab7a8e75e1b1ac574),
[게시 영수증](evidence/PUBLISHED_589.json).

589의 새 재무 bridge/conflict 코드를 대상으로 한 원격 CI는 **NOT_RUN**이다.
기존 공개 driver의 UI/parser/기간 시험은 새 bridge 시험을 포함하지 않으므로
그 실행을 새 코드의 검증으로 대체하지 않았다. 이전 29b/운영 CI 성공과 구분한다.

## v12 인증과 원격 보존 상태

이전 실패는 `GET api.github.com/repos/Horororong/quant-marcap-runner`,
`GH_BACKUP_TOKEN` Bearer 인증의 HTTP401 Unauthorized다. 이전 응답 본문은
저장되지 않아 만료·폐기·잘못된 값·주입 문제 중 어느 것인지 확정할 수 없다.
동일 GH_BACKUP_TOKEN 요청은 반복하지 않았다.

이미 설정된 다른 `gh` 인증은 repository GET와 release POST, 승인된 Git 게시에
성공했다. 그러나 정상 `gh release upload`의 `uploads.github.com` asset POST는
**HTTP401 Bad credentials**로 거절됐다. 그 전 generic asset POST의 실패 본문은
캡처되지 않았다. 이후 업로드 재요청은 중단했다. GitHub 연결 도구의 읽기 접근도
성공했지만, 현재 제공된 도구에는 release asset uploader가 없었다.

새 draft **421514386**은 생성됐지만 **asset 0개**다. 설명도
UPLOAD_PENDING_AUTHENTICATION/다운로드 미제공으로 갱신했다.
[이 draft](https://github.com/Horororong/quant-marcap-runner/releases/tag/untagged-03579765533e135a15a1)는
아직 백업 전달 링크가 아니다. 원격 다운로드/SHA 대조는 미실시다.
[진단](evidence/AUTH_DIAGNOSIS.json).

승인한 ZIP는 538,254바이트, SHA256
`464aa445c1c1d92a891bad9072973f34cc27bf2e92cbb13b8947f38c4a3a820e`로 불변이다.
41 payload + manifest 1 = ZIP 42 entry이고, 계획한 sidecar 3개를 합하면
release asset은 4개다. 41 payload는 store 객체35 + Git bundle2 + 복구 제어4다.
46개 논리 store 파일/비교3개/실행5개 재구성과 ZIP entry 수는 다르다.
공개 저장소이며 자료는 공개 공시·연구 증거·복구 자료다. 승인 manifest/CRC/
전체41해시/비밀값 0을 확인했으나 **v12 원격 보존 완료로 보고하지 않는다**.
원격 Git에 f8·7691·589가 게시됐어도 v12의 정확한 store 객체 다운로드를 대신하지 않는다.

사용자 조치: [GitHub fine-grained PAT](https://github.com/settings/personal-access-tokens)에서
해당 저장소만 선택, Contents 읽기·쓰기와 Metadata 읽기를 지정해 발급/재발급한다.
토큰값은 실행환경 비밀변수 **GH_BACKUP_TOKEN**에만 교체·저장·적용한다.
대상 도메인은 api.github.com/ uploads.github.com이다. GitHub 저장소 Actions
Secrets와 이 실행환경 secret은 별개다. 토큰을 채팅·로그에 보내지 않는다.
환경 편집 화면의 위치는 현재 도구에서 확인할 수 없었다.
사용자가 교체 완료를 확인한 뒤 아래 RESUME의 전용 명령으로 기존 draft에서
한 번 재개한다. 기존 v12 승인을 다시 요청하거나 새 draft를 만들지 않는다.

## 모집단 대조 — 다른 기준일을 감추지 않는다

전략 A는 2010-04-30 KOSPI/KOSDAQ·Marcap>0의 원래 1,946 security codes다.
거래량/종가 양수 1,853은 별도 조건이며, 이를 적용해 원래 모집단을 줄이지 않았다.
장부 B의 1,495는 유효 회사코드와 관측 first/last year가 2009와 겹치는 집합이다.
같은 여섯 자리 종목코드로 대조하면:

|집합|종목 수|
|---|---:|
|A 전략|1,946|
|B source gate 2009|1,495|
|교집합|1,490|
|전략에만 있음|456|
|장부에만 있음|5|

1946=1490+456,1495=1490+5가 동시에 성립한다. 중복 종목코드는 0이다.
단, B는 2010-04-30 snapshot이 아니다. 기존 map을 그 날짜의 관측 구간으로
한정하면 1,521종목/전략 교집합1,516/전략에만430/map에만5다.
기간 관측이 실제 연속 상장/당시 회사 연결을 인증하지 않는다. A에 대응하는
유효 회사코드 hint는 1,784개로, 종목 1,946개와 회사 수를 구분한다.

456개의 서로 배타적인 원인 분류:

|원인|종목|map method|
|---|---:|---|
|해당 신호가 map의 관측 구간 밖|268|current_stock_code|
|유효 회사코드 없음|124|unmatched|
|종목코드 행 자체 없음|38|없음|
|관측 시작이 2010년이어서 2009 장부 제외|26|stock_code|

268개의 current_stock_code 연결은 당시 회사의 동일성 증거가 아니다.
124개에는 우선주 표기가 있지만 이름만으로 전체를 분류·제외하지 않았다.
장부에만 있는 5개는 000030/003380/013310/013890/037030이며 해당 신호일 시세행이
없다. first/last 구간이 상폐·재상장 등 공백을 잇는지 공식 이력이 필요하다.
모든 목록과 원인은 [집합 증거](evidence/population/SUMMARY.json)에 있다.

필수 입력 7slot은 FY2009 equity/revenue/net_income/OCF 네 개와 Q3 2009
Jan1~Sep30 누적 revenue/net_income/OCF 세 개다. FY-Q3가 Q4이며 연간=Q4가 아니다.

|분모|후보 hint/필수slot|후보 존재율|의미 검토 연결slot/필수slot|연결률|
|---|---:|---:|---:|---:|
|장부1495|2337/10465|22.33%|160/10465|1.53%|
|원래 전략1946|2689/13622|19.74%|200/13622|1.47%|

160=914 후보 집합의 고유 의미검토 slot156 + 별도 기존 사조 canary4다.
후보 hint는 정확 원문·기간 인증이 아니며, 연결률은 7개 모두 준비된 종목 비율이
아니다. 모집단 전체 준비 종목은 여전히 0이다.

## 새 공통 변환 — 50회사 후보, PIT 승격은 0

단일 회사의 값 추가 대신 `reviewed_financial_batch_bridge.py`와 재현 CLI를
추가했다. 기존 914=891PASS+23UV 판단을 재사용하며 원문 재추출·재검토 PASS를
새 증가분으로 세지 않는다. 당시 종목/공개일은 catalog hint와 별도 attestation이다.

* 원본 archive/member SHA·좌표·회사·종목 hint·scope·정확 기간·단위·금액에
  기존 독립 검토를 바인딩한다. 월초 placeholder와 비교기/정의 불명 값을 거부한다.
* 의미 검토가 해당 연간/누적 기간을 증명한 IS cumulative 106행만 명시적 duration
  taxonomy로 변환한다. 원본과 변환 binding을 모두 보존하고 금액·기간은 바꾸지 않는다.
* FY/Q3 partition과 모든 receipt를 유지한다. 동일 receipt/field의 상이한 값은
  provider alias 우선순위로 하나를 고르지 않고 양쪽을 격리한다.
* 원본 PIT attestation은 변환 행에 자동 재바인딩하지 않는다. `select_asof`와
  canonical `report_snapshots`를 재사용하고, 운영 registry/완료 장부는 수정하지 않는다.

|실제 데이터 적용|결과|
|---|---:|
|기존 PASS에서 core4로 구조 연결한 행|218|
|회사/종목 hint·접수 각각|50|
|FY2009 candidate snapshot|55 scope-report 행|
|FY core4 모두 있는 scope-report|53그룹/50종목 hint|
|canonical provider 조회 금액 정확 일치|218/218|
|이 집합의 동일 receipt/field 값 충돌|0|
|엄격 source-ready/신규 엔진 허용 종목|0/0|
|신규 의미 검토/PIT 승격/전략·기간|0/0/0|

원래 전략 모집단과 겹치는 것은 49종목/196개 고유 fieldslot이다.
218행 모두 공개·정정 chain·당시 종목 연결·신호일 이용 가능성 attestation이
완결되지 않았다. 이는 종목별 증거가 아직 없는 독립 원인 4개이며, strict selector의
첫 거부 CHAIN_NOT_CLOSED_AT_SIGNAL만 기록해 나머지를 숨기지 않았다.
따라서 이 후보 CSV를 백테스트 입력으로 쓰거나 완료 장부를 채우지 않는다.
[행별 근거/차단](evidence/batch-final/SUMMARY.json),
[provider 실제 조회](evidence/batch-final/CANONICAL_PREVIEW_ROUNDTRIPS.json).

새 경계시험 **9 PASS**: 다른 회사 review 복사 거부, partial attestations 거부,
원본 보존, FY/Q3 분리, 월초 기간 추정 거부, index OK와 검토 구분,
변환 후 PIT 자동승계 거부, 상충값/입력순서로 임의 선택하지 않음을 확인했다.
실제218행 조회는 별도 증거다. 준비도/provider/parser/config/완료장부 5 owner의
SHA256은 정확히 불변이다. 합성시험은 실제 정정공시 두 버전 인증이 아니다.

## 실제 부족 근거와 다음 데이터 작업

보존된 원문/공식 list/viewer/시장 증거를 사용해 새 종목도 조사했다.
고려반도체089890 원문 `(주)고려반도체시스템`과 공식단축명, 제일창투026540
원문 `제일창업투자`와 공식단축명의 역사적 연결을 추정해 PASS로 바꾸지 않았다.
두 원문의 해당 XI member와 당시 공식 렌더링 연결도 미완결이다.
엠피씨050540은 4/1·4/30 정확한 이름/종목 연결 근거와 FY core4 원문 검토가
있으나 공개 member·정정 graph가 닫히지 않았다. 사조의 검증 재실행은 하지 않았다.

우선순위는 (1) 기존 자료에서 이 새 issuer들의 공개·version·identity 연결,
(2) 원래 모집단의 Q3 세 누적 operand와 456개 역사 식별 공백,
(3) 공식 원문을 찾아 53 충돌 adjudication이다. 기존 미확보 원문25접수의
충돌 금액 확정은 여전히 0/53이고, 이전 비달력 FY 분리4건을 해결로 세지 않는다.
다른 receipt의 최신값/평균으로 해결하지 않았다. 추가 원문 HTTP는 실행하지 않았다.

기존 자료로 부족한 엠피씨의 official bounded list/viewer/primary section 세 자료는
신규 소규모 수집 제안(최대4HTTP,600초,재시도포함)으로 명세만 남겼다.
기존 고정41 목록 밖이며 미승인·미실행이다. 이 자료로 FY4 신규 회사가 가능해질
수 있어도 Q3와 전체 모집단 부족을 해결하지는 않는다.
[정확한 공백](evidence/EXISTING_SOURCE_PROBES_AND_GAPS.json).

## 수집·보존·재개

이번 DART HTTP/신규 원문/후보/중복/체크포인트 이동은 모두 0이다. 10/23KST
실제 성공 run39863731314가 이미 하루 기회를 사용해 동일 gate/dispatch를 반복하지
않았다. 이전 실제2HTTP/2원문/34후보/0중복/정상21.709초와 checkpoint2063은 유지한다.
다음은20100331002066. 원래3실행 이력3/3과 별도41문서 예산0/2실행·0/82HTTP는
보존한다. 추가 잔여는21+20문서/2실행/82HTTP,실행당600초,재시도포함이다.
다음 허용 창은10/24KST,이어10/25,유한 만료는10/25KST23:59:59다.
그때 실제 live guard를 만족할 때만 진행하며 자동 실행은 설정하지 않았다.

새 로컬 개발은 `research/multi-provider-20261023`에서 보존하며 정확한 최종 SHA와
증분 manifest/bundle은 `/workspace/quant-multi-provider-20261023/FINAL_STATUS.md`에
기록한다. 공개 승인한589 이후의 새 코드/증거/guide는 v12 ZIP에 들어 있지 않으며,
그 승인에 임의 포함해 전송하지 않았다. 새 증분만 보존하고 기존 ZIP/kit/data를
재포장하지 않는다. 원격 자료만으로 전체 프로젝트 복원 시험은 여전히 미실시다.
