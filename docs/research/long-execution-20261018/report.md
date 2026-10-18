# Long-horizon research execution continuation

All results below are **RESEARCH_ONLY**, not brokerage-account, total-return
or investment PIT certification. DART investment PIT0/6 remains unchanged.

## What actually runs

| Specification | Complete requested period | Status / scope |
|---|---|---|
| Original size10deciles |2019–2020,494sessions| Preserved original selections, executions, costs, NAV and CURRENT metrics |
|3–1momentum top3|Full2020,248sessions| Existing registered technical provider and common engine; frozen outputs unchanged |
|Largest-cap top1|Full2024,244sessions| Frozen outputs unchanged |
|Previously predeclared largest-cap top1, fixed lag|2019–2025,1719sessions| Stage16 full real-data execution, independently validated and browser-tested in CI39083315071 |
|**New separately predeclared largest-cap top1, full-order deferral**|**2001–2025,6168sessions**| Complete JSON and Korean runs, cost NAV and CURRENT interactive report; independent18504book-days |

The new DSL is
`config/strategies/research_size_top1_2001_2025_deferred_v1.json`.
It was committed before any return for that specification: local
c689b9ab6952e8083859ce2ee85c3ee76866276d / remote
370c1fff064dcaa04be66f7374003864635fd2c1.
Historical KOSPI/KOSDAQ, KRW10trillion filter, April month-end, largest-cap
selection, earliest t+1close and original cost rates remain fixed. Its changed
execution policy is explicit, separately fingerprinted and **not** original
fixed-lag performance. The inherited metadata phrase about per-decile capital
does not create ten portfolios: the executable portfolio is top_n1, with one
initial KRW10million ledger and $10000-equivalent standardized report (no FX).

## Evidence and the precise2018 change

Four public KIND requests, zero retries, in successful CI39087969598 /
job117558426672. No new prices, financials or bulk history were collected.
All responses, sizes and hashes are in `source_manifest.json`; original bytes
are under `evidence/`. Official receipt20180503000318, document20180503000874:

https://kind.krx.co.kr/external/2018/05/03/000318/20180503000874/68155.htm

`evidence/20180503000318_body.html`, SHA256
`bf752ec862a850ba862e9d6b9a800ac2ced55b216b2c75f990627577fbc73f8c`:

-①㉯common128,386,494shares→6,419,324,700shares: exactly50:1.
-①㉰par5000→100;⑦common short codeA005930 and standardKR7005930003.
-②issuance2018-05-03;⑤changed listing2018-05-04. These are distinct facts.
- Search response preserves publication2018-05-03. No individual brokerage
  credit, independent full halt/legal calendar or full historical mapping claim.

Only this verified split row was appended to the existing registry; all prior
rows including Kakao remain a byte-identical prefix. Existing raw source rows
show Samsung close2650000 and zero volume2018-04-30/05-02/05-03, then close51900,
positive volume and ChangesRatio−2.08% on05-04. Quantity economics gives
`50*51900/2650000-1`; its difference from−2.08% is about0.453bp, within the
unchanged1bp guard. This calculation is not a claim of an independently
downloaded official reference price.

Original04-30selection excludes a zero-volume signal-date Samsung under the
unchanged tradability rule and selects SKHynix. The original scheduled Samsung
exit05-02 cannot fill. In the new explicitly modeled standing order, the entire
rebalance waits through05-02/03, earns old-position economics through05-04,
applies the50:1quantity change and then sells/buys at that close. No early
SKHynix exposure, partial order or inferred split is introduced.

## Common implementation

- `execution_scheduling.py` is a scheduling contract only. PROJECT still owns
  Gross/Net holdings, drift, cash, trading, fees and NAV. Top-N/deciles share it.
  Every delayed order retains signal, planned date, actual date, blocked
  observations and delay. A new pending conflict or unfilled requested-end
  order fails. Defaults stay reject. Deferred portfolios with stock-dividend
  rights, cash claims or merger interactions currently fail explicitly.
- `annual_selected_preparation.py` runs existing builders against all full
  annual original universes, preserving source hashes, full market calendars
  and provider audits. Only after selection does it project price observations
  to selected codes/verified successors. No survival filter, inferred rows,
  missing-price fill or changed eligible population. DART projection is rejected
  before source access; original PIT preparation and operating gates stay intact.
- Optional DSL fields are omitted from legacy normalized inputs when absent.
  Frozen fingerprints stay exact. New fields change fingerprint/plan and save
  `data_preparation.json` and explicit execution audits. Controlled Korean
  `--execution-contract-from` may add those flags only, never change lag/price.
- CURRENT remains the sole performance/report owner. Long-report calendar
  caching is bounded128entries instead of16; exact sessions and formulas stay
  unchanged. A25year month/prior-month report needs>50year/cross-year keys.
  The old16entry cache repeatedly evicted them between series and benchmark
  passes. A constructor-count test demonstrates50constructions/200hits over
  five passes, plus actual exact-session comparison with the original factory.
  The300second postprocess timeout is unchanged.
- Workbench process exit codes now use the existing run-status owner: failed4,
  data_gap3, capability_gap2, success0. They no longer conflate failed execution
  with data-gap exits. JSON/run status always retain actual failure details.

Engineexec7 / registry9 / machine27 describe this additive contract evolution.
No metric formula, ordinary1bp tolerance, financial value or investment gate
was relaxed. No internet dependencies were installed.

## Actual validation and preservation

