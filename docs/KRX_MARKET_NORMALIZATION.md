# KRX market and segment normalization

`KOSDAQ GLOBAL` is a segment **within KOSDAQ**, not a separate equity market.
The [KRX definition](https://kosdaqglobal.krx.co.kr/01/01010000/KGS01010000.jsp)
describes both segments as trading in the same KOSDAQ market. Today's member
list must never be used to reconstruct historical membership.

## Ingestion contract

`scripts/krx_market_normalization.py` has version 1; the machine DSL contract is
15. The updater normalizes the market before filtering KOSPI/KOSDAQ equities:

| Observed Market | Canonical Market | Expected MarketId | Equity panel |
| --- | --- | --- | --- |
| KOSPI | KOSPI | STK | retained |
| KOSDAQ | KOSDAQ | KSQ | retained |
| KOSDAQ GLOBAL | KOSDAQ | KSQ | retained |
| KONEX | KONEX | KNX | outside this contract |

`SourceMarket` retains the original observation's label, including historical
entry/exit. It is provenance, not a signal filter or a future-survival test.
Unknown/missing market labels and conflicting MarketId/SourceMarket fail before
a yearly file is written. No prefix guessing, price/return adjustment, share
class inheritance, or current-member backfill occurs. Preferred shares remain.

Historical files normally stay immutable. This explicitly inventoried repair
is separate from routine updates. Current-year refreshes retain all observed
KOSDAQ segments and regenerate their convenience matrices/status. The update
workflow is restricted to main, including manual runs; feature-branch pushes
cannot launch the full data pipeline or silently move a PR head.

## Deliberate historical repair

FinanceData/marcap commit `fbd246a94cf8a52a1637b8bce406532a8fd64124` is pinned in
[source_inventory.json](audits/kosdaq-global-repair/source_inventory.json), with
SHA256 identities for both upstream and original stored files. The source's
historical MarketId also confirms KSQ for GLOBAL observations.

Every previously stored Date/Code observation and retained field was compared
exactly against that pinned source. Only missing original GLOBAL observations
inside each stored window were appended, preserving original values. No missing
prices, returns, volumes or dates were manufactured. 2026 ends September 21 in
this repair; later upstream sessions are left to the ordinary current-year update.

| Year | Before rows | After rows | Appended observations | Affected codes |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 616,278 | 617,757 | 1,479 | 51 |
| 2023 | 625,422 | 637,754 | 12,332 | 52 |
| 2024 | 645,711 | 657,429 | 11,718 | 60 |
| 2025 | 655,753 | 667,913 | 12,160 | 56 |
| 2026 | 481,185 | 490,249 | 9,064 | 67 |
| Total | 3,024,349 | 3,071,102 | **46,753** | per-year counts above |

[repair_report.json](audits/kosdaq-global-repair/repair_report.json) records
before/after hashes, dates and exact retained-field checks. Each deterministic
`added-observations-YYYY.csv.gz` independently projects the original source's
Date/Code, market labels, Close, Volume, ChangesRatio and Stocks. Its SHA256 is
in the report. Tests compare all restored observations with those artifacts.
Report hashes describe this repair checkpoint; later valid current-year updates
may change a file's binary hash and extend its end date.

To reproduce, first download the five exact URLs in the inventory into a source
directory, then run from the repository root on the inventoried original files:

```bash
python scripts/repair_krx_market_segments.py \
  --manifest docs/audits/kosdaq-global-repair/source_inventory.json \
  --source-dir /path/to/pinned-source \
  --output /path/to/review/repair_report.json
```

Dry-run is the default. Inspect the report; explicit `--apply` performs the
repair. All years are verified/staged before any replacement; write failure
rolls back replaced yearly files. Source/hash drift, revised retained values,
duplicates and unrelated missing ordinary-market rows fail. Reapplying a
completed repair keeps dataset bytes unchanged and reports zero additions;
use another output directory to preserve the original positive-addition journal.

## Actual-data regression and remaining scope

`kr_equity_market_segment_research.json` is a software fixture, not an investment
recommendation. Its May 31, 2024 signal uses KOSDAQ, positive Volume and observed
Marcap of KRW 800 billion–1.2 trillion, then ranks Marcap high: 43 eligible codes,
including 11 then-observed GLOBAL codes. Top-N holds 30; deciles use all 43.
Both buy on June 3 and end June 18. An independent close-price oracle verifies
every gross/net daily NAV, original 9.5bp buy cost, held-return validation and
zero turnover/cost on June 14's segment change. Recreating the original omission
blocks both public modes before new outputs.

Code 287410's 89 GLOBAL sessions from June 14 through October 25 are restored,
including entry/exit around June 13/14 and October 25/28. Its full 2024 source
contains 207 observations. This repairs an ingestion omission; it does **not**
implement the later cash share exchange or delisting. Those need separate
primary evidence and an explicit cash-event execution contract.

The [repaired 2024 audit](audits/krx-history-2024-repaired/history_audit.json)
now has 257 >25bp price/reference candidates, zero internal observation gaps,
and 140/52 censored starts/ends. The
[repaired reconciliation](audits/corporate-actions-2024-repaired/corporate_action_reconciliation.json)
keeps all candidates: six match verified splits, 251 remain unmatched. Older
snapshots are preserved as before-repair evidence. These counts do not certify
complete corporate actions, dividends, total returns or all historical years.
