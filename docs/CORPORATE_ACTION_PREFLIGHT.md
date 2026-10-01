# Known corporate-action exposure preflight

Machine contract 17, preflight contract 3. Execution remains `v2-16-exec-3`;
canonical performance remains CURRENT `v2-17`. This gate computes no NAV,
return drift, transaction costs or performance metrics.

## Conditional shared selection

Preflight first validates DSL representability, source/provider coverage,
market sessions and optional benchmark prices. It then reads the reviewed
known gaps in `config/kr_corporate_action_gaps.json`. A gap is relevant when
its event date is no later than the requested end and its predecessor is in
the loaded historical panel or a registered successor. Earlier unresolved
conversions remain relevant to later attempted purchases.

With no relevant known gap, source-only preflight stays inexpensive and does
not construct factors/targets. With a relevant gap, the gate calls the same
PIT providers, universe filters, finite-factor intersection and ranking/target
builders as public execution. It traces top_n or each independent D01..D10.
Missing factors or invalid selection/scheduling contracts return `data_gap`
with `phase="corporate_action_selection_contract"`; no failed code is excluded.

## Session order and lineage

The PROJECT scheduler supplies actual signal-to-execution dates and configured
session lag. A final signal without its required execution session fails; the
window is never extended. Positive planned targets above the execution weight
tolerance become planned holdings at execution close.

Each session checks prior holdings before corporate actions and before closing
target replacement. An event-day closing sell cannot undo prior exposure.
Verified stock mergers transfer original code/signal lineage to successors;
verified cash disposals remove stock exposure without valuing cash. Split
share quantities do not affect positive-code exposure. Closing targets are also
checked, rejecting a new attempted purchase after a known unresolved conversion.

This is a conservative planned-cohort check, not simulation of actual drifting
weights, price validity, tradability or liquidity. Runtime guards still apply.

## JSON and CLI contract

Known planned exposure yields `status="data_gap"`, `phase="corporate_actions"`,
`ready_for_execution=false`, CLI exit 3. Capability gaps remain exit 2; `ok`
remains exit 0; `--always-zero` changes only the process exit.

`corporate_action_audit` records coverage/policy, whether selection was performed,
relevant known-gap count, scheduled target count and first exposure per
portfolio/code/event. Exposure rows contain `portfolio`, `Code`, `event_date`,
`check_date`, before-close/target phase, original selected codes and signal dates,
reason and evidence. All error payloads have `ready_for_execution=false`.

An empty exposure audit means only that this plan avoids the reviewed known
gaps. It does not certify unregistered corporate actions, complete historical
coverage, source correctness, dividends or executable NAV. Default source-only
preflight does not guarantee post-filter portfolio size. No source candidate
becomes an automatic event or a future-survival filter.

## Verification and remaining evidence

Run `python scripts/test_corporate_action_preflight.py`. Independent PROJECT
execution checks event-day ordering; temporal fixtures cover lag, past gaps,
successor lineage and verified earlier cash disposal. Fixtures are software
checks, not investment performance.

Actual KRX Sep 2–Oct 24, 2024 data contain 53 signal-day KOSDAQ codes with
Sep 30 Close in [12000,14000]. Jeisys 287410 is third by descending Marcap.
Top_n=3 and decile D01 both stop at its Oct 23 known gap in preflight and the
public runner. Top_n=1 succeeds using the same historical universe; an earlier
window retains source-only preflight. A patched NAV function proves the gate
never simulates NAV, and CLI tests verify structured exit-3 failures.

Jeisys legal completion, gross contractual amount and delisting are evidenced;
actual cash payment and applicable net receipt remain unverified. Historical
tax/withholding guidance does not establish actual net deductions. There is
no production cash exchange registry entry. Preserve the blocker until primary
actual-payment/net-treatment evidence and independent actual receipt tests
support a reviewed event; see [CASH_SHARE_EXCHANGE.md](CASH_SHARE_EXCHANGE.md).
