"""Reusable fixed-sleeve plus macro/price-timed ETF execution; CURRENT owns metrics.

Run only with an integrity-verified offline kit Python. No provider downloads,
package installation, data filling, calendar shortcuts or kit modifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xc


class DataGap(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def read_series(path, field):
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise DataGap(f"duplicate or unsorted dates: {path}")
    series = pd.to_numeric(frame[field], errors="raise").astype(float)
    if not np.isfinite(series).all():
        raise DataGap(f"missing/nonfinite values: {path}")
    return series


def sessions(calendar, start, end):
    return calendar.sessions_in_range(start, end).tz_localize(None)


def check_dates(series, expected, name):
    actual = series.loc[expected[0]:expected[-1]]
    missing = expected.difference(actual.index)
    extra = actual.index.difference(expected)
    if len(missing) or len(extra):
        raise DataGap(f"{name}: missing={list(missing)}, unexpected={list(extra)}")
    if (actual <= 0).any():
        raise DataGap(f"{name}: nonpositive price")
    return actual


def disclosed_macro(signal_date, values, releases, window):
    eligible = releases[releases.ReleaseDate <= signal_date]
    if eligible.empty:
        return None, [{"reason": "no disclosed macro observation"}]
    latest = eligible.index.max()
    months = pd.date_range(end=latest, periods=window, freq="MS")
    gaps = []
    for month in months:
        if month not in values.index:
            gaps.append({"month": month.strftime("%Y-%m"), "reason": "missing macro value"})
        if month not in releases.index:
            gaps.append({"month": month.strftime("%Y-%m"), "reason": "missing primary release evidence",
                         "stored_value": float(values.loc[month]) if month in values.index else None})
        elif releases.loc[month, "ReleaseDate"] > signal_date:
            gaps.append({"month": month.strftime("%Y-%m"), "reason": "macro component not yet released"})
    base = {"macro_month": latest.strftime("%Y-%m"),
            "macro_release_date": releases.loc[latest, "ReleaseDate"].strftime("%Y-%m-%d"),
            "macro_window_start": months[0].strftime("%Y-%m"),
            "unemployment": float(values.loc[latest]) if latest in values.index else None}
    if gaps:
        return base, gaps
    base["unemployment_ma"] = float(values.loc[months].mean())
    return base, []


def monthly_plan(index, price, values, releases, cfg):
    ma = price.rolling(cfg["price_ma_sessions"], min_periods=cfg["price_ma_sessions"]).mean()
    events = [(index[1], index[0], "initial")]
    for i in range(2, len(index)):
        if index[i].month != index[i - 1].month:
            events.append((index[i], index[i - 1],
                           "annual" if index[i].month == cfg["annual_rebalance_month"] else "timing"))
    rows, gaps = [], []
    for execute, signal, kind in events:
        row = {"signal_date": signal.strftime("%Y-%m-%d"),
               "execution_date": execute.strftime("%Y-%m-%d"), "kind": kind}
        row_gaps = []
        if signal not in ma.index or pd.isna(ma.loc[signal]):
            row_gaps.append({"reason": "missing price MA lookback"})
        else:
            row.update(sp500_close=float(price.loc[signal]), sp500_ma=float(ma.loc[signal]))
        macro, errors = disclosed_macro(signal, values, releases, cfg["macro_ma_months"])
        row.update(macro or {})
        row["macro_quality"] = "data_gap" if errors else "release_dates_checked_revised_values"
        row["macro_gaps"] = json.dumps(errors, ensure_ascii=False)
        # For an AND condition, price >= MA already determines QQQ. Preserve
        # the macro quality gap without inventing the unavailable macro mean.
        price_off = not row_gaps and row["sp500_close"] >= row["sp500_ma"]
        if not price_off:
            row_gaps.extend(errors)
        if row_gaps:
            row["status"] = "data_gap"
            for gap in row_gaps:
                gaps.append({**row, **gap})
        else:
            defensive = not price_off and row["unemployment"] > row["unemployment_ma"]
            row.update(status="ready", selected=cfg["defensive_asset"] if defensive else cfg["risk_asset"])
        rows.append(row)
    return pd.DataFrame(rows), gaps


def rebalance(values, target, cash, fee):
    """Solve post-cost target allocations with exact self-financing accounting."""
    total = float(values.sum() + cash)
    low, high = 0., total
    for _ in range(80):
        budget = (low + high) / 2
        traded = float(np.abs(budget * target - values).sum())
        if budget + fee * traded > total:
            high = budget
        else:
            low = budget
    after = target * ((low + high) / 2)
    traded = float(np.abs(after - values).sum())
    cost = fee * traded
    if not np.isclose(float(after.sum()) + cost, total, atol=1e-11, rtol=1e-12):
        raise ValueError("rebalance is not self financing")
    return after, cost, traded


def simulate(prices, plan, cfg, fee, static=False):
    tickers = list(prices.columns)
    fixed = cfg["fixed_weights"]
    risk, defense = cfg["risk_asset"], cfg["defensive_asset"]
    held = pd.Series(0., index=tickers)
    cash = 1.
    events = plan.set_index("execution_date")
    returns = prices.pct_change(fill_method=None)
    nav_rows, trades, holding_rows = [], [], []
    for i, day in enumerate(prices.index):
        cost = traded = 0.
        if i:
            if returns.loc[day].isna().any():
                raise DataGap("missing daily ETF return")
            held *= 1 + returns.loc[day]
        key = day.strftime("%Y-%m-%d")
        if key in events.index:
            event = events.loc[key]
            selected = risk if static else event.selected
            if event.kind in {"initial", "annual"}:
                target = pd.Series(0., index=tickers)
                for ticker, weight in fixed.items():
                    target[ticker] = weight
                target[selected] = cfg["timing_weight"]
                held, cost, traded = rebalance(held, target, cash, fee)
                cash = 0.
            elif not static:
                other = defense if selected == risk else risk
                old = float(held[other])
                if old > 0:
                    new = old * (1 - fee) / (1 + fee)
                    traded = old + new
                    cost = fee * traded
                    held[other] = 0.
                    held[selected] += new
            trades.append({"Date": key, "kind": event.kind, "selected": selected,
                           "signal_date": event.signal_date, "traded_notional": traded, "cost": cost})
        nav = float(held.sum() + cash)
        if nav <= 0 or not np.isfinite(nav):
            raise ValueError("invalid portfolio NAV")
        nav_rows.append({"Date": day, "NAV": nav})
        holding_rows.append({"Date": day, **{t: float(held[t] / nav) for t in tickers}, "cash": cash / nav})
    return pd.DataFrame(nav_rows).set_index("Date")["NAV"], pd.DataFrame(trades), pd.DataFrame(holding_rows)


def run(args):
    root, kit, out = args.repo_root.resolve(), args.kit_root.resolve(), args.output_dir.resolve()
    if Path(sys.prefix).resolve() != kit / ".venv":
        raise ValueError("use the original kit's dedicated Python")
    out.mkdir(parents=True, exist_ok=False)
    status = {"status": "running", "phase": "verify", "nav_ready": False, "report_ready": False,
              "output_dir": str(out)}
    write_json(out / "run_status.json", status)
    try:
        verify = subprocess.run([sys.executable, "-I", str(kit / "scripts/sandbox_runtime.py"), "verify"],
                                capture_output=True, text=True, timeout=60)
        (out / "verify.stdout.json").write_text(verify.stdout)
        (out / "verify.stderr.log").write_text(verify.stderr)
        write_json(out / "verify_process.json", {"exit_code": verify.returncode})
        if verify.returncode:
            raise ValueError(f"kit verify failed: exit {verify.returncode}; inspect verify logs")
        cfg = json.loads(args.config.read_text())
        write_json(out / "strategy.json", cfg)
        if cfg["macro_policy"] != "latest_revised_values_at_evidenced_release_dates":
            raise ValueError("unsupported macro policy")
        if not np.isclose(sum(cfg["fixed_weights"].values()) + cfg["timing_weight"], 1.) or any(w <= 0 for w in cfg["fixed_weights"].values()):
            raise ValueError("invalid allocation weights")
        tickers = [*cfg["fixed_weights"], cfg["risk_asset"], cfg["defensive_asset"]]
        cal = xc.get_calendar(cfg["calendar"], start="1994-01-01", end=cfg["end"])
        dates = sessions(cal, cfg["start"], cfg["end"])
        if len(dates) < 2:
            raise DataGap("insufficient requested sessions")
        files = [root / f"data/etf_us/{t}.csv" for t in [*tickers, cfg["benchmark"]]]
        files += [root / cfg[k] for k in ("price_signal", "macro_values", "macro_releases")]
        manifest = {"kit": json.loads(verify.stdout), "python": sys.executable,
                    "strategy_sha256": sha(args.config), "execution_sha256": sha(__file__),
                    "source_checkout": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                    "sources": [{"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files],
                    "limitations": cfg["limitations"], "registered_dsl": False}
        write_json(out / "input_manifest.json", manifest)
        status["phase"] = "preflight"
        prices = pd.DataFrame({t: check_dates(read_series(root / f"data/etf_us/{t}.csv", "Adj Close"), dates, t) for t in tickers})
        benchmark = check_dates(read_series(root / f"data/etf_us/{cfg['benchmark']}.csv", "Adj Close"), dates, cfg["benchmark"])
        price = read_series(root / cfg["price_signal"], "Close")
        warmup = cal.sessions[cal.sessions < dates[0]][-(cfg["price_ma_sessions"] - 1):].tz_localize(None)
        price_dates = warmup.append(dates)
        price = check_dates(price, price_dates, "S&P500 with lookback")
        macro = read_series(root / cfg["macro_values"], "UNRATE")
        release = pd.read_csv(root / cfg["macro_releases"], parse_dates=["Date", "ReleaseDate"]).set_index("Date")
        if release.index.has_duplicates or release.ReleaseDate.isna().any() or (release.ReleaseDate <= release.index).any():
            raise DataGap("invalid macro release calendar")
        plan, gaps = monthly_plan(dates, price, macro, release, cfg)
        plan.to_csv(out / "signal_plan.csv", index=False)
        write_json(out / "preflight.json", {"ready": not gaps, "requested_start": cfg["start"],
                   "requested_end": cfg["end"], "observations": len(dates), "calendar": cfg["calendar"],
                   "price_coverage": "exact", "gaps": gaps,
                   "macro_values_basis": cfg["macro_policy"]})
        if gaps:
            raise DataGap(f"{len(gaps)} signal dependency gaps; first: {gaps[0]}")
        status["phase"] = "execute"
        nav = pd.DataFrame(index=dates)
        for bps in cfg["cost_bps"]:
            series, trades, weights = simulate(prices, plan, cfg, bps / 10000)
            nav[f"NAV_Cost_{bps}bp"] = series
            trades.to_csv(out / f"trades_{bps}bp.csv", index=False)
            weights.to_csv(out / f"weights_{bps}bp.csv", index=False)
        nav["NAV_Static_5bp"], _, _ = simulate(prices, plan, cfg, 5 / 10000, static=True)
        nav["NAV_Benchmark"] = benchmark / benchmark.iloc[0]
        nav.to_csv(out / "daily_nav.csv", index_label="Date")
        status["nav_ready"] = True
        periods = [{"id": "longest", "label": "실제 ETF 최장", "start": "longest", "end": "latest"},
                   {"id": "from_2021", "label": "2021 이후", "start": "2021-01-01", "end": "latest"}]
        write_json(out / "periods.json", periods)
        status["phase"] = "report"
        command = [sys.executable, "-I", str(kit / "scripts/quant_backtest_postprocess.py"),
                   "--daily-csv", str(out / "daily_nav.csv"), "--report-periods", str(out / "periods.json"),
                   "--title", "LAA: IWD GLD IEF + QQQ/SHY", "--market-calendar", cfg["calendar"],
                   "--benchmark-series", "NAV_Benchmark", "--book-start", cfg["start"], "--book-end", cfg["end"],
                   "--as-of-date", "2026-10-06", "--output-dir", str(out / "report")]
        process = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (out / "report.stdout.log").write_text(process.stdout)
        (out / "report.stderr.log").write_text(process.stderr)
        write_json(out / "report_process.json", {"command": command, "exit_code": process.returncode})
        if process.returncode:
            raise ValueError(f"CURRENT postprocess failed: exit {process.returncode}")
        if not (out / "report/metrics_CURRENT.csv").is_file() or not (out / "report/report_CURRENT.html").is_file():
            raise ValueError("CURRENT outputs missing")
        status.update(status="ok", phase="complete", report_ready=True)
        code = 0
    except Exception as exc:
        code = 3 if isinstance(exc, DataGap) else 4
        status.update(status="data_gap" if code == 3 else "failed", error={"type": type(exc).__name__, "message": str(exc)})
    status["exit_code"] = code
    write_json(out / "run_status.json", status)
    outputs = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": sha(p)}
               for p in sorted(out.rglob("*")) if p.is_file()]
    write_json(out / "output_manifest.json", {"files": outputs})
    print(json.dumps(status, ensure_ascii=False))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--kit-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
