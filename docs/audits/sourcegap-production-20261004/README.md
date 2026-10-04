# PR33 운영 반영·실제 배치·독립 감사 — 2026-10-04

## 실제 확인한 시작 상태
main778b02b9, PR33초안0bd49086(처음에는 이전 감사 branch를 base로 함), active/queued0. 접수번호 고유 mapped115020 /index행138540, 처리13401, 대기101619. 초기4F1523/partial1341/NO_METRICS8943/API014→NO_DOCUMENT1594/SOURCE_GAP0. 원문 raw-state와indexGitblob을 직접 일치 확인했다. 이전 환경 프로세스/파일은 확인 불가. 기존2000건/78개 감사는 반복하지 않았다. 시작 상세 `start.json`.

## 병합·검증·운영 경로
PR33 최종18857483의 nativeCI37204637739/fullCI37204637742 통과 후 main6e2ee6c에 실제 병합했다. 7개 sourceSHA별 차단을 기록해 원본값/체크포인트를 보존했다. SOURCE_GAP은 처리 결과일 뿐 추출 성공이나 준비 완료가 아니다. 정상 부분추출은 source구조PASS이면 계속 허용한다. 모든 gap은 분모에 남고collection_complete/quality_complete=false.

첫 실제100건 run37210246868/code6e2ee6c/data86de66b는100 SOURCE_GAP/새값0이었다. CP949의 UTF8 잘못된 선언과 bare HTMLamp를 정상자료까지 차단하는 v1 결함을 실제로 확인하여 대규모 실행을 보류했다. PR34가 byte-round-trip strict CP949/EUC-KR 복구와 구조검사용 amp escaping만 허용한다. 원문/금융 parser값 정의는 바꾸지 않았다. v2 sourcec5231009의 nativeCI37212563763/fullCI37212563755 모두 통과, 실제main967dae08 병합. 12개 기존 parsed 원문 대조에서10정상 유지,2 실제불완전 원문 차단;5정상/손상CP949 fixture와21pytest, standalone 회귀 검증을 통과했다. 고정 kit33개 코드/계약 hash변경0, registry/wheel/provider/engine 우회0.

v2 실제100건 재처리 run37214492414/job111472131773/code967dae08/dataed5232c7는 이전100개와 접수번호·ZIP SHA100/100동일. 20 PARSED_4F/11PARTIAL/11NO_METRICS/58SOURCE_GAP/오류0;581새 후보 항목/31공시. 중복0, sourcegap값 게시0, checkpoint25단위. source잘못 차단된100개만 유한 재처리했고 중복처리 분모 증가는 없다. qledger42행에서v2추가관측11행으로53행, revision별active/inactive이며 raw기록 삭제0. v1잘못된metadata100/3가20/4로 기록됐던 이력도 보존하고v2부터 actualenv가100/3임을 확인했다.

소규모 실제 gate 통과 후 PR35 71aee8cd nativeCI37213118229/fullCI37213118208 통과, mainf81ca8db 병합의 `[legacy-verified-batch-2000]` 기존 fast job marker로 신규2000건을 실행했다. 새 workflow/schedule를 만들지 않았다. actualrun37215324227/job111474535668/codef81ca8db/data bce2d91b 완료: selected/completed/requests2000, BATCH_COMPLETE, modern0, rate-limit0, 오류0. source=`opendart-document-v1`, parser=`legacy-v5-single-amount`, diagnostic=`legacy-document-quality-v2`. 2500요청/3300초/요청timeout90초·최대4시도/0.5초간격/3workers/checkpoint25의 기존 유한 한도. 88 PARSED_4F/48PARTIAL/31NO_METRICS/1830SOURCE_GAP/3API014. 새 후보2476항목/136공시;duplicate0/sourcegap게시 overlap0. 소규모와 합계3057후보/167공시이며 투자용 유효복구 수0. CI와 실제수집/게시/숫자/PIT 검증은 구분한다.

## 전후 집계
고유 mapped접수번호115020, 현재parser/source호환+과거transportAPI014, durableprocessed는 parsed게시rowcount/SHA/수집상태+gapoverlay를 확인한다. pending=115020−durableprocessed;SOURCE_GAP도 처리결과에 포함되지만 성공값·준비 완료에는 포함되지 않는다. 전 기간 compatibleNO_DOCUMENT는 unmapped2개를 포함하므로 다음 표에서는mapped만 쓴다.

|시점|처리|대기|4F|부분추출|NO_METRICS|NO_DOCUMENT|SOURCE_GAP|오류|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|시작778b02b|13401|101619|1523|1341|8943|1594|0|0|
|v2 신규2000 직전ed5232c|15476|99544|2380|2168|9232|1607|89|0|
|v2 신규2000 직후bce2d91b|17476|97544|2468|2216|9263|1610|1919|0|

중간 기존예약 old-main run37205264164는1975건/DEADLINE/modern0/data c767fb6를 독립적으로 처리했다. user의 이전2000건 반복이나 수정본 검증으로 합산하지 않았다. 이를main merge가보존했고, 추가v1신규100건+v2동일100건재처리+신규2000이 분모 차이를 설명한다.

## 신규 숫자 독립 감사 — 전체 통과 아님
값 보기 전에 Git8f16bf38/NEW_NUMERIC_SELECTION.md로 고정한 회계연도/기간/연결·별도/기업 교차12공시 plan, 공시마다metric/scope lexical round-robin30항목. 저장 parser로 다시계산하여oracle를 만들지 않았다. 원본ZIP/memberSHA, 원본literal TR byte범위, 당기/전기header, 실제단위·기간·연결heading을 독립적으로 읽어 수동expectation을 기록했다.

