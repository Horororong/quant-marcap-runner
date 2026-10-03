# Canonical performance v2-18 · v2-17 compatibility

The execution template remains PROJECT v2-16; current engine versions are
defined in `scripts/execution_contract.py` (currently v2-16-exec-3).
Performance/chart calculations live only in `quant_backtest_template_CURRENT.py`
v2-18. PROJECT re-exports those exact functions for compatibility; no copied
metric/chart implementations remain. This milestone introduced machine contract
13; the current value is defined in `scripts/execution_contract.py`. Execution
plans record the performance version separately.

## Periods and compatibility

CURRENT/postprocess keeps `book_validation`, `from_2001`, `from_2021`, `longest`,
and the existing nine-chart manifest order. Formal reports require all four
periods' actual source history. Missing required history still fails; no
fabrication, shortened periods or synthetic long-history investment claims.

Direct legacy PROJECT callers use its `BacktestConfig` subclass with
`standard_start_year=2000`. This preserves their old period keys/labels while
using the same CURRENT computation functions. CURRENT's default remains 2001;
the standard DSL report uses that default. The compatibility setting accepts
only 2000/2001. Archived versioned template files are historical snapshots,
not active canonical paths. Reports use the requested as-of year's bound,
not a permanent 2026 ceiling. No changes to execution/NAV/cost/event formulas.

The committed `config/testing/canonical_performance_v215_baseline.json` records
pre-change v2-15 outputs for a deterministic artificial NAV series. The test
compares every original metric in every period to tolerance 1e-12. It is a
software regression fixture, never an investment backtest.

## Exact daily coverage

`quant_backtest_postprocess.py --market-calendar XKRX` validates supplied NAV
between its first and last observations, and formal NAV through the actual
last session of its final complete month. Missing/extra sessions fail before
canonical output creation. First-date inception can be partial; fixed periods
still require their full months for daily risk. Calendar-free direct API/CLI
callers retain the legacy weekday heuristic and labeled `monthly_fallback`.
Direct metric functions with a named calendar recheck dates even if callers
supply a `coverage_verified` attribute. They never interpolate daily losses.

Both public Korean equity DSL modes explicitly pass XKRX; a CSV cannot carry
DataFrame calendar attributes. Other asset/cross-market callers must declare
the calendar used for their NAV. An incorrect declaration is not fixed by
filling data. Calendar sessions come from the installed `exchange_calendars`
version; this checks dates, not underlying NAV accuracy or complete event
coverage. Historical calendar discrepancies require source investigation.
With a named calendar, inception CAGR uses the actual prior exchange session;
without one, the old business-day baseline remains for compatibility.

## Additional metrics

The checked DSL run lifecycle reuses CURRENT's date-window policy through
`standard_period_windows_from_dates()` and the postprocessor's
`canonical_report_readiness()`. Readiness inspects verified session dates and
explicit as_of before any NAV, without constructing placeholder values or
calculating metrics. Existing `standard_period_windows()` still validates its
actual monthly NAV and delegates to that same date policy. Short history cannot
silently become a four-period report. Actual postprocess coverage/NAV checks
remain mandatory after readiness; formulas and outputs are unchanged.

Monthly sample policy matches existing Sharpe/volatility: exclude an incomplete
inception month when its explicit baseline date is in that same month.
Existing CAGR, MDD, Sharpe, volatility and recovery definitions remain.

Let P=12, annual rf be the explicit configured decimal rate (default 0),
monthly rf=(1+rf)^(1/P)-1, and e=r-monthly rf for complete monthly returns.

- Cumulative return = final rebased multiple - 1.
- Sortino = P*mean(e) / [sqrt(P)*sqrt(mean(min(e,0)^2))].
  The denominator includes zero contributions from nonnegative excess months;
  minimum acceptable return is the monthly risk-free rate.
- Calmar = CAGR / abs(MDD), with the exact risk source shown in MDD_source.
- Monthly win rate = count(r>0)/count(r); zero returns are not wins.
- Too few statistical months or zero denominators yield NaN where undefined,
  never fabricated zero or infinity. CSV represents these as blank values.

## Explicit benchmark comparison

Only `--benchmark-series <actual NAV column>` requests comparison. The DSL
passes `NAV_Benchmark` only when its specification contains a benchmark.
No benchmark is guessed from other portfolio columns. In each of the four
periods, every non-benchmark NAV is compared using the same complete-month
sample, excluding partial inception. The optional output is
`benchmark_statistics_CURRENT.csv`, also recorded in the manifest.

For strategy monthly r_s, benchmark r_b and active a=r_s-r_b:

- Tracking error = sample_std(a)*sqrt(P).
- Information ratio = mean(a)/sample_std(a)*sqrt(P).
- Beta = sample_cov(r_s,r_b)/sample_var(r_b).
- Arithmetic annual alpha = P*[mean(r_s-rf_month)-beta*mean(r_b-rf_month)].
- Downside capture = mean(r_s where r_b<0)/mean(r_b where r_b<0).

Undefined ratios are NaN. The return basis is the input NAV's basis; the DSL's
index Close benchmark excludes dividends. Alpha is arithmetic annualized,
not compounded alpha or a guarantee of statistically significant skill.
Reusing an output directory without a benchmark removes stale benchmark stats.

## Validation and limits

`python scripts/test_canonical_performance.py` checks independent metric and
benchmark formulas, zero denominators, partial-month exclusion, pre-upgrade
regressions, exact holiday calendars, deleted/extra/missing final sessions,
forged coverage attributes, both template function identities, DSL CLI wiring,
and a synthetic full-length CLI report with all four periods and nine charts.
CURRENT and PROJECT self-tests and all existing actual DART/KRX/event E2Es
remain in the full CI. Artificial NAV is labeled software validation only.

Annual/rolling report exports and evaluated walk-forward/OOS reporting are
follow-up work. Full-market events, dividends, rights, delisting cashflows and
long-history investment validation remain separate source/execution work.

## Explicit requested-period reporting (v2-18)

Read `docs/REQUESTED_PERIOD_REPORT.md`. The new `--report-periods` mode has its
own versioned readiness/sample contract; it does not relax four-period dates or
execution-only restrictions. CURRENT `calculate_metrics(requested_period=True)`
uses actual elapsed dates, full daily risk and complete monthly statistical
samples. Insufficient samples are null; unavailable requested periods stay gaps.
The default dashboard has three interactive plots and one shared period selector.
The legacy four-period metric outputs/nine-chart payload and render order remain
available, with the latter explicitly marked as legacy compatibility. Display
capital $10000 is normalized NAV, not a currency conversion or added contribution.
The offline HTML contains pinned Plotly and canonical data only; JS formats and
selects values without implementing investment metric formulas.
