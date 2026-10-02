from __future__ import annotations

# manual-safe-trigger-20260924-1

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(".")
STATUS_DIR = Path("data/status")
STATUS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATUS_DIR / "super_value_fast_backfill_status.csv"

MODERN_LIMIT = max(0, int(os.getenv("SUPER_VALUE_FAST_MODERN_TASKS", "8000")))
LEGACY_LIMIT = max(0, int(os.getenv("SUPER_VALUE_FAST_LEGACY_DOCS", "5000")))
MODERN_WORKERS = max(1, min(8, int(os.getenv("SUPER_VALUE_FAST_MODERN_WORKERS", "6"))))
LEGACY_WORKERS = max(1, min(8, int(os.getenv("SUPER_VALUE_FAST_LEGACY_WORKERS", "6"))))

# Make the legacy index finish quickly. The imported module reads these at import time.
os.environ.setdefault("LEGACY_DART_INDEX_TASKS", os.getenv("SUPER_VALUE_FAST_LEGACY_INDEX_TASKS", "180"))
os.environ.setdefault("LEGACY_DART_MAX_DOCS", str(LEGACY_LIMIT))
os.environ.setdefault("LEGACY_DART_WORKERS", str(LEGACY_WORKERS))


def import_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


modern = import_module("dart_modern_fast", "scripts/backfill_dart_full_financials.py")
legacy = import_module("dart_legacy_fast", "scripts/backfill_dart_legacy_2000_2014.py")


def terminal_state_map(path: Path) -> dict[tuple[str, str, int, str, str], str]:
    if not path.exists():
        return {}
    s = pd.read_csv(path, dtype={"stock_code": str, "corp_code": str})
    if s.empty:
        return {}
    s["stock_code"] = s["stock_code"].astype(str).str.zfill(6)
    s["year"] = pd.to_numeric(s["year"], errors="coerce").astype("Int64")
    out = {}
    for _, r in s.dropna(subset=["year"]).iterrows():
        key = (
            str(r["stock_code"]).zfill(6),
            str(r["corp_code"]),
            int(r["year"]),
            str(r["period"]),
            str(r["fs_div"]),
        )
        out[key] = str(r["status"])
    return out


def task_key(r) -> tuple[str, str, int, str, str]:
    return (
        str(r["stock_code"]).zfill(6),
        str(r["corp_code"]),
        int(r["year"]),
        str(r["period"]),
        str(r["fs_div"]),
    )


def process_modern_batch(tasks: pd.DataFrame) -> tuple[list[dict], list[dict], bool]:
    states: list[dict] = []
    rows: list[dict] = []
    rate_limited = False
    if tasks.empty:
        return states, rows, rate_limited

    with ThreadPoolExecutor(max_workers=MODERN_WORKERS) as ex:
        futs = {ex.submit(modern.process_task, r.to_dict()): r.to_dict() for _, r in tasks.iterrows()}
        n = 0
        for fut in as_completed(futs):
            task = futs[fut]
            try:
                state, recs = fut.result()
                states.append(state)
                rows.extend(recs)
            except modern.RateLimitExceeded as e:
                rate_limited = True
                states.append({
                    **task,
                    "status": "ERROR",
                    "rows_saved": 0,
                    "error": f"RATE_LIMIT: {e}",
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                })
            except modern.FatalDartError:
                raise
            except Exception as e:
                states.append({
                    **task,
                    "status": "ERROR",
                    "rows_saved": 0,
                    "error": repr(e),
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                })
            n += 1
            if n % 500 == 0 or n == len(tasks):
                print(f"super-value modern fast progress {n}/{len(tasks)}", flush=True)
    return states, rows, rate_limited


