# Moat + anti-overheat exploratory backtest

- Period: 1990-01-02 ~ 2026-02-25
- Base: Gold 30% + 3M T-Bill 30% + moat sleeve 40%
- Candidate universe (defined with 2026 hindsight): ASML, TSM, NVDA, AVGO, GOOGL, MSFT, AAPL, AMZN, META, ORCL
- Annual signal: previous trading day only
- Eligibility: at least ~3 trading years (756 observations) of own price history
- Overheat score: current adjusted price / median adjusted price of previous 756 trading days
- Select the 4 LOWEST scores each year; equal 10% each
- If fewer than 4 eligible names, unused 10% slots remain in T-Bills
- Rebalance: first trading day each year
- Trading cost: 5bp on one-way turnover
- Taxes: excluded
- IMPORTANT: this is NOT a historical valuation backtest because PIT P/E or P/S data are unavailable in the repository. It tests price-overheat avoidance inside a present-day moat candidate universe.
- IMPORTANT: candidate-universe survivorship/hindsight bias remains.
