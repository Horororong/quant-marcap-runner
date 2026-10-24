"""Recover preserved Q3 sources through GitHub blob API, with no DART key/call.

Fresh destination only. This verifies transport provenance/CRC, never semantics,
PIT eligibility or investment readiness. It does not modify a source ledger.
"""
import argparse,base64,gzip,hashlib,json,os,re,subprocess,sys,zlib
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_q3_three as m,financial_q3_source as q

def recover(manifest,read_blob,output):
 if manifest.get('approval_id')!=m.APPROVAL or manifest.get('raw_data_publication_requires')!=m.PUBLIC:raise ValueError('Q3_MANIFEST_SCOPE')
 if manifest.get('automatic_financial_publication')!='HOLD' or manifest.get('PIT')!='UNVERIFIED' or manifest.get('engine_eligible')is not False:raise ValueError('Q3_FINANCIAL_PROMOTION_REFUSED')
 output.mkdir(exist_ok=False,parents=True);seen={};duplicates=0;packs=[];archives=[]
 targets={x['receipt']:x for x in q.TARGETS}
 for label,proof in manifest['source_packs'].items():
  if label not in {'metadata',*targets}:raise ValueError('Q3_UNKNOWN_SOURCE_PACK')
  encoded=read_blob(proof['blob_sha'])
  if m.old.git_blob_sha(encoded)!=proof['blob_sha']:raise ValueError('GIT_BLOB_HASH_MISMATCH')
  packed=base64.b64decode(encoded,validate=False)
  if len(packed)>12*1024*1024 or q.sha(packed)!=proof['compressed_sha256']or len(packed)!=proof['compressed_bytes']:raise ValueError('Q3_COMPRESSED_HASH_OR_SIZE')
  decoder=zlib.decompressobj(31);raw=decoder.decompress(packed,64*1024*1024+1)
  if len(raw)>64*1024*1024 or not decoder.eof or decoder.unused_data:raise ValueError('Q3_DECOMPRESSION_BOUND')
  files=json.loads(raw)['files'];declared={x['path']:x for x in proof['files']}
  if files.keys()!=declared.keys() or len(declared)!=len(proof['files']):raise ValueError('Q3_FILE_MANIFEST_MISMATCH')
  for name,content in files.items():
   p=PurePosixPath(name)
   if p.is_absolute() or '..'in p.parts or '\\'in name:raise ValueError('Q3_UNSAFE_SOURCE_PATH')
   allowed_metadata=re.fullmatch(r'metadata/(\d{8})-list[12](?:\.proof)?\.json',name)
   if allowed_metadata:
    if allowed_metadata[1]not in {x['corp']for x in q.TARGETS}:raise ValueError('Q3_UNKNOWN_METADATA_COMPANY')
   elif not any(re.fullmatch(t+r'-(?:[a-f0-9]{64}\.zip|source\.json|official\.json)',name)for t in targets):raise ValueError('Q3_UNKNOWN_SOURCE_FILENAME')
   data=base64.b64decode(content,validate=True);sha=q.sha(data)
   if sha!=declared[name]['sha256']or len(data)!=declared[name]['bytes']:raise ValueError('Q3_FILE_HASH_OR_SIZE')
   if name in seen:
    if seen[name]!=sha:
     conflict=output/'conflicts'/(sha+'-'+p.name);conflict.parent.mkdir(exist_ok=True);conflict.write_bytes(data);raise ValueError('Q3_DUPLICATE_PATH_CONFLICT_BOTH_PRESERVED')
    duplicates+=1;continue
   path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);seen[name]=sha
   if name.endswith('.zip'):
    target=targets[name[:14]];checked=q.validate_archive(data,target)
    if checked['archive_sha256']!=name[15:-4]:raise ValueError('Q3_ARCHIVE_FILENAME_HASH')
    archives.append(dict(receipt=target['receipt'],archive=name,sha256=sha,ZIP_CRC='PASS'))
  packs.append(dict(label=label,blob_sha=proof['blob_sha'],compressed_sha256=q.sha(packed)))
 if len({a['receipt']for a in archives})!=len(archives):raise ValueError('Q3_DUPLICATE_ORIGINAL')
 for archive in archives:
  receipt=archive['receipt'];target=targets[receipt];pages=[]
  for page in [1,2]:
   name=target['corp']+'-list'+str(page)+'.json';path=output/'metadata'/name
   body=path.read_bytes();provenance=json.loads(path.with_suffix('.proof.json').read_text())
   if provenance.get('endpoint')!='list.json' or provenance.get('params')!=dict(q.LIST_BASE,corp_code=target['corp'],page_no=str(page))or provenance.get('sha256')!=q.sha(body):raise ValueError('Q3_LIST_SOURCE_BINDING')
   parsed=q.validate_page(body,target,page);pages.append(parsed)
   if page==int(parsed['total_page']):break
  official=q.confirm_receipt(pages,target)
  if json.loads((output/(receipt+'-official.json')).read_text())!=official:raise ValueError('Q3_OFFICIAL_SOURCE_BINDING')
  source=json.loads((output/(receipt+'-source.json')).read_text());checked=q.validate_archive((output/archive['archive']).read_bytes(),target)
  if source['target']!=target or source['official']!=official or any(source['source'].get(k)!=checked[k]for k in ['archive_sha256','members','ZIP_CRC']):raise ValueError('Q3_ORIGINAL_MEMBER_BINDING')
 report=dict(classification='RESEARCH_ONLY',DART_HTTP=0,source_packs=packs,unique_files=len(seen),repeated_identical_metadata_files_deduplicated=duplicates,raw_originals=len(archives),archives=archives,new_candidates=0,new_semantic_PASS=0,new_PIT=0,new_engine_eligible=0,financial_publication='HOLD',incomplete_receipts=[r for r in targets if r not in {a['receipt']for a in archives}])
 (output/'RECOVERY_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--revision',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if not sys.flags.isolated or sys.prefix==sys.base_prefix:raise ValueError('ISOLATED_FIXED_KIT_VENV_REQUIRED')
 if not re.fullmatch(r'\d+',a.run_id)or not re.fullmatch(r'[a-f0-9]{40}',a.revision):raise ValueError('EXACT_RUN_AND_COMMIT_REQUIRED')
 env=dict(os.environ)
 if env.get('GH_BACKUP_TOKEN'):env['GH_TOKEN']=env['GH_BACKUP_TOKEN']
 def api(path):
  result=subprocess.run(['gh','api','/repos/Horororong/quant-marcap-runner'+path],env=env,capture_output=True,text=True,timeout=30)
  if result.returncode:raise ValueError('GITHUB_SOURCE_READ_FAILED_NO_RETRY')
  return json.loads(result.stdout)
 path=str(m.BASE/'runs'/a.run_id/'manifest.json');d=api('/contents/'+path+'?ref='+a.revision)
 if d.get('encoding')=='base64':raw=base64.b64decode(d['content'])
 else:raw=base64.b64decode(api('/git/blobs/'+d['sha'])['content'])
 manifest=json.loads(raw);read_blob=lambda sha:base64.b64decode(api('/git/blobs/'+sha)['content'])
 report=recover(manifest,read_blob,a.output);report.update(source_revision=a.revision,source_run=a.run_id,manifest_sha256=q.sha(raw))
 (a.output/'RECOVERY_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
