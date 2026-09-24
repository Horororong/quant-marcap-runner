# Super-value audit status — 2026-09-24

The existing `results/super_value_v216` output is NOT a validated investment backtest. Account substring matching can select pretax or attributable profit. KRX ChangesRatio alone does not reconstruct existing-holder returns at rights issues or capital reductions. Do not treat the automatic rerun's success as validation.

Fast run 35939950187 completed 6000 tasks. Signals 2020-04-29 and 2020-10-30 are fully queried (OK/NO_DATA, not complete factor coverage). 2021-04-30 still needed 2243 CFS and 738 fallback OFS tasks at the end of the batch. The next batch resumes from the committed state.

An isolated audit uses unchanged supplied CURRENT v2-16, exact IFRS account definitions, standalone-quarter factors, next-session close execution, locked holdings during suspension, and explicit corporate-action assumptions. Its 2016-11 to 2020-04 research window is not any of the required standard windows. Historical original filings, full-period coverage, cash distributions, rights prices and corporate-action entitlements still require work.
