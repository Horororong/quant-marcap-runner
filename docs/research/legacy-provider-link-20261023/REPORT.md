# 실제2문서 재개·운영 추가예산 배포·legacy 연결 —2026-10-23KST

RESEARCH_ONLY. 원문확보/추출/숫자/의미/완전성/PIT/엔진입력을분리한다. 이전날짜의게이트검사는당시정상기록이며오류로재조사하지않았다. 29b완료UI/130동일상태CI/751전체해시/복원·대용량백업을반복하지않았다.

## 1. 실제 수집 증가와 예산

2026-10-23KST07:16:26의실제main7912455f138abf3d1ce9762f8de6a67c70e5b835/config/state검사에서gateOPEN,원래2/3사용/1잔여,승인sourceowner6SHA모두일치. parent39504052321선택/순서/중복/체크포인트/워크플로동시실행을확인한후기존mainworkflow를1회dispatch했다.

[실제run39863731314](https://github.com/Horororong/quant-marcap-runner/actions/runs/39863731314)SUCCESS,코드7912455f...,결과56514a4631fc5d677af732e90b382fb5937504c6. 원문2/34후보/실제DART HTTP2(문서당1)/재시도0/접수중복0/후보identity중복0/두ZIP SHA·CRC·memberbindingPASS. sourcebatch21.709초정상종료,체크포인트20100331002054→20100331002063,41pending. 기존HOLD_FAILURE의원인과oldrun이력은보존하고새실제상태는PAUSED_QUEUE다. 원문pack은동일저장소의data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39863731314/sources00.json.gz.b64및manifest에보존돼로컬전용자료가아니다.

직접artifact파일전달은작업공간네트워크에서차단됐다. 반복수집대신GitHub고정kit감사[39864835870](https://github.com/Horororong/quant-marcap-runner/actions/runs/39864835870)가원래artifact12462438642를SHA256792ebb5767cd93bae59dad33c3e1a69145d201e3b25897ac478f15b7cea01263/CRC로검증하고실제workerprogress를집계했다. 무수집success를성공으로세지않는다.

|항목|이번사용|누적·잔여|
|---|---|---|
|원래3실행|1실행|3/3사용,0잔여;기존기록보존|
|2문서4HTTP/600초|2문서/2HTTP/21.709초|시험종료;미사용2HTTP를다른목적에재사용하지않음|
|추가41/2실행/82HTTP|0/0/0|41문서·2실행·82HTTP잔여,선행조건실제통과|
|유한원문|+2|기존157→159,새2는두이전집합과중복0|
|후속57집합의운영후보|+34|871→905,수리제안9별도,제안총914|

## 2. 최소 운영 변경을 실제 반영

운영전용브랜치fix/supplemental-41-20261023의7f77d83bbe956c15b84172c51c8c10cdee7e75b6이[PR47](https://github.com/Horororong/quant-marcap-runner/pull/47)로main에병합됐다. 병합18f5d064bc2e5f3a106a2a03603be3d5b5bbbf0a. 연구UI브랜치전체를병합하지않았다. 8개운영파일만변경됐고main의원래상태/3실행이력과기존config/expiry는병합전후정확히같은byte임을확인했다.

[최종고정kitCI39865916930](https://github.com/Horororong/quant-marcap-runner/actions/runs/39865916930)SUCCESS,실제checkout7f77d83전체SHA,driverf36309c6ce7234ed987479d6740db09dc391b22d(파일SHA256a25c81f1ca2dd31a266e1370b8378ba90044acf53264be0db31c357818107ac1). 17새예산/리스시험+66기존수집·실제SIGKILL·재개회귀=83PASS,원래실제2문서artifact조건재검증,6sourceowner고정hashPASS. 인터넷pip설치0. 기존범용워크플로의불필요한인터넷설치를피하고동일관련수집시험을고정kit으로실행했다. PRmergeable_stateclean/headSHA와CI성공을확인하고expected_head_sha로병합했다. 보호규칙조회API403은조회불가로기록했고,관리자우회나force병합은하지않았다.

추가승인finite41-20261023은별도config/별도status장부,41고정접수순서SHA7bfafadb83322a9c7e2d358fd3c0f9331784b7597770c133ed83fb3e78283904에묶인다. max21+20/2리스/82최악요청예약(재시도포함2/문서)/600초/하루1회가원래장부와함께적용된다. 원래3회는리셋하지않는다. 미완료/강제종료리스는RUNNING/HOLD에남아자동재시도하지못한다. 후속승인은별도유한창2026-10-25KST23:59:59까지이며원래승인의만료일을고치지않았다. 이새창은현재승인된두추가일일실행을집행하기위한별도예산의기한이며무제한/rolling연장이아니다.

07:39KST배포후신규gate는ONCE_PER_KST_DAY. 오늘실제시험이기회를사용했으므로후속HTTP추가0. 다음창10/24KST00:00,두번째는10/25일일창에서모든실시간조건이충족돼야한다. **미래자동실행을설정하지않았고자동재개를약속하지않는다.** 동일예산재승인불필요. 실제오류가나면원인/상태를보존하고중단한다.

## 3. 18,473개legacy행의 실제 범위

|항목|Q3|FY|
|---|---:|---:|
|행|13,271|5,202|
|고유corp/종목힌트쌍|650|281|
|고유접수|683|288|
|필드종류|22|22|
|필드·범위·statement identity|12,613|5,077|
|동일원천·버전중복행|0|0|
|다중행필드identity|626|105|
|서로다른값을가진identity|44|9|
|같은접수/범위에core4필드가존재하는종목힌트|607|262|
|canonical엔진적격종목|0|0|

행을종목수나사용가능값으로세지않았다. oldsource_qualityPASS18,473은v5자동판정이지현행독립의미/PIT완료가아니다. 서로다른44+9는정정/중복·기간차이등을대조할대상이지자동오류/FAIL확정이아니다. 소스·버전별로분리하고최신값을임의선택하지않았다. 원래canonical2009장부0행/shard0,0/1495완료기준을갱신할근거가없어장부를그대로두었다.

미연결사유를분리했다:①metric/amountschema와canonicalaccountrows차이,②현재종목/회사힌트대신당시연결필요,③12/01·09/01등period_end는보고월힌트이고정확한기간말일이아님(비12월결산/이전기간도섞임),④source단위와이미정규화된KRW중복곱셈금지,⑤문서SHA만있고member/원본문버전연결부족,⑥v5confidence와source_quality를의미PASS로쓸수없음,⑦공개·정정·사용가능일·법인연결PIT미완료. 동일schema로로드되는것과의미가동일한재무데이터는별개다.

## 4. 공통provider 연결과 실제 차단

새legacy_reviewed_provider_bridge는독립attestation→기존financial_record_readiness.select_asof→명시적accountrow변환→기존DARTreport_snapshots/latest_snapshot순서다. 계정명을소스확인된기존alias로연결하고IFRSID를조작하지않는다. Jan~Sep누적은thstrm_add_amount,연간합계는current,실제3개월값은current로구분해FY−Q3를잘못계산하지않는다. 단위는이미KRW로확인된amount를다시곱하지않는다. month-firstperiod/잘못된ID/미검증최신값은채우지않는다.

기존attested사조FY3필드가한표준providerframe3행/1회사로조회됐지만**기존검증을새PIT증가로세지않았다**. 해당사조FY접수는oldv5묶음에행0이고새canary원문에서온것이다. old18,473행에서새엔진허용0,전체1495중실제전략적격0이다. source-ready조회와전략모집단준비도를분리했다. bridge7경계시험PASS. 기존canonicalprovider/coverage/금융상태장부/UI코드를바꾸지않았다.

구체대상은기존KOSPI/KOSDAQ book_to_price순위전략의2010-04-30신호다. 원래provider계약은2009Q3/FY와equity_FY,같은범위revenue·net_income·ocf의FY−Q3누적을요구한다. 보수적예상1495전체의소스완료·기간·의미·PIT·종목연결/거래일/기업행위조건을충족해야한다. 확보하기쉬운1~2종목을원래모집단으로바꾸지않았다. [1495종목요건표](evidence/VALUE_STRATEGY_1495_REQUIREMENTS.csv)에raw힌트범위/필드부족/차단을모두남겼다. 이표는원자료힌트조사지원이지사후생존종목선정목록이아니다.

## 5. 신규 두회사·34값의 독립 검토

원본ZIP/member SHA·당기셀·header기간·OFS/단위·부호를productionparser와별도Grid/Decimal로대조했다. 34숫자·부호·단위PASS/34명명된원문필드의미PASS,전체공시추출완전성과PIT는UNVERIFIED다. amortization/depreciation은IS비용,CF무형자산취득은원문부호의취득액,유동성장기부채는명명된aggregate라는출처문맥을보존해임의로ratio/CFaddback과동일하다고하지않는다. old880판정은변경0;제안914=891PASS+23기존UV/미검토0,운영905/수리제안9별도다. 앞선100문서의1,363후보는이914집계와별도다.

원문기업00302078/엠피씨→050540의공식KRX4/1·4/30명칭은정확히같다.00501970/미주레일주식회사→078940은4/1미주레일과일치하지만4/30KRX명칭이일경산업개발이다. 이변화를숨기거나이름정규화를느슨하게하지않고4/30연결을UNVERIFIED_NAME_CHANGE_LINK_REQUIRED로남겼다. 두회사모두원본문member공개/정정graph가미완료여서8corefieldprovider질의는입력0/명시적차단을반환한다. 신규PIT0/신규전체전략0이다.

사조Q3접수20091116000562는현재41대상밖에그대로둔다. 다음최소확보안은**기존원문byte를먼저찾고없을때단일ZIP1문서/최대2HTTP/재시도포함**이며별도요청범위로만제안한다(미실행/승인추정안함). 이는사조단일FY→Q4차분을검증할자료부족한항목의직접원인이지만1495전체순위차단을풀지는못한다. 공개/정정viewer·공식목록이부족하면추가근거요청을별도로정의해야하고ZIP하나로PIT완료를보장하지않는다.

## 6. 복구자료/한계

f8/v9/v10/v11을한번에복원할준비묶음을만든다. 원격29b코드·kit·751자료는재포장하지않고f8의로컬증분Git객체만재사용한다. v9와v10중정확한비교재열기에필요한3비교/5성공run/46논리파일만선택하고동일content를dedup한다. 원격Git/JSON으로정확히복원되는파일을SHA256으로확인해제외한다. 대형reportHTML5개는보존chat_manifest의dashboard_payload+원격29b의동일renderer+원래kitPlotly로동일hash재생성이가능함을확인해전송하지않는다. 이는브라우저/엔진/성과재계산반복이아닌복구용직렬화검증이다.

추가원격CI색인게시시도는자동승인검토가승인운영범위밖이라고거절해명령자체가실행되지않았다. 우회재시도없이로컬복원·publicGit내용주소·JSON부분객체·canonicalrenderer로대체했다. 가능한CIartifact의나머지내용일치까지새로인증했다고하지않는다. 새전송범위/SHA/비밀값검사와승인질문은준비묶음manifest를따르며,이번미명세자료는아직외부전송하지않았다. v9/v10/v11ZIP자체의원본byte복제나원격만의전체프로젝트복원시험완료를주장하지않는다.

현재새연구코드·34검토·원격운영결과·인계는별도로컬연구커밋/추가bundle로보존한다. 승인된운영8파일과해당원문2건은이미원격main에있어다시보내지않는다.
