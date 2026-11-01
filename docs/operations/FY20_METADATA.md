# FY20 finite metadata collection · RESEARCH_ONLY

This is a prepared operating adapter, not a financial strategy or an executed
collection. Its manual-only workflow requires explicit publication/deployment
authorization before use. A source-budget approval alone is insufficient.

The exact full 20-company cohort is fixed in the approval JSON. Required fields
are 2009 calendar FY OFS revenue, net income, operating cash flow and equity.
No missing company, period or field is silently excluded. This is not a whole
market universe. Existing financial, publication and PIT gates stay unchanged.

## Request and response contract

- Official DART `list.json`: 2009-01-01 through 2010-04-30, report class A,
  `last_reprt_at=N`, 100 rows/page, at most two pages/company, at most 40 HTTP.
  This listing endpoint supports historical filings; modern financial-account
  APIs with a different supported period are not used for FY2009.
- Original `dsaf001/main.do`: exactly one per original receipt, at most 20 HTTP.
  HTML receipt presence means transport identity only, not a verified attachment
  chain or publication time. A changed/ambiguous menu stays held.
- `document.xml`: at most ten newly required material correction originals,
  only after offline review and immutable private target freeze. Original 20
  ZIPs must be reused. Corrections need complete company pagination, original
  receipt presence, exact list and menu fingerprints, a listed corrected
  FY2009 receipt and explicit affected core fields. An ambiguous correction
  relationship is not converted into an automatic financial approval.

An HTTP 200 or an empty status 013 never closes a version chain. Duplicate
receipts, wrong companies/dates/pages, inconsistent counts and invalid ZIP CRC
stay blocked. More than two pages are recorded as an unresolved source gap,
without fetching page three or blocking independent companies' inventories.
Metadata and inventory must be reviewed against retained originals before
any provider attestation. The collector never grants PIT or provider eligibility.

## Limits, private preservation and restart

The separate immutable FY20 grant is 70 HTTP / 2 executions total, at most
35 HTTP and 600 seconds per execution, zero retries, one execution per KST day,
expiry 2026-11-04 23:59:59 KST. Every list, document, failed source attempt and
authentication attempt consumes its source counter. GitHub control operations
are separately identifiable and do not count as DART source requests.

The same private journal stores an independent grant entry, preserving all
prior B/B2 counters, failures and raw responses. B/B2's remaining 11 HTTP and
zero executions cannot be transferred. Old finite-channel histories and active
source runs are checked; the workflow shares the existing concurrency group.
The prior B/B2 failure does not hold this new independent grant, but a same-day
old execution still consumes the shared daily opportunity. A new FY20 failure
or interrupted running lease holds that grant without automatic retry/reset.

The existing exact private repository, branch and storage primitives are reused.
No destination or credentials are copied into public output. Source responses
are content addressed, locally persisted before validation, privately saved and
read back. The journal is CAS-written before each HTTP attempt. If private
storage fails, the source call is not repeated. Safe diagnostics distinguish
raw existence check, CREATE, READBACK and journal CAS operations without bodies,
tokens, private paths or source digests in public logs.

The 600-second deadline includes hydration, history checks, source HTTP and
private persistence. Processing checkpoints before the deadline/per-run cap.
A later approved execution reuses complete cached responses. Finished work
requires no new lease. The two executions and time limits are ceilings, not a
guarantee that all 80 fields become eligible; unresolved corrections at the end
stay held. No schedule is configured or promised.

## Deployment after approval

Publish only the six files in the final transfer manifest to an operating
branch based on the recorded current main. Do not push the research branch's
unrelated ancestry. Open a reviewable PR; run the new workflow's validation and
existing required checks using the original pinned kit. Record actual code and
workflow SHAs. Merge only the minimal approved change after required checks.
Then manually dispatch `collect-fy20-asof-metadata.yml` on main with `collect`
true, after checking current expiry, shared day and remaining budget. The first
run normally collects inventory and metadata. A second permitted day may use
the private offline material-correction review. Do not rerun a failed job.

No new source secrets are needed: existing `DART_API_KEY` and
`B_PRIVATE_BACKUP_TOKEN` are injected only into the source/preservation step.
KRX authentication is unnecessary because retained official April 30 market
responses are reused. No source/financial data is uploaded to a public artifact,
release or source commit. No Internet pip, new server or paid service is used.
