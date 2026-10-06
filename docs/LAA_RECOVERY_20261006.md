# LAA execution and recovery checkpoint · 2026-10-06 UTC

## Actual outcome

The original user request is preserved in `config/allocation/laa.json`: IWD, GLD,
IEF each 25%; a 25% QQQ/SHY sleeve; SHY only when S&P500 Close is below its
200-session mean AND the latest publicly released unemployment rate is above
its 12-calendar-month mean. Annual full rebalance at the first January session
close; other months only switch the timing sleeve at the first session close,
using the previous session's month-end information. Initial cash anchor is
2004-11-18; first purchase is next-session close. Fixed sleeves do not trade
on timing-only switches. Costs are 0/5/15bp on each dollar bought or sold,
including initial entry. USD, no taxes, no FX. Revised historical macro values
are explicitly accepted for this initial study; vintage correctness remains
unverified. The nominal 10% target is not a backtest result.

`allocation_backtest.py` is a separate reusable allocation executor. The frozen
kit's registered DSL still supports only `kr_equity`; no ETF capability is
claimed for that DSL. Kit code, original price/UNRATE files, backfill state,
collector and schedules were not changed.

Actual requested span remains **2004-11-18 through 2026-10-02**. All six ETF
series (including SPY benchmark) pass exact XNYS session coverage with zero
missing/extra dates, nonfinite or nonpositive adjusted prices. The S&P500 input
includes its full 200-session warmup. This is coverage validation, not an
independent certification of distribution adjustments.

Final run: `results/laa/run-20261006-v2/run_status.json`, **exit 3 / data_gap /
phase preflight / nav_ready=false / report_ready=false**. The first run is
preserved separately in `results/laa/run-20261006`; it treated every missing
macro mean as fatal. Final code correctly evaluates the AND rule without
inventing a macro value when price >= MA already determines QQQ. Ten monthly
macro quality gaps remain visible, of which **one affects selection**:

- Signal **2026-03-31**, execution **2026-04-01**.
- S&P500 Close 6528.52001953125, 200-session mean 6638.858090820312.
- Latest evidenced release: February 2026 observation, released 2026-03-06.
- Twelve-calendar-month window: March 2025 through February 2026.
- October 2025 has stored value **4.4**, but no official observation/release.

