"""Original pinned-kit tests, original DART E2E included; no defer or skips."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    (a.output/"execution.json").write_text(json.dumps(dict(python=sys.executable,github_sha=os.getenv("GITHUB_SHA"),
        run_id=os.getenv("GITHUB_RUN_ID"),test_policy="all listed commands actually run; no defer/skip",timeout_seconds=150),indent=2)+"\n")
    spec=importlib.util.spec_from_file_location("frozen_stage12_validation",ROOT/"docs/research/stage12-stock-dividend-20261016/validate.py")
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    tests=["test_dart_snapshot_selection.py","test_stock_dividend_execution.py",*old.TESTS,"export_strategy_dsl_contract.py"]
    results=[]
    for name in tests:
        args=["--check"] if name.startswith("export_") else []
        boot="import runpy,sys;sys.path.insert(0,'scripts');sys.argv="+repr(["scripts/"+name]+args)+";runpy.run_path(sys.argv[0],run_name='__main__')"
        start=time.monotonic()
        try:
            r=subprocess.run([sys.executable,"-I","-c",boot],cwd=ROOT,capture_output=True,timeout=150)
            raw,code=r.stdout+r.stderr,r.returncode
        except subprocess.TimeoutExpired as e:
            raw,code=(e.stdout or b"")+(e.stderr or b"")+b"\nTIMEOUT150\n",124
        path=a.output/(name+".log");path.write_bytes(raw)
        results.append(dict(file=name,exit_code=code,status="PASS" if code==0 else "FAIL",timeout_seconds=150,
                            elapsed_seconds=round(time.monotonic()-start,3),log=path.name,sha256=hashlib.sha256(raw).hexdigest()))
        (a.output/"results.json").write_text(json.dumps(results,indent=2)+"\n")
        print(name,code,flush=True)
    return int(any(r["exit_code"]!=0 for r in results))


if __name__=="__main__": raise SystemExit(main())
