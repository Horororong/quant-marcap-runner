"""Actual browser and data E2E; no collection, pip, mocks or alternative engine."""
import argparse, hashlib, json, os, select, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-I',str(ROOT/'scripts/research_web.py'),'--store',str(out/'store'),'--port','0']
    with (out/'server-stderr.log').open('w')as err:
        server=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,cwd=ROOT)
        try:
            if not select.select([server.stdout],[],[],30)[0]:raise RuntimeError('SERVER_START_TIMEOUT')
            ready=json.loads(server.stdout.readline());assert ready['status']=='ready',ready
            with(out/'browser.log').open('w')as log:
                try:
                    subprocess.run(['node',str(ROOT/'scripts/verify_research_workspace.cjs'),ready['url'],str(out/'browser')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                except(subprocess.CalledProcessError,subprocess.TimeoutExpired):
                    log.flush()
                    print((out/'browser.log').read_text()[-16000:],file=sys.stderr)
                    raise
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
    proof=json.loads((out/'browser/verification.json').read_text());runs={r['name']:out/'store/runs'/r['id']/'run'for r in proof['runs']}
    natural=runs['research_size_top1_2024'];same=runs['json_same_top1'];changed=runs['amended_top1']
    equal={}
    for name in ['daily_nav.csv','target_weights.csv','selections.csv','held_return_checks.csv']:
        first=natural/'artifacts'/name;second=same/'artifacts'/name
        assert first.is_file()and second.is_file(),name
        assert first.read_bytes()==second.read_bytes(),name
        equal[name]=digest(first)
    import pandas as pd
    x=pd.read_csv(natural/'artifacts/daily_nav.csv');y=pd.read_csv(changed/'artifacts/daily_nav.csv')
    assert x['Date'].equals(y['Date'])
    assert x['NAV_Gross'].equals(y['NAV_Gross'])
    assert not x['NAV_Net_fixed_cost'].equals(y['NAV_Net_fixed_cost'])
    # Existing independent raw-price/share/cash oracle, never the engine formula.
    import importlib.util
    source=ROOT/'docs/research/stage15-research-environment-20261017/verify_research_nav.py'
    spec=importlib.util.spec_from_file_location('independent_book',source);book=importlib.util.module_from_spec(spec);spec.loader.exec_module(book)
    independent={name:book.verify(run,out/'independent'/name)for name,run in runs.items()if name!='json_same_top1'}
    baseline=json.loads((ROOT/'docs/research/stage15-research-environment-20261017/numeric_manifest.json').read_text())
    keys={'research_size_top1_2024':'size2024','research_momentum_top3_2020':'momentum2020','research_size_deciles_2019_2020_v1':'original'}
    baseline_checks={}
    for name,label in keys.items():
        key=label+'/artifacts/daily_nav.csv'
        if key not in baseline:raise RuntimeError('Missing preserved regression '+key)
        actual=digest(runs[name]/'artifacts/daily_nav.csv');assert actual==baseline[key]['sha256'],name
        baseline_checks[name]=actual
    result=dict(status='PASS_REAL_WORKSPACE_E2E',browser=proof,equivalent_json_artifacts=equal,
        original_nav_preserved=baseline_checks,independent_books=independent,
        cost_change='Gross unchanged; fixed-cost Net changed; canonical engine/CURRENT only',
        investment_approved=False,external_model_connected=False)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k not in {'browser','independent_books'}},ensure_ascii=False))
    return 0
if __name__=='__main__':raise SystemExit(main())
