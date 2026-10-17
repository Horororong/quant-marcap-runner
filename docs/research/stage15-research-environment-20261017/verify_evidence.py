"""Verify preserved bytes and explicit source controls, without any network.

This does not authenticate complete legal/PIT history. The Celltrion181000
reference is explicitly an earlier official-page observation, not raw HTTP.
"""
import base64,hashlib,json
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]

def main():
 # Stage14's full historical manifest also pins the workflow, which Stage15
 # intentionally extends. Verify its preserved evidence entries without
 # pretending the previous workflow is still the current workflow.
 previous=json.loads((HOME.parent/'stage14-celltrion-2019-20261017/artifact_manifest.json').read_text())['files']
 for name,pin in previous.items():
  if name.startswith('docs/research/stage14-celltrion-2019-20261017/'):
   raw=(ROOT/name).read_bytes()
   assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],name
 pins=json.loads((HOME/'evidence_manifest.json').read_text())
 for name,pin in pins['files'].items():
  raw=(ROOT/name).read_bytes()
  assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],name
 raw_by_hash={}
 for folder in [HOME/'evidence',HOME.parent/'stage14-celltrion-2019-20261017/evidence']:
  for p in folder.iterdir():
   if not p.is_file():continue
   raw=p.read_bytes()
   if p.suffix=='.b64':raw=base64.b64decode(raw.strip(),validate=True)
   raw_by_hash[hashlib.sha256(raw).hexdigest()]=p
 facts=json.loads((ROOT/'config/research/stock_dividends_2019_2020.json').read_text())['events']
 controls=[]
 for f in facts:
  for key in ['terms_evidence','reference_evidence']:
   e=f[key]
   if f['event_id']=='068270_stock_dividend_2019' and key=='reference_evidence':
    p=ROOT/'docs/research/stage11-official-event-evidence-20261016/evidence.json'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256']
    s=next(s for s in json.loads(p.read_text())['sources'] if s['id']=='E11-01')
    assert s['short_exact_excerpt']=='셀트리온 : 181,000원'
    kind='PRESERVED_OFFICIAL_PAGE_OBSERVATION_NOT_HTTP_BYTES'
   else:
    assert e['sha256'] in raw_by_hash,(f['event_id'],key)
    p=raw_by_hash[e['sha256']];kind='PRESERVED_ORIGINAL_BYTES'
   controls.append(dict(event=f['event_id'],field=key,path=str(p.relative_to(ROOT)),evidence_level=kind))
  if f['listing']:
   assert f['listing']['evidence']['sha256'] in raw_by_hash
   controls.append(dict(event=f['event_id'],field='listing',evidence_level='PRESERVED_ORIGINAL_BYTES_NOT_ACCOUNT_CREDIT'))
  if f['decision']:
   e=f['decision']['evidence']
   if f['security']=='091990':assert e['sha256'] in raw_by_hash
   else:
    issuer=(HOME.parent/'stage14-celltrion-2019-20261017/evidence/issuer_697_text.txt').read_text()
    assert '2020년 3월 27일 결의된' in issuer and '2020.04.06' in issuer
   controls.append(dict(event=f['event_id'],field='decision',evidence_level='ORIGINAL_MEMBER' if f['security']=='091990' else 'PRESERVED_ISSUER_TEXT_RAW_RESPONSE_HASH_IN_PRIOR_ARTIFACT'))
 print(json.dumps(dict(status='PASS_PRESERVED_EVIDENCE_CONTROLS',files=len(pins['files']),controls=controls,investment_approved=False),ensure_ascii=False))
if __name__=='__main__':main()
