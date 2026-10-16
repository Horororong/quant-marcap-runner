"""Pinned-kit Stage12 software regression runner, not a financial re-audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TESTS = ["test_stock_dividend.py", "test_stock_dividend_collection.py",
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
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    results = []
    for name in TESTS + ["export_strategy_dsl_contract.py"]:
        args = ["--check"] if name.startswith("export_") else []
        bootstrap = "import runpy,sys;sys.path.insert(0,'scripts');sys.argv=" + repr(["scripts/" + name] + args) + ";runpy.run_path(sys.argv[0],run_name='__main__')"
        try:
            r = subprocess.run([sys.executable, "-I", "-c", bootstrap], cwd=ROOT, capture_output=True, timeout=150)
            log, exit_code = r.stdout + r.stderr, r.returncode
        except subprocess.TimeoutExpired as exc:
            log, exit_code = (exc.stdout or b"") + (exc.stderr or b"") + b"\nTIMEOUT 150s\n", 124
        path = a.output / (name + ".log")
        path.write_bytes(log)
        results.append({"file": name, "exit_code": exit_code,
                        "status": "PASS" if exit_code == 0 else "FAIL",
                        "log": path.name, "log_sha256": hashlib.sha256(log).hexdigest()})
        (a.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(name, exit_code, flush=True)
    return int(any(r["exit_code"] != 0 for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
