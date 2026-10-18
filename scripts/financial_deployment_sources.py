"""Freeze corporations/receipts before source-value review; no DART requests."""
import argparse, base64, csv, gzip, hashlib, io, json, os, re, zipfile
from pathlib import Path
from urllib import request, error, parse
ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'docs/audits/financial-deployment-20261018'
def sha(b): return hashlib.sha256(b).hexdigest()
class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args): return None
def rows(path):
    with path.open(encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def restore(spec, out):
    out.mkdir(parents=True, exist_ok=False)
    api = f"https://api.github.com/repos/Horororong/quant-marcap-runner/actions/artifacts/{spec['id']}/zip"
    try:
        request.build_opener(NoRedirect()).open(request.Request(api, headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']}), timeout=25)
        raise ValueError('EXPECTED_OFFICIAL_REDIRECT')
    except error.HTTPError as e:
        if e.code != 302: raise ValueError('ARTIFACT_HTTP_'+str(e.code)) from None
        target = e.headers['Location']; host = parse.urlparse(target).hostname or ''
    if parse.urlparse(target).scheme != 'https' or not host.endswith(('.blob.core.windows.net','.actions.githubusercontent.com','.githubusercontent.com')):
        raise ValueError('UNAPPROVED_ARCHIVE_HOST')
    archive = out/'original.zip'; digest = hashlib.sha256(); size = 0
    with request.build_opener(NoRedirect()).open(target, timeout=60) as response, archive.open('xb') as f:
        while part := response.read(1048576):
            size += len(part)
            if size > 270*1024*1024: raise ValueError('ARCHIVE_BYTE_BUDGET')
            digest.update(part); f.write(part)
    assert digest.hexdigest() == spec['sha256'], 'Original artifact SHA mismatch'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(out/'evidence')
    return out/'evidence'
def main(out):
    out.mkdir(parents=True, exist_ok=False)
    plan = json.loads((HOME/'independent_plan.json').read_text())
    with gzip.open(ROOT/'data/financials/legacy_2000_2014/legacy_filings.csv.gz','rt',encoding='utf-8-sig') as f:
        index = {r['rcept_no']:r for r in csv.DictReader(f)}
    sources=[]; chosen=[]; used=set(plan['excluded_corp_codes']); shortages=[]
    for spec in plan['archives']:
        folder=restore(spec,out/str(spec['id'])); sources.append((spec,folder))
        available={p.name[:14] for p in folder.rglob('*.zip') if re.fullmatch(r'\d{14}-[a-f0-9]{64}\.zip',p.name)}
        state_paths=list(folder.rglob('effective-state.csv'))
        if len(state_paths)!=1: raise ValueError('Expected exactly one preserved effective state')
        state=rows(state_paths[0])
        for status,count in spec['strata'].items():
            candidates=[dict(index.get(r['rcept_no'],{}),**r) for r in state if r['rcept_no'] in available and r.get('status')==status]
            buckets={}
            for r in candidates:
                corp=r.get('corp_code')
                if not corp or corp in used or r['rcept_no'] in plan['excluded_receipts']: continue
                buckets.setdefault((r.get('fiscal_year',''),r.get('period',''),r.get('corp_cls','')),[]).append(r)
            for group in buckets.values(): group.sort(key=lambda r:sha((plan['seed']+':'+r['rcept_no']).encode()))
            selected=[]
            while any(buckets.values()) and len(selected)<count:
                for key in sorted(buckets):
                    group=buckets[key]
                    while group and group[0]['corp_code'] in used: group.pop(0)
                    if group and len(selected)<count:
                        r=group.pop(0);used.add(r['corp_code']);selected.append(r)
            for r in selected: chosen.append(dict(r,sample='D'+str(len(chosen)+1).zfill(2),artifact=spec['id'],stratum=status))
            if len(selected)<count: shortages.append(dict(artifact=spec['id'],status=status,wanted=count,available=len(selected)))
    selection=dict(plan_sha256=sha((HOME/'independent_plan.json').read_bytes()),samples=chosen,shortages=shortages,source_amounts_opened=False,parser_executed=False)
    dest=out/'selected_receipts.json';dest.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(selection_sha256=sha(dest.read_bytes()),receipts=[r['rcept_no'] for r in chosen],companies=len({r['corp_code'] for r in chosen}),shortages=shortages)),flush=True)
    if len(chosen)<12 or len({r['corp_code'] for r in chosen})<12: raise ValueError('Independent minimum12 not met; no source-value review')
    # The list and digest are now durable. Only selected originals/amounts follow.
    payload=dict(selection=selection,files={},manifest=[],metrics=[])
    for spec,folder in sources:
        wanted={r['rcept_no'] for r in chosen if r['artifact']==spec['id']}
        metrics=list(folder.rglob('new-metrics.csv'))
        if len(metrics)==1: payload['metrics'].extend(r for r in rows(metrics[0]) if r.get('rcept_no') in wanted)
        for rec in [r for r in chosen if r['artifact']==spec['id']]:
            archives=[]
            for p in sorted(folder.rglob(rec['rcept_no']+'-*.zip')):
                b=p.read_bytes();name=str(spec['id'])+'/'+p.name
                if name in payload['files']: continue
                payload['files'][name]=base64.b64encode(b).decode();archives.append(dict(path=name,bytes=len(b),sha256=sha(b)))
            assert archives, 'Frozen source filename vanished'
            payload['manifest'].append(dict(receipt=rec['rcept_no'],sample=rec['sample'],archives=archives))
    packed=gzip.compress(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
    assert len(packed)<12*1024*1024
    encoded=base64.b64encode(packed).decode()+'\n'
    req=request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner/git/blobs',data=json.dumps(dict(content=encoded,encoding='utf-8')).encode(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/json'})
    with request.urlopen(req,timeout=60) as response: blob=json.load(response)
    result=dict(blob_sha=blob['sha'],compressed_bytes=len(packed),compressed_sha256=sha(packed),selection_sha256=sha(dest.read_bytes()),receipts=[r['rcept_no'] for r in chosen],new_DART_calls=0)
    (out/'transfer.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
