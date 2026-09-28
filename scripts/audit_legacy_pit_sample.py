from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import pandas as pd

import backfill_dart_legacy_2000_2014 as legacy

OUT_DETAIL = Path("data/status/legacy_pit_audit_sample.csv")
OUT_SUMMARY = Path("data/status/legacy_pit_audit_summary.csv")
FULL_N = max(1, int(os.getenv("LEGACY_AUDIT_SAMPLE", "24")))
PARTIAL_N = max(4, FULL_N // 2)

EXPECTED_STATEMENT = {
    "equity": "BS",
    "revenue": "IS",
    "net_income": "IS",
    "ocf": "CF",
}
VALID_METRICS = set(EXPECTED_STATEMENT)
VALID_SCOPES = {"CFS", "OFS"}
VALID_UNITS = set(legacy.UNIT_MULTIPLIERS)


def stable_sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if df.empty or n <= 0:
        return df.iloc[0:0].copy()
    x = df.drop_duplicates("rcept_no").copy()
    x["_hash"] = x["rcept_no"].astype(str).map(
        lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
    )
    # Spread the sample across fiscal years first, then fill remaining slots globally.
    picks = []
    years = sorted(pd.to_numeric(x["fiscal_year"], errors="coerce").dropna().astype(int).unique())
    if years:
        per = max(1, n // len(years))
        for y in years:
            gy = x[pd.to_numeric(x["fiscal_year"], errors="coerce").eq(y)].sort_values("_hash")
            picks.append(gy.head(per))
    chosen = pd.concat(picks, ignore_index=True) if picks else x.iloc[0:0].copy()
    chosen = chosen.drop_duplicates("rcept_no")
    if len(chosen) < n:
        rem = x[~x["rcept_no"].astype(str).isin(chosen["rcept_no"].astype(str))].sort_values("_hash")
        chosen = pd.concat([chosen, rem.head(n - len(chosen))], ignore_index=True)
    return chosen.head(n).drop(columns=["_hash"], errors="ignore")


def close_enough(a: float, b: float) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    a = float(a)
    b = float(b)
    tol = max(1.0, abs(a), abs(b)) * 1e-9
    return abs(a - b) <= tol


def load_normalized() -> pd.DataFrame:
    frames = []
    for p in sorted(legacy.NORM_DIR.glob("legacy_metrics_*.csv.gz")):
        try:
            f = pd.read_csv(
                p,
                dtype={"rcept_no": str, "stock_code": str, "corp_code": str},
                low_memory=False,
            )
        except Exception:
            continue
        if not f.empty:
            f["_source_file"] = p.name
            frames.append(f)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    if "parser_version" in out.columns:
        out = out[out["parser_version"].eq(legacy.PARSER_VERSION)].copy()
    return out


def audit_one(meta: dict, stored: pd.DataFrame, state_row: pd.Series) -> dict:
    rcept = str(meta["rcept_no"])
    status = str(state_row.get("status", ""))
    best_scope = str(state_row.get("best_scope", "") or "")
    reasons = []

    if stored.empty:
        return {
            "rcept_no": rcept,
            "fiscal_year": meta.get("fiscal_year"),
            "period": meta.get("period", ""),
            "stock_code": meta.get("stock_code", ""),
            "status": status,
            "best_scope": best_scope,
            "stored_rows": 0,
            "fresh_rows": 0,
            "metric_match_count": 0,
            "structural_checks_ok": False,
            "fresh_reparse_ok": False,
            "mapping_ok": False,
            "audit_ok": False,
            "issues": "no stored normalized rows",
        }

    # Basic source/mapping consistency.
    stored_codes = set(stored.get("stock_code", pd.Series(dtype=str)).fillna("").astype(str).str.zfill(6))
    mapped_code = str(meta.get("stock_code", "") or "").zfill(6)
    mapping_ok = bool(mapped_code and mapped_code in stored_codes)
    if not mapping_ok:
        reasons.append("stock_code mismatch vs filing index")

    # Structural checks independent of a fresh network fetch.
    structural_ok = True
    for _, r in stored.iterrows():
        metric = str(r.get("metric", ""))
        statement = str(r.get("statement", ""))
        scope = str(r.get("scope", ""))
        unit = str(r.get("unit", ""))
        reported = pd.to_numeric(r.get("amount_reported"), errors="coerce")
        mult = pd.to_numeric(r.get("unit_multiplier"), errors="coerce")
        krw = pd.to_numeric(r.get("amount_krw"), errors="coerce")

        if metric not in VALID_METRICS:
            structural_ok = False
            reasons.append(f"unexpected metric:{metric}")
        if metric in EXPECTED_STATEMENT and statement != EXPECTED_STATEMENT[metric]:
            structural_ok = False
            reasons.append(f"statement mismatch:{metric}:{statement}")
        if scope not in VALID_SCOPES:
            structural_ok = False
            reasons.append(f"bad scope:{scope}")
        if not unit or unit not in VALID_UNITS:
            structural_ok = False
            reasons.append(f"missing/bad unit:{metric}:{unit}")
        if pd.isna(reported) or pd.isna(mult) or pd.isna(krw) or not close_enough(float(reported) * float(mult), float(krw)):
            structural_ok = False
            reasons.append(f"unit conversion mismatch:{metric}")

    # PARSED_4F must truly contain all four metrics in one scope.
    if status == "PARSED_4F":
        by_scope = {
            scope: set(stored.loc[stored["scope"].eq(scope), "metric"].astype(str))
            for scope in VALID_SCOPES
        }
        if not any(VALID_METRICS.issubset(v) for v in by_scope.values()):
            structural_ok = False
            reasons.append("PARSED_4F missing 4 metrics in a single scope")
        if best_scope and not VALID_METRICS.issubset(by_scope.get(best_scope, set())):
            structural_ok = False
            reasons.append("best_scope does not contain all 4 metrics")

    # Freshly download the authoritative DART document and reparse.
    fresh_reparse_ok = False
    metric_match_count = 0
    fresh_rows_n = 0
    try:
        fresh_rows, fresh_state = legacy.process_filing(meta)
        fresh = pd.DataFrame(fresh_rows)
        fresh_rows_n = len(fresh)
        if fresh_state.get("status") in {"PARSED_4F", "PARSED_PARTIAL", "NO_METRICS"}:
            compare_scope = best_scope if best_scope in VALID_SCOPES else ""
            s = stored[stored["scope"].eq(compare_scope)].copy() if compare_scope else stored.copy()
            f = fresh[fresh["scope"].eq(compare_scope)].copy() if compare_scope and not fresh.empty else fresh.copy()
            if not s.empty and not f.empty:
                pairs = s.merge(
                    f[["metric", "scope", "amount_krw", "account_name", "unit"]],
                    on=["metric", "scope"],
                    how="left",
                    suffixes=("_stored", "_fresh"),
                )
                checks = []
                for _, q in pairs.iterrows():
                    ok = close_enough(q.get("amount_krw_stored"), q.get("amount_krw_fresh"))
                    checks.append(ok)
                    if ok:
                        metric_match_count += 1
                    else:
                        reasons.append(f"fresh value mismatch:{q.get('metric')}:{q.get('scope')}")
                fresh_reparse_ok = bool(checks) and all(checks)
            elif status == "NO_METRICS":
                fresh_reparse_ok = fresh.empty
            else:
                reasons.append("fresh parse missing comparable rows")
        else:
            reasons.append(f"fresh fetch/reparse status:{fresh_state.get('status')}")
    except Exception as e:
        reasons.append(f"fresh fetch exception:{type(e).__name__}:{e}")

    detail_parts = []
    for _, rr in stored.sort_values(["scope", "metric"]).iterrows():
        detail_parts.append(
            f"{rr.get('metric')}|{rr.get('scope')}|stmt={rr.get('statement')}|"
            f"acct={rr.get('account_name')}|raw={rr.get('raw_amount')}|"
            f"unit={rr.get('unit')}|krw={rr.get('amount_krw')}"
        )

    audit_ok = bool(structural_ok and fresh_reparse_ok and mapping_ok)
    return {
        "rcept_no": rcept,
        "fiscal_year": meta.get("fiscal_year"),
        "period": meta.get("period", ""),
        "stock_code": mapped_code,
        "status": status,
        "best_scope": best_scope,
        "stored_rows": len(stored),
        "fresh_rows": fresh_rows_n,
        "metric_match_count": metric_match_count,
        "structural_checks_ok": structural_ok,
        "fresh_reparse_ok": fresh_reparse_ok,
        "mapping_ok": mapping_ok,
        "audit_ok": audit_ok,
        "issues": " | ".join(dict.fromkeys(reasons)),
        "stored_metric_details": " || ".join(detail_parts),
    }


def main() -> None:
    if not legacy.API_KEY:
        raise RuntimeError("DART_API_KEY is missing")

    idx = legacy.load_csv(
        legacy.INDEX_FILE,
        dtype={"rcept_no": str, "stock_code": str, "corp_code": str},
    )
    state = legacy.load_csv(legacy.STATE_FILE, dtype={"rcept_no": str})
    norm = load_normalized()
    if idx.empty or state.empty or norm.empty:
        raise RuntimeError("legacy index/state/normalized data missing")

    if "parser_version" in state.columns:
        state = state[state["parser_version"].eq(legacy.PARSER_VERSION)].copy()

    base = idx.merge(
        state[["rcept_no", "status", "best_scope", "usable_metric_count"]],
        on="rcept_no",
        how="inner",
    )
    full = stable_sample(base[base["status"].eq("PARSED_4F")], FULL_N)
    partial = stable_sample(base[base["status"].eq("PARSED_PARTIAL")], PARTIAL_N)
    sample = pd.concat([full, partial], ignore_index=True).drop_duplicates("rcept_no")

    details = []
    for _, row in sample.iterrows():
        rcept = str(row["rcept_no"])
        stored = norm[norm["rcept_no"].astype(str).eq(rcept)].copy()
        details.append(audit_one(row.to_dict(), stored, row))

    out = pd.DataFrame(details)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    summary_rows = []
    for label, g in [("ALL", out)] + [(k, v) for k, v in out.groupby("status")]:
        summary_rows.append({
            "group": label,
            "sampled_filings": len(g),
            "audit_pass": int(g["audit_ok"].sum()) if len(g) else 0,
            "audit_fail": int((~g["audit_ok"]).sum()) if len(g) else 0,
            "pass_pct": round(100.0 * g["audit_ok"].mean(), 2) if len(g) else math.nan,
            "structural_pass_pct": round(100.0 * g["structural_checks_ok"].mean(), 2) if len(g) else math.nan,
            "fresh_reparse_pass_pct": round(100.0 * g["fresh_reparse_ok"].mean(), 2) if len(g) else math.nan,
            "mapping_pass_pct": round(100.0 * g["mapping_ok"].mean(), 2) if len(g) else math.nan,
        })

    pd.DataFrame(summary_rows).to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    if (~out["audit_ok"]).any():
        print("\nFAILURES")
        print(out.loc[~out["audit_ok"], ["rcept_no", "fiscal_year", "status", "issues"]].to_string(index=False))


if __name__ == "__main__":
    main()
