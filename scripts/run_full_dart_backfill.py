from __future__ import annotations

"""Run the full DART history collector with PIT-safe availability rules.

OpenDART's standardized financial-statement history has 2015 FY data, while
quarterly Q1/H1/Q3 structured history is reliably available from 2016.
The wrapper removes permanently unavailable 2015 quarterly tasks and writes
coverage diagnostics for the backtest pipeline.

Important:
- Backtests must use each filing's actual filing_date.
- Completed task keys are never requested again by the historical backfill.
- Once all currently available historical tasks are complete, scheduled runs
  become lightweight no-ops until a genuinely new report period becomes
  available. The separate recent-DART refresh workflow continues to revisit
  recent years so amendments/corrections are captured.
"""

from pathlib import Path

import pandas as pd

import backfill_dart_full_financials as base

_original_build_tasks = base.build_tasks
_latest_tasks = pd.DataFrame()

COVERAGE_FILE = Path("data/status/dart_pit_coverage_by_period.csv")
COVERAGE_STATUS_FILE = Path("data/status/dart_pit_coverage_status.csv")


def build_tasks_fixed(mapping, now_kst):
    global _latest_tasks

    tasks = _original_build_tasks(mapping, now_kst)
    if tasks.empty:
        _latest_tasks = tasks.copy()
        return tasks

    # 2015: standardized DART history is annual-only. From 2016 onward retain
    # Q1/H1/Q3/FY for both CFS and OFS.
    bad_2015_quarter = (tasks["year"].astype(int) == 2015) & tasks["period"].isin(
        ["Q1", "H1", "Q3"]
    )
    tasks = tasks.loc[~bad_2015_quarter].reset_index(drop=True)
    _latest_tasks = tasks.copy()
    return tasks


def _normalise_task_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["stock_code"] = out["stock_code"].astype(str).str.zfill(6)
    out["corp_code"] = out["corp_code"].astype(str)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["period"] = out["period"].astype(str)
    out["fs_div"] = out["fs_div"].astype(str)
    return out


