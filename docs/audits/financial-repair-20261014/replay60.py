"""Offline 60-receipt integration replay. Network transport alone is replaced.
Original SHA/CRC and dedicated kit verification are mandatory; no saved data writes.
"""
import argparse,hashlib,json,os,subprocess,sys,tempfile,types,zipfile
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--original40',type=Path,required=True)
p.add_argument('--holdout20',type=Path,required=True)
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo))
expected='26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd'
assert Path(sys.executable).absolute()==(a.runtime/'.venv/bin/python').absolute()
assert json.loads((a.runtime/'kit_manifest.json').read_text())['kit_id']==expected
a.output.mkdir(parents=True,exist_ok=True)
v=subprocess.run([sys.executable,'-I',str(a.runtime/'scripts/sandbox_runtime.py'),'verify'],capture_output=True,text=True)
(a.output/'runtime-verify.json').write_text(v.stdout)
(a.output/'runtime-verify.stderr').write_text(v.stderr)
assert v.returncode==0 and json.loads(v.stdout)['status']=='ok'
network=types.ModuleType('requests')
def forbidden(*args,**kwargs):raise AssertionError('Network disabled in exact original fixture replay')
network.get=network.post=network.Session=forbidden
network.Timeout=type('Timeout',(Exception,),{})
network.ConnectionError=type('ConnectionError',(Exception,),{})
sys.modules['requests']=network
oldcwd=Path.cwd()
with tempfile.TemporaryDirectory() as working:
 os.chdir(working)
 from scripts import backfill_dart_legacy_2000_2014 as subject
 manifests=[];seen=set()
 for root in (a.original40,a.holdout20):
  samples=json.loads((root/'selection.json').read_text())['samples']
  manifest=json.loads((root/'source_manifest.json').read_text())
  for meta in samples:
   sid=meta['sample_id'];receipt=meta['rcept_no'];assert receipt not in seen;seen.add(receipt)
   evidence=next(x for x in manifest if x['sample_id']==sid)
   source=next((root/'originals').glob(receipt+'-*.zip'))
   blob=source.read_bytes();digest=hashlib.sha256(blob).hexdigest()
   assert digest==evidence['sha256']==meta['document_sha256']
   with zipfile.ZipFile(source) as z:
    assert z.testzip() is None
    for m in evidence['members']:assert hashlib.sha256(z.read(m['name'])).hexdigest()==m['sha256']
   subject.fetch_document=lambda requested,b=blob,d=digest,r=receipt: (b,d) if requested==r else forbidden()
   # Source preservation must not touch any original or production data directory.
   os.environ.pop('LEGACY_DART_SOURCE_DIR',None)
   rows,state=subject.process_filing(meta)
   state.pop('updated_at_utc',None)
   assert state['status'] not in {'ERROR','NO_DOCUMENT','DEFERRED','RATE_LIMIT'}
   assert state.get('backtest_eligible') is False
   assert all(x['backtest_eligible'] is False for x in rows)
   result={'sample':meta,'rows':rows,'state':state,'source':evidence}
   (a.output/(sid+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
   manifests.append({'id':sid,'status':state['status'],'rows':len(rows),'sha256':digest})
   print(json.dumps(manifests[-1],ensure_ascii=False),flush=True)
 os.chdir(oldcwd)
assert len(seen)==60
(a.output/'replay_summary.json').write_text(json.dumps(manifests,indent=2)+'\n')
