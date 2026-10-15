"""Verify previously collected artifacts; no DART, financial parsing or replay.

HTTP restore gaps are UNVERIFIED, hash/content mismatches FAIL. Exactly one
attempt per pinned artifact. Original audit evidence is never rewritten.
"""
import argparse, csv, hashlib, io, json, os, zipfile
from pathlib import Path
from urllib import request, error, parse

HOME = Path(__file__).resolve().parent
REPO = HOME.parents[2]
ARTIFACTS = [
    {'kind': 'originals60', 'id': 11906556857, 'bytes': 4473693,
     'sha256': '07fc734b53aa966974f42ec4836629394362d01e07b3f1fc33d7f5c15822c105'},
    {'kind': 'replay60', 'id': 11906601896, 'bytes': 265460,
     'sha256': '07c671aa0b6025f181b32179af084e6a1fd5db5e6291cfb768899e9df9ba99b9'},
]
def digest(raw): return hashlib.sha256(raw).hexdigest()
class RestoreGap(Exception):
    def __init__(self,kind,http=None):self.kind,self.http=kind,http
class Redirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):
        redirected=super().redirect_request(req,fp,code,msg,headers,url)
        if redirected is not None and parse.urlsplit(req.full_url).netloc!=parse.urlsplit(url).netloc:
            redirected.remove_header('Authorization')
        return redirected
def fetch(entry,folder):
    token=os.getenv('GH_TOKEN','')
    if not token:raise RestoreGap('GITHUB_ACTIONS_TOKEN_MISSING')
    url=f'https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/{entry["id"]}/zip'
    req=request.Request(url,headers={'Authorization':'Bearer '+token})
    try:
        with request.build_opener(Redirect()).open(req,timeout=30)as response:
            raw=response.read(8*1024*1024+1)
    except error.HTTPError as exc:raise RestoreGap('ARTIFACT_HTTP_FAILURE',exc.code)from None
    except Exception:raise RestoreGap('ARTIFACT_TRANSPORT_FAILURE')from None
    assert len(raw)==entry['bytes'] and digest(raw)==entry['sha256'],'pinned artifact bytes/SHA mismatch'
    path=folder/(entry['kind']+'.zip');path.write_bytes(raw);return path
def verify_originals(z):
    expected=json.loads((HOME/'preservation60.json').read_text());names=z.namelist()
    assert len(expected)==60 and z.testzip()is None
    for entry in expected:
        basename=entry['rcept_no']+'-'+entry['sha256']+'.zip'
        matches=[n for n in names if Path(n).name==basename];assert len(matches)==1,basename
        raw=z.read(matches[0]);assert digest(raw)==entry['sha256'],basename
        with zipfile.ZipFile(io.BytesIO(raw))as nested:
            assert nested.testzip()is None
            assert set(nested.namelist())=={m['name']for m in entry['members']}
            for member in entry['members']:assert digest(nested.read(member['name']))==member['sha256']
    return 60
def member(z,suffix):
    names=[n for n in z.namelist()if n==suffix or n.endswith('/'+suffix)]
    assert len(names)==1,suffix
    return z.read(names[0])
def verify_replays(z):
    proof=json.loads((HOME/'evidence/preservation_verification.json').read_text())
    assert z.testzip()is None and len(proof['replay60_identical'])==60
    for name,expected in proof['replay60_identical'].items():
        assert digest(member(z,'replay60/'+name))==expected,name
    root=REPO/'docs/audits/financial-extraction-stage3-20261014/results'
    for name,expected in proof['financial_results_identical'].items():
        raw=member(z,'results/'+name)
        assert digest(raw)==expected and raw==(root/name).read_bytes(),name
    fields=list(csv.DictReader(io.StringIO(member(z,'results/protected518.csv').decode('utf-8-sig'))))
    assert len(fields)==518 and all(r['verdict']==r['new_independent_field_verdict']=='PASS'and r['before_value']==r['after_value']for r in fields)
    summary=json.loads(member(z,'results/validation_summary.json'))
    assert summary['holdout64_targets']=={'PASS':64,'FAIL':0,'UNVERIFIED':0}
    return {'replay60':60,'financial_results_byte_identical':len(proof['financial_results_identical']),
            'protected518':518,'core64':64}
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--local-originals',type=Path);p.add_argument('--local-replays',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result={'scope':'preserved-artifact integrity only, no financial reprocessing','requests':0,
            'original60':'UNVERIFIED','replay60':'UNVERIFIED','protected518':'UNVERIFIED',
            'core64':'UNVERIFIED','status':'UNVERIFIED','investment_approved':0}
    exit_code=0
    try:
        for entry in ARTIFACTS:
            local=a.local_originals if entry['kind']=='originals60'else a.local_replays
            if local is None:
                result['requests']+=1;local=fetch(entry,a.output)
            # Local mode verifies individual pinned members even when the outer
            # ZIP has different transport timestamps. CI pins the exact archive.
            with zipfile.ZipFile(local)as z:
                if entry['kind']=='originals60':
                    result['original60_verified']=verify_originals(z);result['original60']='PASS'
                else:
                    result['verified']=verify_replays(z)
                    for k in ['replay60','protected518','core64']:result[k]='PASS'
        result['status']='PASS'
    except RestoreGap as exc:
        result['restore_error']={'kind':exc.kind,'http_status':exc.http,'retries':0}
    except Exception as exc:
        result['status']='FAIL';result['verification_error_type']=type(exc).__name__;exit_code=1
    (a.output/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return exit_code
if __name__=='__main__':raise SystemExit(main())
