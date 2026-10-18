# Multi-security research continuation

This work extends the **common** PROJECT engine. It does not certify an
investment portfolio or produce a successful NAV for a blocked request.
Read [report.md](report.md), [reproduction.md](reproduction.md),
[predeclaration.json](predeclaration.json), and [source_revision.json](source_revision.json).

Previously successful examples remain available through:

```sh
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I scripts/research_workbench.py examples
"$PY" -I scripts/research_workbench.py capabilities
"$PY" -I scripts/research_workbench.py inventory
"$PY" -I scripts/research_workbench.py check --strategy config/strategies/research_broad_size_top10_2001_2025_v1.json --output /workspace/top10-readiness.json
```

Exit3 means an affected request remains blocked. Inspect `first_blocker`,
`issues`, `diagnostic_only`, original pending signal, affected dates and required
evidence. Secondary diagnostics after a failed whole-order schedule are **not**
actual executed positions. Do not treat them as successful holdings or returns.

The original fixed-lag2019–2025 deciles still stop at LG2021-05-03.
The opt-in `defer_full_rebalance_events_v1` is a separate research contract:
freeze signal/targets, wait for ALL required tradable legs, no advance of sale
proceeds, no cancellation/reselection, fail on overlapping/end-pending orders.
Illiquid dividend/cash rights contribute to NAV but cannot fund purchases;
targets use available liquid NAV, separately in Gross and each Net book.

Two simultaneous-listing demergers and two additional2021 stock dividends have
actual-price component accounting evidence. These small functional components
are not reduced-period substitutes for the requested full-period studies.
Continuous quantities and virtual listing-close settlement do not certify
integer fractional cash, distributions/tax, legal listing history, actual
account credits or investment PIT. Cash dividends are excluded: **not total return**.

Use CURRENT/postprocess for every accepted NAV. Blocked requests have no
accepted performance or interactive result. Existing accepted reports retain
period/cost/portfolio selectors, explicit KOSPI price benchmark, wealth10000,
log-multiple, drawdown, zoom and hover. Final CI performs real browser checks;
the local sandbox cannot start Chromium (`setsockopt: Operation not permitted`).
