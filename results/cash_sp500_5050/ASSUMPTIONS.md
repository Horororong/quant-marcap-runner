# Backtest assumptions

- Period: 2001-01-02 to 2026-08-24 (latest SPY observation in repository)
- Initial capital: $10,000
- Equity: SPY adjusted close (dividends/splits reflected)
- Allocation: S&P500 50% / cash leg 50%
- Rebalance: once per year, at close of first SPY trading day of each calendar year
- Cash version A: 0% return
- Cash version B: repository FRED DTB3 3-month Treasury bill secondary-market discount yield; previous available day's rate; converted approximately to investment-basis annual yield using a 91-day bill and accrued by calendar day
- Base trading cost: 5 bp on SPY notional traded at each annual rebalance; sensitivity 0/5/10 bp
- Taxes: excluded
- MDD: daily NAV
- Sharpe: daily excess return over DTB3 cash proxy, annualized with 252 trading days
- Sortino: MAR=0, annualized with 252 trading days
- 2026 return: partial year through latest repository date
