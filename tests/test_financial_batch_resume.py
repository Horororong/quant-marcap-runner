"""Real subprocess/SIGKILL recovery tests; synthetic sources are never financial proof."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.financial_rollout import run_batch
from scripts import financial_limited_resume as limited
from datetime import datetime,timezone

WORKER='''import hashlib,json,os,sys,time,zipfile
from pathlib import Path
m=json.loads(Path(sys.argv[sys.argv.index('--worker')+1]).read_text());r=m['rcept_no']
out=Path(os.environ['LEGACY_DART_SOURCE_DIR']);out.mkdir(exist_ok=True);p=out/(r+'-synthetic.zip')
if not os.getenv('FINANCIAL_VALIDATION_SOURCE_CACHE'):
 with zipfile.ZipFile(p,'w')as z:z.writestr(r+'.xml','<DOCUMENT>synthetic'+r+'</DOCUMENT>')
 with Path(os.environ['SYNTHETIC_DOWNLOAD_COUNTER']).open('a')as f:f.write(r+'\\n');f.flush();os.fsync(f.fileno())
 if m.get('pause_after_source'):
  Path(os.environ['SYNTHETIC_SOURCE_MARKER']).write_text(r)
  while True:time.sleep(.05)
result=dict(meta=m,parser_version='synthetic',rows=[],state=dict(rcept_no=r,status='NO_METRICS',document_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
Path(sys.argv[sys.argv.index('--result')+1]).write_text(json.dumps(result))
'''

class Resume(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.w=self.p/'worker.py';self.w.write_text(WORKER)
  self.counter=self.p/'counter';self.marker=self.p/'marker';self.old={k:os.environ.get(k)for k in ['SYNTHETIC_DOWNLOAD_COUNTER','SYNTHETIC_SOURCE_MARKER']}
  os.environ.update(SYNTHETIC_DOWNLOAD_COUNTER=str(self.counter),SYNTHETIC_SOURCE_MARKER=str(self.marker))
 def tearDown(self):
  for k,v in self.old.items():
   if v is None:os.environ.pop(k,None)
   else:os.environ[k]=v
  self.tmp.cleanup()
 def call(self,metas,**kw):return run_batch(metas,self.p/'batch',worker_script=self.w,**kw)
 def test_count_pause_resume_skips_durable_without_rewrite(self):
  metas=[dict(rcept_no=str(i))for i in range(3)]
  self.assertEqual(self.call(metas,max_documents=1),0)
  s=json.loads((self.p/'batch/run_status.json').read_text());self.assertEqual(s['stop_reason'],'BATCH_DOCUMENT_LIMIT');self.assertEqual(s['remaining_receipts'],['1','2'])
  first=(self.p/'batch/collection/0.json').read_bytes()
  self.assertEqual(self.call(metas,resume=True,max_documents=2),0)
  self.assertEqual(self.counter.read_text().splitlines(),['0','1','2']);self.assertEqual(first,(self.p/'batch/collection/0.json').read_bytes())
  s=json.loads((self.p/'batch/run_status.json').read_text());self.assertEqual(s['completed'],3);self.assertEqual(s['remaining_receipts'],[])
 def test_insufficient_admission_time_yields_before_worker(self):
  self.assertEqual(self.call([dict(rcept_no='1')],document_seconds=1,total_seconds=1,shutdown_reserve_seconds=.1),0)
  self.assertFalse(self.counter.exists());s=json.loads((self.p/'batch/run_status.json').read_text());self.assertEqual(s['stop_reason'],'YIELD_BEFORE_RUN_BUDGET');self.assertEqual(s['completed'],0)
 def test_sigkill_after_raw_source_resumes_without_redownload(self):
  metas=[dict(rcept_no='1'),dict(rcept_no='2',pause_after_source=True)]
  runner=self.p/'coordinator.py';runner.write_text('import json,sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(ROOT))+')\nfrom scripts.financial_rollout import run_batch\nrun_batch('+repr(metas)+',Path('+repr(str(self.p/'batch'))+'),worker_script=Path('+repr(str(self.w))+'),document_seconds=2,total_seconds=6)\n')
  proc=subprocess.Popen([sys.executable,'-I',str(runner)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  try:
   deadline=time.monotonic()+5
   while not self.marker.exists()and time.monotonic()<deadline:
    if proc.poll()is not None:self.fail(proc.stderr.read().decode())
    time.sleep(.02)
   self.assertTrue(self.marker.exists());proc.kill();proc.wait(timeout=3)
   first=(self.p/'batch/collection/1.json').read_bytes()
   self.assertEqual(self.call(metas,resume=True,document_seconds=2,total_seconds=6),0)
   self.assertEqual(self.counter.read_text().splitlines(),['1','2']);self.assertEqual(first,(self.p/'batch/collection/1.json').read_bytes())
   self.assertEqual(len(list((self.p/'batch/collection').glob('*.json'))),2)
   s=json.loads((self.p/'batch/run_status.json').read_text());self.assertEqual(s['last_checkpoint'],'2');self.assertEqual(s['completed'],2)
  finally:
   if proc.poll()is None:proc.kill();proc.wait()
   proc.stderr.close()
 def test_changed_selection_or_source_hash_is_hard_failure(self):
  metas=[dict(rcept_no='1')];self.call(metas)
  with self.assertRaisesRegex(ValueError,'SELECTION_CHANGED'):self.call([dict(rcept_no='2')],resume=True)
  next((self.p/'batch/native').glob('*.zip')).write_bytes(b'corrupt')
  with self.assertRaisesRegex(ValueError,'SOURCE_HASH'):self.call(metas,resume=True)
 def test_same_day_and_three_attempt_caps_remain_closed(self):
  c=json.loads((ROOT/limited.CONFIG).read_text());s=json.loads((ROOT/'tests/fixtures/limited_resume_state_20261021.json').read_text());now=datetime(2026,10,20,23,tzinfo=timezone.utc)
  with self.assertRaisesRegex(ValueError,'ONCE_PER_KST_DAY'):limited.check_recovery_gate(c,s,now,'39504052321',2)
  later=datetime(2026,10,21,15,tzinfo=timezone.utc);limited.check_recovery_gate(c,s,later,'39504052321',2)
  s['runs'][-1]['resume_segments']=[dict(day_kst='2026-10-22')]
  with self.assertRaisesRegex(ValueError,'ATTEMPTS_EXHAUSTED'):limited.check_recovery_gate(c,s,later,'39504052321',2)
 def test_quality_checkpoint_corruption_is_not_silently_repaired(self):
  metas=[dict(rcept_no='1')];self.call(metas)
  p=self.p/'batch/quality/1.json';q=json.loads(p.read_text());q['extraction_state']='PARSED_4F';p.write_text(json.dumps(q));before=p.read_bytes()
  with self.assertRaisesRegex(ValueError,'QUALITY_CONFLICT'):self.call(metas,resume=True)
  self.assertEqual(before,p.read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
