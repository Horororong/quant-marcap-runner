"""Offline parser regression only. Independent source audits remain separate."""
import collections,hashlib,json,subprocess,sys,types,zipfile
from pathlib import Path
R=Path('/workspace/quant-parser-repair-20261021/code');P=R.parent/'evidence'
S=Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded')
sys.path.insert(0,str(R))
from scripts import legacy_native_financials as new
from scripts.legacy_document_quality import inspect_member,empty_parse_status
old=types.ModuleType('original_native_parser')
code=subprocess.check_output(['git','-C',str(R),'show','01731c73ff3d8023d1747d5d1b11cfacad509eb0:scripts/legacy_native_financials.py'])
exec(compile(code,'<original-pinned-native-parser>','exec'),old.__dict__)
audit=json.loads((R/'docs/research/source-review-batch2-20261021/all-871-candidate-decisions.json').read_text())
fields=['metric','scope','statement','term','period_start','period_end','measurement_basis','amount_reported','amount_krw','unit','unit_multiplier','structural_status','availability_status','backtest_eligible','source_member','source_member_sha256','table_index','row_index','value_col','source_character','raw_amount','account_name','correction_file','amendment_region','numeric_normalization','fiscal_year','fiscal_year_evidence']
def key(r):return(r['metric'],r['scope'],r['period_end'],r['measurement_basis'])
def fingerprint(row):return {k:row.get(k)for k in fields}
documents=[];additions=[];changes=[];losses=[];stored_mismatch=[];gaps=[];old_total=new_total=0
for result in sorted(S.rglob('results/*.json')):
 d=json.loads(result.read_text());rec=d['meta']['rcept_no'];archive=next((result.parent.parent/'native').glob(rec+'-*.zip'))
 obs_old=[];obs_new=[];diags=[]
 with zipfile.ZipFile(archive)as z:
  for name in z.namelist():
   if name.endswith('/'):continue
   data=z.read(name);diag=inspect_member(data,name);diags.append(diag)
   if diag.get('resolved_encoding'):text=data.decode(diag['resolved_encoding'])
   else:
    for enc in ['utf-8','cp949','euc-kr']:
     try:text=data.decode(enc);break
     except UnicodeDecodeError:continue
    else:raise AssertionError(('UNRESOLVED_ENCODING',rec,name))
   metadata=dict(source_member=name,source_member_sha256=hashlib.sha256(data).hexdigest())
   obs_old.extend({**r,**metadata}for r in old.parse_native(text)['candidates'])
   obs_new.extend({**r,**metadata}for r in new.parse_native(text)['candidates'])
 source_gap=empty_parse_status(diags)=='SOURCE_GAP'
 before=[]if source_gap else old.select_verified(obs_old);after=[]if source_gap else new.select_verified(obs_new)
 if source_gap:gaps.append(rec)
 b={key(r):r for r in before};a={key(r):r for r in after};stored={key(r):r for r in d['rows']}
 for k in b.keys()|stored.keys():
  if k not in b or k not in stored or fingerprint(b[k])!=fingerprint(stored[k]):stored_mismatch.append(dict(receipt=rec,key=k,before=b.get(k),stored=stored.get(k)))
 for k in b:
  if k not in a:losses.append(dict(receipt=rec,key=k,before=b[k]))
  elif fingerprint(b[k])!=fingerprint(a[k]):changes.append(dict(receipt=rec,key=k,before=b[k],after=a[k]))
 for k in a.keys()-b.keys():additions.append(dict(receipt=rec,**a[k],source_archive=str(archive.relative_to(S)),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),state='NEW_HELD_STRUCTURAL_CANDIDATE_NOT_SEMANTIC_OR_PIT_CERTIFIED'))
 old_total+=len(before);new_total+=len(after)
 documents.append(dict(receipt=rec,company=d['meta']['corp_name'],before=len(before),after=len(after),source_gap_unchanged=source_gap,added=len(a.keys()-b.keys()),removed=len(b.keys()-a.keys())))
 print(rec,len(before),'->',len(after),'GAP'if source_gap else'',flush=True)
report=dict(classification='RESEARCH_ONLY_OFFLINE_REGRESSION',before_version=old.PARSER_VERSION,after_version=new.PARSER_VERSION,source_documents=len(documents),source_gap_documents_unchanged=gaps,old_candidates=old_total,new_candidates=new_total,additions=additions,existing_changes=changes,existing_losses=losses,baseline_replay_vs_stored_mismatch=stored_mismatch,documents=documents,all_old_PASS_preserved=len(changes)==len(losses)==0,source_HTTP=0,financial_publication=0,whole_source_completeness='UNVERIFIED',PIT='UNVERIFIED',method_limit='Same-parser before/after replay is regression evidence, not independent accuracy certification. New rows need separate original-source controls.')
(P/'original-57-replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
assert len(documents)==57 and len(gaps)==9 and old_total==871
assert not stored_mismatch,('BASELINE_REPLAY_MISMATCH',len(stored_mismatch))
assert not changes and not losses,('REGRESSION',len(changes),len(losses))
assert sum(r['semantic_verdict']=='PASS'for r in audit)==848
assert sum(r['semantic_verdict']=='UNVERIFIED'for r in audit)==23
print(json.dumps({k:v for k,v in report.items()if k not in {'additions','documents','existing_changes','existing_losses','baseline_replay_vs_stored_mismatch'}},ensure_ascii=False,indent=2))
