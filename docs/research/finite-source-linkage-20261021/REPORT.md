# 승인29b 배포와 유한 데이터 연결 진척 / 2026-10-21

RESEARCH_ONLY. 금융 게시HOLD/PIT0/6/source-only backtest_eligible=False, 전체 모집단 재무 순위 차단을 유지한다. 복원·751전체해시·기존 대용량 전송을 반복하지 않았다. 승인29b 공개/CI와 이후의 새로운 로컬 원문 검토를 분리한다.

## 1. 승인 코드와 정확한 원격 검증

|항목|결과|
|---|---|
|실제 코드 SHA|29b6c4a2c277f6b2070e4bf70da54899f9fe4bcf|
|공개 브랜치|fix/native-source-boundaries-20261021;7c→9365→29b fast-forward;force/main병합 없음|
|증분|49파일713,061바이트;공개 적합성 검사/비밀값0/제외0/원격49SHA256일치|
|승인 manifest SHA256|54a30918d92ad0c585490017a73265849aad2fbbeda1ed9ebe3e860d2c4efae7|
|별도 driver 커밋|2997930ea4cfe67c04441648dd066bc1e50efca7;부모fe04aba1aa9bdd46a955fe2068fa044799e1842c|
|driver 파일|8,152바이트,49파일에 미포함;SHA256110c12a2bbed0ee9dc11fa001fe9fffc4a87fd985f5af5a087c0da8c2ecbb59f|
|integration CI|[39604804071](https://github.com/Horororong/quant-marcap-runner/actions/runs/39604804071) SUCCESS|
|PIT/기간 CI|[39604801251](https://github.com/Horororong/quant-marcap-runner/actions/runs/39604801251) SUCCESS|

두 실행의API head_sha는driver2997930이며 **실제 checkout은29b전체SHA**다. Actions원격로그/step결과/원격 파일 readback을 확인했다. 원래kitrestore/bootstrap/verify만 사용했으며 인터넷pip설치0이다. 130엄격파일PASS/9기존계약확장/12과거상세미검증의 구분을 그대로 유지한다. 선정·비중·체결·NAV·성과를 예외 처리로 숨기지 않았다. 기존12상세원본 미확보는 현재기준을 만들어 해결한 것으로 세지 않는다.

기간CI는56관련unit범위(6언어+6웹+6비교+38기간/readiness/source-query),checked DSL lifecycle,기존 실 브라우저/공통엔진/CURRENT/독립장부,비교저장·서버재시작,기존NAV하위기간과268세션새기간재실행·독립장부까지 통과했다. integration은130엄격비교,66수집/중단재개시험,9readiness시험과 실제preflight/event gate를 추가 확인했다. 두job의공통 E2E는 서로 다른 suite의필수 선행이며 같은run을이유없이재실행한 것이 아니다. CIartifact12348063178/12347513604는90일 보존 결과이며v10ZIP 업로드가 아니다. 이번 새로운 연간조회 helper는29b 뒤의 로컬 변경으로 원격CI범위에 포함되지 않는다.

## 2. 운영 main 변경과 실제 수집 상태

main은이전fd232d의자식08dfad14e1bb2e0d9cb9fdca5b8a6979ad79c1fa로진척됐다. `Refresh recent DART financials`는recent_batches02400~02699와rotation/status 두파일을갱신한 자동 수집진척이다(300companies/297,773records라는해당batch상태). 이를새legacy수집·새고유인증자료수로합산하지않고연구751snapshot에덮어쓰지않았다. legacyworkflow/coordinator/sourceowners/parser9.2는fd232d와동일하다. 연구9.3공개와운영배포를구분한다.

실제메인config/state와main함수로2026-10-21T22:02:18KST에검사한결과 ONCE_PER_KST_DAY. **내부 하루1실행 정책**이며DART외부quota응답이아니다. 마지막실제성공원문02054/KST07:05:20.561506,source run39504052321;오늘이미기회를사용했다. 이번새DART HTTP0/원문0/후보0/중복생성0/checkpoint20100331002054유지. 실패재시도도dispatch도보내지않았다. 외부DART잔여quota/현재key실동작은미검증이다. 기존workflow는DART_API_KEY secret참조와GitHub.contentswrite를사용하지만,이번차단상태에서원격키값을읽거나인증성공을추정하지않는다. 저장경로는기존main의data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/<newrun> 및고정batch/native/results/checkpoint이며 새run경로만사용한다.

|승인 예산|사용|잔여·조건|
|---|---|---|
|원래 최대3실행|기존2;이번0|1실행,2062/2063시험 전용|
|2문서 시험4HTTP/600초|0HTTP/0실행|미실행,재시도포함4상한|
|조건부추가41문서/2실행/82HTTP|0문서/0실행/0HTTP|사용자가승인한조건부예산;다시승인을묻지않음|
|문서예약300상한|기존200예약|추가41은부모기존예약을재사용,새예약0|

02054COMPLETE/02062DEFERRED/02063PENDING,pending43이다. 다음창10/22KST00:00이후모든livegate/hash/firstreview/인증/중복/저장경로/동시실행을확인해야한다. 문서당max2HTTP(재시도1),문서90초,worker75초,run600초,admission종료여유15초를유지한다. 정상종료·저장·무결성·추출·중복0·checkpoint·실패없음이실제로확인돼야추가예산을사용한다. future자동실행은설정하지않았다.

조건부예산승인은인계JSON에고정했다. **현재main은원래3실행을보호계약으로고정**하므로추가2실행을위해서는원래장부를보존하는별도supplemental승인/장부의최소운영배포가필요하다. config.max_runs만올리면LIMIT_CONTRACT_CHANGED이며그런우회는하지않았다. 이번main병합미승인과시험성공전조건을유지했다. 같은수집예산을다시승인받아야한다는뜻이아니다. 구체요건은SUPPLEMENTAL_DEPLOYMENT_REQUIREMENTS.md다.

## 3. 41문서의 부족분과 provider0/1495

고정41접수번호는이전제안의21+20목록과동일하며고유41/종목힌트41/제목2009.12사업보고서41이다. 기존v5의2009/2010정규화파일에는이41접수번호의행이0이다. [연결표](evidence/FROZEN_41_DOCUMENT_GAP_MAP.csv)에접수번호·회사/종목힌트·회계기간미확인·필요필드·기존상태·분기의존성·전략차단을보존했다. 28종목힌트만보수적2009provider모집단에포함되며나머지13도승인목록에서삭제하지않았다. 힌트의교집합을역사적법인연결인증으로부르지않는다. 우신시스템20100331002136의정정제목은원본/정정관계확인의단서이며그자체가PIT증거는아니다.

|2009기간|canonical완료/예상|canonical상태행·shard|별도legacy v5정규화|공시catalog|
|---|---|---|---|---|
|Q3|0/1495|0행/0shard|13,271행/683접수/650종목힌트(예상집합교집합538)|2,231접수/예상집합힌트교집합1,452|
|FY|0/1495|0행/0shard|5,202행/288접수/281종목힌트(교집합243)|2,430접수/교집합1,482|

`0/1495`는canonical CFS-first terminal source-completion장부의완료종목수다. 공시존재수/의미PASS/PITPASS수가아니다. canonicalfull_history2009자료와상태는없지만,다른legacy저장소에는자료가있다. 따라서“세계적으로원자료없음”으로판단하지않았다. raw_ok=True는0OK코드에대한빈shard-consistency조건이므로존재증거가아니다;ratio0이먼저차단한다.

병목은복합적이다:①canonicalraw/상태부재,②legacy별도schema/기간/scope미연결,③v5confidence/source_qualityPASS가현행독립의미검증이아님,④실제공개·정정·당시종목관계증거부족. v5값을그대로full_history에복사하거나CFS OK로표시하지않았다. 이미확보된원문에서완결된필드만기존snapshotowner에명시적으로연결하는방식을먼저진척시켰다.

41수집은현재동결FY원문/네핵심필드(자본·연간매출·연간순익·연간OCF)의검토증거부족을줄일수있다. **현재해결분0**이며실제결과전필드완료를예상값으로채우지않는다. 2010년4월분기재무기반valuefactor는같은범위FY−Q3가필요하므로41FY만으로Q3/1495/PIT결손은해결되지않는다. 실제신규값/추출/의미/PIT/엔진입력을별도집계한다.

## 4. 기존 원문 재사용으로 늘린 작은 PIT 범위

이번에는사조산업corp00124799/stock007160/원본20100331001582의**연간매출액328,527,137,799원·연간순이익34,326,086,558원**두필드를추가검토했다. 기존자본총계필드의신호일검증을새값으로다시세지않는다. sourcecanary는유한157/현재880밖이다.

- 원본ZIP/member SHA,strictCP949roundtrip,원문XML table168 IS행1/72와공식primary node2591068/ele25 HTML table3행1/72를대조했다. 독립rawTR1518/1589의원시토큰/비교열까지같다. 순이익은이익잉여금주석의당기순익도대조했다. whole-filing추출완전성인증은아니다.
- `XBRL 개별재무제표`에서이어지는XI본문IS/제39기2009-01-01~12-31/원/현재열/양수부호다. 늦게추가된CFS와혼합하지않았다. 숫자2·의미2PASS를기존880의857PASS에합산하지않는다.
- 기존공식viewer/list의3/31공개·bounded4/30까지원본문관계를각새필드에바인딩했다. 정확한시각은미확인하여당일사용금지,실제4/1다음거래일종가부터만조회한다. 원문AREGCIK/회사명과공식KRX4/1·4/30거래행의코드/명칭은각신호일에정확히연결했다. 연속법인계보/전체정정이력은미인증이다.
- **기존financial_record_readiness.select_asof→기존DART report_snapshots/latest_snapshot**으로조회했다. 새calendar-FY OFS consumer는지원필드/단위/기간을엄격히검사하며운영provider를등록하거나전체모집단gate를바꾸지않는다. annual total을Q4나quarterlyyield로이름만바꾸지않고quarterly_amount=None을반환한다.
- 두필드모두3/30·3/31값없음,4/1·4/30PASS,증거폐쇄밖5/3은값없이UNVERIFIED다. **새고유필드2/실제필드×신호4**,누적사조bounded3필드×2신호(자본기존2+연간두필드4)다. 이는운영PIT0/6/880PIT승격0과다르다.
- 새query6개+옛equityquery6개unit검사PASS. 정정후과거덮어쓰기/최신미검증일때stalefallback금지시험은**합성**이며,실제정정두버전을대조했다고하지않는다.

같은issuerQ3의기존catalog접수번호는20091116000562이고v5후보31행이있다. 그러나기존표본pack/이름기반현재경로에서원문/기간·범위·버전·PIT연결증거를확보하지못했다. 임의로FY에서이를차감하지않았다. 현재43승인대상에는SajoQ3가없으므로그접수번호를이번HTTP예산에끼워넣지않는다. 다음은보존된그원문byte존재/출처를우선찾고없으면별도정확한source확보범위를제안하는것이다.

## 5. 사용자 기능·실제 진척·남은 범위

화면보기구간/기존NAV하위기간CURRENT분석/초기현금부터새기간실행의기존29b계약을바꾸지않았다. 원격실제브라우저는2024-06-03~10-31분석(원래NAV불변·직전5/31baseline),2019-12-02~2020-12-30모멘텀268세션·초기현금·사전63session자료·첫실제체결,기존/새비교저장재열기를통과했다. 기존CURRENT산식·비용·기간/초기상태메타데이터를유지했다. 표시구간변경은새백테스트0이다.

이번새실행가능전략/기간증가0:앞선구현의실제원격검증을완료한것이다. 새연간두필드는단일issuer진단조회가능범위를늘렸지만,현재DSL의분기재무순위전략을확장하지못했다. 2009Q3·모집단coverage/현행의미/PIT/연결자료가필요하다. 자유문장모델/외부전화호스팅·인증도미구현상태다. 짧은구간의좋은성과를전체전략성과로일반화하지않았다.

## 6. 보존과 재개

원격에는29b코드/driver2997930/두CI로그·artifact가있다. v10ZIP전송은하지않았고v1~v10은보존했다. 로컬목록은[evidence/LOCAL_ONLY_RECOVERY_INVENTORY.json](evidence/LOCAL_ONLY_RECOVERY_INVENTORY.json)이다: v7/v8의ZIP·backup-only기록, v9의정확한옛비교store17파일11,166,333바이트, v10의새결과/비교store78파일18,500,316바이트와ZIP. 코드bundle의코드는이제원격Git에서회복할수있지만**옛runID/hash로묶인비교store는새CIartifact로교체할수없다**. 원격hash문서만있어도원래HTML/NAV/메타데이터byte를재구성할수있다는뜻이아니다. v10의2024source snapshot은v9를의존한다.

새연간조회코드·검토증거·41연결표·승인예산인계는새로컬커밋/작은증분으로보존한다. 이추가코드는승인된49파일에포함되지않으므로공개게시나원격CI를했다고하지않는다. 원문source4pack은이미원격에있어중복전송하지않았다. 원격자료만의전체프로젝트복원은여전히미실시다.
