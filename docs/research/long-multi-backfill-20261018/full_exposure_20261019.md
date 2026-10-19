# Full planned exposure census, 2026-10-19

No new long multi-security NAV completed. The engine, DSL, costs, event records,
original successful outputs and investment PIT0/6 are unchanged. This census
uses the preserved whole-period planned-readiness-v2 diagnostics, not only each
strategy's first blocker. It does not authenticate an economic corporate action
from a return discontinuity.

| Strategy | Issues | Existing diagnostic-only | Unique kind/code/date symptoms |
|---|---:|---:|---:|
|2019–2025 event-deferred-v2 size deciles|17|2|17|
|2001–2025 broad size deciles|9997|9687|9923|
|2001–2025 broad size top10|21|18|21|
|2001–2025 broad momentum top10|101|91|101|

Across strategies there are9926 unique kind/code/date symptoms, not9926 certified
corporate actions. All10136 portfolio-level records are retained in the compressed
CSV; no failing security or date is excluded. Repeated missing-price observations
remain aggregated with their original occurrence count and affected-through date.

`PLANNED_PREFIX_FIRST_UNRESOLVED_CONSTRAINT` means the earliest independently
observable constraint in that portfolio's planned prefix. It is not an executed
holding/NAV certificate. All subsequent observations, plus the existing
diagnostic-only schedule, are `POTENTIAL_ONLY_AFTER_UNRESOLVED_PATH`. Earlier
unresolved rights or settlement can change later actual holdings; no synthetic
cash, liquidation, settlement or successor ratio is inferred.

The common types are source/reference discontinuity, held quote disappearance,
non-tradable planned order, known unresolved event, and pending-order/new-target
conflict. The first four need historical source evidence before economic
settlement can be chosen; the last also needs an explicit cancellation/expiry
contract. Existing all-or-none/event-linked waiting contracts remain unchanged.

207940 needs executable rights quote/disposal or funded-subscription and actual
new-share tradability evidence; official760000 reference-price proof alone does
not settle rights cash. Historical015580/023130 and002580/018415 need original
stock-transfer/exchange entitlement, cancellation and successor tradability
records.037950/2001-05-08 and012170/2001-06-21 need original exchange notice,
reference price, exact event terms and effective dates. Existing KRX401 denial
is not retried. No newly available sufficient official record was found in the
preserved evidence, so no new executable event was registered in this census.

Known LG/LX, SKT/SKSquare and stock-dividend research events were already handled
by the common engine and independently checked; they are not new completions.
There is no new single-security substitute, performance report or claim that a
whole strategy passed. RESEARCH_ONLY and no cash-dividend total-return claim.

Reproduction: decode `full_exposure_details_20261019.csv.gz.b64`, verify compressed
and CSV SHA256 against `full_exposure_scope_20261019.json`, then count CSV rows by
strategy/kind/exposure. Each original preflight path and SHA256 is in that JSON;
the source is the existing full-prefix-synced artifact preserved locally, not the
older full-multi-rerun artifact whose readiness-v1 counters differ. Do not replace
the corrected counts with the earlier9970/9960 version.

Financial production work remains a separate main-only minimal PR. This research
branch is not merged into main; its parser certification is not applied to new
production documents.
