"""Bounded official evidence discovery through the existing Actions DART secret.

Reuse Stage5's credential-safe transport/decoder. At most four list requests,
two corporations, one declared 2019-12..2021-04 window, exchange category I.
No original documents, prices, backfill, retries or production-data writes.
This discovery cannot certify prices, listing/credit or absence of corrections.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage5_transport", ROOT / "docs/audits/dart-history-stage5-20261014/collect_history.py")
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
TARGETS = [("00413046", "068270"), ("00554024", "091990")]


def acquire(output, key, fetch=transport.fetch):
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "UNVERIFIED", "requests": 0, "responses": [], "candidates": [],
             "scope": "exchange category I, 20191201..20210430, max2 pages/corp, max4 calls; no document requests",
             "backtest_eligible": False, "retries": 0}
    try:
        if not re.fullmatch(r"[A-Za-z0-9]{40}", key):
            raise transport.Stop("AUTH_ENV_MISSING_OR_INVALID")
        for corp, security in TARGETS:
            expected_total = None
            seen = set()
            for page in (1, 2):
                params = {"corp_code": corp, "bgn_de": "20191201", "end_de": "20210430",
                          "last_reprt_at": "N", "pblntf_ty": "I", "page_count": "100", "page_no": str(page),
                          "sort": "date", "sort_mth": "asc"}
                state["requests"] += 1
                http, raw = fetch(params, key)
                parsed, status = transport.reply(raw, key)
                name = f"{security}_page{page}.json"
                (output / name).write_bytes(raw)
                state["responses"].append({"file": name, "parameters": params, "http": http,
                    "dart_status": status, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                if status == "013":
                    if page != 1:
                        raise transport.Stop("INCONSISTENT_PAGINATION", http, status)
                    break
                if status != "000":
                    raise transport.Stop("DART_FAILURE", http, status)
                total, pages = int(parsed["total_count"]), int(parsed["total_page"])
                rows = parsed["list"]
                if (int(parsed["page_no"]) != page or int(parsed["page_count"]) != 100
                        or total <= 0 or pages != (total + 99) // 100
                        or (expected_total is not None and total != expected_total)
                        or len(rows) != min(100, total - (page - 1) * 100)):
                    raise transport.Stop("INVALID_PAGINATION", http, status)
                expected_total = total
                for row in rows:
                    if (row.get("corp_code") != corp or row.get("stock_code") not in (security, "")
                            or not re.fullmatch(r"\d{14}", row.get("rcept_no", ""))
                            or not re.fullmatch(r"\d{8}", row.get("rcept_dt", ""))
                            or not "20191201" <= row["rcept_dt"] <= "20210430"):
                        raise transport.Stop("INVALID_IDENTITY_OR_DATE", http, status)
                    if row["rcept_no"] in seen:
                        raise transport.Stop("DUPLICATE_RECEIPT", http, status)
                    seen.add(row["rcept_no"])
                    if any(word in row.get("report_nm", "") for word in ["배당", "추가상장", "주주총회"]):
                        state["candidates"].append(row)
                if page == pages:
                    break
                if pages > 2:
                    raise transport.Stop("DECLARED_PAGE_BUDGET_EXCEEDED", http, status)
        state["status"] = "COMPLETE_LIMITED_METADATA_ONLY"
    except transport.Stop as exc:
        state["error"] = {"kind": exc.kind, "http_status": exc.http_status, "dart_status": exc.dart_status}
    except Exception as exc:
        # Never stringify exceptions containing HTTP request objects/URLs.
        state["error"] = {"kind": "VALIDATION_FAILURE", "exception_type": type(exc).__name__}
    (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    state = acquire(args.output, os.environ.get("DART_API_KEY", ""))
    print(json.dumps({k: state[k] for k in ["status", "requests", "retries"]}))
    raise SystemExit(0 if state["status"] == "COMPLETE_LIMITED_METADATA_ONLY" else 2)
