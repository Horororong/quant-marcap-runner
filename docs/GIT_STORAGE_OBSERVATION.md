# Four-week Git storage observation

The recent DART storage fix is integrated independently from the other feature
branches. It does not deploy broad raw-ZIP archival, strict DSL input validation
or checked execution orchestration. Engine/provider/generated contracts and the
existing data/results trees are preserved.

## Baseline and automatic observation

`config/git_storage_baseline_20261001.json` records the pre-integration main
commit `b763c5ca903d652a815bbdbff6df978843a45c86`. This is a real read-only Git
measurement, not an estimate of file contents. It includes 1,305,337,466 bytes
at HEAD and 3,331,926,677 logical bytes across 3,760 unique reachable blobs.
Logical history bytes are **not** compressed Git storage; the original clone's
pack occupied approximately 1.21 GiB. Do not compare logical totals directly to
a 3–5 GB physical-storage migration threshold.

`.github/workflows/observe-git-storage.yml` runs on deployment, manual dispatch
and Thursdays 02:20 UTC / 11:20 KST. Scheduled full-history observations run on
October 8, 15, 22 and 29. From October 30 UTC the gate skips full downloads;
manual/push observations remain available. Review after two and four weeks.

The job uses read-only permissions, no API key, no financial API calls and no
Git commit. JSON reports are Actions artifacts retained for 90 days. Record the
workflow run ID and artifact before expiry if longer retention is needed.
Full checkout transfers about the repository's compressed history each week;
this is intentionally limited to four weekly samples. No GC, pruning, repacking,
history rewrite or financial source modification is performed.

## Measurement meanings

`git_storage_snapshot.py` fixes a commit before measurement and requires full
history. It rejects shallow totals instead of presenting incomplete history.

- `head_bytes` and `head_by_category`: currently tracked bytes/file counts.
- `history_logical_blob_bytes`: one full logical size per unique blob reachable
  from the sampled commit, not one copy per commit. Other feature branches do
  not inflate the sampled main history.
- `history_by_category`: DART recent/full/raw, KRX yearly/derived, results and
  other groups. A reused blob is counted once; actual changed gzip adds a blob.
  Git's object-to-path choice is an attribution approximation for shared blobs.
- `clone_object_store`: compressed pack and loose bytes in this clone, possibly
  including other fetched refs. This is not GitHub's server accounting. Packing,
  Git version and fetched refs vary between clones; use the logical per-category
  growth alongside this physical indication, not physical deltas alone.
- `growth_since_baseline`: elapsed days, current-tree and unique-history deltas.
  A baseline must belong to the sampled commit's ancestry. No extrapolated
  annual rate is automatically claimed from a one-time backfill.

Compare recent **HEAD file count**, unique historical blob count and bytes.
During the first old-offset tail and first aligned cycle, some new boundary
files can still appear. After alignment with the same company set and batch size,
14 boundaries repeat for 3,933 companies. Changed filings/amounts, changed
company membership and calendar-year rollover legitimately create versions.
Old overlapping files remain present; no cleanup is implied.

Track DART recent separately from full-history/raw backfill and KRX. Otherwise
successful one-time backfill could hide the reduction in refresh churn. Inspect
`dart-recent-status` artifacts for run heartbeat/changed paths and actual rotation
progress. State-only commits can remain necessary for the next company offset.

## Local usage

```bash
python scripts/git_storage_snapshot.py \
  --baseline config/git_storage_baseline_20261001.json \
  --output /tmp/new-storage-observation.json
```

Output must be new. The script is standard-library-only and does not expose
remote credentials or read API environment values. Four fixture regressions
cover unchanged/changed gzip blob accounting, Unicode paths, branch isolation,
shallow/foreign baseline rejection, timestamp ordering and source preservation.
The full Strategy DSL workflow includes these tests and the nine recent-writer
regressions, in addition to all existing main regressions.
