from __future__ import annotations

"""Run the full DART history collector with known OpenDART availability fixes.

OpenDART's standardized financial-statement history has 2015 FY data, while
quarterly Q1/H1/Q3 bulk/structured history is reliably available from 2016.
The underlying collector originally generated 2015 quarterly tasks, which
wasted API quota as permanent NO_DATA rows.  This wrapper filters those tasks
before execution without changing the immutable task/state format.

Backtests must still use each filing's actual filing_date; this filter only
controls what the data collector requests.
"""

import backfill_dart_full_financials as base

_original_build_tasks = base.build_tasks


def build_tasks_fixed(mapping, now_kst):
    tasks = _original_build_tasks(mapping, now_kst)
    if tasks.empty:
        return tasks

    # 2015: standardized DART history is annual-only.  From 2016 onward retain
    # Q1/H1/Q3/FY for both CFS and OFS.
    bad_2015_quarter = (tasks["year"].astype(int) == 2015) & tasks["period"].isin(
        ["Q1", "H1", "Q3"]
    )
    return tasks.loc[~bad_2015_quarter].reset_index(drop=True)


base.build_tasks = build_tasks_fixed

if __name__ == "__main__":
    base.main()
