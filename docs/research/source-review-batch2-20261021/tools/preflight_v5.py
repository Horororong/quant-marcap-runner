import datetime,hashlib,json,os,re,urllib.request,zipfile
from pathlib import Path
P=Path(__file__).parent
D=Path('/workspace/quant-backups/quant-source-review-v5-20261021')
B=json.loads((D/'BUILD.json').read_text())
assert B['bytes']==8635482 and B['payload_files']==46
assert B['sha256']=='c1de9872045c0d1d066b37fb7aab5f968f986c5854bda1083f238a261ff46490'
raw=Path(B['archive']).read_bytes()
assert len(raw)==B['bytes'] and hashlib.sha256(raw).hexdigest()==B['sha256']
secret_names=[k for k in os.environ if re.search(r'(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)$',k)]
known=[os.environ[k].encode() for k in secret_names if len(os.environ[k])>=16]
patterns={
 'github_token':rb'(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'credential_url':rb'https?://[^\s/:]+:[^\s/@]{6,}@',
 'literal_secret_assignment':rb'(?i)(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\s*[=:]\s*[\"\x27][A-Za-z0-9_./+=-]{24,}[\"\x27]'
}
hits=[]
with zipfile.ZipFile(Path(B['archive'])) as z:
 manifest=json.loads(z.read('MANIFEST.json'));assert len(manifest['files'])==46
 for name in z.namelist():
  data=z.read(name)
  if any(v in data for v in known):hits.append({'path':name,'kind':'configured_secret_value'})
  for kind,pattern in patterns.items():
   if re.search(pattern,data):hits.append({'path':name,'kind':kind})
assert not hits, json.dumps(hits)
req=urllib.request.Request('https://api.github.com/repos/Horororong/quant-marcap-runner',headers={'Authorization':'Bearer '+os.environ['GH_BACKUP_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'quant-v5-preflight'})
with urllib.request.urlopen(req,timeout=45) as r:repo=json.load(r)
assert repo['full_name']=='Horororong/quant-marcap-runner'
report=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),repository=repo['full_name'],visibility=repo['visibility'],private=repo['private'],draft_is_not_a_privacy_boundary=True,archive_bytes=len(raw),archive_sha256=B['sha256'],payload_files=46,configured_secret_values_checked=len(known),secret_value_hits=hits,patterns_checked=list(patterns),public_suitability='APPROVED_SCOPE: public DART source excerpts, RESEARCH_ONLY outputs, source provenance and recovery instructions. Workspace paths/run IDs are operational metadata, not credentials. No detected credential values or private keys; no private account records included.',user_explicit_approval=True)
(D/'TRANSFER_PREFLIGHT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(P/'USER_APPROVAL_FOR_V5.json').write_text(json.dumps(dict(repository=repo['full_name'],draft=True,archive_sha256=B['sha256'],archive_bytes=8635482,user_explicit_approval=True,approval='User explicitly approved this exact v5 payload in this session, including public suitability check and authenticated remote readback.',checked_at=report['checked_at']),indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
