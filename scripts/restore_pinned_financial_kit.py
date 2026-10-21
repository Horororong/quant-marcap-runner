"""Restore the SAME immutable release kit without GitHub artifact egress.

System Python performs transport only; all audit/API work uses verified kit Python.
No dependency resolution, no pip, no alternate kit, no retries.
"""
import argparse, hashlib, urllib.request, zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
dest=a.output/'original-kit.zip'
url='https://github.com/Horororong/quant-marcap-runner/releases/download/quant-report-26e4ec02e569/quant-sandbox-26e4ec02e569.zip'
with urllib.request.urlopen(url,timeout=120) as response,dest.open('wb') as f:
    while chunk:=response.read(1024**2):f.write(chunk)
assert hashlib.sha256(dest.read_bytes()).hexdigest()=='f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784'
with zipfile.ZipFile(dest) as z:
    assert z.testzip() is None
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(a.output/'kit-parts')
print('Original pinned kit release SHA/CRC verified; no artifact download or pip')