`results/summary.json`, `commands.json`, `post_completion_checks.json` and
`local_validation/` preserve actual execution evidence. Local release validation
made no requests. Both full25year requests completed NAV+report. NAV, targets,
metrics and canonical NAV match byte-for-byte across JSON/Korean; full selections
match exactly after the registered factor audit label mapping (`size`/`Marcap`).

The independent oracle reads original annual data and independently derives
all April rankings, pending orders, first-liquid-close dates and share/cash/fees.
It does not use engine returns, weights or resolved schedules as expectations.
18504book-days across6168sessions match, maximum absolute NAV error
0.0000022351741790771484KRW, below the existing0.00001KRW tolerance.
It checks the engine schedule only after independently deriving the dates.

The actual original2019–2020 ten portfolios also completed through the new
annual projection, with no new execution policy. Its selection, root target,
execution schedule and trade bytes match the PRE-CHANGE frozen archive.
NAV and both CURRENT numeric files match old pins; independent14820book-days
match within unchanged tolerance. This is a real-data test of both portfolio
paths, not just a synthetic top1test.

The original19command suite, original DART E2E included, completed with all
exit0. Existing five research/sensitivity runs and Korean replay completed,
all15prior numeric files retain old hashes. The frozen151file archive audit
finds130exact files,9explicit metadata/preflight contract evolutions and
12preserved volatile envelopes. No expected numeric pins were replaced.
The Stage16 executable checker alone has its reviewed version tuple updated;
its immutable old plan snapshots and all other plan fields remain exact.

New scheduler/preparation/calendar modules have15current unit cases;
Workbench has5cases including failure/data-gap exit distinctions. The initial
local validation log contains the earlier5case preparation suite; the added
early-DART rejection is separately verified in its6case log and runs in final CI.

Stage16's82original report/source/result files are pinned separately; its
original registry prefix is pinned. Existing849preservation checks, financial
518/518, core64/64 and original60 retained bytes pass the old preservation owner.
Original prices, old audit records, Stage6ZIP and151file archive remain intact.

Initial failures are preserved, not erased:

- First long NAV and independent ledger passed; its report hit the unchanged
 300second timeout because the already-running child had the16entry calendar
 cache. Wrapper exit3/run status failed/postprocess are preserved. Its NAV is
 byte-identical to the subsequent complete run after the cache fix.
- Initial missing-price unit case incorrectly expected an already registered
 suspension contract to fail; corrected fixture now checks an unregistered
 ordinary gap. No production suspension behavior was weakened.
- Initial annual comparison fixtures used a column order different from the
 actual registered loader; fixture now uses the exact required column order.
- First independent index comparison rejected microsecond-versus-nanosecond
 storage units. Exact instants are now compared after explicit unit conversion;
 no dates, values or accounting tolerance changed.

## Remaining exact blockers and model limits

| Request | Remaining outcome |
|---|---|
|Original fixed-lag deciles2019–2025|FAIL execution constraint:003550LG2021-05-03scheduled exit, observed zero volume and official halt. No source file can make that original-day fill possible.|
|Original deciles2001–2025|FAIL strategy population: first2001-04-30signal only4eligible,10required under the original cap filter.|
|Original fixed-lag top1,2001–2025|FAIL2018-05-02Samsung exit during zero-volume halt. New separate deferral result does not change it.|
|2026requests|UNVERIFIED source/calendar mismatch06-03and07-17 and exact KOSPI benchmark closes missing after09-17; no completion through2026claimed.|
|Deferred orders interacting with rights/cash/mergers|Explicit capability gap until independent pending-order/illiquid-claim settlement tests and event evidence are available.|

Data facts and research assumptions remain separate. Observed positive volume
does not certify legal listing, an actual attainable whole-portfolio close fill
or market impact. The research model uses continuous quantity and fixed
illustrative trading costs, not a historical-tax-certified account. Unmodeled
cash distributions, rights issues and recoveries are not reconstructed here;
these price/cap results are not a complete cash-dividend total-return study.
Corporate-action completeness outside selected exposure is unverified.
Later official documents are historical fact checks, not retroactive factors.
Named-calendar/source equality is research validation, not new official2007PIT
certification. Financial investment PIT remains0/6.

Next minimal development is a separately predeclared execution model for
nontradable orders interacting with spin-off/stock-dividend/receivable claims,
starting with exact LG/LX entitlement and trading evidence. It must not be
called the original fixed-lag result.2026requires exact original calendar/day
and benchmark source resolution. No user upload or extra permission is needed
to reproduce the now-completed price/cap examples from current repository data.

## Publication / actual CI

Earlier Stage16 final CI39083315071 succeeded at remote
5eb2951fdba20fa8ccac298aed92610f15c24782, including browser and financial/original
restoration. Artifact12119563583 retains29242834bytes.
The new implementation was published and read back as remote
0acfed11e5a4af6ded40319807dd47b48aab9d2a, tree
f6e8f3328d64375a5970d4171a66e5c54716baf0, byte-identical to its local tree.

This report is written before the final evidence commit is sent, so it does
not claim that future CI has passed. The final `[stage16] [long-research]`
commit must actually run both `stock-dividend-regression` and
`explicit-long-research`, the latter with fresh `--check`, real browser and
artifact upload. Exact final SHA/run/jobs/artifacts are read from GitHub and
reported after completion. A skipped source job is expected and is never
counted as a tested research job. No new primary requests occur in final CI.
