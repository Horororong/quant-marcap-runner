# Legacy 원인별 준비도·53충돌·신규 OCF 연결 — 2026-10-23KST

RESEARCH_ONLY. 금융게시HOLD·투자PIT0/6·기존 source coverage/CFS-first/OFSfallback/기업행위/held-return/no-lookahead 계약 유지. 원본·최소/전체복원·기존 결과·v1~v12 ZIP는 바꾸지 않았다. 이번에는 원문 재수집0, 완료29b UI/브라우저/130회귀/대용량 해시/동일CI 재실행0이다.

## 1. v12 승인과 실제 업로드 차단

사용자가 정확한 v12 공개 전송을 승인했다. ZIP538254bytes/SHA256464aa445c1c1d92a891bad9072973f34cc27bf2e92cbb13b8947f38c4a3a820e와 승인 manifest cbc409b6f6ac580abda6df62619d16f15668d23a09acbeffec450d085b54a80c를 유지했다. ZIP CRC·42entry·41payload 각각의 길이/SHA와 bundle에 들어간 두 증분의 실제 Git 소스 blob을 새로 비밀값 검사해0건이다. 현재 환경의 GH_BACKUP_TOKEN은 설정상ready지만 **실제 GitHub 저장소GET가401 Unauthorized**로 거절됐다. release 생성 전 중단,생성0/업로드0/원격다운로드검증미실시. 같은 인증 재시도0,CI색인우회0. 환경 비밀값 교체가 필요한 항목이다. 토큰은 채팅·Git·로그에 넣지 않는다. [차단증거](evidence/V12_DELIVERY_BLOCKED.json).

파일 수:41payload=35content-addressedstore objects+2Gitbundle+4복구제어파일. ZIP 안에는별도TRANSFER_MANIFEST.json1개가더있어42entry다. 이42파일이35고유store객체/공개Git·JSON3/정확히재생성되는HTML5/중복참조를통해46논리store파일,3저장비교/5성공run을복구한다. 원래v9의17/v10의78은원본backupstore파일수이며,그전체를중복복제한수가아니다. 계획한releaseasset은ZIP1+manifest/VERIFICATION/SHA256SUMS sidecar3=4개다. 검증자료는ZIP체크섬을바꾸지않는다.

v12의 f8-code-delta.bundle은public29b→f8의22파일256702byte연구증분, research-legacy-bridge-delta.bundle은f8→7691의22파일706756byte증분이다. public29b기본객체/고정kit/기존데이터가필요하며,두bundle로7691의정확한코드·증거tree를복구한다. 저장소연구branch에7691을push한것이나그SHA원격CI통과는아니다. 둘다미실시다. shallow/promisor원본으로새bare기본history이전은미완료이며,원격만의전체프로젝트복원시험도미실시다.

## 2. 수집과 예산

시작시각10/23KST13:14. 오늘실제run39863731314가이미기회를썼으므로현재gate를반복조회하거나dispatch하지않았다. 이번DARTHTTP0/원문0/후보0. 누적최근실제증가분은이전시험2HTTP/2원문/34후보/중복0/체크포인트20100331002063이다. 이전날짜검사를오류로재조사하지않았다.

추가승인finite41-20261023잔여41문서(고정순서21+20)/2실행/82HTTP including retries/실행600초. 사용0. 원래3실행이력3/3은보존한다. 다음대상20100331002066,다음허용창10/24KST00:00이후,두번째10/25일일창,추가승인유한만료10/25KST23:59:59. 매번그때의live조건을확인해야한다. 원격main18f5d064bc2e5f3a106a2a03603be3d5b5bbbf0a/PR47/고정kit83PASS증거는변경없어재실행하지않았다. 동일예산재승인불필요. 추가자동실행설정없음.

## 3. 0/1495의 겹치는 원인

기존source완료gate는2009Q3/FY의1495codes, CFS OK 또는CFS NO_DATA후OFS OK/NO_DATA와해당rawshard일관성을요구한다. raw_ok=True지만완료0은완료증거가아니다. 필요한필드입력은FY equity/revenue/net_income/ocf4개와Q3Jan~Sep누적revenue/net_income/ocf3개,종목당7slot이다. FY−Q3가Q4이며,연간값을Q4라고부르지않는다. Q3equity는이계산의필수operand가아니지만전체원천장부계약은그대로다.