def write_pit_coverage(tasks: pd.DataFrame) -> None:
    """Write an explicit year/period coverage table for research gating.

    A task is complete only when its CFS/OFS request has a terminal status
    (OK or NO_DATA). NO_DATA is still a completed API task; it must not be
    silently treated as usable financial data. Codes with at least one OK task
    are reported separately from task-completion percentages.
    """
    COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    generated_at = pd.Timestamp.now(tz="UTC").isoformat()

    key_cols = ["stock_code", "corp_code", "year", "period", "fs_div"]
    expected = _normalise_task_keys(tasks)
    if expected.empty:
        pd.DataFrame(
            columns=[
                "year",
                "period",
                "expected_tasks",
                "completed_tasks",
                "remaining_tasks",
                "ok_tasks",
                "no_data_tasks",
                "error_tasks",
                "task_completion_pct",
                "expected_codes",
                "completed_codes",
                "codes_with_data",
                "code_completion_pct",
                "data_available_pct",
                "generated_at_utc",
            ]
        ).to_csv(COVERAGE_FILE, index=False, encoding="utf-8-sig")
        pd.DataFrame(
            [
                {
                    "mode": "NO_AVAILABLE_TASKS",
                    "historical_backfill_complete": True,
                    "expected_tasks": 0,
                    "completed_tasks": 0,
                    "remaining_tasks": 0,
                    "completion_pct": 100.0,
                    "fully_completed_years": "",
                    "first_year": "",
                    "latest_year": "",
                    "generated_at_utc": generated_at,
                }
            ]
        ).to_csv(COVERAGE_STATUS_FILE, index=False, encoding="utf-8-sig")
        return

    expected = expected[key_cols].drop_duplicates().copy()

    if base.TASK_FILE.exists():
        state = pd.read_csv(
            base.TASK_FILE,
            dtype={"stock_code": str, "corp_code": str},
            low_memory=False,
        )
        state = _normalise_task_keys(state)
        if "updated_at_utc" in state.columns:
            state = state.sort_values("updated_at_utc")
        state = state.drop_duplicates(key_cols, keep="last")
        state = state[key_cols + ["status"]]
    else:
        state = pd.DataFrame(columns=key_cols + ["status"])

    merged = expected.merge(state, on=key_cols, how="left")
    merged["status"] = merged["status"].fillna("PENDING").astype(str)
    merged["is_complete"] = merged["status"].isin(["OK", "NO_DATA"])
    merged["is_ok"] = merged["status"].eq("OK")
    merged["is_no_data"] = merged["status"].eq("NO_DATA")
    merged["is_error"] = merged["status"].eq("ERROR")

    code_period = (
        merged.groupby(["year", "period", "stock_code"], dropna=False)
        .agg(
            expected_tasks=("fs_div", "size"),
            completed_tasks=("is_complete", "sum"),
            has_data=("is_ok", "max"),
            has_error=("is_error", "max"),
        )
        .reset_index()
    )
    code_period["is_complete"] = (
        code_period["completed_tasks"] == code_period["expected_tasks"]
    )

    task_summary = (
        merged.groupby(["year", "period"], dropna=False)
        .agg(
            expected_tasks=("status", "size"),
            completed_tasks=("is_complete", "sum"),
            ok_tasks=("is_ok", "sum"),
            no_data_tasks=("is_no_data", "sum"),
            error_tasks=("is_error", "sum"),
        )
        .reset_index()
    )
    code_summary = (
        code_period.groupby(["year", "period"], dropna=False)
        .agg(
            expected_codes=("stock_code", "nunique"),
            completed_codes=("is_complete", "sum"),
            codes_with_data=("has_data", "sum"),
        )
        .reset_index()
    )

    coverage = task_summary.merge(code_summary, on=["year", "period"], how="left")
    coverage["remaining_tasks"] = (
        coverage["expected_tasks"] - coverage["completed_tasks"]
    )
    coverage["task_completion_pct"] = (
        100.0 * coverage["completed_tasks"] / coverage["expected_tasks"]
    ).round(2)
    coverage["code_completion_pct"] = (
        100.0 * coverage["completed_codes"] / coverage["expected_codes"]
    ).round(2)
    coverage["data_available_pct"] = (
        100.0 * coverage["codes_with_data"] / coverage["expected_codes"]
    ).round(2)
    coverage["generated_at_utc"] = generated_at

    period_order = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}
    coverage["_period_order"] = coverage["period"].map(period_order).fillna(99)
    coverage = (
        coverage.sort_values(["year", "_period_order"])
        .drop(columns="_period_order")
        .reset_index(drop=True)
    )
    coverage.to_csv(COVERAGE_FILE, index=False, encoding="utf-8-sig")

    total_expected = int(coverage["expected_tasks"].sum())
    total_completed = int(coverage["completed_tasks"].sum())
    total_remaining = int(coverage["remaining_tasks"].sum())
    year_summary = (
        coverage.groupby("year", dropna=False)[["expected_tasks", "completed_tasks"]]
        .sum()
        .reset_index()
    )
    full_years = year_summary.loc[
        year_summary["expected_tasks"] == year_summary["completed_tasks"], "year"
    ].astype(int).tolist()

    complete = total_remaining == 0
    mode = "RECENT_ONLY_READY" if complete else "BACKFILL_ACTIVE"
    summary = pd.DataFrame(
        [
            {
                "mode": mode,
                "historical_backfill_complete": complete,
                "expected_tasks": total_expected,
                "completed_tasks": total_completed,
                "remaining_tasks": total_remaining,
                "completion_pct": round(
                    100.0 * total_completed / total_expected, 2
                )
                if total_expected
                else 100.0,
                "fully_completed_years": ",".join(map(str, full_years)),
                "first_year": int(coverage["year"].min()),
                "latest_year": int(coverage["year"].max()),
                "generated_at_utc": generated_at,
            }
        ]
    )
    summary.to_csv(COVERAGE_STATUS_FILE, index=False, encoding="utf-8-sig")

    print(
        f"PIT coverage mode={mode} completed={total_completed}/{total_expected} "
        f"remaining={total_remaining} full_years={full_years}",
        flush=True,
    )


base.build_tasks = build_tasks_fixed

if __name__ == "__main__":
    base.main()
    write_pit_coverage(_latest_tasks)
