"""Bounded offline extraction subjects; source controls are NOT imported here."""
import argparse,base64,gzip,hashlib,importlib.util,io,json,sys,zipfile
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2];sys.path.insert(0,str(ROOT))
from scripts import legacy_native_financials as parser
from scripts.legacy_document_quality import inspect_member,empty_parse_status

def sha(b):return hashlib.sha256(b).hexdigest()
def payload():
 b=base64.b64decode((HOME/'sources/selected_originals.json.gz.b64').read_bytes());freeze=json.loads((HOME/'parser_freeze.json').read_text())
 assert sha(b)==freeze['compressed_sha256']
 return json.loads(gzip.decompress(b))

def run(out,before=False,cohort=None):
 out.mkdir(parents=True,exist_ok=False);data=payload();subject=parser
 if before:
  raw=gzip.decompress(base64.b64decode((HOME/'sources/parser_v7.py.gz.b64').read_bytes()))
  subject=type('BeforeParser',(),{})();ns={'__name__':'previous_financial_parser'};exec(compile(raw,'<pinned-v7>','exec'),ns);subject.parse_native=ns['parse_native'];subject.select_verified=ns['select_verified'];subject.PARSER_VERSION=ns['PARSER_VERSION']
 result=[]
 for rec in data['manifest']:
  if cohort and rec['cohort']!=cohort:continue
  allrows=[];diagnostics=[];issues=[];present=False
  for ar in rec['archives']:
   blob=base64.b64decode(data['files'][ar['path']]);assert sha(blob)==ar['sha256'];assert len(blob)==ar['bytes']
   with zipfile.ZipFile(io.BytesIO(blob)) as z:
    assert z.testzip() is None
    for name in z.namelist():
     if name.endswith('/'):continue
     b=z.read(name);d=inspect_member(b,name);diagnostics.append(d)
     if not name.lower().endswith('.xml'):continue
     if not d.get('resolved_encoding'):continue
     text=b.decode(d['resolved_encoding']);q=subject.parse_native(text);present|=q['financial_data_present'];issues.extend(dict(member=name,**x)for x in q['issues'])
     allrows.extend(dict(r,rcept_no=rec['receipt'],document_sha256=ar['sha256'],source_member=name,source_member_sha256=sha(b))for r in q['candidates'])
  selected=subject.select_verified(allrows)
  withheld=empty_parse_status(diagnostics)=='SOURCE_GAP'
  rows=[] if withheld else selected
  state='SOURCE_GAP' if withheld else 'PARSED' if rows else 'EXTRACTION_FAILED' if present else 'NO_METRICS'
  result.append(dict(receipt=rec['receipt'],sample=rec['sample'],cohort=rec['cohort'],rows=rows,diagnostics=diagnostics,issues=issues,financial_data_present=present,status=state,parser_version=subject.PARSER_VERSION,candidate_count=len(allrows),withheld_structural_candidates=len(selected) if withheld else 0,availability_status='UNVERIFIED',backtest_eligible=False))
 (out/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'filings':len(result),'rows':sum(len(x['rows'])for x in result),'parser':subject.PARSER_VERSION,'sources_recollected':0,'investment_approved':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--before',action='store_true');p.add_argument('--cohort',choices=['development','holdout']);a=p.parse_args();run(a.output,a.before,a.cohort)
