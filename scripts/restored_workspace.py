"""Portable entry point for an existing pinned runtime; no installation or fallback."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,default=os.environ.get('QUANT_PINNED_RUNTIME'));p.add_argument('command',choices=['layout','web','run','check','capabilities']);p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
 if a.runtime is None:p.error('--runtime or QUANT_PINNED_RUNTIME is required; no system-Python fallback')
 runtime=a.runtime.expanduser().resolve();python=runtime/'.venv/bin/python'
 required=[python,runtime/'scripts/sandbox_runtime.py',ROOT/'web/research/index.html',ROOT/'web/research/app.js',ROOT/'web/research/app.css',ROOT/'data/krx_equities/yearly',ROOT/'scripts/quant_backtest_template_CURRENT.py']
 missing=[str(x)for x in required if not x.exists()]
 if missing:
  print(json.dumps(dict(status='restoration_gap',missing=missing,scope='Layout only; no execution or source certification')));return 3
 if a.command=='layout':
  print(json.dumps(dict(status='ok',root=str(ROOT),python=str(python),classification='RESEARCH_ONLY',scope='Layout only; use saved runtime verify and per-request preflight')));return 0
 script=ROOT/'scripts'/('research_web.py'if a.command=='web'else'research_workbench.py')
 args=[str(python),'-B','-I',str(script)]+([]if a.command=='web'else[a.command])+a.arguments
 os.execv(str(python),args)
if __name__=='__main__':raise SystemExit(main())
