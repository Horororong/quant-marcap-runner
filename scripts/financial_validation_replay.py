"""Offline common-collector replay of only the authorized100 + prior10 sources."""
import argparse,base64,gzip,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from financial_review_gate import unpack
from financial_rollout import atomic,run_batch,sha
def main(root,out):
    manifest=json.loads((root/'source_manifest.json').read_text());files={};samples={}
    for pack in manifest['packs']:
        data=unpack(root/pack['path'],pack['compressed_sha256']);files.update(data)
        for s in json.loads(data['selection.json'])['samples']:samples[s['rcept_no']]=s
    if len(samples)!=110:raise ValueError('EXPECTED_AUTHORIZED100_PLUS_PRIOR10_ONLY')
    out.mkdir(parents=True,exist_ok=False);cache=out/'readonly-cache';cache.mkdir();subjects={}
    metas=[]
    for receipt in sorted(samples):
        archives=[(k,b)for k,b in files.items()if k.startswith('native/'+receipt+'-')and k.endswith('.zip')]
        if len(archives)!=1:raise ValueError('ONE_PRESERVED_ARCHIVE_REQUIRED')
        name,b=archives[0];dest=cache/Path(name).name;dest.write_bytes(b)
        metas.append({**samples[receipt],'_source_cache_sha256':sha(b)})
    old=os.environ.get('FINANCIAL_VALIDATION_SOURCE_CACHE');os.environ['FINANCIAL_VALIDATION_SOURCE_CACHE']=str(cache.resolve())
    try:
        # Each replay preserves the same90s/document and600s/run boundary.
        for i in range(0,len(metas),20):
            folder=out/f'chunk{i//20:02d}'
            code=run_batch(metas[i:i+20],folder)
            if code:raise RuntimeError('OFFLINE_REPLAY_STOPPED_CHECKPOINT_PRESERVED')
            for p in (folder/'results').glob('*.json'):subjects[p.stem]=json.loads(p.read_text())
    finally:
        if old is None:os.environ.pop('FINANCIAL_VALIDATION_SOURCE_CACHE',None)
        else:os.environ['FINANCIAL_VALIDATION_SOURCE_CACHE']=old
    packed=gzip.compress(json.dumps(dict(subjects=subjects,new_HTTP_calls=0,source_mode='IMMUTABLE_OFFICIAL_ZIP_CACHE'),ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
    (out/'subjects_v92.json.gz.b64').write_bytes(base64.b64encode(packed)+b'\n')
    summary=dict(documents=len(subjects),new_HTTP_calls=0,compressed_sha256=sha(packed),rows=sum(len(s['rows'])for s in subjects.values()),parser_version=next(iter(subjects.values()))['parser_version'])
    atomic(out/'summary.json',summary);print(json.dumps(summary))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.root,a.output)