def modern_fast() -> dict:
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)

    corp = modern.load_all_dart_corps()
    mapping = modern.build_historical_code_map(corp, now_kst)
    tasks = modern.build_tasks(mapping, now_kst)
    if tasks.empty:
        return {"modern_total_cfs": 0, "modern_cfs_done": 0, "modern_fallback_done": 0,
                "modern_run_tasks": 0, "modern_rate_limited": False}

    states0 = terminal_state_map(modern.TASK_FILE)
    terminal = {"OK", "NO_DATA"}

    cfs = tasks[tasks["fs_div"] == "CFS"].copy()
    cfs["_done"] = [states0.get(task_key(r), "") in terminal for _, r in cfs.iterrows()]
    pending_cfs = cfs[~cfs["_done"]].drop(columns="_done")

    # Oldest years first so the contiguous backtest window expands as fast as possible.
    period_order = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}
    pending_cfs["_po"] = pending_cfs["period"].map(period_order).fillna(9)
    pending_cfs = pending_cfs.sort_values(["year", "_po", "stock_code"]).drop(columns="_po")

    phase1 = pending_cfs.head(MODERN_LIMIT).copy()
    states1, rows1, limited1 = process_modern_batch(phase1)
    if rows1:
        modern.merge_full_rows(rows1)
    if states1:
        modern.save_state(states1)

    used = len(phase1)
    left = max(MODERN_LIMIT - used, 0)

    # CFS first. OFS is requested only when CFS explicitly reports NO_DATA.
    # This avoids the roughly 2x cost of downloading OFS for every company-period.
    states_after = terminal_state_map(modern.TASK_FILE)
    fallback_rows = []
    if left > 0:
        ofs = tasks[tasks["fs_div"] == "OFS"].copy()
        for _, r in ofs.iterrows():
            ofs_key = task_key(r)
            cfs_key = (ofs_key[0], ofs_key[1], ofs_key[2], ofs_key[3], "CFS")
            if states_after.get(cfs_key) == "NO_DATA" and states_after.get(ofs_key, "") not in terminal:
                fallback_rows.append(r)
    fallback = pd.DataFrame(fallback_rows)
    if not fallback.empty:
        fallback["_po"] = fallback["period"].map(period_order).fillna(9)
        fallback = fallback.sort_values(["year", "_po", "stock_code"]).drop(columns="_po").head(left)
        states2, rows2, limited2 = process_modern_batch(fallback)
        if rows2:
            modern.merge_full_rows(rows2)
        if states2:
            modern.save_state(states2)
    else:
        states2, limited2 = [], False

    state_final = terminal_state_map(modern.TASK_FILE)
    cfs_done = 0
    fallback_needed = 0
    fallback_done = 0
    for _, r in cfs.iterrows():
        k = task_key(r)
        st = state_final.get(k, "")
        if st in terminal:
            cfs_done += 1
        if st == "NO_DATA":
            fallback_needed += 1
            ok = (k[0], k[1], k[2], k[3], "OFS")
            if state_final.get(ok, "") in terminal:
                fallback_done += 1

    return {
        "modern_total_cfs": len(cfs),
        "modern_cfs_done": cfs_done,
        "modern_cfs_completion_pct": round(100.0 * cfs_done / len(cfs), 2) if len(cfs) else 0.0,
        "modern_fallback_needed": fallback_needed,
        "modern_fallback_done": fallback_done,
        "modern_run_tasks": len(phase1) + (len(fallback) if not fallback.empty else 0),
        "modern_rate_limited": bool(limited1 or limited2),
    }


def signal_date(year: int, month: int) -> pd.Timestamp | pd.NaT:
    p = Path("data/krx_equities/yearly") / f"marcap-{year}.parquet"
    if not p.exists():
        return pd.NaT
    try:
        x = pd.read_parquet(p, columns=["Date"])
    except Exception:
        return pd.NaT
    d = pd.to_datetime(x["Date"], errors="coerce")
    d = d[(d.dt.year == year) & (d.dt.month == month)]
    return pd.NaT if d.empty else pd.Timestamp(d.max())


