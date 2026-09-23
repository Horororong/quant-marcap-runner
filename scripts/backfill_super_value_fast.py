from __future__ import annotations

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
os.environ.setdefault("LEGACY_DART_MAX_DOCS", "1")
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
    if not legacy.STATE_FILE.exists():
        return set()
    s = pd.read_csv(legacy.STATE_FILE, dtype={"rcept_no": str})
    if s.empty:
        return set()
    terminal = {"PARSED_4F", "PARSED_PARTIAL", "NO_METRICS"}
    if "parser_version" in s.columns:
        s = s[s["parser_version"].eq(legacy.PARSER_VERSION)]
    return set(s.loc[s["status"].isin(terminal), "rcept_no"].astype(str))


def legacy_fast() -> dict:
    # update_filing_index resumes from the existing index-state file; with INDEX_TASKS=180
    # it can finish all remaining list-query buckets in one run, subject to DART limits.
    idx = legacy.update_filing_index()
    if idx.empty and legacy.INDEX_FILE.exists():
        idx = legacy.load_csv(legacy.INDEX_FILE, dtype={"rcept_no": str, "stock_code": str, "corp_code": str})
    if idx.empty:
        return {"legacy_target_docs": 0, "legacy_target_done": 0, "legacy_run_docs": 0,
                "legacy_target_completion_pct": 0.0}

    targets = legacy_target_index(idx)
    done = legacy_done_set()
    pending = targets[~targets["rcept_no"].astype(str).isin(done)].copy()
    pending = pending.sort_values(["fiscal_year", "period", "stock_code"]).head(LEGACY_LIMIT)

    metric_rows: list[dict] = []
    state_rows: list[dict] = []
    rate_limited = False
    if not pending.empty:
        with ThreadPoolExecutor(max_workers=LEGACY_WORKERS) as ex:
            futs = {ex.submit(legacy.process_filing, r.to_dict()): str(r["rcept_no"]) for _, r in pending.iterrows()}
            n = 0
            for fut in as_completed(futs):
                rows, st = fut.result()
                metric_rows.extend(rows)
                state_rows.append(st)
                if st.get("status") == "RATE_LIMIT":
                    rate_limited = True
                n += 1
                if n % 250 == 0 or n == len(pending):
                    print(f"super-value legacy fast progress {n}/{len(pending)}", flush=True)

    if metric_rows:
        legacy.append_normalized(metric_rows)
    if state_rows:
        legacy.upsert_state(legacy.STATE_FILE, state_rows, "rcept_no")

    done_after = legacy_done_set()
    target_done = int(targets["rcept_no"].astype(str).isin(done_after).sum())

    # Keep the generic legacy coverage report current too.
    latest_idx = legacy.load_csv(legacy.INDEX_FILE, dtype={"rcept_no": str, "stock_code": str, "corp_code": str})
    if not latest_idx.empty:
        latest_idx["rcept_dt"] = pd.to_datetime(latest_idx["rcept_dt"], errors="coerce")
        latest_idx["period_end"] = pd.to_datetime(latest_idx["period_end"], errors="coerce")
        legacy.write_coverage(latest_idx)

    return {
        "legacy_target_docs": len(targets),
        "legacy_target_done": target_done,
        "legacy_target_completion_pct": round(100.0 * target_done / len(targets), 2) if len(targets) else 0.0,
        "legacy_run_docs": len(pending),
        "legacy_rate_limited": rate_limited,
    }


def main() -> None:
    if not os.getenv("DART_API_KEY", "").strip():
        raise RuntimeError("DART_API_KEY is missing")

    modern_result = modern_fast()
    legacy_result = legacy_fast()

    row = {
        "mode": "SUPER_VALUE_FAST_BACKFILL",
        **modern_result,
        **legacy_result,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    pd.DataFrame([row]).to_csv(STATUS_FILE, index=False, encoding="utf-8-sig")
    print(pd.DataFrame([row]).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
