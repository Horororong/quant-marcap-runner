"""SYNTHETIC transport only; no source request or real execution authority."""
import copy,json,tempfile,unittest,io,zipfile,gzip
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timezone
from fy20_completion_collection import CompletionCollector,validate_plan,collect_queue
from bounded_official_evidence import Stop,atomic,sha,raw,request_id
ROOT=Path(__file__).resolve().parents[1]
FORM_FIELDS={'method','forward','currentPageSize','pageIndex','fromDate','toDate','searchCodeType','repIsuSrtCd','searchCorpName','oldSearchCorpName','reportNm','reportNmTemp','marketType','orderMode','orderStat'}
SYNTHETIC_FORM=('<form id="searchForm" method="post">'+''.join('<input name="'+k+'">'for k in sorted(FORM_FIELDS))+'</form><script>searchDetailsSub details_sub /disclosure/details.do "A"+repIsuSrtCd 조회기간은 3년 이내만 가능합니다.</script>').encode()
class ContinuationTests(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);r=Path(t.name);r.chmod(0o700)
  a=json.loads((ROOT/'config/research/fy20_completion_amendment_20261103.json').read_bytes());g=json.loads((ROOT/'config/research/fy20_metadata_approval_20261030.json').read_bytes())
  s=dict(group='completion_evidence',method='GET',url='https://law.krx.co.kr/',params={},purpose='calendar_catalog')
  q=dict(approval_id=a['approval_id'],user_approved=True,amendment_sha256=sha(raw(a)),phase='identity_calendar',targets=[s])
  prior=dict(contract=g['contract'],approval_id=g['approval_id'],approval_sha256=sha(raw(g)),requests=[dict(id=str(i),status='COMPLETE',phase='list',group='list',execution_id='old')for i in range(40)],executions=[dict(id='old'+str(i),day_kst='2026-11-0'+str(i+1),status='FINISHED')for i in range(2)],status='PAUSED',inventory={},correction_freeze=None)
  atomic(r/'budget.json',prior)
  q.update(original40_requests_sha256=sha(raw(prior['requests'])),original2_executions_sha256=sha(raw(prior['executions'])))
  now=datetime(2026,11,4,0,0,tzinfo=timezone.utc)
  h=dict(contract='fixed-three-shared-source-history-v1',day_kst='2026-11-04',observed_at=now.isoformat(),main_sha='SYNTHETIC',state_sha256={'a':'a','b':'b','c':'c'},executions=[],active_source_runs=[],old_authorized_channels_exhausted=True)
  calls=[]
  def transport(spec,timeout):calls.append(spec);return b'<html>Source discovery only. No historical applicability certified.</html>'
  kwargs=dict(now=lambda:now,monotonic=lambda:0,source_ready=True,transport=transport)
  return r,g,h,a,q,prior,kwargs,calls
 def test_no_approval_never_starts_or_changes_history(self):
  r,g,h,a,q,old,k,calls=self.fixture();q['user_approved']=False
  with self.assertRaises(Stop):CompletionCollector(r,g,h,a,q,SYNTHETIC_FORM,**k)
  self.assertEqual(json.loads((r/'budget.json').read_bytes()),old);self.assertFalse(calls)
 def open(self,r,g,h,a,q,k):return CompletionCollector(r,g,h,a,q,SYNTHETIC_FORM,**k)
 def test_original40_and_two_leases_are_preserved_no_duplicate_request(self):
  r,g,h,a,q,old,k,calls=self.fixture()
  with self.open(r,g,h,a,q,k)as c:
   c.get(q['targets'][0]);c.get(q['targets'][0]);self.assertEqual(len(c.state['requests']),41);self.assertEqual(len(c.state['executions']),3)
  after=json.loads((r/'budget.json').read_bytes());self.assertEqual(after['requests'][:40],old['requests']);self.assertEqual(after['executions'][:2],old['executions']);self.assertEqual(len(calls),1)
 def test_today_used_or_expiry_or_exhausted_never_transports(self):
  for case in ['today','expiry','exhausted']:
   r,g,h,a,q,old,k,calls=self.fixture()
   if case=='today':h['executions']=[dict(day_kst='2026-11-04')]
   elif case=='expiry':k['now']=lambda:datetime(2026,11,7,tzinfo=timezone.utc);h.update(day_kst='2026-11-07',observed_at=k['now']().isoformat())
   else:old['executions'] +=[dict(id='new'+str(i),day_kst='2026-11-03',status='FINISHED')for i in range(2)];atomic(r/'budget.json',old)
   with self.assertRaises(Stop):
    with self.open(r,g,h,a,q,k)as c:c.get(q['targets'][0])
   self.assertFalse(calls)
 def test_source_host_and_phase_and_all20_selection_cannot_be_changed(self):
  r,g,h,a,q,old,k,calls=self.fixture();q['targets'][0]['url']='https://evil.example/'
  with self.open(r,g,h,a,q,k)as c:
   with self.assertRaises(Stop):c.get(q['targets'][0])
  q['phase']='selected_holding'
  with self.assertRaises(Stop):validate_plan(a,q)
  self.assertFalse(calls)
 def test_failure_is_not_retried_or_given_an_extra_lease(self):
  r,g,h,a,q,old,k,calls=self.fixture()
  def failed(s,t):calls.append(s);raise Stop('SYNTHETIC_SOURCE_FAILURE')
  k['transport']=failed
  with self.assertRaises(Stop):
   with self.open(r,g,h,a,q,k)as c:c.get(q['targets'][0])
  self.assertEqual(len(calls),1);d=json.loads((r/'budget.json').read_bytes());self.assertEqual(d['status'],'HOLD_FAILURE');self.assertEqual(len(d['requests']),41)
  with self.assertRaises(Stop):self.open(r,g,h,a,q,k)
 def test_raw_response_is_never_financial_or_backtest_success(self):
  r,g,h,a,q,old,k,calls=self.fixture()
  with self.open(r,g,h,a,q,k)as c:out=collect_queue(c)
  self.assertEqual(out['financial_values_admitted'],0);self.assertFalse(out['backtest_completed'])
 def test_changed_original_history_is_not_a_fresh_budget(self):
  r,g,h,a,q,old,k,calls=self.fixture();old['requests'][0]['id']='tampered';atomic(r/'budget.json',old)
  with self.assertRaises(Stop):self.open(r,g,h,a,q,k)
  self.assertFalse(calls)
 def test_literal_children_cannot_overrun_three_request_calendar_branch(self):
  r,g,h,a,q,old,k,calls=self.fixture()
  def linked(s,t):
   calls.append(s)
   return ('<html>'+''.join('<a href="https://law.krx.co.kr/history2010'+str(i)+'">history</a>'for i in range(12))+'</html>').encode()if s['url'].endswith('/')else b'<html>Actual period must still be independently reviewed.</html>'
  k['transport']=linked
  with self.open(r,g,h,a,q,k)as c:out=collect_queue(c)
  self.assertEqual(len(calls),3);self.assertEqual(out['new_HTTP'],3);self.assertTrue(out['source_gaps']);self.assertFalse(out['backtest_completed'])
 def test_new_cohort_issuer_closes_both_lists_before_original_document(self):
  from fy20_completion_collection import MEMBERS
  r,g,h,a,q,old,k,calls=self.fixture();stock='001430';corp=MEMBERS[stock];receipt='20101101000001'
  q['phase']='selected_holding';q['selection']=dict(status='PASS',declared_companies=20,declared_codes=list(MEMBERS),signal='2010-04-30',all_required_inputs_verified=True,selection_binding_sha256='a'*64,selected_codes=[stock],market='KOSPI',proposed_fill_quote_tradable=True)
  issuer=dict(group='completion_evidence',method='GET',url='https://opendart.fss.or.kr/api/list.json',params=dict(corp_code=corp,bgn_de='20091101',end_de='20110430',last_reprt_at='N',page_no='1',page_count='100',sort='date',sort_mth='asc'),purpose='issuer_inventory',security=stock)
  exchange=dict(group='completion_evidence',method='POST',url='https://kind.krx.co.kr/disclosure/details.do',params=dict(method='searchDetailsSub',forward='details_sub',currentPageSize='100',pageIndex='1',orderMode='0',orderStat='D',fromDate='2009-11-01',toDate='2011-04-30',searchCodeType='char',repIsuSrtCd='A'+stock,searchCorpName='SYNTHETIC',oldSearchCorpName='SYNTHETIC',reportNm='',reportNmTemp='',marketType=''),purpose='exchange_inventory',security=stock)
  q['targets']=[issuer,exchange]
  def source(s,t):
   calls.append(s)
   if s['url'].endswith('list.json'):return raw(dict(status='000',page_no=1,total_page=1,total_count=1,list=[dict(corp_code=corp,rcept_no=receipt,rcept_dt='20101101',report_nm='주식분할 결정')]))
   if s['purpose']=='exchange_inventory':return b'<html>SYNTHETIC exchange source</html>'
   self.assertIn('completion_holding_inventory_freeze',json.loads((r/'budget.json').read_bytes()))
   buffer=io.BytesIO()
   with zipfile.ZipFile(buffer,'w')as z:z.writestr(receipt+'.xml','<DOCUMENT>SYNTHETIC</DOCUMENT>')
   return buffer.getvalue()
  k['transport']=source
  def parsed(s,b):return dict(page_no=1,total_page=1,total_count=1,rows=[dict(receipt='20101102000002',source_literal='<tr>기타 공시</tr>')])
  with patch('fy20_completion_collection.kind_page',side_effect=parsed):
   with self.open(r,g,h,a,q,k)as c:out=collect_queue(c)
  self.assertEqual(len(calls),3);self.assertEqual(calls[-1]['params'],{'rcept_no':receipt});self.assertFalse(out['backtest_completed'])
 def test_private_rehydrate_reads_only_needed_parent_or_cached_request(self):
  from fy20_metadata_github import FYJournal,APPROVAL
  from bounded_official_github import PRIVATE
  r,g,h,a,q,old,k,calls=self.fixture();dest=r/'selective';dest.mkdir(mode=0o700)
  bodies={'include':b'SYNTHETIC selected parent','exclude':b'SYNTHETIC unneeded old response'}
  state=copy.deepcopy(old);state['requests']=[dict(id=n,body_path='raw/'+sha(b)+'.bin',sha256=sha(b))for n,b in bodies.items()]
  outer=dict(executions=[],requests=[],additional_finite_grants={APPROVAL:state});reads=[]
  def content(api,repo,path,branch):
   reads.append(path)
   if path.endswith('budget.json'):return raw(outer),'SYNTHETIC'
   self.assertTrue(path.endswith(sha(bodies['include'])+'.bin.gz'))
   return gzip.compress(bodies['include']),'SYNTHETIC'
  def meta(*args,**kwargs):return dict(full_name=PRIVATE,private=True,permissions={'push':True})
  with patch('fy20_metadata_github.content',side_effect=content):FYJournal(meta,dest,rehydrate_ids={'include'})
  self.assertEqual(len(reads),2);self.assertTrue((dest/('raw/'+sha(bodies['include'])+'.bin')).exists());self.assertFalse((dest/('raw/'+sha(bodies['exclude'])+'.bin')).exists())
 def test_binary_calendar_source_is_preserved_but_not_certified(self):
  r,g,h,a,q,old,k,calls=self.fixture()
  def pdf(s,t):calls.append(s);return b'%PDF-1.4\nSYNTHETIC\xff\n%%EOF'
  k['transport']=pdf
  with self.open(r,g,h,a,q,k)as c:out=collect_queue(c)
  self.assertEqual(len(calls),1);self.assertFalse(out['backtest_completed']);self.assertEqual(out['financial_values_admitted'],0)
if __name__=='__main__':unittest.main()
