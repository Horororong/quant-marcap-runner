# Registered corporate-action source reconciliation

This is a source diagnostic, not a backtest or a completeness certificate.
It never changes registry records, candidates, prices, eligibility, holdings or
NAV. The held-return guard remains mandatory in both public DSL runners.

## Command and interpretation

```bash
python scripts/corporate_action_reconciliation.py \
  --start 2024-01-01 --end 2024-12-31 \
  --output-dir results/corporate-actions-2024
```

The command loads every requested yearly source file for KOSPI and KOSDAQ,
checks exact market sessions and records SHA256 hashes for source and registry.
It checks every registered event in the period, including records whose security
is absent from the source. It does not infer an event from a price ratio.

For a manually evidenced same-code split, require a finite positive share ratio,
zero cash, source metadata, a prior actual trade (positive Volume), a positive
resumption-day Close and Volume, and finite exchange return. All intervening
XKRX sessions must be observed: suspension Volume is zero, Close remains the last
traded value and ChangesRatio is zero or missing. Missing rows are not generated.
Then compare `share_ratio * event_close / last_trade_close - 1` with
`ChangesRatio / 100`, using the same 1bp rounding allowance as execution.

| Event status | Meaning |
| --- | --- |
| `reference_consistent` | The registered split and observed source agree within 1bp |
| `reference_mismatch` | The available values do not agree; investigate the source/record |
| `data_gap` | Price, reference, volume, observation interval or evidence metadata is missing/inconsistent |
| `invalid_event` | The event violates the same-code, ratio or zero-cash split contract |
| `unsupported` | This audit cannot compare this event type; merger disposal values need separate reconciliation |

Only a close/reference candidate with the **exact Code and event date** receives
the corresponding event status/source URL. Other codes, dates, observation gaps
and censored endpoints remain unresolved. Every original candidate row is kept.
The matching label is source agreement, not proof of complete history or a
holding-level result. Unsupported events never resolve a candidate.

Outputs are `corporate_action_reconciliation.json`, `registry_event_checks.csv`
and `candidate_reconciliation.csv`. Exit 0 / summary `ok` means the available
registered split checks and market dates pass. It does not mean all candidates
are explained. Exit 3 reports data gaps, invalid events or reference mismatches.
Source-load failure writes an error summary and removes stale CSVs in a reused
output directory. A valid diagnostic with event issues retains its detailed CSVs.

## BYC common and preferred split evidence