|원인(중복포함)|종목수|해석|
|---|---:|---|
|필드또는정확회계기간부족|1495|1315는7개후보hint중일부누락;180은hint가있지만정확원문기간/당기·누적미입증|
|원문member·원본문버전연결미완료|1495|필요한Q3/FY전체chain완료0;문서SHA나원문일부확보만으로충족하지않음|
|당시회사·종목연결미완료|1494|사조1개특정신호연결은기존증거;나머지힌트는인증아님|
|필요7필드의의미검증미완료|1495|914집합기존891PASS는원문행수,7operand전체준비0|
|공개시점·정정/PIT미완료|1495|개별canary준비도와전체종목의7slot완료는별개|
|canonical완료장부·바인딩미충족|1495|변환코드4개alias는구현;증거없는장부를채우면안됨.코드오류만고치면완료되는종목0|

겹친원인소속8969건,고유차단1495종목이다. 행별근거는[1495원인matrix](evidence/CAUSE_MATRIX_1495.csv). 기존v5후보hint2337/10465=22.33%,전기간공통scope/접수pairhint178종목이다. 정확기간확정으로세지않았다. 의미검토slot은914집합156+별도기존canary3/신규OCF1=160/10465=1.53%;종목전체검증완료율0이다. rawhint와독립원문검증을같은확보율로부르지않는다.

### 실제 전략 모집단과 장부의 차이

계획한원래KOSPI/KOSDAQ+Marcap>0입력은2010-04-30의1946종목이고거래량/종가양수는1853종목이다. require_tradable_on_signal=False원래계약을변경하지않았다.1495source-map과교집합1490/장부밖456/장부에만5다. **1495만채웠다고원래1946의전체모집단순위조건을충족한것이아니다.** [원래1946](evidence/ORIGINAL_SIGNAL_UNIVERSE_1946.csv),[차이456](evidence/SOURCE_MAP_GAP_456.csv). 이456중103종목에도v5후보2356행이있다. 단순원자료부재가아니라식별/기간/검증/장부연결도해결해야한다. 우선주·정지·상장시점등을공식근거로구분하기전임의종목유형을추정하거나제외하지않았다.

## 4. 53충돌의 실제 판정

53그룹/107행/12회사/25접수의두값과원문SHA·보고명·공시일·연결별도·단위·소스좌표를모두보존했다. 같은원천/버전을최신값이나평균으로합치지않는보존키를만들었다. 모든그룹은색인정정표시가있지만실제정정원문graph인증은없다. 접근가능한원문파일/보존sourcecohort색인에서해당25의nativeZIP을찾지못했다. 현재원문근거로금액확정0/53,정의완전해소0/53,엔진허용순증가0이다.

|겹치는원인후보|그룹|
|---|---:|
|원·천원등source단위표현차이|31|
|정확한1000배scale signature|20|
|부호/항목정의차이|5|
|표시정밀도차이범위안이지만동일하지않음|4|
|당기·비교기/정정/정의미해결값차이|24|
|원래FY목표와다른보고월hint|4|

4그룹은케이비물산008540의2009.01사업보고서여서calendar2009.12FY목표에서분리했고49그룹이이목표에관련된다. **이분리는4개금융충돌해결이아니다.** 53개모두미확정상태를유지한다. 연결/별도와statement는원래키에이미포함돼차이그룹을섞지않는다. 당기/비교기와누적/단독분기·정확기간은v5에원문header가없어UNVERIFIED다. 단위차이를다른경제적개념키로바꿔금액충돌을숨기지않았다. [107대안과판정](evidence/CONFLICT53_DECISIONS.json),[필요25원문](evidence/REQUIRED_EXISTING_SOURCE_RECOVERY_25.csv).

우선복구대상은파워로직스047310 Q3원문20091113001332·정정색인20091116000083이다.18그룹의각raw숫자는같고단위적용으로1000배가된다. 실제원문의unit/currentheader를확보해야어느쪽을채택할지알수있다. 먼저이두원문의기존원격/PC캐시출처를찾고없을때만**별도2ZIP/최대4HTTP(재시도포함)** 소규모수집을제안한다. 현재41scope밖이고미실행/미승인이다. 이18이풀려도단일회사Q3의검토진척이며전체시장전략완료가아니다. 사조Q320091116000562도기존scope밖에유지했다.

## 5. 실제 신규provider 연결1값

