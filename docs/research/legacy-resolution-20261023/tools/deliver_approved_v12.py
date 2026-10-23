"""Exact explicitly approved v12 only; no CI driver or research branch writes."""
import hashlib,json,os,re,subprocess,tempfile,urllib.request,urllib.parse,zipfile
from pathlib import Path
P=Path('/workspace/quant-legacy-resolution-20261023');P.mkdir(parents=True,exist_ok=True);B=Path('/workspace/quant-backups/quant-recovery-union-v12-20261023');R=Path('/workspace/quant-parser-repair-20261021/code')
A='https://api.github.com/repos/Horororong/quant-marcap-runner';expected='464aa445c1c1d92a891bad9072973f34cc27bf2e92cbb13b8947f38c4a3a820e';archive=B/'quant-recovery-union-v12-20261023.zip'
def sha(b):return hashlib.sha256(b).hexdigest()
assert archive.stat().st_size==538254 and sha(archive.read_bytes())==expected
manifest=json.loads((B/'TRANSFER_MANIFEST.json').read_text());assert manifest['payload_files']==41 and len(manifest['files'])==41
known=[v.encode()for k,v in os.environ.items()if re.search('TOKEN|PASSWORD|SECRET|API_KEY|ACCESS_KEY',k,re.I)and len(v)>=12];patterns=[rb'github_pat_[A-Za-z0-9_]{30,}',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'AKIA[0-9A-Z]{16}']
def scan(data,label):assert not any(re.search(p,data)for p in patterns)and not any(v in data for v in known),label
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None and len(z.namelist())==42
 assert z.read('TRANSFER_MANIFEST.json')==(B/'TRANSFER_MANIFEST.json').read_bytes()
 for f in manifest['files']:
  b=z.read(f['path']);assert len(b)==f['bytes'] and sha(b)==f['sha256'];scan(b,f['path'])
 mapping=json.loads(z.read('RECOVERY_MAP.json'))
 for delta in mapping['code_bundles']:
  assert sha(z.read(delta['path']))==delta['sha256']
  for path in subprocess.check_output(['git','diff','--name-only',delta['base'],delta['target']],cwd=R,text=True).splitlines():
   scan(subprocess.check_output(['git','show',delta['target']+':'+path],cwd=R),path)
H={'Authorization':'Bearer '+os.environ['GH_BACKUP_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'quant-exact-approved-v12'}
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,hdrs,url):
  nxt=super().redirect_request(req,fp,code,msg,hdrs,url)
  if nxt and urllib.parse.urlsplit(req.full_url).hostname!=urllib.parse.urlsplit(url).hostname:nxt.remove_header('Authorization')
  return nxt
op=urllib.request.build_opener(Redirect())
def req(url,data=None,extra=None,method=None):return op.open(urllib.request.Request(url,data=data,headers={**H,**(extra or{})},method=method),timeout=90)
with req(A)as r:repo=json.load(r)
assert repo['private']is False and repo['visibility']=='public'
pre=dict(status='PASS_EXACT_APPROVAL_PREFLIGHT',archive_bytes=538254,archive_sha256=expected,payload_files=41,ZIP_entries=42,ZIP_manifest_files=1,secret_hits=0,bundle_changed_source_blobs_scanned=True,repository_public=True,public_suitability='Research outputs, provenance and public-source audit; no credentials or private personal records detected',user_explicit_approval=True,CI_index_publication=False)
(P/'V12_TRANSFER_PREFLIGHT.json').write_text(json.dumps(pre,indent=2)+'\n')
release_file=P/'V12_RELEASE.json'
if release_file.exists():release=json.loads(release_file.read_text())
else:
 body=dict(tag_name='backup-quant-recovery-union-v12-20261023-7691fd2',target_commitish='29b6c4a2c277f6b2070e4bf70da54899f9fe4bcf',name='quant-recovery-union-v12-20261023',draft=True,body='RESEARCH_ONLY exact explicitly approved v12 recovery delta. ZIP538254bytes; SHA256 '+expected+'. 41payloadfiles plus TRANSFER_MANIFEST.json =42ZIPentries. Logical reconstructed store:46files,3savedcomparisons/5runs. Includes f8 and7691 incremental Git bundles over public29b; bundle preservation is NOT research-branch publication or remoteCI. Existing publicGit/JSON and pinned-kit deterministic HTML reconstruction required; kit/common data excluded. Separate/tmp CRC/SHA/reopenPASS; whole remote-only project restoreNOTPERFORMED. Credentials0; financialHOLD/PIT0of6 preserved. Existing backups unchanged.')
 with req(A+'/releases',json.dumps(body).encode(),{'Content-Type':'application/json'},'POST')as r:release=json.load(r)
 release_file.write_text(json.dumps(release,indent=2)+'\n')
assert release['draft']is True
with req(release['url']+'/assets?per_page=100')as r:existing={x['name']:x for x in json.load(r)}
paths=[archive,B/'TRANSFER_MANIFEST.json',B/'VERIFICATION.json',B/'SHA256SUMS.txt'];assets={}
for p in paths:
 raw=p.read_bytes();scan(raw,p.name)
 if p.name in existing:asset=existing[p.name];assert asset['size']==len(raw) and asset['state']=='uploaded'
 else:
  typ='application/zip'if p==archive else'application/json'if p.suffix=='.json'else'text/plain'
  with req(release['upload_url'].split('{')[0]+'?'+urllib.parse.urlencode({'name':p.name}),raw,{'Content-Type':typ},'POST')as r:asset=json.load(r)
  assert asset['state']=='uploaded'and asset['size']==len(raw)
 assets[p.name]={k:asset[k]for k in ['id','name','size','url','browser_download_url']}
 (P/'V12_ASSETS.json').write_text(json.dumps(assets,indent=2)+'\n')
# Authenticated retrieval with cross-host Authorization removed; never print signed redirect.
with req(assets[archive.name]['url'],extra={'Accept':'application/octet-stream'})as response:remote=response.read()
assert len(remote)==538254 and sha(remote)==expected,'REMOTE_BYTES_OR_SHA256_MISMATCH'
with tempfile.TemporaryDirectory(prefix='quant-v12-remote-readback-',dir='/tmp')as t:
 p=Path(t)/archive.name;p.write_bytes(remote)
 with zipfile.ZipFile(p)as z:
  assert z.testzip()is None and len(z.namelist())==42
  for f in manifest['files']:assert sha(z.read(f['path']))==f['sha256']
for p in paths[1:]:
 with req(assets[p.name]['url'],extra={'Accept':'application/octet-stream'})as r:assert r.read()==p.read_bytes()
receipt=dict(status='PASS_V12_REMOTE_DOWNLOAD_SHA256_CRC_ALL41_PAYLOADS',release_id=release['id'],release_url=release['html_url'],draft=True,repository_public=True,archive_bytes=538254,archive_sha256=expected,payload_files=41,ZIP_entries=42,sidecar_assets=3,total_release_assets=4,secret_hits=0,existing_backups_changed=False,large_data_retransmitted=False,remote_branch_publication=False,remote_CI_for7691='NOT_RUN',assets=assets)
(P/'V12_DELIVERY_COMPLETED.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='assets'},indent=2),flush=True)