Reviewed on 2026-10-01. BYC's [2024-03-04 KIND decision](https://kind.krx.co.kr/external/2024/03/04/000699/20240226000932/91128.htm)
specifies KRW 5,000 to 500 par value, common shares 624,615 to 6,246,150,
preferred shares 215,385 to 2,153,850, suspension April 9–16 and scheduled
listing April 17. The [subsequent half-year report](https://kind.krx.co.kr/external/2024/08/14/002536/20240814008057/11012.htm)
confirms shareholder approval, completed April 12 split, unchanged capital and
the actual common/preferred totals. Actual KRX observations confirm April 17
trading resumption. Legal split effectiveness and trading resumption are distinct;
the execution registry uses trading resumption, as in the existing split contract.
The report is event verification evidence, not an April signal input.

Register 001460 and 001465 separately, each with share ratio 10. The last actual
trade was April 8. Source prices give the following **event-day checks**, without
dividends or a claim about investment performance:

| Security | Last traded Close | Resumption Close | Share-value return | Exchange rounded return |
| --- | ---: | ---: | ---: | ---: |
| BYC 001460 | 489,500 | 42,400 | −13.381001% | −13.38% |
| BYC preferred 001465 | 198,900 | 17,100 | −14.027149% | −14.03% |

Correct share-count adjustment preserves these real losses; it does not make
the event flat or erase adverse price movement. A missing preferred record
cannot inherit the common stock's event.

`config/strategies/kr_equity_split_classes_research.json` is a narrow execution
regression ending April 19. It filters the March 29 KOSPI cross-section by actual
signal-day nominal price (KRW 100,000–600,000), ranks Close high and selects 40
equal-weight holdings. The test also runs the full filtered universe as deciles.
An independent raw-price/share-count oracle verifies each day's gross/net NAV,
original buy costs and zero split cost in both modes. It checks that removing
only the preferred event stops execution before new outputs. This fixture is
not a recommended strategy or a broad-history performance result.

## Namyang share classes and APR autumn split evidence

Reviewed on 2026-10-01. Namyang's [official 2024-10-25 shareholder notice](https://company.namyangi.com/ko/investment/board/elect/detail?bbsSn=392)
specifies KRW 5,000 to 500 par value and ten shares per old share for both
classes: common 679,731 to 6,797,310 and preferred 200,000 to 2,000,000.
Its planned November 6 suspension start was subsequently revised. The
[completed KIND timeline](https://kind.krx.co.kr/external/2025/03/07/001066/20250307002609/11335.htm)
records actual suspension November 8–19, legal effectiveness November 12 and
new listing November 20. Actual KRX prices/Volume independently confirm this
trading interval. Register 003920 and 003925 separately on **November 20**.
The later disclosure verifies historical events only; it is never a factor input.

APR's [official shareholder notice dated 2024-09-20](https://www.apr-in.com/public-notice-view.php?page=1&wr_id=77)
confirms five shares per old share, KRW 500 to 100 par value. Its current website
reproduces that notice on 2025-03-28. The company's
[2024-07-31 release](https://apr-blog.com/apr-stock-split) planned suspension
October 18–30 and resumption October 31. Actual KRX source confirms those dates
and the five-for-one share-value return. Register 278470 on **October 31**;
the October 22 certificate-submission deadline is not trading resumption.

| Security | Last actual trade | Last traded Close | Resumption Close | Share-value return | Exchange rounded return |
| --- | --- | ---: | ---: | ---: | ---: |
| APR 278470 | 2024-10-17 | 266,500 | 50,100 | −6.003752% | −6.00% |
| Namyang 003920 | 2024-11-07 | 687,000 | 67,700 | −1.455604% | −1.46% |
| Namyang preferred 003925 | 2024-11-07 | 399,500 | 38,100 | −4.630788% | −4.63% |

These are event-day source checks, not portfolio or investment performance.
The real losses remain after share-count adjustment.

`config/strategies/kr_equity_autumn_splits_research.json` is a narrow actual-source
execution regression for September 2–November 22. Its September 30 signal uses
only then-observed KOSPI tradability and nominal prices (KRW 100,000–900,000),
ranks Close high and selects 30 equal-weight holdings. The same filtered universe
of 95 stocks is also run as ten independently capitalized deciles. The actual
next session is October 2 because October 1 is an XKRX holiday. A separate
raw-price/share-count oracle checks every gross/net daily NAV, the original buy
cost and zero event turnover/cost in both public modes. Removing any of these
three securities' own records, giving APR a wrong ratio or using Namyang's legal
date must fail the held-return guard before new outputs. This fixture does not
establish broad-history event coverage or recommend nominal-price investing.

## Archived 2024 checkpoint before segment repair

[Summary](audits/corporate-actions-2024/corporate_action_reconciliation.json),
[event checks](audits/corporate-actions-2024/registry_event_checks.csv) and
[all candidates](audits/corporate-actions-2024/candidate_reconciliation.csv)
record source/registry hashes and registry version 4. Six registered security
events (BYC common/preferred, EcoPro, Namyang common/preferred and APR) agree
with exchange references.
All 256 original >25bp price candidates remain in the report: six match
consistent registered splits and 250 remain unmatched by this audit. The one
internal gap and all censored endpoints also remain. These are source-observation
counts, not counts of distinct events, proven defects or executed losses.

Continue primary-source investigation, other years, explicit rights/spin-off/
delisting/dividend contracts and merger-value reconciliation. Never turn an
unresolved candidate into a future-survival filter or an automatic correction.

## Repaired 2024 checkpoint

After the deliberate [KOSDAQ segment repair](KRX_MARKET_NORMALIZATION.md), the
[new summary](audits/corporate-actions-2024-repaired/corporate_action_reconciliation.json),
[event checks](audits/corporate-actions-2024-repaired/registry_event_checks.csv) and
[all candidates](audits/corporate-actions-2024-repaired/candidate_reconciliation.csv)
record the repaired source hash: 257 price candidates, six consistent registered
splits, 251 unmatched price candidates and zero internal observation gaps.
The original report above is retained. Repairing a segment omission does not
verify a cash share exchange, delisting or the remaining event history.