기존canonicalaccountrowbridge는durationflow만받아원문의CF cumulative표시를명시적으로처리하지못했다. 검증된OCF에한해Jan1부터정확FY/Q3말일까지의**cumulative**를canonical thstrm_add_amount로연결했다. 일반IS cumulative는계속거부하고,실제Jul~Sep단독CF를기존Q3CF의YTDfallback열에넣는것도거부한다. financial_record_readiness/select_asof와공식dart_value_factor_adapter/report_snapshots/latest_snapshot소유자는바꾸지않았다. sourceparser/hash/config/완료장부도불변이다.

신규대상은사조007160/corp00124799/원문20100331001582의OFS2009Jan1-Dec31영업현금흐름15922637039원이다. 원본ZIP/member SHA와원본문table174,row1,col1,보존공식XI본문table9,row1,col1,원시TR1633을독립대조했다. 제39기당기/제38·37기비교열·원/OFS를확인하고상위항목34326086558+14580298231−28544031412−4439716338=15922637039도정확히같다. 중첩항목을두번합치거나CFS첨부를섞지않았다.

별도필드정확성근거를추가하고이미증명한동일원본문공개·bounded버전관계·각신호일당시종목연결을바인딩했다. 실제provider에서4/1·4/30에OCF cumulative15922637039조회PASS,공개전/3월31일당일·닫힌범위밖5월3일·원문금액변조차단PASS. 기존3source행과provider금융값은정확히불변이다. 기존3+신규1의FYcore4필드가동일providerframe에서조회된다. [실제경계증거](evidence/OCF_CASE.json),[4필드표](evidence/CANONICAL_FY4_SNAPSHOT.csv).

증가1uniquefield/0newstock/0newperiod/2field×signalpairs다. 이는914집합밖의별도canary기존자료이며914PIT승격0,운영값변경0,투자PIT0/6이다. 정확공개시각은미확인이라공개당일을배제하고입증된다음거래일종가부터읽는다. 실제정정공시두버전인증/전공시추출완전성/연간CF를Q4로변환하는권한은없다.

## 6. 우선할 실제 재무 전략과 남은 범위

원래super_value_dart_dsl의동일4factor EP/BP/CFP/SP 평균percentile 상위20·동일비중·4/10월말·다음session종가를선택했다. 이번계획기간2010-04-01..09-30은4월30일신호와이후보유를검토할범위다. 전체원래유니버스를유지하며단일종목성과로대신하지않는다. [DSL](evidence/STRATEGY_REQUIREMENTS_DSL.json)과[compile계획](evidence/EXECUTION_PLAN.json)은구조검증만PASS,실제백테스트미실행이다.

필수data는정확FY2009equity와세연간flow/같은scope의Q3Jan~Sep누적3flow,각신호전공개및정정chain·종목관계/원래전체가격·Marcap·거래일·다음실제체결가능일·보유기간원시수익률/기업행위/비용이다. gross0과assumed_net(commission2/selltax30/spread5/slippage5bps)은명시적연구가정이며실제과거거래비용인증이아니다. 다음날거래량과전체보유기간CA/held-return·표준CURRENT보고기간은아직수집·검증을끝냈다고하지않는다.

먼저178개raw同scope pair의원문기간/단위·fieldbinding과53충돌관련근거를복구하고,새159원문중미검토first100및914집합의원천메타를연결한다. Q3독립의미/PIT공백이현재가장큰막힘이다. 사조는FY4가준비돼같은OFS Q3세누적operand가남았으나한회사control이지1495/1946순위를허용하지않는다. 신규실행가능전체전략·기간0을유지한다.

## 7. 검증·보존·재개

고정kitverifyPASS. 신규충돌경계6PASS,수정bridge10PASS,실제OCF원문/provider/전후세값경계PASS. 최초검증script의packhash전사오타와CF/IS에중복된당기순이익TR의전역unique가정오류는원인확인후고쳤다. 원문hash/금액/허용오차를통과시키려고바꾸지않았다. 실패폴더·로그는원래P경로에보존한다. 이번commit의원격CI와연구branch게시미실시;기존83CI를이번연구코드의CI로인용하지않는다.

새코드·evidence는별도research/legacy-resolution-20261023로컬커밋/증분bundle/manifest에보존한다. 현재v12에새증분을끼워넣지않고원래SHA를유지한다. 추가공개전송은이번v12승인밖이다. 정확한새SHA/파일수/크기/비밀값검사는/workspace/quant-legacy-resolution-20261023/FINAL_STATUS.md와새TRANSFER_MANIFEST.json을따른다.
