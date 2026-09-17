# 60/40 backtest assumptions

- Attached-book rule: 60% US stocks / 40% US intermediate Treasuries; annual rebalance.
- Initial capital: $10,000.
- Complete-data cutoff: 2026-08-31 (September 2026 excluded as incomplete on 2026-09-17).
- Long proxy: pofo S&P 500 total-return series + pofo IEF/VFITX intermediate-Treasury backfill; daily from the common 1962 start.
- Rebalance timing: before the first valuation/business-day return of each calendar year.
- Gross result: no trading cost.
- Net base: 5 bp per dollar of gross traded notional at annual rebalance; 0/5/15 bp sensitivity.
- Taxes: excluded.
- Sharpe risk-free rate: 0% to match the attached standard template default and facilitate book comparison.
- CAGR/Sharpe/annualized volatility: monthly NAV.
- MDD/max recovery: daily NAV.
- Actual-instrument robustness check: repository SPY and IEF adjusted-close overlap from IEF inception onward.

## Important limitation

The book's 1970~2021 result necessarily uses pre-ETF backfills. Different historical bond proxies, dividend timing, rebalance date, and Sharpe convention can produce nontrivial differences. The actual SPY/IEF overlap check is therefore reported separately.
