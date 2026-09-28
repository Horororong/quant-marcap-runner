# 하면 된다! 퀀트 투자 — 데이터 커버리지 맵

목적: 책에 등장하는 한국 주식 종목선정 전략을 PIT(point-in-time) 방식으로 재현하기 위해 필요한 원천 데이터를 정의한다.

## 1. 가격/시장 데이터 — 기존 KRX/Marcap 데이터로 충족
- 종가/수익률: 상대모멘텀, 3/6/12개월 모멘텀, 주가변동성, 베타
- 시가총액: 소형주 필터, PER/PBR/PCR/PSR/PFCR, EV 계열
- 거래량/거래대금: 유동성 필터, 거래가능성/시장충격 검토
- 상장주식수(Stocks): 증자 여부 후보 판정 및 주당지표 보조
- 시장/종목코드/이름/상장생존구간: 과거 유니버스 구성

## 2. 재무 원천항목 — legacy-v3-book부터 함께 추출
핵심 4개:
- equity
- revenue
- net_income
- ocf

추가:
- total_assets
- total_liabilities
- current_assets
- current_liabilities
- cash_and_equivalents
- short_term_borrowings
- current_portion_long_term_debt
- long_term_borrowings
- bonds_payable
- operating_income
- gross_profit
- cost_of_sales
- ppe
- capex_ppe
- capex_intangibles
- depreciation
- amortization
- ebitda
- dividends_paid
- cash_dividend_total
- dividend_per_share

## 3. 책의 팩터/전략과 데이터 연결

| 팩터/전략 | 필요한 원천값 | 상태 |
|---|---|---|
| 소형주 | 시가총액 | READY |
| PBR | 시가총액, equity | READY |
| PER | 시가총액, net_income | READY |
| PCR | 시가총액, ocf | READY |
| PSR | 시가총액, revenue | READY |
| NCAV | current_assets, total_liabilities, 시가총액 | v3 |
| EV/EBIT | 시가총액, 차입금, cash_and_equivalents, operating_income | v3 |
| EV/EBITDA | EV 입력값, ebitda 또는 operating_income+depreciation+amortization | v3 |
| PFCR | 시가총액, ocf, capex_ppe(+필요시 capex_intangibles) | v3 |
| GP/A | gross_profit, total_assets | v3 |
| ROA/ROE | net_income, total_assets/equity | v3 |
| 부채비율 | total_liabilities, equity | v3 |
| 차입금비율/증가율 | 차입금 계정, equity/전기값 | v3 |
| 영업이익/차입금 증가율 | operating_income, 차입금, 전기값 | v3 |
| 자산성장률 | total_assets, 4분기 전 값 | v3 |
| 이익변동성 | 여러 분기의 operating_income/net_income | v3 |
| 영업/순이익 모멘텀 | 분기 operating_income/net_income | v3 |
| ROC(마법공식) | operating_income, current_assets, current_liabilities, ppe | v3 |
| F-score 9개 | net_income, ocf, total_assets, 장기차입, current_assets/liabilities, gross_profit, revenue, 주식수 변화 | v3 + KRX shares |
| 신 F-score | net_income>0, ocf>0, 신규주식발행 없음 | v3 + KRX shares |
| 배당수익률/배당성향 | dividend_per_share 또는 cash_dividend_total/dividends_paid, 주가/시총, net_income | v3; 별도 검증 필요 |
| 상대/절대 모멘텀 | 가격 수익률 | READY |
| 주가변동성/베타 | 가격 수익률, 시장지수 | READY |
| 계절성 | 거래일 캘린더 | READY |

## 4. 아직 품질 게이트가 필요한 항목
1. 신규주식발행 여부
   - KRX 일별 상장주식수 변화만으로 후보를 만들 수 있으나 액면분할/병합/합병/주식배당을 유상증자와 혼동하지 않도록 기업행위 보정이 필요하다.
2. 배당
   - 2000~2014는 원문 공시에서 현금배당총액/주당배당/현금흐름상 배당지급을 함께 추출한다.
   - 2015년 이후는 OpenDART 배당 API와 교차검증하는 것이 최종 기준이다.
3. 과거 유니버스 제외 플래그
   - 금융업, 지주회사, SPAC, 관리종목, 거래정지, 우선주 등은 신호일 당시 상태로 별도 관리한다.

## 5. 원칙
- 파생 팩터를 저장하지 않고 PIT 원천값을 저장한 뒤 전략 실행 시 계산한다.
- 공시일 이후에만 해당 재무값을 사용할 수 있다.
- CFS/OFS를 섞지 않는다.
- 결측을 임의 보간하지 않는다.
- legacy PARSED_4F 상태는 확장 스키마에서도 기존 4개(equity/revenue/net_income/ocf)가 한 scope에 모두 존재할 때만 부여한다.
