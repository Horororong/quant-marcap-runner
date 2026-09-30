# Super-value audit status — 2026-09-24

The existing `results/super_value_v216` output is NOT a validated investment backtest. Account substring matching can select pretax or attributable profit. KRX ChangesRatio alone does not reconstruct existing-holder returns at rights issues or capital reductions. Do not treat the automatic rerun's success as validation.

Fast run 35939950187 completed 6000 tasks. Signals 2020-04-29 and 2020-10-30 are fully queried (OK/NO_DATA, not complete factor coverage). 2021-04-30 still needed 2243 CFS and 738 fallback OFS tasks at the end of the batch. The next batch resumes from the committed state.

An isolated audit uses unchanged supplied CURRENT v2-16, exact IFRS account definitions, standalone-quarter factors, next-session close execution, locked holdings during suspension, and explicit corporate-action assumptions. Its 2016-11 to 2020-04 research window is not any of the required standard windows. Historical original filings, full-period coverage, cash distributions, rights prices and corporate-action entitlements still require work.

## Strategy DSL DART adapter update — 2026-10-01

`feature/dsl-dart-factors` adds a new standardized DART PIT adapter used by Strategy DSL. It intentionally does not reproduce the legacy broad account-substring matching. The adapter accepts explicit IFRS concepts (with controlled Korean account-name fallbacks), checks filing dates against each signal date, reconstructs standalone Q2/Q4 inputs, and refuses to run when the required DART backfill population is incomplete.

The integration test covers the completed 2020-04-29 and 2020-10-30 signals and verifies the four factor formulas plus an independently reconstructed composite rank. This is a data/factor-selection validation milestone, not yet a claim that the full investment backtest is production-valid. Full historical validation still requires the remaining PIT coverage plus explicit corporate-action/delisting cash-flow handling and cost/tax regime treatment.
