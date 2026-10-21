"""Browser test over preserved real runs; no baseline rerun or source HTTP."""
import argparse,hashlib,json,select,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from research_web import Workspace
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-store',type=Path,required=True);p.add_argument('--source-proof',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);store=out/'store'
 original=json.loads(a.source_proof.read_text());runs={x['name']:x['id']for x in original['runs']}
 ids=[runs['json_same_top1'],runs['amended_top1']];before={}
 for jid in ids:
  src=a.source_store/'runs'/jid;dst=store/'runs'/jid
  shutil.copytree(src,dst)
  (store/'jobs').mkdir(exist_ok=True)
  shutil.copy2(a.source_store/'jobs'/str(jid+'.json'),store/'jobs'/str(jid+'.json'))
  for f in src.rglob('*'):
   if f.is_file():
    h=hashlib.sha256(f.read_bytes()).hexdigest();relative=str(f.relative_to(a.source_store));before[relative]=h
    assert hashlib.sha256((store/relative).read_bytes()).hexdigest()==h
 command=[sys.executable,'-I',str(ROOT/'scripts/research_web.py'),'--store',str(store),'--port','0']
 with (out/'server-stderr.log').open('w')as err:
  server=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=err,text=True)
  try:
   if not select.select([server.stdout],[],[],30)[0]:raise RuntimeError('SERVER_START_TIMEOUT')
   line=server.stdout.readline()
   if not line:raise RuntimeError('SERVER_START_FAILED: '+(out/'server-stderr.log').read_text()[-4000:])
   ready=json.loads(line);assert ready['status']=='ready'
   with(out/'browser.log').open('w')as log:
    try:subprocess.run(['node',str(ROOT/'scripts/verify_saved_research_comparisons.cjs'),ready['url'],str(out/'browser')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    except(subprocess.CalledProcessError,subprocess.TimeoutExpired):
     log.flush();print((out/'browser.log').read_text()[-5000:],file=sys.stderr);raise
  finally:
   server.terminate();server.wait(timeout=10)
 proof=json.loads((out/'browser/verification.json').read_text())
 w=Workspace(ROOT,store)
 try:opened=w.reopen_comparison(proof['saved_comparison_id'])
 finally:w.pool.shutdown()
 assert opened['saved_comparison']==proof['record']
 for relative,h in before.items():
  assert hashlib.sha256((a.source_store/relative).read_bytes()).hexdigest()==h
  assert hashlib.sha256((store/relative).read_bytes()).hexdigest()==h
 result=dict(status='PASS_BROWSER_AND_SERVER_RESTART',browser=proof,original_and_copy_unchanged=len(before),
  original_proof_sha256=hashlib.sha256(a.source_proof.read_bytes()).hexdigest(),no_collection=True,no_engine_rerun=True,investment_approved=False)
 (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k!='browser'}))
 return 0
if __name__=='__main__':raise SystemExit(main())
