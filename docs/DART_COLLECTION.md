# Durable broad DART collection

Collection storage/status contract 1. Engine, registry, machine contracts and
canonical performance are unchanged. Collected accounts are not automatically
exposed as validated factors.

## Active collector and broader scope

The September 17–October 1 commit history identifies the daily
`backfill-super-value-fast.yml` / `scripts/backfill_super_value_fast.py` path.
Its [September 30 scheduled run](https://github.com/Horororong/quant-marcap-runner/actions/runs/36770908185)
succeeded in 2h32m45s, producing the September 30 22:43 UTC state updates.
This establishes recent successful collection, not access to another GPT chat.

The workflow now explicitly sets `DART_COLLECTION_SCOPE=all_filings` and
`DART_STATEMENT_SCOPE=both`. It collects all mapped periodic legacy filings
(including original/correction receipts), and OFS even when CFS exists, with
CFS still prioritized. Direct script defaults preserve the previous
`signal_priority`/`cfs_first` behavior. Unknown scope values fail explicitly.
This does not resolve the existing 156 missing corp mappings or implement all
possible factors. The legacy store remains disconnected from the public DSL.

## Durable source and checkpoint contracts

- Whole API responses, including unknown fields/accounts, are compressed JSON
  under `data/financials/dart_raw/api/`. Request metadata is whitelisted; API
  keys and request URLs are excluded.
- Original ZIPs retain every member under
  `dart_raw/documents/<year>/<receipt>/<sha256>.zip`. Re-parsing reuses a
  checksum-verified cache. Corrupt caches fail explicitly.
- Full-history batch identity includes all source values, including amounts,
  excluding incidental collection time. Changed observations create new files;
  identical ones deduplicate. The prior key-only digest could discard changes.
- Generic full collection, scheduled fast collection and signal acceleration
  share `collect_task_batch()`. Signals no longer discard non-super-value
  account rows. Factor/provider semantics remain unchanged.
- Checkpoints default to 100 tasks/documents (`DART_CHECKPOINT_TASKS`). Atomic
  source writes precede terminal state. Failed/unsubmitted work resumes; a
  missing entire raw group invalidates its OK resume keys.
- Only a worker-sized request window is submitted. Quota/fatal errors stop new
  dispatch and drain existing requests. Errors produce nonzero exits and
  explicit phase/heartbeat/checkpoint run records.
- Shared local locks protect the generic and fast writers. Historical workflows
  share a concurrency group with running-job cancellation disabled. Separate
  machines still require one collection owner; locks are not a global quota.
- `DART_COLLECTION_MAX_SECONDS` reserves 20 minutes of job runtime for
  publication; in-flight requests drain. Commit/status steps run after collection
  failure. Failed publication has a 90-day raw/checkpoint recovery artifact.

Archives start with new downloads. Old terminal tasks are not all downloaded
again to manufacture archive coverage. Previously filtered source rows or absent
ZIPs may require explicit recovery before future providers can use them.

## Offline authoritative health

```bash
python scripts/dart_backfill_health.py
python scripts/dart_backfill_health.py --refresh
```

The first prints JSON from a byte-hashed state snapshot. The second refreshes
full task/period summaries and `data/status/dart_collection_health.json` under
the full-collector lock. No API calls, financial data edits or invented coverage.
`SNAPSHOT_ONLY` is distinct from collector success. Instrumented
`dart_*_collection_run.json` files record phase, heartbeat, checkpoint counts
and finish/error. Missing run records stay unknown; old running heartbeats are
identified using a configurable threshold, without claiming a live process.

Counts join current expected tasks to latest unique state: out-of-plan keys do
not inflate completion. OK, NO_DATA, errors, pending, mapping and raw-group gaps
remain distinct. Request completion and PARSED_4F are not validated PIT coverage.

October 1 both-scope snapshot: 222,884 expected, 123,260 terminal (89,366 OK +
33,894 NO_DATA), 99,624 remaining, 7,154 stored keys outside the current plan.
No whole OK raw group is missing. Approximately 55.3% is request completion,
not verified financial coverage or CFS-first strategy readiness.

## Storage, activation and tests

Identical content deduplicates; genuine source changes grow storage. Default
workflows commit immutable compressed archives for persistence beyond a runner.
Large ZIP archives should move to durable external storage before repository size
becomes impractical. `DART_RAW_ARCHIVE_DIR` accepts a persistent mounted or
synchronized directory; it does not itself upload to S3/Drive. The 90-day
recovery artifact is temporary backup, not permanent archival storage.

Feature-checkout changes do not update main's scheduler. Deploy verified code
to the collection owner before resuming. Local collection requires an environment
DART_API_KEY; GitHub uses the existing repository secret. This coding environment
has no key: tests use explicit software fixtures and real stored-state snapshots,
without launching live collection or fabricating new financial observations.

`scripts/test_dart_collection.py` covers source/cache/checksum failures, changed
amounts, atomic writes, current-plan counts, quota/fatal checkpoint/resume, time
budget, shared fast/signal writers, both scopes, all receipts and offline health.
Full Strategy DSL CI retains real DART/KRX/decile and CURRENT regressions.
