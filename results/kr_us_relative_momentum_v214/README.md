# Korea-US Relative Momentum v2-14

Rule from book: compare trailing 12-month return of Korea and US equity indices monthly; hold the stronger index.

## Main execution-safe test
- Exact repository indices: data/indices/KOSPI.csv and data/indices/SP500.csv.
- Signal: last available close of each market at each calendar month-end.
- MOM12 = P_t / P_(t-12) - 1.
- Execution: first trading day of the next month on which both markets are open; trade at each market's Open.
- Hold 100% of the selected index until the next signal changes the selected country.
- Base cost: 25bp per full country switch; initial entry 12.5bp.
- Monthly CAGR/volatility/Sharpe; daily MDD/recovery.
- Completed data only through 2026-08-31.

## Book validation layer
- The repository's exact KOSPI history starts 1995-05-02, later than the book's 1982 start.
- Exploratory long proxy: OECD/FRED broad share-price series for Korea and US, spliced to exact repository indices at first overlap.
- Korea proxy begins 1981-01-31, so a 12-month signal is first available at 1982-01 month-end and the first strategy return is 1982-02.
- This layer uses the conventional month-end close-to-close timing only to compare with the book. It is NOT the execution-safe result.
- MDD/recovery therefore use monthly fallback.

## Currency
Index levels are compared and compounded in each index's local-currency terms, matching the book-style index rule. No USD/KRW conversion is imposed. A Korean investor's actually investable ETF implementation can differ materially because of FX, taxes, tracking error and product costs.
