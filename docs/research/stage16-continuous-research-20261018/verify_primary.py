"""No-network byte, identity, lifecycle and primary-price evidence assertions."""
import base64,hashlib,html,json,re,zipfile,io
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
def text(raw):
 for enc in ['utf-8','cp949','euc-kr']:
  try:return html.unescape(re.sub('<[^>]+>',' ',raw.decode(enc)))
  except UnicodeDecodeError:pass
 raise ValueError('unknown original encoding')
def main():
 first=json.loads((HOME/'evidence_manifest.json').read_text());count=0
 for name,pin in first['files'].items():
  raw=(ROOT/pin['preserved_as']).read_bytes()
  if name.endswith('.zip'):raw=base64.b64decode(raw.strip(),validate=True)
  assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],name;count+=1
  if name.endswith('.zip'):
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None;t=' '.join(text(z.read(n)) for n in z.namelist())
    assert ('셀트리온헬스케어' if name.startswith('202103269') else '셀트리온') in t
    assert all(s in t for s in ['2021-03-26','주식배당','원안대로 가결','3,003,213' if name.startswith('202103269') else '2,675,697'])
 for m in ['actions2021_manifest.json','reference2021_manifest.json']:
  for name,pin in json.loads((HOME/m).read_text())['files'].items():
   raw=(ROOT/name).read_bytes();assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],name;count+=1
 ct=text((HOME/'evidence/20210419000083_body.html').read_bytes());assert all(s in ct for s in ['셀트리온','2,675,697','2021년04월22일','2021년03월26일','A068270'])
 hc=text((HOME/'evidence/20210420000350_body.html').read_bytes());assert all(s in hc for s in ['셀트리온헬스케어','3,003,213','2021-04-23','주식배당','A091990'])
 split=text((HOME/'evidence/actions2021/20210414000374_body.html').read_bytes());assert all(s in split for s in ['카카오','88,761,861','443,809,305','500원','100원','2021년04월15일','매매거래정지 해제','A035720'])
 reference=text((HOME/'evidence/reference2021/20210414000560_body.html').read_bytes());assert all(s in reference for s in ['액면분할','카카오','112,000','2021-04-15','시행세칙 제30조'])
 halt=text((HOME/'evidence/actions2021/20210422000329_body.html').read_bytes());assert all(s in halt for s in ['LG','2021년04월29일','변경상장일','회사분할'])
 catalog=json.loads((ROOT/'config/research/stock_dividends_2019_2020_lifecycle2021_v1.json').read_text());new=[r for r in catalog['events'] if r['ex_date']=='2020-12-29']
 assert [r['decision']['actual_date'] for r in new]==['2021-03-26']*2
 assert {r['security']:r['listing']['date'] for r in new}=={'068270':'2021-04-22','091990':'2021-04-23'}
 print(json.dumps(dict(status='PASS_PRIMARY_BYTES_AND_EXPLICIT_CONTROLS',files=count,requests=23,retries=0,investment_approved=False,scope='specific2021 approvals/listings/split/reference/halt; no account-credit or history-completeness certification')))
if __name__=='__main__':main()
