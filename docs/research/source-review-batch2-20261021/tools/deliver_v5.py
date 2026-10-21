"""Only new small delta, authenticated readback; old releases never modified."""
import base64,hashlib,json,os,tempfile,urllib.parse,urllib.request,zipfile
from pathlib import Path
P=Path(__file__).parent;D=Path('/workspace/quant-backups/quant-source-review-v5-20261021');B=json.loads((D/'BUILD.json').read_text());A='https://api.github.com/repos/Horororong/quant-marcap-runner';H={'Authorization':'Bearer '+os.environ['GH_BACKUP_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'quant-source-review-v5'}
def sha(b):return hashlib.sha256(b).hexdigest()
# Automatic review blocked this new external payload; require its explicit approval.
approval_file=P/'USER_APPROVAL_FOR_V5.json'
assert approval_file.exists(),'V5_EXTERNAL_TRANSFER_APPROVAL_REQUIRED'
approved=json.loads(approval_file.read_text())
assert approved.get('repository')=='Horororong/quant-marcap-runner'and approved.get('draft')is True and approved.get('archive_sha256')==B['sha256']and approved.get('user_explicit_approval')is True,'V5_APPROVAL_SCOPE_MISMATCH'

class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,hdrs,url):
  nxt=super().redirect_request(req,fp,code,msg,hdrs,url)
  if nxt and urllib.parse.urlsplit(req.full_url).hostname!=urllib.parse.urlsplit(url).hostname:nxt.remove_header('Authorization')
  return nxt
op=urllib.request.build_opener(Redirect())
def req(url,data=None,extra=None,method=None):return op.open(urllib.request.Request(url,data=data,headers={**H,**(extra or{})},method=method),timeout=90)
f=D/'RELEASE.json'
if f.exists():release=json.loads(f.read_text())
else:
 body=dict(tag_name='backup-quant-source-review-v5-20261021-397d311',target_commitish='397d311e212765b872106b3596814a705ecb178d',name='quant-source-review-v5-20261021-397d311',draft=True,body='RESEARCH_ONLY changed source-review evidence; collector PR45 deployed asfd232d129bfa2ef01714b94890460c5ef47bdbf0. Code397d311e212765b872106b3596814a705ecb178d; original pinned kit unchanged. SHA256'+B['sha256']+'. New document audit and current12future envelopes only; prior backups preserved; original integrationCI reused. Use authenticated download_backup.py and the listed Base64 parts; no credentials included.')
 with req(A+'/releases',json.dumps(body).encode(),{'Content-Type':'application/json'},'POST')as r:release=json.load(r)
 f.write_text(json.dumps(release,indent=2)+'\n')
assert release['draft'];helper=Path('/workspace/quant-backups/quant-full-project-v2-20261020/download_backup.py').read_text().replace('RELEASE=418935587','RELEASE='+str(release['id']));(D/'download_backup.py').write_text(helper)
T=D/'transfer-text';T.mkdir(exist_ok=True);parts=[]
with Path(B['archive']).open('rb')as stream:
 while raw:=stream.read(4*1024**2):
  wire=base64.b64encode(raw);name=Path(B['archive']).name+'.b64part'+str(len(parts)+1).zfill(3);p=T/name
  if p.exists():assert p.read_bytes()==wire
  else:p.write_bytes(wire)
  parts.append(dict(name=name,bytes=len(raw),sha256=sha(raw),encoded_bytes=len(wire),encoded_sha256=sha(wire)))
ledger=dict(archive_name=Path(B['archive']).name,archive_bytes=B['bytes'],archive_sha256=B['sha256'],encoding='Independently decode each Base64 part and concatenate in listed order',parts=parts);(D/'download_manifest_text.json').write_text(json.dumps(ledger,indent=2)+'\n')
with req(release['url']+'/assets?per_page=100')as r:existing={x['name']:x for x in json.load(r)}
paths=[T/x['name']for x in parts]+[D/n for n in ['download_manifest_text.json','download_backup.py','PROVENANCE.json','REPORT.md','RESUME.md','VERIFICATION.json',Path(B['archive']).name+'.sha256']];assets={}
for p in paths:
 raw=p.read_bytes()
 if p.name in existing:a=existing[p.name];assert a['size']==len(raw)and a['state']=='uploaded'
 else:
  url=release['upload_url'].split('{')[0]+'?'+urllib.parse.urlencode({'name':p.name})
  with req(url,raw,{'Content-Type':'text/plain'},'POST')as r:a=json.load(r)
  assert a['state']=='uploaded'and a['size']==len(raw)
 assets[p.name]={k:a[k]for k in ['id','name','size','url','browser_download_url']};(D/'DELIVERY_PROGRESS.json').write_text(json.dumps(assets,indent=2)+'\n');print('PRESERVED_OR_UPLOADED',p.name,flush=True)
tmp=Path(tempfile.mkdtemp(prefix='quant-v5-remote-',dir='/tmp'));archive=tmp/ledger['archive_name']
with archive.open('xb')as out:
 for part in parts:
  with req(assets[part['name']]['url'],extra={'Accept':'application/octet-stream'})as r:wire=r.read()
  assert len(wire)==part['encoded_bytes']and sha(wire)==part['encoded_sha256'];raw=base64.b64decode(wire,validate=True);assert len(raw)==part['bytes']and sha(raw)==part['sha256'];out.write(raw)
assert archive.stat().st_size==B['bytes']and sha(archive.read_bytes())==B['sha256']
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None;manifest=json.loads(z.read('MANIFEST.json'))
 for row in manifest['files']:
  p=Path(row['path']);assert not p.is_absolute()and'..'not in p.parts;raw=z.read(row['path']);assert len(raw)==row['bytes']and sha(raw)==row['sha256'];dest=tmp/'unpacked'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
for p in paths[len(parts):]:
 with req(assets[p.name]['url'],extra={'Accept':'application/octet-stream'})as r:assert r.read()==p.read_bytes()
receipt=dict(status='PASS_V5_AUTHENTICATED_READBACK_AND_SEPARATE_UNPACK',archive_sha256=B['sha256'],archive_bytes=B['bytes'],parts=len(parts),payload_files_verified=len(manifest['files']),zip_crc='PASS',separate_directory=str(tmp),release_id=release['id'],release_url=release['html_url'],draft=True,old_backups_or_raw_data_retransmitted=False,assets=assets)
raw=(json.dumps(receipt,indent=2)+'\n').encode();(D/'DELIVERY_COMPLETED.json').write_bytes(raw)
with req(release['upload_url'].split('{')[0]+'?name=DELIVERY_COMPLETED.json',raw,{'Content-Type':'text/plain'},'POST')as r:asset=json.load(r)
with req(asset['url'],extra={'Accept':'application/octet-stream'})as r:assert r.read()==raw
print(json.dumps({k:v for k,v in receipt.items()if k!='assets'},indent=2),flush=True)
