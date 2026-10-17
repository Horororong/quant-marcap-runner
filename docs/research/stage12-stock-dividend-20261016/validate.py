"""Pinned-kit Stage12 software regression runner, not a financial re-audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import resource

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["test_stock_dividend.py", "test_stock_dividend_collection.py", "test_stock_dividend_krx.py",
         "test_held_return_guard.py", "test_cash_share_exchange.py",
         "test_corporate_action_execution.py", "test_corporate_action_reconciliation.py",
         "test_corporate_action_preflight.py", "test_verified_autumn_splits.py",
         "test_strategy_dsl_validation.py", "test_strategy_dsl.py",
         "test_strategy_dsl_deciles.py", "test_strategy_dsl_preflight.py",
         "test_dart_custom_rebalance.py", "test_dsl_execution_e2e.py",
         "test_dsl_deciles_e2e.py"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--defer-dart-e2e-after-native-crash", action="store_true",
                   help="Never a PASS: records known timeout/native diagnostic crash as UNVERIFIED and exits2")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    results = []
    for name in TESTS + ["export_strategy_dsl_contract.py"]:
        args = ["--check"] if name.startswith("export_") else []
        if a.defer_dart_e2e_after_native_crash and name == "test_dsl_execution_e2e.py":
            log = b"UNVERIFIED: prior CI exit124 at150s; diagnostic local process exit139 while dumping pandas frames. Native/test/instrumentation cause unresolved. No repeat and no PASS. See native_runtime_incident.json.\n"
            path = a.output / (name + ".log")
            path.write_bytes(log)
            results.append({"file": name, "execution": "DEFERRED_KNOWN_NATIVE_INCIDENT",
                            "exit_code": None, "status": "UNVERIFIED", "log": path.name,
                            "log_sha256": hashlib.sha256(log).hexdigest()})
            (a.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            print(name, "UNVERIFIED; final harness cannot pass", flush=True)
            continue
        limit = 150
        bootstrap = "import runpy,sys;sys.path.insert(0,'scripts');sys.argv=" + repr(["scripts/" + name] + args) + ";runpy.run_path(sys.argv[0],run_name='__main__')"
        started = time.monotonic()
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        try:
            r = subprocess.run([sys.executable, "-I", "-c", bootstrap], cwd=ROOT, capture_output=True, timeout=limit)
            log, exit_code = r.stdout + r.stderr, r.returncode
        except subprocess.TimeoutExpired as exc:
            log, exit_code = (exc.stdout or b"") + (exc.stderr or b"") + f"\nTIMEOUT {limit}s\n".encode(), 124
        path = a.output / (name + ".log")
        path.write_bytes(log)
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        results.append({"file": name, "exit_code": exit_code, "timeout_seconds": limit,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "child_cpu_seconds": round(usage_after.ru_utime + usage_after.ru_stime - usage_before.ru_utime - usage_before.ru_stime, 3),
                        "status": "PASS" if exit_code == 0 else "FAIL",
                        "log": path.name, "log_sha256": hashlib.sha256(log).hexdigest()})
        (a.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(name, exit_code, flush=True)
    if any(r["status"] == "UNVERIFIED" for r in results):
        return 2
    return int(any(r["exit_code"] != 0 for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
