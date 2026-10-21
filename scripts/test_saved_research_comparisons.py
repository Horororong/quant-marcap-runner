"""Saved comparison integrity boundaries; synthetic files are software fixtures."""
import json,tempfile,unittest
from pathlib import Path
from research_web import Workspace,write
from research_language import translate
from test_research_language import TEXT
ROOT=Path(__file__).resolve().parents[1]

class SavedComparison(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.w=Workspace(ROOT,Path(self.temp.name));self.addCleanup(self.w.pool.shutdown)
  self.ids=['a'*32,'b'*32]
  for i,jid in enumerate(self.ids):
   run=self.w.store/'runs'/jid/'run';spec=translate(TEXT)['strategy']
   write(self.w.store/'jobs'/str(jid+'.json'),dict(id=jid,mode='run',status='ok',fingerprint='fixture-'+str(i),period=spec['period']))
   write(run/'run_status.json',dict(nav_ready=True,report_ready=True,run_id='fixture-'+str(i)))
   write(run/'strategy_normalized.json',spec);write(run/'preflight.json',dict(source_files=[dict(path='fixture',sha256='fixture-source')]))
   write(run/'report/chat_manifest_CURRENT.json',dict(classification='SOFTWARE_FIXTURE'))
   for name,text in [('artifacts/daily_nav.csv','Date,NAV\n'),('report/metrics_CURRENT.csv','CAGR,MDD,Sharpe\n,,,\n'),('report/report_CURRENT.html','<p>SOFTWARE FIXTURE</p>')]:
    path=run/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 def save(self):return self.w.save_comparison(dict(name='비용 비교',run_ids=self.ids))
 def test_reopen_after_new_workspace_preserves_run_order_and_saved_sources(self):
  saved=self.save();other=Workspace(ROOT,self.w.store);self.addCleanup(other.pool.shutdown)
  opened=other.reopen_comparison(saved['id'])
  self.assertEqual([j['id']for j in opened['runs']],self.ids)
  self.assertEqual(opened['saved_comparison'],saved)
  self.assertFalse(opened['investment_approved'])
  self.assertEqual(len(other.saved('comparisons')),1)
 def test_each_current_source_mutation_blocks_reopen_without_overwriting_saved_record(self):
  saved=self.save();record=self.w.store/'comparisons'/str(saved['id']+'.json');before=record.read_bytes()
  run=self.w.store/'runs'/self.ids[0]/'run'
  for f in saved['runs'][0]['files']:
   p=run/f['path'];old=p.read_bytes();p.write_bytes(old+b' ')
   with self.assertRaisesRegex(ValueError,'COMPARISON_SOURCE_CHANGED'):self.w.reopen_comparison(saved['id'])
   p.write_bytes(old);self.assertEqual(record.read_bytes(),before)
 def test_missing_artifact_never_replaced_with_current_editor_or_run(self):
  saved=self.save();(self.w.store/'runs'/self.ids[0]/'run/artifacts/daily_nav.csv').unlink()
  with self.assertRaisesRegex(ValueError,'COMPARISON_SOURCE_MISSING'):self.w.reopen_comparison(saved['id'])
 def test_invalid_duplicate_blocked_and_incomplete_runs_cannot_be_saved(self):
  for ids in [self.ids[:1],[self.ids[0]]*2,['../path',self.ids[0]]]:
   with self.assertRaises(ValueError):self.w.save_comparison(dict(name='bad',run_ids=ids))
  job=self.w.store/'jobs'/str(self.ids[0]+'.json');data=json.loads(job.read_text());data['status']='data_gap';write(job,data)
  with self.assertRaisesRegex(ValueError,'성공한 실제 실행'):self.save()
  self.assertEqual(self.w.saved('comparisons'),[])
 def test_append_only_and_client_metric_injection_ignored(self):
  one=self.save();two=self.w.save_comparison(dict(name='same',run_ids=self.ids,metrics=[dict(CAGR=999)]))
  self.assertNotEqual(one['id'],two['id']);self.assertEqual(one['runs'],two['runs'])
  self.assertNotIn('metrics',two);self.assertEqual(len(self.w.saved('comparisons')),2)
 def test_changed_job_identity_blocks_reopen(self):
  saved=self.save();p=self.w.store/'jobs'/str(self.ids[0]+'.json');job=json.loads(p.read_text());job['fingerprint']='changed';write(p,job)
  with self.assertRaisesRegex(ValueError,'COMPARISON_SOURCE_CHANGED'):self.w.reopen_comparison(saved['id'])

if __name__=='__main__':unittest.main()
