# Collection outcome observability; no collection-policy change

Existing collector intentionally returns process exit0 for a gate refusal:
NO_COLLECTION/OBSERVATION_STOPPED_OR_UNREVIEWED, expiry, daily ceiling, etc.
The scheduler workflow treated successful process exit as an ordinary green job.
Scheduled calls do not carry explicit Q3/supplemental approval inputs, so enter
the original finite observer, whose PAUSED_QUEUE state is outside READY_FIRST/NEXT.
A green observation therefore does not mean source collection or validation.
10/26run40240641770/10/25run40138686177 job steps and unchanged checkpoint are
preserved; old raw log and6275B gate artifact downloads both failed, not retried.
Exact historic emitted reason text is not claimed as directly read. Code/state
indicate OBSERVATION_STOPPED_OR_UNREVIEWED before an actual source lease.

New reporter snapshots ledgers before/after, reads original output evidence and
publishes machine outcome plus job summary: workflow invocation, process start/
finish, source start, source HTTP, new original count, checkpoint change, extracted
candidate count, semantic/PIT/engine increases. Source gaps with no archive and
zero-work/expiry are never RAW_COLLECTED. Missing evidence remains unknown.
NO_COLLECTION can keep a successful process status, while the business outcome
and notice explicitly say no collection. Financial increments remain0 because
no semantics/PIT certification runs in this collection workflow.

64local tests PASS. Collector/source-owner hashes, lease/checkpoint, HTTP/time/
run/daily gates unchanged. No Internet pip, DART call, schedule addition or source
retry. Reporting code not published/deployed/remote-CI tested. Existing cron is
still an observation schedule, not automatic approved Q3/FY resume.

ONCE_PER_KST_DAY is project policy retained by explicit user approval, not a DART
external mandate. Config finite1/day is separate from source HTTP budget, response
020/RATE_LIMIT and600-second execution budget. Session inactivity never schedules
future work. External DART remaining quota is not inferable from our6HTTP count.

FY20 window expired2026-10-26KST23:59:59. Proposed finite renewal is JSON, not active
configuration: one execution/20exactreceipts/40HTTPincludingretries/600seconds,
notbefore10/27KST,expiry10/28KST23:59:59. Original3runhistory+FY21used42reserved/
21actualHTTP andQ3singleused6HTTP retained. No quota reset or batch substitution.
Publication/minimal operating PR+CI+merge and this exact finite window amendment
need approval; never dispatch from this unreviewed research branch.