신규2000 cohort 12기업30항목: source의선택된숫자/단위변환28일치,1양수괄호부호 불일치,1원문단위 공백으로KRW적절히 미게시. 당기 기간/연결/열/부호까지 고려하면13개확인된 오류+2개미확정,15개구성요소일치하나fiscal/PIT미검증. 원인별기간9/연결2/과거열3/QX미확정3/단위부재1/부호1(중복). 부호증거는유니슨20021206000173 원문매출세부합계와매출총이익·원가관계가 양수 소계괄호임을 보여준다. 모든괄호를양수로 바꾸거나 기존Δ/손실 음수정의를 바꾸면 안 된다.

추가pilot소규모30항목/10기업도 별도감사했다: literal변환30일치하지만 당기구성요소14문제(기간8/연결3/과거열2/원문날짜상충2, 중복),16구성요소만일치. 이전78숫자를 신규감사에 재산입하지 않았다. 총60신규항목이지PIT/전체 인증이 아니다.

같은 실제원문/table/header/cell원인 범위만 확장하여소규모54후보/8공시,신규2000에서는66후보/9공시를 영향표에 남겼다. 미검토 신규공시는 각각21/124개. 전체3057/과거운영자료로 일반화하지 않았다. collector의PARSED와source_qualityPASS는 기술구조 상태로 보존하며 재무문제를SOURCE_GAP으로 바꾸거나 자료를 삭제하지 않는다. 현재등록DartFactorProvider→DartValueFactorAdapter는modern full_history만 읽고nativelegacy/staging를 전략입력으로 받지 않는다. 영향자료를포함한legacy전체의 실제전략입력차단은기존provider 경계이며새ledger가collector를필터링하는것은아니다. 검증되지않은legacy capability를공개하지 않는다.

## 과거 운영자료 영향·공백
첫7개SHA hold의29과거v2/v4 candidate와 두실제원문손상공시20000330000124/20000814000240의 currentv5 32행+과거v4 38행을 식별, 총99행원기록 보존. currentv5문제32행은source quarantine에서현재유효집계/입력대상으로 배제되며 과거99행을삭제·덮어쓰지 않았다. falsehold20020330000187는v2revision에서해제;21v1+21v2historical ledger에서20active,후속11active추가. 신규sourcegap는rawstate에서 차단한다. status/version/rowcount정합은원checkpoint+overlay 및actualmainblob으로검증했다.

기존5개외 NO_METRICS를 사전고정한두12표본의 중복1을빼23공시 직접대조: 구조계약공백12/대체문자+구조8/대체문자2/정상CP949 재무TE값존재 parser지원공백1. 실제항목부재는표본으로입증못했다. XMLinvalid전체를재무내용절단으로 단정하지 않는다(중복DOCUMENT wrapper예별도). 신규1830SOURCE_GAP는자동diagnostic집계이고그중최초lexical5공시는ZIP CRC정상이나member가문장/표중간에서끝나BODY/DOCUMENT닫힘없는 실제절단을별도확인. 나머지1825에이원인을일괄적용하지않는다. 신규31NO_METRICS는인정원문에서현재parser항목인식0이며실제금융항목부재인증아니다. API0143건은공식endpoint nofile,공개공시없음의증거는아니다.

기존공식document.xml 재다운로드는지원되며old24표본의SHA모두기존checkpoint와같았다. 손상원문반복다운로드로복구되지않았다. 현재provider계약에publicviewer값의운영승격경로없고 기존viewer는guarded offline staging만지원한다. 임의복붙·보간·대체0. 원자료79MB전체는GitHub artifact90일(로컬authorizeddownload32MiB상한으로전체검사불가); 실제감사한bounded subset 원문은primary/ZIP으로Git에동결했다. 각각SHA명시,원본파일유효범위와한계를구분한다.

## PIT 및 실행 준비
20개 공개viewer body에표시된공시family/date와5정정family를확보했고4개공개뷰어는TLS/timeout. 원문2개정정표를보존했다(20000814000485 BSdate변경2000-01-30→2000-06-30 등). 20010330001533 실제공개viewer날짜2001-03-31은index2001-03-30과다르다. 접수번호prefix를공개일로대체하지않았다. 공개시각/completeoriginal-correction값chain/과거버전financial내용/전략당시사용값은미확보. 정정후값을정정전투자시점에쓸수있는증거없음. 기존78staging숫자운영승격0/완전PIT0,신규60항목PIT0. 임의공시시차0. 실행가능일은현재provider·next-close계약의 실제available정보가충족된후판단한다.

현재작업batch완료,최종관측active/queued0,이전외부환경확인불가. 기존daily15:30UTC/October07:30·23:30UTCschedule와sharedsuper-value-fast-pit-backfill lock/cancel-in-progress=false유지,동일목적예약추가0. 다음작업한가지: 확인된당기기간/열·연결·양수소계괄호사례를회귀fixture로nativefinancialparser guard를수정하고정확한영향자료만버전재처리한다. legacy투자capability활성화는독립숫자·PIT검증이후. 비용/OOS/강건성/운용가능성/실제전략검증모두미수행. 성과재계산/UI확대0.

## 증거·재현
`live-small-v1.json`, `live-small-v2.json`, `live-large-v2.json`, 각runlog/plan/report/summary/checkpoint identity; `new-{small,large}-v2-primary-audit.csv` 및手入力expectations JSON; financial-impact/affected-candidates; `old-no-metrics-primary-unique23.json`; `pit-*`; `kit-boundary.json`; `RESUME.md`. main수집code967/f81와data bce를따로기록한다. 문서PR은기술code/data를재수정하지않으며최종CI/병합상태는liveGitHub에서확인한다.
