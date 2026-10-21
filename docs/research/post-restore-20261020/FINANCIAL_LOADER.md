# 재무 로더 사용과 의미 계약

AST로 scripts/*.py 전체를 검사했다. load_dart_financial_rows 정의3개(krx_backtest_data, PROJECT v2-15/v2-16)가 있지만 직접호출0이며 템플릿의 callable 확인만있다. 동적 외부 사용자 호출까지 부재라고 인증하지않는다. 현재 등록 DSL 경로는 DartValueFactorAdapter -> load_financial_raw -> 공시별snapshot/분기계산 -> 신호일coverage다. 사용되지않는 보조 API를 강제로 provider alias로 대체하지 않았다. 보조API에는 비활성/대체경로 설명만 추가했고 원래 schema오류를 유지했다.

|정의|기존 보조 raw API|등록 provider|
|---|---|---|
|종목|stock_code만필수, pandas기본dtype 후zfill|dtype=str, _stock_code/stock_code alias후6자리문자열|
|공시|filing_date 또는rcept_no 앞8자리|_filing_date alias지원; 공시별snapshot과실제신호일gate별도|
|연결/별도|파일명fs_div한가지만반환|CFS/OFS요청구분보존, 완전성확인뒤CFS우선선택|
|기간|연도/기간shard원천행|누적/당분기정책·선행분기공시의존성·최신공시준비도별도|
|단위/숫자|원천열그대로; 임의팩터계산안함|등록계정값파싱, 보존단위/원천정의에따른정규화; 다른통화/스코프를동일시하지않음|
|출력|선택shard전체raw행|등록4재무계정후보와공시marker·dedup; 동일행집합아님|

현재2020 FY 원본은 _stock_code/_filing_date 등을가진다. 따라서보조함수의명시적schema실패와등록provider의로딩성공은모순이아니다. alias만맞춘다고두결과의회계기간/단위/정정/PIT의미가같아지는것도아니다. 금융정확성·PIT신규인증0. 다음작업은외부보조API호출자가실제로발견됐을때별도전환계약과오류테스트를작성하는것이다.