[BLS November 2025 original release](https://www.bls.gov/news.release/archives/empsit_12162025.htm)
explicitly states October household survey data were not collected. The
[BLS archive](https://www.bls.gov/bls/news-release/empsit.htm) marks that month
not published. A missing official observation cannot be recovered by another
download, monthly lag, interpolation, excluding the month from the MA, or
silently carrying another value. The repository's 4.4 was preserved, not used
as a proven published observation. No NAV, CAGR, MDD, Sharpe or report was
published. No shortened-period performance was substituted.

Eight independent tests pass under the verified dedicated Python, covering
public release timing, missing official observations, exact sessions, initial
purchase costs, self-financing annual weights, timing-switch fees, old-asset
return through execution, unchanged fixed dollar holdings, strict inequalities
and the AND decision boundary. These are local tests; no remote CI or main
deployment is claimed. Output manifest SHA256 and sizes were independently
rechecked; all eight listed result files match. No metrics or daily NAV files
exist in the final blocked run.

## Failed commands and recovered environment

1. Original ambient Python was
   `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`
   (resolved Python 3.12.14). It was not the quant project's dedicated Python.
2. Internet pip installation failed while trying to connect through the proxy:
   `NewConnectionError("HTTPSConnection(host='proxy', port=8080): Failed to establish a new connection: [Errno 1] Operation not permitted")`.
   The initial call yielded session 66632; no final process exit was captured.
3. Two subsequent extra-network-permission tool attempts were **aborted by the
   user**, after 4883.9s and 259.0s. They have no process exit code and do not
   establish execution or installation. Neither requested `/tmp/laa_deps` nor
   `/tmp/laa_bls_archive.html` existed on recovery. No such commands were retried.
4. Historical runtime paths in prior checkpoint documents were absent. No local
   kit manifest, wheel cache or dedicated runtime was found. An `rg` scan of
   `/tmp` hit a protected daemon directory (exit 2); direct checks of the three
   documented runtime paths confirmed their absence. This was distinguished
   from a successful complete-filesystem scan.
5. Original kit artifacts from CI **37157470156**, source
   **822c435f4b6148c2832e12370a6ccb324a9e875f**, were restored through the GitHub
   connector. Ledger artifact **11286469722**, 13 transport artifacts, their
   artifact digests, inner segment digests, full ZIP SHA and all ZIP CRCs passed.
   ZIP: 311922550 bytes,
   SHA256 `f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784`.
6. The original standard-library-only `bootstrap_quant.py` restored the exact
   pinned kit into a new destination with its bundled wheels and offline
   installer. The seed Python only performed archive hashing/restoration and
   the original bootstrap; it did not execute the strategy or replace missing
   packages. No internet pip installation or package version changes were used.
   Bootstrap actual exit **0**, status **ok**. The prior runtime was not
   overwritten; it was absent.
7. Dedicated Python:
   `/workspace/scratch/laa-recovery/runtime/.venv/bin/python`.
   `sandbox_runtime.py verify` actual exit **0**, status **ok**, kit
   `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`.
   Bootstrap/verify stdout and stderr are preserved in
   `/workspace/scratch/laa-recovery/`. Each strategy run repeats verify and
   stores the exact process exit and outputs.

Primary release lookup produced four invalid HTML/TXT link resolutions. The
equivalent PDF links in the same BLS archive were read instead, and their dates
match the original publication filenames/headers. All **274** sourced release
dates (November 2003–September 2026, excluding unpublished October 2025) are
stored with original URLs in `US_UNEMPLOYMENT_RELEASE_DATES.csv`. Release-date
coverage is not a vintage-value or all-original-header audit. September 2025's
actual delayed release is 2025-11-20, not October's first Friday. The ALFRED
release list was only inspected as a cross-check; its list can include revisions
and was not automatically mapped to observation months.

## Preservation and exact resume

Local/main baseline **c087007ee6923dc7039caa71ff70ea337401a274** was directly
rechecked on GitHub. Its completed data commits were preserved. No backfill,
collector, existing strategy run or remote commit was repeated.

Original archives, transport pieces, download ledger and manifest are under
`/workspace/scratch/laa-recovery/`. Recovered kit manifest is
`/workspace/scratch/laa-recovery/runtime/kit_manifest.json`. Result directories
refuse overwrites. Recovery runtime files are outside the source repository.

Before any subsequent calculation:

```bash
timeout 60 /workspace/scratch/laa-recovery/runtime/.venv/bin/python -I /workspace/scratch/laa-recovery/runtime/scripts/sandbox_runtime.py verify
/workspace/scratch/laa-recovery/runtime/.venv/bin/python -I tests/test_allocation_backtest.py
```

Unchanged-input reproduction of the same diagnostic, with a new output path:

```bash
/workspace/scratch/laa-recovery/runtime/.venv/bin/python -I scripts/allocation_backtest.py --repo-root /workspace/quant-marcap-runner --kit-root /workspace/scratch/laa-recovery/runtime --config config/allocation/laa.json --output-dir results/laa/run-resume-001
```

Expected unchanged outcome is **exit 3**, not performance success. Re-running
without a source/rule change adds no recovery. The next dependent action requires
the owner's explicit missing-observation policy. A rule such as holding the
existing timing ETF when an indispensable signal is unavailable would be a new
strategy rule, not restoration of the nonexistent October observation. It was
offered for clarification but has not been applied. Changing the twelve-month
definition or using a shorter end date also requires explicit scope change.

If a new session loses the runtime again, restore the exact kit from
[the original release](https://github.com/Horororong/quant-marcap-runner/releases/tag/quant-report-26e4ec02e569)
or the CI artifacts listed in `docs/audits/laa-recovery-20261006/transport_inventory.json`.
Verify ledger/segments/full original ZIP and bootstrap from its unmodified parts
with the supported 3.11/3.12 seed Python. Run the dedicated `verify` before any
computation. Do not install internet packages, alter the manifest, or run the
strategy under ambient Python.
