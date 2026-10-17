"""Exact before/after comparison on 64 actual report groups, same Python."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import types

HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import pandas as pd
import dart_value_factor_adapter as current


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if a.output.exists(): raise ValueError('new output required')
    old=types.ModuleType('before_dart_adapter')
    source=(HOME/'baseline_dart_adapter.py.txt').read_bytes()
    exec(compile(source,'baseline/dart_value_factor_adapter.py','exec'),old.__dict__)
    raw=current.load_financial_raw(ROOT,2019,'Q3',preserve_reports=True)
    groups=[g for _,g in raw.groupby(['stock_code','fs_div_requested','rcept_no','filing_date'],dropna=False)]
    small=pd.concat(groups[:64],ignore_index=True)
    result=dict(baseline_code_sha256=hashlib.sha256(source).hexdigest(),real_input_rows=len(small),real_report_groups=64,comparisons=[])
    for keep in [False,True]:
        start=time.monotonic();before=old.report_snapshots(small,keep_empty_reports=keep);elapsed=time.monotonic()-start
        start=time.monotonic();after=current.report_snapshots(small,keep_empty_reports=keep);new_elapsed=time.monotonic()-start
        pd.testing.assert_frame_equal(before,after,check_exact=True)
        result['comparisons'].append(dict(keep_empty_reports=keep,rows=len(after),exact_frame_equal=True,before_seconds=elapsed,after_seconds=new_elapsed))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__': main()
