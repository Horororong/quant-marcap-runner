"""Historical proposal apply/rollback with explicit original parser pin; candidate code is validated separately.
This does not invoke a collector, publish main or claim live requests coverage.
"""
import ast,base64,gzip,hashlib,json,subprocess,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HOME=Path(__file__).resolve().parent/'main_proposal';sys.path.insert(0,str(ROOT))
from scripts.legacy_backfill_runtime import CollectionControl,CollectionPaused

def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument("--candidate-manifest",type=Path,required=True);approved=json.loads(parser.parse_args().candidate_manifest.read_text())
 base=json.loads(gzip.decompress(base64.b64decode((HOME/'main_base.json.gz.b64').read_bytes())))
 pins=json.loads((HOME/'patch_verification.json').read_text())
 with tempfile.TemporaryDirectory(prefix='main-shadow-')as d:
  root=Path(d);subprocess.run(['git','init','-q',str(root)],check=True)
  for n,s in base.items():
   assert hashlib.sha256(s.encode()).hexdigest()==pins['base_sha256'][n]
   (root/n).parent.mkdir(parents=True,exist_ok=True);(root/n).write_text(s)
  names=['01_service_and_phase.patch','02_financial_shadow_candidate_NOT_AUTO_DEPLOY.patch']
  for n in names:
   p=HOME/n;assert hashlib.sha256(p.read_bytes()).hexdigest()==pins['patches'][n]['sha256']
   subprocess.run(['git','apply','--check',str(p)],cwd=root,check=True);subprocess.run(['git','apply',str(p)],cwd=root,check=True)
   if n==names[0]:
    helper={};exec(compile((root/'scripts/dart_service_status.py').read_text(),'<main-proposal-service>','exec'),helper)
    code=(root/'scripts/backfill_dart_legacy_2000_2014.py').read_text();assert 'PARSER_VERSION = "legacy-v5-single-amount"'in code
    node=next(x for x in ast.parse(code).body if isinstance(x,ast.FunctionDef)and x.name=='fetch_document')
    for http,body,reason in [(200,b'<result><status>800</status></result>','SERVICE_MAINTENANCE_800'),(503,b'outage','TRANSIENT_HTTP_503')]:
     class T:
      calls=0;Timeout=type('Timeout',(Exception,),{});ConnectionError=type('ConnectionError',(Exception,),{})
      def get(self,*a,**kw):
       self.calls+=1
       return types.SimpleNamespace(status_code=http,content=body,text=body.decode(),raise_for_status=lambda:None)
     t=T();c=CollectionControl(min_interval=0);env=dict(helper,requests=t,RUN_CONTROL=c,CollectionPaused=CollectionPaused,RateLimitExceeded=type('RateLimitExceeded',(Exception,),{}),BASE='https://synthetic.invalid',API_KEY='synthetic-test-only')
     exec(compile(ast.Module(body=[node],type_ignores=[]),'<main-patched-fetch-AST>','exec'),env)
     try:env['fetch_document']('synthetic');raise AssertionError('outage accepted')
     except CollectionPaused:pass
     assert t.calls==1 and c.stop_reason==reason
  assert hashlib.sha256((root/'scripts/legacy_native_financials.py').read_bytes()).hexdigest()==approved['prior_parser_sha256'], 'Historical proposal pin; candidate code has a separate approved SHA'
  for n in reversed(names):
   subprocess.run(['git','apply','--reverse','--check',str(HOME/n)],cwd=root,check=True);subprocess.run(['git','apply','--reverse',str(HOME/n)],cwd=root,check=True)
  for n,s in base.items():assert (root/n).read_bytes()==s.encode()
 print(json.dumps(dict(apply='PASS',reverse='PASS_BYTE_IDENTICAL',main_v5_800_and503_deferral='PASS_ACTUAL_PATCHED_FETCH_AST',live_collector='UNVERIFIED_DEPENDENCY_AND_NETWORK_NOT_EXERCISED',main_modified=False)))
if __name__=='__main__':main()
