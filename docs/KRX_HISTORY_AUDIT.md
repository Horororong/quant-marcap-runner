# KRX source-history audit

The source audit checks observed data, not investment performance. It cannot
certify that every historical security, dividend or corporate action is present.
Read `AGENTS.md` and `BACKTEST_START_HERE.md` first.

## Required session gate

Preflight and both top-N/decile runners compare each requested market's dates
with the XKRX calendar over the complete requested interval. Missing beginning,
interior or ending sessions and unexpected dates stop execution. A KOSPI row
does not mask a missing KOSDAQ session. Weekends/holidays need no invented rows.
Success saves `history_coverage.json`. Preflight failures expose the full date
audit and retain `data_gap` classification. Calendar package version is recorded.
Historical calendar disagreements require source verification, not date filling.

## Detailed source diagnostics

```bash
python scripts/krx_history_audit.py \
  --start 2020-01-01 --end 2020-12-31 \
  --output-dir results/history-audit-2020
```

`--markets KOSPI KOSDAQ` is the default. Every requested yearly parquet must
exist. Missing files and malformed data produce a structured `history_audit.json`
and exit 3. Complete market-session presence exits 0, even when security-level
review candidates remain. Known CSV outputs are removed on source-load failure
so a reused output directory cannot expose stale candidates as the new result.

Outputs:

| File | Contents |
| --- | --- |
| `history_audit.json` | Source file SHA256 hashes, calendar/version/date coverage, counts, event-registry scope |
| `security_observation_coverage.csv` | First/last observation, observation count, censored endpoints, missing internal sessions by code |
| `history_review_candidates.csv` | Full gap, invalid-close and price/reference-return review candidates |

For consecutive XKRX observations with finite positive closes and finite
ChangesRatio, compare `Close_t / Close_previous - 1` with `ChangesRatio_t / 100`.
An absolute difference **greater than 25bp (0.0025 decimal return)** is a review
candidate. ChangesRatio is stored in percent; close-return differences are
recorded in basis points. This threshold is a documented diagnostic choice,
not an execution tolerance, correction or verified-event definition. Ordinary
two-decimal percentage rounding is below the threshold. Nonconsecutive code
observations are gap candidates and are excluded from this comparison.

Observed starts/ends are censored by the requested window. They must not be
labelled IPOs/delistings without evidence. Gaps can reflect data defects or
security events. Registered events are reported with source references; their
presence does not establish complete history. Candidates never change targets,
prices, NAV, eligibility or the corporate-action registry. Future observations
must never become a strategy's survival filter.

## Recorded source snapshots

The snapshots below were generated from the repository's actual yearly parquet
files. Their JSON records source SHA256 hashes and exchange_calendars 4.13.2.
The committed CSVs retain all review candidates; regenerate for the full per-code
coverage table.

| Requested period | Rows | Codes | Sessions per market | Close/reference differences >25bp | Internal gap candidates | Observed starts / ends inside window |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01-01–2020-12-31 | 580,252 | 2,426 | 248 | 290 | 0 | 102 / 38 |
| 2024-01-01–2024-12-31 | 645,711 | 2,758 | 244 | 256 | 1 | 150 / 61 |

Both markets match the calendar in both snapshots. Code 287410 has 89 missing
sessions between 2024-06-13 and 2024-10-28 observations. This is a source fact,
not a verified explanation. These archived snapshots used registry version 1, with one merger in 2020 and
no registered events in 2024. Registry version 2 subsequently adds the verified
EcoPro split in 2024, and version 3 adds BYC common/preferred. Neither snapshot
count certifies complete event history. The separate [corporate-action reconciliation](CORPORATE_ACTION_RECONCILIATION.md)
retains all candidates and checks exact registered split matches against source data.

- [2020 summary](audits/krx-history-2020/history_audit.json) and [candidates](audits/krx-history-2020/history_review_candidates.csv)
- [2024 summary](audits/krx-history-2024/history_audit.json) and [candidates](audits/krx-history-2024/history_review_candidates.csv)

Remaining work: audit other years, reconcile historical calendar differences,
verify relevant events with primary disclosures, expand explicit supported event handling. Public DSL runners now fail on
unresolved held-return discrepancies and support the registered EcoPro split;
see [HELD_RETURN_VALIDATION.md](HELD_RETURN_VALIDATION.md). The audit candidates
remain source observations, not automatic corrections or dividend/total returns.
CURRENT remains the sole performance calculator.
