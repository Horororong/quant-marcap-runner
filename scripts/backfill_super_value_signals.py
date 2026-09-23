from __future__ import annotations

import importlib.util
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(".")
STATUS_FILE = ROOT / "data/status/super_value_signal_backfill_status.csv"
STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

TASK_BUDGET = max(1, int(os.getenv("SUPER_VALUE_SIGNAL_TASKS", "6000")))
BATCH_SIZE = max(50, int(os.getenv("SUPER_VALUE_SIGNAL_BATCH", "500")))
WORKERS = max(1, min(8, int(os.getenv("SUPER_VALUE_SIGNAL_WORKERS", "6"))))


def import_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


modern = import_module("dart_modern_signal", "scripts/backfill_dart_full_financials.py")
bt = import_module("super_value_backtest_signal", "scripts/backtest_super_value_v216.py")


def load_state() -> pd.DataFrame:
    if not modern.TASK_FILE.exists():
        return pd.DataFrame(
            columns=["stock_code", "corp_code", "year", "period", "fs_div", "status", "updated_at_utc"]
        )
    x = pd.read_csv(modern.TASK_FILE, dtype={"stock_code": str, "corp_code": str})
    if x.empty:
        return x
    x["stock_code"] = x["stock_code"].astype(str).str.zfill(6)
    x["corp_code"] = x["corp_code"].fillna("").astype(str)
    x["year"] = pd.to_numeric(x["year"], errors="coerce").astype("Int64")
    x["period"] = x["period"].astype(str)
    x["fs_div"] = x["fs_div"].astype(str)
    x = x.sort_values("updated_at_utc").drop_duplicates(
        ["stock_code", "corp_code", "year", "period", "fs_div"], keep="last"
    )
    return x


def terminal_keys(state: pd.DataFrame) -> set[tuple[str, str, int, str, str]]:
    if state.empty:
        return set()
    z = state[state["status"].isin(["OK", "NO_DATA"])].dropna(subset=["year"]).copy()
    return set(
        zip(
            z["stock_code"].astype(str).str.zfill(6),
            z["corp_code"].astype(str),
            z["year"].astype(int),
            z["period"].astype(str),
            z["fs_div"].astype(str),
        )
    )


def factor_only(rows: list[dict]) -> list[dict]:
    """Retain only rows that the v2-16 factor builder can actually consume."""
    out: list[dict] = []
    for row in rows:
        metric, _ = bt.metric_priority(pd.Series(row))
        if metric is not None:
            out.append(row)
    return out


def error_state(task: dict, exc: Exception) -> dict:
    return {
        **task,
        "status": "ERROR",
        "rows_saved": 0,
        "error": repr(exc),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def process_chunk(chunk: pd.DataFrame) -> tuple[int, bool]:
    if chunk.empty:
        return 0, False

    states: list[dict] = []
    saved_rows: list[dict] = []
    rate_limited = False

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(modern.process_task, row.to_dict()): row.to_dict()
            for _, row in chunk.iterrows()
        }
        completed = 0
        for future in as_completed(futures):
            task = futures[future]
            try:
                state, rows = future.result()
                states.append(state)
                saved_rows.extend(factor_only(rows))
            except modern.RateLimitExceeded as exc:
                rate_limited = True
                states.append(error_state(task, exc))
            except modern.FatalDartError:
                raise
            except Exception as exc:
                states.append(error_state(task, exc))

            completed += 1
            if completed % 100 == 0 or completed == len(chunk):
                print(f"signal accelerator progress {completed}/{len(chunk)}", flush=True)

    if saved_rows:
        modern.merge_full_rows(saved_rows)
    if states:
        modern.save_state(states)

    return len(chunk), rate_limited


def run_tasks(pending: pd.DataFrame, budget_left: int) -> tuple[int, bool]:
    used = 0
    limited = False
    if pending.empty or budget_left <= 0:
        return used, limited

    for start in range(0, min(len(pending), budget_left), BATCH_SIZE):
        n = min(BATCH_SIZE, budget_left - used, len(pending) - start)
        if n <= 0:
            break
        chunk = pending.iloc[start : start + n].copy()
        done, hit_limit = process_chunk(chunk)
        used += done
        limited = limited or hit_limit
        if hit_limit or used >= budget_left:
            break
    return used, limited


def required_task_rows(tasks: pd.DataFrame, signal: pd.Timestamp, fs_div: str) -> pd.DataFrame:
    req = set(bt.required_periods(signal))
    x = tasks[tasks["fs_div"].eq(fs_div)].copy()
    mask = [(int(y), str(p)) in req for y, p in zip(x["year"], x["period"])]
    return x.loc[mask].sort_values(["year", "period", "stock_code"]).reset_index(drop=True)


def missing_cfs(tasks: pd.DataFrame, signal: pd.Timestamp, state: pd.DataFrame) -> pd.DataFrame:
    done = terminal_keys(state)
    x = required_task_rows(tasks, signal, "CFS")
    keep = []
    for _, r in x.iterrows():
        key = (
            str(r["stock_code"]).zfill(6),
            str(r["corp_code"]),
            int(r["year"]),
            str(r["period"]),
            "CFS",
        )
        keep.append(key not in done)
    return x.loc[keep].reset_index(drop=True)


