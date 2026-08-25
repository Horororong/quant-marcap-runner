# 닻과 돛 백테스트 가정

- 기간: 1990-01-02 ~ 2026-02-25 (저장소 공통 최신일)
- 초기자산: $10,000
- 기본 비중: 금 30% + 미국 3개월 T-Bill 30% + 공격자산 40%
- 해자기업 공격자산: ASML 10% + TSM 10% + NVDA 10% + GOOGL 10%
- 리밸런싱: 매년 첫 S&P500 거래일 종가 기준, 연 1회
- 기본 거래비용: one-way turnover 기준 5bp, 민감도 0/5/10bp
- 세금: 제외
- 금: 저장소 data/proxy_long/raw/GOLD_LBMA_PM_USD.csv
- 단기채: 저장소 FRED DTB3 3개월 T-Bill 할인수익률을 투자수익률로 근사 후 달력일수로 복리 누적
- S&P500 및 NASDAQ: 저장소 지수 데이터를 우선 사용
- 저장소 NASDAQ 데이터의 1990~1994 결손 구간만 yfinance ^IXIC로 보완
- ASML/TSM/NVDA/GOOGL은 저장소에 개별주 장기데이터가 없어 yfinance Adjusted Close 사용
- 생존자편향 주의: 네 기업은 2026년 시점에 알고 있는 승자를 사후 선정한 것이므로 1990년 투자자가 미리 선택할 수 있었다는 뜻이 아님
- 이를 완화하기 위해 각 기업의 상장 전에는 해당 10% 슬리브를 NASDAQ Composite로 운용하고, 상장 다음 해 첫 연간 리밸런싱 때 기업으로 전환
- 별도 summary_modern_all_actual.csv는 네 기업이 모두 실제 상장된 이후만 잘라 본 보조검증
- S&P500/NASDAQ 지수는 price index, 개별주는 Adjusted Close이므로 배당 처리 기준이 완전히 동일하지 않음. 해자전략의 절대수익률보다는 방어력·상관·낙폭 구조 비교에 더 적합
- MDD: 일별 NAV 기준
