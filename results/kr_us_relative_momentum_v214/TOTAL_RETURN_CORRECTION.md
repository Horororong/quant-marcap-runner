# Total-return correction for Strategy 6

The original `kr_us_relative_momentum_v214` run used KOSPI and S&P 500 **price indices**, so cash dividends were omitted from both the signal inputs and benchmark returns.

Use `results/kr_us_relative_momentum_total_return_v214/` for the dividend-reinvestment rerun.

Key correction:
- Standalone SPY adjusted-close total return, 2001-01-02 to 2026-08-31: CAGR 9.12%, versus the earlier S&P 500 price-index benchmark CAGR 7.10%.
- Yahoo Adjusted Close incorporates applicable split and dividend adjustments.
- Long-history exact KOSPI TR could not be retrieved from KRX in the GitHub Actions environment. The long TR rerun therefore uses Nasdaq Korea Total Return Index (USD) as an explicitly labeled proxy, plus KODEX200 adjusted-close robustness tests.
- The original price-index run remains useful only as a price-index diagnostic and should not be treated as the final investable comparison.
