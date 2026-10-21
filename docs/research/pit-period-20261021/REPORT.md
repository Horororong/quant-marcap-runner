# 2026-10-21 승인 게시 이후의 실제 목표 진척

RESEARCH_ONLY. 운영 main·금융값·PIT 게이트는 변경하지 않았다. 전체 복원/751파일 해시 감사/기존 대용량 백업 전송은 반복하지 않았다. 이번 신규 DART/KRX 원문 HTTP는0이다. 아래의 확보·추출·의미·PIT·엔진 입력 상태는 서로 다른 판정이다.

## 1. 승인된 기능 커밋과 원격 CI

- 코드 `7c2269aaeeaf146ed95aeaed24f59411c0e09730`, 공개 연구 브랜치 `fix/native-source-boundaries-20261021`에 ba26에서 fast-forward 게시했다.22파일243,921바이트, 비밀값 검출0/제외0, 원격22SHA256 일치.
- **CI driver6,703바이트는22파일에 포함되지 않는다.** 별도 브랜치 `ci/fixed-kit-restored-20261020`의 커밋 `fe04aba1aa9bdd46a955fe2068fa044799e1842c`다. 부모 da7885a1afb1f0edc3a59ed0e70f7c463ef5bd9e. Driver SHA256 `87f470538d3356659d897093ef33f16a865228d752c21b16eb70af2719f8951b`도 원격 readback과 일치했다. 기능코드와 driver를 합쳐250,624바이트의 승인 범위다.
- 게시 전 승인 manifest SHA256 `46a9a5422377ab62d71e977151b0fc80b66081d60cf86f4bd5df38e91bcfc5be`.
- [CI39575278064](https://github.com/Horororong/quant-marcap-runner/actions/runs/39575278064) SUCCESS, 실제 checkout **7c2269aaeeaf146ed95aeaed24f59411c0e09730**. API run head_sha가 driver fe04인 것과 구분한다.18계약시험, 기존 실제 브라우저→공통엔진→CURRENT·독립장부, 세 원래 NAV hash, 비교 저장/재열기·서버 재시작 통과. 원래 kit26e4ec02e569 SHA/CRC 검증 후 사용했으며 인터넷 pip 설치는 없다.
- 이번 추가 개발은 별도 `feat/pit-analysis-period-20261021`에서 진행했다. 먼저 필수 수정9365b9f51e052198ac50537e858ab1799b966763을 분리했다. 그 뒤의 하위기간/PIT 기능 최종 SHA는 인수인계/증분 FINAL_STATUS.md와 `git rev-parse HEAD`를 따른다. **추가 코드의 원격 CI는 아직 미실행**이며 위7c CI로 대신하지 않는다. 이번 공개 승인은7c의22파일과 지정 driver로 한정된다.

## 2. 데이터 확보·검증 범위

157은 전체 프로젝트의 모든 DART 원문 수가 아니라 **limited_resume_v1 장부의100+57문서**다. 두 집합은 접수번호 중복0이다. 기존 canary/validation 및 구버전 처리 이력은 별도이며 자동 합산하지 않는다.

|집합|확보|추출|의미 검증|PIT·엔진 입력|
|---|---|---|---|---|
|앞선 유한 관찰100문서|원문100|4F84문서+partial1, 후보1,363; SOURCE_GAP14/추출실패1|별도23문서 표본의46재무 control 중38PASS/8UV;1,363개 전체 판정 아님|새 값 게시HOLD, 전체PIT 미인증|
|후속57문서|원문57;100과 비중복|48문서871후보+SOURCE_GAP9문서|48문서의 기존 후보871판정 완료:848PASS/23UV|871모두 사용가능일/정정/종목관계 미인증, source-onlyHOLD|
|9개 수리 제안|위57의 기존 원문 재사용|STC8+CJ1; 기존871과 중복0|9source-rowPASS|9모두PIT 미인증, 운영값 교체 없음|
|현재 연구 제안 집합|위48후보 문서|880=운영871+오프라인9|857PASS/0FAIL/23검토후UV/미검토0|880모두PIT/whole-filing완전성 미인증|
|이번 사조산업 사례|기존 canary 원문·공식 primary/viewer·목록·당시 KRX 증거|기존OFS equity1필드|기존 의미PASS 재사용; 새 의미PASS 증가0|새2010-04-01 신호1건의 bounded research 조회PASS; 아래 범위 제한|

57=48+9이며9SOURCE_GAP은57의 부분집합이다. 유한157전체의 SOURCE_GAP은14+9=23문서다. **이23문서, 의미UV23개 후보, 앞선 표본23문서는 서로 다른 단위**다.157전체 후보1,363+871=2,234와 현재 상세 검토의880제안도 구분한다.880중23UV의 이전12개는 그대로이고 과거 미검토에서 추가 판정한11개다. 사채 정의16/유동성장기부채 합계·구성4/영업비용과 매출원가3의 기존 사유를 유지했다.

이번 생성한 [종목·필드별880행 현황](evidence/candidate_coverage_by_security_field.csv), [기간·범위·필드42그룹](evidence/legacy_field_scope_summary.csv), [접수번호 포함 관계](evidence/OBSERVATION_COHORTS.json)는 기존 장부를 재집계한 것이다. CSV의 stock/name은 동결 인덱스의 **힌트**이며880개에 대한 당시 법적 종목 연결 인증이 아니다. 실제 검토한 당기 회계기간 말일은2009-12-31이다. 동결 큐의 period_end2009-12-01/fiscal_year2010 같은 메타는 원문 결산일 대신 쓰지 않고 원본도 수정하지 않았다.

|데이터 종류·범위|확보 완료 범위|추출·로딩|의미·PIT 검증|실제 엔진 입력/차단|
|---|---|---|---|---|
|KRX 가격·시총·거래량·종목/시장·수익률|복원 snapshot의 equities38파일, 연도 원본1995~2026의32parquet|Date/Code/Market/Close/Volume/Marcap/Stocks/ChangesRatio 등; 기존 대표연도 로더 증거 재사용|전체 종목·상폐·기업행위·legal mapping 투자 인증 아님|기존 size/momentum 연구 경로 사용. 개별 노출의 거래가능성/1bp held-return/event gate 필수|
|거래일·지수|indices9파일 및 기존 공식 캘린더 보정/원문|요청 시장·벤치마크 날짜를 기존 XKRX/원본 owner로 검사|일부 실제 공식 일자 증거와 전체 달력·종목 인증을 구분|누락 날짜·기준지수 mismatch는 차단, 보간 없음|
|2026 추가 공식 자료|research_extensions2파일|기초2026parquet은10/08까지; 등록 extension10/12~10/16의 equities13,808행 및 KOSPI|기존 등록 source별 검증 범위 유지|10/16까지 등록 연구 경로,10/21의 새 관측으로 추정하지 않음|
|DART modern2015FY~2025H1|full_history에서39연도·분기 그룹이 snapshot에 존재|기존 canonical loader의 equity/revenue/net_income/ocf와 분기 차분 의존성|수집 상태 완료는 필드 의미/정정/정확한 공개시점/issuer 인증 아님|기존 provider의 source coverage21그룹 통과/18그룹 미완결. 아래 표 참조|
|DART legacy2000~2014 상태·가공자료|snapshot의 legacy 관련319파일 및 별도 원문 pack/관찰 장부|구버전 상태 CSV에는v3/v4/v5 등이 섞여 있음|v5 PARSED_4F14,047 같은 과거 상태를 현행9.3 금융/PIT PASS에 합산하지 않음|구버전 재수집/게시 재개 금지. 원문 보존과 파싱 상태를 구분|
|최근 유한 관찰157|대부분2010-03-31 접수, 공시명2009.12 사업보고서|1,363+871 후보; 상세 제안880은 후속57 subset|SOURCE_GAP와 whole-filing 완전성 미인증|현재 legacy source-only이며 운영 금융값으로 미반영|
|기업행위·상폐·권리|현재 corporate_actions9등록행과 별도 references/research/gap 자료|등록 사건 계약만 기존 engine에서 처리|전체 시장의 배당·상폐현금흐름·권리·법적 종목 계보 완결 아님|207940/2022-02-28 등 미해결 원래 증거 gate 유지|
|ETF·FX·macro·proxy·derived|KR ETF6/US ETF29/FX2/macro7/proxy12/derived4파일|기존 파일·대표 schema 증거 재사용|이번 독립 정확성/PIT 인증 없음|데이터 존재를 한국주식 DSL의 ETF/매크로 전략 지원으로 바꾸지 않음|

고정 복원 snapshot은 기존 감사에서 확인된751파일/1,373,060,882바이트이며 이번에 전체 파일을 다시 해시하지 않았다. financials618/status24 등 종류별 파일 수는 DATA_COVERAGE.json에 있다. 이 데이터 파일 수와 문서/후보/코드파일 수는 서로 다른 단위다.1995/2000/2010/2021/2026 대표 로더의 관측 종목 수1,140/1,673/2,073/2,516/2,844는 기존 증거의 범위이며 모든 연도의 개별종목 정확성을 새로 인증한 것이 아니다.

|Modern 원자료 기간|기존 source-completion 상태(코드 수)|판정|
|---|---|---|
|2015FY|2,077/2,077|수집 상태 gate 통과|
|2016 Q1/H1/Q3/FY|각2,162/2,162|동일|
|2017 Q1/H1/Q3/FY|각2,254/2,254|동일|
|2018 Q1/H1/Q3/FY|각2,321/2,321|동일|
|2019 Q1/H1/Q3/FY|각2,387/2,387|동일|
|2020 Q1/H1/Q3/FY|각2,461/2,461|동일|
|2021 Q1/H1/Q3/FY|1,768/1,781/1,804/1,831 중 각분모2,536|미완결|
|2022 Q1/H1/Q3/FY|1,831/1,861/1,871/1,907 중 각분모2,622|미완결|
|2023 Q1/H1/Q3/FY|1,897/1,917/1,995/2,014 중 각분모2,722|미완결|
|2024 Q1/H1/Q3/FY|2,008/2,035/2,039/2,079 중 각분모2,812|미완결|
|2025 Q1/H1|2,069/949 중 각분모2,867|미완결;Q3/FY shard 부재|

여기서 completion은 기존 `CFS OK` 또는 `CFS NO_DATA→OFS terminal` 계약이다. **모든 issuer의 네 필드 존재/정확성/PIT PASS라는 뜻이 아니다.** 종목별 상태 원본은 `data/status/dart_full_backfill_state.csv`이고 [39기간 세부표](evidence/modern_year_period_coverage.csv)에 source/raw_ok가 있다. 재무 전략의 실제 병목은 필요한 분기와 전체 대상 issuer의 자료·시점/정정/연결 검증이다.2009Q3/FY의 기존 provider는 각각0/1,495이며, 단일 issuer equity 하나로 이를 우회하지 않는다.

## 3. 신규 PIT 사용 사례의 정확한 범위

새 코드는 기존 `financial_record_readiness.select_asof` 이후에 기존 DART `report_snapshots/latest_snapshot`을 호출하는 **필드 단위 진단 consumer**다. 별도 factor provider를 등록하거나 운영 원자료를 주입하지 않는다. 실제 데이터 source가 원래 GAAP 자본총계이므로 IFRS account ID를 만들어 붙이지 않고 기존 정확한 한국어 account fallback을 사용한다.

|연결 항목|실제 확인 결과|
|---|---|
|회사/종목|사조산업, corp00124799, stock007160; 원문 AREGCIK/회사명과2010-04-01 공식 KRX 거래행의 명칭/코드 연결|
|원문|20100331001582 primary OFS BS 자본총계; ZIP/member와 공식 primary node2591068/ele25의131,053,210,651원 대조|
|회계기간/단위|2009-12-31 instant, 원/배수1, 당기 열; CFS 늦은 첨부와 분리|
|공개|공식 viewer/list는2010-03-31, 정확한 공개 시각은 미검증|
|보수적 사용 규칙|공개 당일 제외. 실제 공식 거래행이 확인된 바로 다음 거래일2010-04-01의 **종가 신호부터** 사용. 장 시작 전 공개로 추정하지 않음|
|버전/정정|기존 공식 primary graph와 last_reprt_at=N 목록의 bounded 구간은4/30까지. 그 안에서 원본을 대체하는 정정 후보 없음. 전기간 정정 인증 아님|
|공개 전/당일|3/30·3/31 조회value=None/UNAVAILABLE|
|공개 후 실제 신호|4/01 조회PASS, equity131,053,210,651원; 당시 공식 시총127,000,000,000원으로 기존 factor owner의 book_to_price1.031915044496063|
|닫힌 증거 범위 이후|5/03은CHAIN_NOT_CLOSED_AT_SIGNAL/UNVERIFIED, 값을 반환하지 않음|
|전체 전략 진입|동일 기존 adapter.factor_frame 호출은2009Q3/FY0/1,495를 이유로 거부|

이 필드는 **157/880 이전 canary 자료**에 속한다. 기존 의미PASS를 새로 세지 않았고 새 고유 재무필드도0개다. 이번 순증가는 **같은1필드의 새 신호일4/01에 대한 bounded research 조회1건**이다.880개를 PIT 통과로 올린 수는0, 운영 backtest_eligible=False/투자PIT0/6/금융게시HOLD 유지다.

나중 정정이 과거 값을 덮지 않는 동작과 최신 정정값 미검증 시 이전 값 fallback 금지는 실제 snapshot owner를 호출하는 **별도 합성 정정 fixture**로 검증했다. 실제 chosen interval에는 정정이 없어 두 실제 버전의 숫자 정확성까지 인증했다고 보고하지 않는다. 그런 확대에는 실제 정정 접수번호/정정 대상 원본 관계, 각 dcm/member 원문 hash·공개일/시각 또는 다음거래일 규칙, 같은 회계기간·범위·항목, 해당 신호일의 역사적 issuer/code 증거가 추가로 필요하다. 확보 경로는 기존 공시 인덱스/보존 viewer를 우선 사용하고, 부족한 공식 DART 목록(last_reprt_at=N)·primary viewer/원문을 별도 유한 승인 범위에서 확보하는 것이다. 이번에는 추가 source HTTP를 호출하지 않았다.

## 4. 실제 수집 상태와 다음 유한 예산

현재 main `fd232d129bfa2ef01714b94890460c5ef47bdbf0`/수집 parser9.2다. 연구9.3 공개나 이번 UI/PIT consumer는 운영 배포가 아니다.09:18UTC/18:18KST의 실제 state/config/main recovery gate 검사 결과 ONCE_PER_KST_DAY다. DART 외부 잔여 quota는 알 수 없다.

|제한|실제 근거/값|
|---|---|
|일일 실행|PROJECT_CHARTER+config.maximum_runs_per_kst_day=1, 코드가 KST day_kst 중복을 거부하는 **내부 정책**|
|누적 예산|원래3회 중2회 사용/1회 잔여, 예약200/300문서|
|문서 수|원래 예약/실행당100; recovery segment1~25; 승인된 시험은2062·2063 두 문서|
|DART HTTP|문서당최대2요청/통신재시도1회. 따라서2문서 시험은최대4HTTP이지2HTTP 보장이 아님|
|시간|coordinator600초, 문서90초, worker HTTP control75초, 새 문서 admission은90+기본종료여유15초가 남을 때만; HTTP connect10/read15/wall35초, 재시도대기2초|
|차단/실패 차감|lease 전 gate차단0회 차감; durable lease 후0건/실패는 실행1회 유지. config/day 처리 오류 증거 없음|

오늘 기회를 사용한 실제 source run39504052321은KST06:55~07:05에57원문/871후보를 저장한 뒤600초로 중단했다. 마지막02054 원문 저장07:05:20.561506KST다. 최근 예약39513249271은 workflow/job success지만 실제 로그는 `NO_COLLECTION/OBSERVATION_STOPPED_OR_UNREVIEWED`이고0수집이다. 이는 job skipped도 백필 성공도 아니다. 이번은 source workflow를 dispatch하지 않은 읽기 전용 차단 검사다. 신규원문0/DART HTTP0/후보0/체크포인트02054유지. 과거57durable originals를 과거 전체HTTP57로 단정하지 않는다.

02054는완료,02062는옛 worker가 -15로 종료된 DEFERRED이며 durable 완료 아님,02063은PENDING이다. pending43/next2062·2063 그대로다. 다음 창은KST10/22 00:00(UTC10/21 15:00) 이후이며 모든 gate를 다시 확인해야 한다. 마지막 슬롯으로2문서를 실제 처리한 뒤에만 성공/호출량/소요시간/원문/후보/중복/정상종료/새 checkpoint를 기록하고 HOLD_FAILURE 해소 여부를 판단한다. 지금은 실패/HOLD를 지우지 않았다. 기존 cron05:17KST는 존재하지만 parent 없는 예약이 HOLD를 자동 복구하지 않으며 미래 실행을 완료로 세지 않는다.

아직2문서 실측이 없어 **시험 후 확정 예산을 만들 수 없다.** [조건부 다음 예산안](evidence/NEXT_FINITE_BACKFILL_BUDGET_PROPOSAL.json)은 성공 후남을41문서를21+20 두 segment, 추가실행최대2회/HTTP최대82/각600초/문서예약추가0/하루1회로 제안한다. 과거57건의 완료 간격 median9.83477/p9519.452389초(다운로드+파싱+저장 합계)를 참고했으며 순수HTTP latency나 새2문서 실측으로 부르지 않는다. 실제 trial 후 보정해야 하고 시간 내41완료를 보장하지 않는다. 기존3회 장부를 리셋하거나 config 숫자만 올리는 활성 변경은 없다. 별도 유한 supplemental 승인과 최소 운영 계약/PR 검증이 필요하며 이번 main병합 승인도 없다. 원래 만료UTC10/23 23:59:59 이후에는 명시적 새 기간 승인 없이는 실행하지 않는다.

효과는 이미 동결한2009.12 사업보고서의 남은 원문/추출 증거 부족을 줄이는 것이다. 다음 범위에는 원문 관계 확인 단서가 될 `[기재정정]20100331002136`(우신시스템/코드힌트017370)도 있으나 제목만으로 정정 관계/PIT를 인증하지 않는다. 이 수집이2009Q3·1,495issuer 전체/2021이후 modern 결손을 자동 해결하지 않는다.

## 5. 사용자 기능: 기존 것과 이번 증가분

기존 결과 저장/재열기는 **개별 실행의 DSL/NAV/CURRENT 결과를 다시 여는 기능**이다. 이미 게시한7c의 비교 저장은 **2~6개 성공 결과의 선택 순서·이름·당시 hash를 보존하여 같은 비교 묶음을 다시 여는 기능**이다. 계산 결과나 backtester를 다시 만든 것이 아니다. 이번에는 그 비교 기능을 재사용해 원래 실행+새 하위기간 분석을 저장·재열기했고, 옛v9 비교 record도 새 코드에서 변경 없이 열리는 것을 확인했다. 이후 실제 새 기간 모멘텀 재실행과 옛2020년 모멘텀 실행의 비교도 저장·재열기했다(새 comparison e917c722324544c4b46932f28b3d83a1). 이 후속 확인은 추가 엔진/HTTP0이며 선택된 UI 순서와 두 기간·fingerprint를 그대로 보존했다.

|사용자 동작|실제 처리|보유/현금·성과·식별|
|---|---|---|
|보기 구간만 변경|기존 Plotly x축 표시 범위 변경|작업·엔진 실행·성과표 변화0. DOM view metadata에display_range_only 기록. 확대구간 자체는 저장하지 않음|
|기존 NAV 하위기간 분석|성공한 source NAV 전체를 hash로 묶어 새 경로에 보존; 기존 CURRENT에selection/source_full기간 전달|source 보유·현금·비용 경로 유지, engine_rerun=False. source engine ID 유지/새 analysis ID. CURRENT만 기간별 표/세 차트를 계산|
|기간 변경 후 새 백테스트 준비|정확한 날짜의 한국어 수정→새 DSL/digest→명시적 확인→새 preflight/공통엔진/CURRENT|초기자산 전액 현금/보유없음, 첫 유효신호·t+lag까지 대기. source 보유를 넘겨받지 않음. 새 strategy fingerprint·실행 ID·warmup/원본검사|

실제 하위 분석:2024-06-03~10-31, CURRENT가직전관측5/31을 기준으로 하위기간을 재보고했다. source 전체NAV SHA256 `47888164238553907324d01f85486acf572e060d1734ab21bf28dae47d687cde`는 그대로다. 새로운 선정/비중/체결 파일을 만들지 않았다. selection↔source_full selector, 성장·실제log축·낙폭/성과표, 원본+분석 비교 저장/재열기 통과.2028요청은data_gap이며 원래 전체기간 성과로 대체하지 않았다. 기존 전략/자료/비용은source snapshot에서 읽고 현재 편집기로 대체하지 않는다.

실제 재실행: 시총10조 이상 코스피·코스닥의3-1모멘텀 top3동일비중, 기간2019-12-02~2020-12-30.268거래일 common engine/CURRENT와 독립 원가격·수량·현금 장부 PASS. 최초신호2020-04-29/첫체결5/04 전에는GrossNAV1의 초기 현금이다. 기존 provider lookback63session중63/skip21/raw_ok를 확인했고 관련 사전 원본 provenance를 남겼다. 첫2019년 조각에 신호가 없다는 잘못된 preflight 차단은 원인을 수정했으며 기간이나 모집단을 바꾸어 피해가지 않았다([별도 필수 수정](FRAGMENT_FIX.md)).

CURRENT CSV fixed_cost Net 결과: 최종배수1.7647780377675135, CAGR0.6931074915902198, MDD-0.2287631847089694, Sharpe1.5007166351512593. 표준화초기자산10,000→17,647.780377675135(환율변환/추가납입 아님). 이는 연구 실행/보고 검증이지 알파·투자/PIT·배당총수익 인증이 아니다.2024하위기간 CAGR는365일 미만으로 비어 있는 기존 계약을 유지했다. 로그배수/낙폭은기존CURRENT chart owner이며 별도지표계산을 만들지 않았다.

UI/메타데이터는 각 동작을 명시한다. source의 component contract versions, strategy fingerprint, data/control hashes, 비용·benchmark 및 제한을 유지하고, analysis_context/workspace_operation과 source-run 관계를 저장한다. 일반 자유문장 모델·손절/레버리지 추정 실행·외부 휴대폰 접속/호스팅·사용자 인증은 이번 구현 범위가 아니다.

## 6. 검증·이번 순증가·보존

- 승인7c 원격CI 성공과 **새추가코드의 로컬 검증**을 분리한다. 추가코드는관련54 unit집합 PASS 후최종 source-query guard6개 PASS(중복 제외고유56범위), 생성계약/JS검사, checked DSL lifecycle, 실제브라우저새기간 및 독립장부 통과다. 금액/단위 추정·미래 회계기간·최신 미검증값에 대한 stale fallback도 차단한다. 정정fixture는 합성 소프트웨어검사라고 표시한다.
- 기존3전략NAV는 승인7c CI에서 hash회귀 통과. 전체130엄격비교/옛12envelope조사/57parser재생/751재해시/기존백업전송은 반복하지 않았다. 옛12상세미검증과 금융PIT0/6은 그대로다.

|항목|이번 실제 증가분|누적·남은 제한|
|---|---|---|
|신규 원문/HTTP|0/0|내부일일 gate;157유한장부 유지, 다음2시험 미실행|
|새 후보/의미PASS/누락수리|0/0/0|880=857PASS+23UV;운영871 유지;9SOURCE_GAP별도|
|PIT 사용 범위|기존1필드의 새신호일1건|기존4/30+새4/01의 bounded단일issuer 조회;880승격0/전체투자PIT0/6|
|전략·기간|모멘텀top3 새정확기간1개,268세션|전시장재무순위새가능0. price/technical공통엔진의기간 확장|
|사용자 기능|기존NAV하위기간 재보고/정확날짜변경 재실행|표시만변경은새backtest0;확인·비교·저장재열기실제조작PASS|

변경 코드·집계표·PIT 연결·실행 증거·재개 명령만 새 증분으로 보존한다. v1~v9는 변경하지 않는다.7c의22코드는 원격에 있으나v9ZIP/backup-only metadata/정확한옛store는여전히별도 로컬자료다. 새 추가커밋과 새 결과도 원격 업로드를 했다고 주장하지 않는다. 이 증분의 검증은원격자료만의전체프로젝트복원시험이 아니며 그시험은여전히미실시다. source의공식증거pack/고정Git/data/kit출처는기존원격자료와새복구명세로연결한다. 새공개전송/driver/CI대상은최종manifest에구체화해별도승인범위로남긴다.

재개명령은 [RESUME.md](RESUME.md), 실제수치/파일연결은 evidence의JSON/CSV/log를 따른다.
