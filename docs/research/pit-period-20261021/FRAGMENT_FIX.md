# 선행 연도에 신호가 없는 요청의 사전 검사 수정

실제 모멘텀 top3 기간을2019-12-02~2020-12-30으로 변경하자 연도 단위 planned preflight가2019년12월 조각에4월 신호가 없다는 이유로 `source_or_provider_gap`을 만들었다. 전체 요청에는 실제2020-04-29 신호가 있어 기존 공통 엔진은 처음에 현금으로 기다릴 수 있다. annual_selected_preparation도 이미 같은 관측/신호 구분을 사용한다.

수정은 신호 날짜 owner에 명시적인 `allow_empty`를 추가하고 연도 분할 검사에서만 사용한다. 해당 조각의 원본 파일/해시/시장 거래일/관측 날짜는 계속 검사·보존한다. 신호가 있는 해의 전체 모집단·기술 lookback·선정·비중 검사는 그대로다. 전체 요청에 신호가 하나도 없으면 명시적인 strategy_definition 실패로 남긴다. 캘린더가 불완전하면 신호 유무와 관계없이 차단한다. 일반 신호 builder의 strict 기본 동작은 변경하지 않았다.

별도로 CURRENT subprocess는 고정 전용 Python의 `-I`와 명시적인 신뢰 scripts 경로로 실행하도록 했다. 산식·engine/provider registry·원자료·선정·체결·비용·금융/PIT 게이트는 변경하지 않았다.

검증: 원래 planned guard7개와 새 신호/캘린더 경계2개 PASS. 관련54 unit checks와 checked DSL lifecycle PASS. 실제 변경 기간은268거래일 common engine/CURRENT 실행 및 독립 원가격·수량·현금 장부 PASS. 시작부터 첫 체결2020-05-04 전까지 Gross NAV1을 확인했다. 이전 원래 전략과 새 전략은 서로 다른 fingerprint/output으로 보존한다. 새 기간은 RESEARCH_ONLY이며 금융/PIT 인증이나 알파 검증이 아니다.
