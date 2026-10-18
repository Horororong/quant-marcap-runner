# Explicit long-horizon execution research

This is a separate, predeclared execution-model experiment. Original fixed-lag
strategies and their frozen evidence remain unchanged and may remain blocked.

Before any NAV for the new specification, commit
`config/strategies/research_size_top1_2001_2025_deferred_v1.json` with these rules:
historical KOSPI/KOSDAQ cross-sections, original KRW10trillion cap filter,
largest-cap top1, April last-session signals, earliest t+1 close, original
fixed trading costs, full2001–2025 window and explicit KOSPI price benchmark.

The opt-in `defer_full_rebalance` policy retains the old portfolio until all
old and target holdings have observed positive closes and positive volume.
It fills the whole order at the first such close, preserving its original
signal and planned date. A new signal while an order is pending, or an order
still pending at the requested end, fails. No partial fills, exclusions,
estimated prices, return overrides or changed selections are permitted.
This conservative model does not certify actual attainable close fills.

The opt-in `annual_selected_projection` preparation reads complete original
annual source cross-sections before reducing price observations to the union
of selected securities and verified successors. It preserves full original
calendar and provider audits. No current-member master or source-gap fill.

This model is RESEARCH_ONLY, not the original fixed-lag strategy and not an
investment PIT certificate. Source facts, modeled execution, price checks and
economic/account verification are separate. No performance has yet been
computed for this new specification.
