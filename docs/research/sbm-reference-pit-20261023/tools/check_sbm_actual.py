"""Reproduce the new SBM extraction against the already preserved original."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.root));sys.path.insert(0,str(a.root/'scripts'))
from scripts.legacy_native_financials import parse_native,select_verified
from historical_source_identity import assess_identity
from financial_record_readiness import assess,binding,select_asof
from reviewed_financial_batch_bridge import normalise_reviewed

observations=[];members=[]
with zipfile.ZipFile(a.archive)as z:
 assert z.testzip()is None
 for name in z.namelist():
  if name.endswith('/'):continue
  raw=z.read(name)
  for enc in ['utf-8','cp949','euc-kr']:
   try:text=raw.decode(enc);assert text.encode(enc)==raw;break
   except(UnicodeError,AssertionError):pass
  else:raise ValueError('SOURCE_ENCODING')
  parsed=parse_native(text);observations.extend(dict(r,source_member=name,source_member_sha256=hashlib.sha256(raw).hexdigest())for r in parsed['candidates'])
  members.append(dict(member=name,member_sha256=hashlib.sha256(raw).hexdigest(),observations=len(parsed['candidates']),tables=sorted({r['table_index']for r in parsed['candidates']})))
  if name=='20100331001822.xml':primary_raw=raw;primary_text=text
assert members[0]['observations']==19 and members[0]['tables']==[71,73,79]
assert members[1]['observations']==0  # Annex lacks its own proved cover period.
selected=select_verified(observations);assert len(selected)==15
selected_path=a.output/'SBM_SELECTED.json';selected_path.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
helper=Path(__file__).with_name('review_sbm_source.py')
subprocess.run([sys.executable,'-I',str(helper),'--root',str(a.root),'--archive',str(a.archive),'--candidates',str(selected_path),'--output',str(a.output/'SBM_SOURCE_REVIEW.json')],check=True)
pack=base64.b64decode((a.root/'docs/research/source-readiness-20261019/official-market-proof.json.gz.b64').read_bytes())
assert hashlib.sha256(pack).hexdigest()=='52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23'
files={k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(pack))['files'].items()}
issuer=re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)',primary_text[:3000])
identity=dict(corp_code=issuer[1],original_issuer=issuer[2],rcept_no='20100331001822',stock_code='037630',source_member_sha256=hashlib.sha256(primary_raw).hexdigest(),source_archive_sha256=hashlib.sha256(a.archive.read_bytes()).hexdigest())
identities=[]
for day in ['20100401','20100430']:
 signal=day[:4]+'-'+day[4:6]+'-'+day[6:];names=[f'stk_bydd_trd_{day}.json',f'ksq_bydd_trd_{day}.json'];official=[r for n in names for r in json.loads(files[n])['OutBlock_1']]
 evidence=dict(date=signal,source=names,sha256={n:hashlib.sha256(files[n]).hexdigest()for n in names},source_pack_sha256=hashlib.sha256(pack).hexdigest())
 verdict=assess_identity(identity,primary_raw,official,evidence,signal);assert verdict['verdict']=='PASS';identities.append(verdict)
report=dict(classification='RESEARCH_ONLY',source_HTTP=0,selected_candidates=15,source_member_observations=members,independent_source_review='15PASS_NOT_PIT',historical_identity=identities,new_PIT=0,new_engine=0,financial_publication='HOLD')
(a.output/'ACTUAL_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('PASS_ACTUAL15_SOURCE_ROWS_2_IDENTITY_POINTS_NO_PIT_PROMOTION')