def missing_ofs_fallback(
    tasks: pd.DataFrame, signal: pd.Timestamp, state: pd.DataFrame, mapping: pd.DataFrame
) -> pd.DataFrame:
    if state.empty:
        return tasks.iloc[0:0].copy()

    req = set(bt.required_periods(signal))
    terminal = {"OK", "NO_DATA"}
    done = terminal_keys(state)
    expected_by_period = {
        (y, p): bt.expected_codes_for_period(mapping, y, p)
        for y, p in req
    }

    latest = state.sort_values("updated_at_utc").drop_duplicates(
        ["stock_code", "corp_code", "year", "period", "fs_div"], keep="last"
    )
    cfs_no_data = latest[
        latest["fs_div"].eq("CFS") & latest["status"].eq("NO_DATA")
    ].copy()

    needed: set[tuple[str, int, str]] = set()
    for _, r in cfs_no_data.iterrows():
        yp = (int(r["year"]), str(r["period"]))
        code = str(r["stock_code"]).zfill(6)
        if yp in req and code in expected_by_period[yp]:
            needed.add((code, yp[0], yp[1]))

    ofs = required_task_rows(tasks, signal, "OFS")
    keep = []
    for _, r in ofs.iterrows():
        code = str(r["stock_code"]).zfill(6)
        yr = int(r["year"])
        period = str(r["period"])
        key = (code, str(r["corp_code"]), yr, period, "OFS")
        keep.append((code, yr, period) in needed and key not in done)

    return ofs.loc[keep].reset_index(drop=True)


def candidate_signals() -> list[pd.Timestamp]:
    out: list[pd.Timestamp] = []
    for year in range(2016, bt.AS_OF.year + 1):
        for month in (4, 10):
            signal = bt.last_trading_day_from_file(year, month)
            if signal is not None and signal <= bt.AS_OF:
                out.append(pd.Timestamp(signal))
    return sorted(set(out))


def is_complete(mapping: pd.DataFrame, state: pd.DataFrame, signal: pd.Timestamp) -> bool:
    ok, _ = bt.signal_completeness(mapping, state, signal)
    return bool(ok)


def main() -> None:
    if not os.getenv("DART_API_KEY", "").strip():
        raise RuntimeError("DART_API_KEY is missing")

    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)

    corp = modern.load_all_dart_corps()
    mapping = modern.build_historical_code_map(corp, now_kst)
    tasks = modern.build_tasks(mapping, now_kst)

    budget_left = TASK_BUDGET
    total_used = 0
    hit_rate_limit = False
    status_rows: list[dict] = []

    signals = candidate_signals()
    initial_state = load_state()
    first_complete_idx = next(
        (i for i, signal in enumerate(signals) if is_complete(mapping, initial_state, signal)),
        None,
    )
    if first_complete_idx is None:
        raise RuntimeError("No PIT-complete anchor signal exists; accelerator will not guess a start point")

    # Match the backtest's contiguous-window rule: ignore incomplete dates before
    # the first verified signal, then target the first gap after the verified run.
    signals = signals[first_complete_idx:]

    for signal in signals:
        state = load_state()
        before = is_complete(mapping, state, signal)
        if before:
            continue

        used_here = 0
        print(f"TARGET SIGNAL {signal.date()} required={bt.required_periods(signal)}", flush=True)

        # Phase 1: finish CFS for only the two report periods required by this rebalance.
        cfs = missing_cfs(tasks, signal, state)
        if len(cfs) and budget_left > 0:
            n, limited = run_tasks(cfs, budget_left)
            used_here += n
            total_used += n
            budget_left -= n
            hit_rate_limit = hit_rate_limit or limited

        state = load_state()

        # Phase 2: OFS only where the completed CFS request explicitly returned NO_DATA.
        # This preserves the same CFS-first/OFS-fallback rule used by the v2-16 backtest.
        ofs = missing_ofs_fallback(tasks, signal, state, mapping)
        if len(ofs) and budget_left > 0 and not hit_rate_limit:
            n, limited = run_tasks(ofs, budget_left)
            used_here += n
            total_used += n
            budget_left -= n
            hit_rate_limit = hit_rate_limit or limited

        state = load_state()
        after = is_complete(mapping, state, signal)
        cfs_left = len(missing_cfs(tasks, signal, state))
        ofs_left = len(missing_ofs_fallback(tasks, signal, state, mapping))

        status_rows.append(
            {
                "signal_date": signal.date().isoformat(),
                "required_periods": "|".join(f"{y}-{p}" for y, p in bt.required_periods(signal)),
                "complete_before": before,
                "complete_after": after,
                "tasks_used_this_run": used_here,
                "cfs_tasks_left": cfs_left,
                "ofs_fallback_tasks_left": ofs_left,
                "budget_left": budget_left,
                "rate_limited": hit_rate_limit,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

        print(
            f"SIGNAL {signal.date()} complete={after} used={used_here} "
            f"cfs_left={cfs_left} ofs_left={ofs_left} budget_left={budget_left}",
            flush=True,
        )

        # Contiguous validation cannot advance past this signal until it is complete.
        if not after or budget_left <= 0 or hit_rate_limit:
            break

    if not status_rows:
        status_rows.append(
            {
                "signal_date": "",
                "required_periods": "",
                "complete_before": True,
                "complete_after": True,
                "tasks_used_this_run": 0,
                "cfs_tasks_left": 0,
                "ofs_fallback_tasks_left": 0,
                "budget_left": budget_left,
                "rate_limited": False,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

    pd.DataFrame(status_rows).to_csv(STATUS_FILE, index=False, encoding="utf-8-sig")
    print(
        f"SUPER VALUE SIGNAL ACCELERATOR DONE total_used={total_used} "
        f"budget={TASK_BUDGET} rate_limited={hit_rate_limit}",
        flush=True,
    )


if __name__ == "__main__":
    main()