def legacy_target_index(idx: pd.DataFrame) -> pd.DataFrame:
    if idx.empty:
        return idx

    x = idx.copy()
    x["rcept_dt"] = pd.to_datetime(x["rcept_dt"], errors="coerce")
    missing_rcept_dt = x["rcept_dt"].isna()
    if missing_rcept_dt.any():
        x.loc[missing_rcept_dt, "rcept_dt"] = pd.to_datetime(
            x.loc[missing_rcept_dt, "rcept_no"].astype(str).str[:8],
            format="%Y%m%d",
            errors="coerce",
        )
    x["fiscal_year"] = pd.to_numeric(x["fiscal_year"], errors="coerce").astype("Int64")
    x["period"] = x["period"].astype(str)
    x["stock_code"] = x["stock_code"].fillna("").astype(str).str.zfill(6)
    x = x[
        x["stock_code"].str.fullmatch(r"\d{6}")
        & x["period"].isin(["Q1", "H1", "Q3", "FY"])
        & x["fiscal_year"].between(1999, 2014, inclusive="both")
        & x["rcept_dt"].notna()
    ].copy()
    if x.empty:
        return x

    signals: dict[tuple[int, int], pd.Timestamp] = {}
    cutoffs = []
    for _, r in x.iterrows():
        fy = int(r["fiscal_year"])
        if r["period"] in {"Q1", "H1"}:
            sy, sm = fy, 10
        else:
            sy, sm = fy + 1, 4
        key = (sy, sm)
        if key not in signals:
            signals[key] = signal_date(sy, sm)
        cutoffs.append(signals[key])
    x["signal_cutoff"] = cutoffs
    x = x[x["signal_cutoff"].notna() & (x["rcept_dt"] <= x["signal_cutoff"])].copy()

    # For each stock/report period, use the last filing actually available by that rebalance date.
    x = x.sort_values(["stock_code", "fiscal_year", "period", "rcept_dt", "rcept_no"])
    return x.groupby(["stock_code", "fiscal_year", "period"], as_index=False).tail(1)


def legacy_done_set() -> set[str]:
    return legacy.durable_done_receipts(legacy.current_state())


def legacy_fast() -> dict:
    # Reuse the generic queue/checkpoints. All mapped historical receipts,
    # including corrections, are collected rather than a strategy-specific subset.
    if LEGACY_LIMIT == 0:
        return {"legacy_run_docs": 0, "legacy_scope": "DISABLED_BY_BATCH_LIMIT"}
    guard = legacy.new_control()
    legacy.RUN_CONTROL = guard
    try:
        with guard.signals():
            idx = legacy.update_filing_index()
            result = legacy.process_pending(idx, max_docs=LEGACY_LIMIT,
                                            workers=LEGACY_WORKERS, control=guard)
        return {"legacy_scope": "ALL_MAPPED_RECEIPTS", "legacy_run_docs": result["completed"],
                "legacy_pending_before_run": result["eligible_before_run"],
                "legacy_rate_limited": result["rate_limited"],
                "legacy_stop_reason": result["stop_reason"],
                "legacy_requests": result["requests"],
                "legacy_quarantined_errors": result["quarantined_errors"]}
    finally:
        latest = legacy.load_csv(legacy.INDEX_FILE, dtype={"rcept_no": str, "stock_code": str, "corp_code": str})
        legacy.write_coverage(latest)
        legacy.RUN_CONTROL = None


def main() -> None:
    if not os.getenv("DART_API_KEY", "").strip():
        raise RuntimeError("DART_API_KEY is missing")

    legacy_result = legacy_fast()
    # Legacy gets its bounded quota first. Never continue API calls after 020.
    modern_result = (modern_fast() if MODERN_LIMIT > 0 and not legacy_result.get("legacy_rate_limited")
                     and legacy_result.get("legacy_stop_reason") != "FATAL_API"
                     else {"modern_run_tasks": 0, "modern_skipped": True})

    row = {
        "mode": "SUPER_VALUE_FAST_BACKFILL",
        **modern_result,
        **legacy_result,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    legacy.atomic_write_if_changed(pd.DataFrame([row]), STATUS_FILE, ignore_columns=("updated_at_utc",))
    print(pd.DataFrame([row]).to_string(index=False), flush=True)
    if legacy_result.get("legacy_stop_reason") == "FATAL_API":
        raise RuntimeError("DART authentication/service failure; saved progress preserved")


if __name__ == "__main__":
    main()
