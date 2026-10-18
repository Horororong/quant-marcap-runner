"""Actual wrapper phase boundary and durable status, with no network/collection."""
import ast,contextlib,io,json,os,sys,tempfile,types,unittest,time
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from csv_storage import atomic_write_if_changed
class Wrapper(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # Full module import is separately UNVERIFIED in this kit (requests absent).
  # Compile only the ACTUAL wrapper main, with transport collectors replaced.
  source=Path('scripts/backfill_super_value_fast.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='main')
  env=dict(os=os,json=json,time=time,pd=pd,datetime=datetime,timezone=timezone,MODERN_LIMIT=1000,LEGACY_LIMIT=2000,legacy_fast=lambda:None,modern_fast=lambda:None,STATUS_FILE=None,legacy=types.SimpleNamespace(atomic_write_if_changed=atomic_write_if_changed),modern=types.SimpleNamespace(RateLimitExceeded=type('RateLimitExceeded',(Exception,),{})))
  exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-wrapper-main-AST>','exec'),env)
  cls.m=types.SimpleNamespace(**env)
 def test_deadline_persists_skip_and_does_not_invoke_modern(self):
  m=self.m;logs=io.StringIO()
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DART_API_KEY':'synthetic-test-only'}),patch.object(m,'STATUS_FILE',Path(d)/'status.csv'),patch.object(m,'MODERN_LIMIT',1000),patch.object(m,'legacy_fast',return_value=dict(legacy_stop_reason='DEADLINE',legacy_run_docs=1369,legacy_rate_limited=False)),patch.object(m,'modern_fast',side_effect=AssertionError('No new API phase after deadline')) as modern,contextlib.redirect_stdout(logs):
   m.main.__globals__.update(vars(m));m.main();self.assertFalse(modern.called)
   import pandas as pd
   r=pd.read_csv(Path(d)/'status.csv').iloc[0];self.assertTrue(r.modern_skipped);self.assertEqual(r.modern_phase_decision,'LEGACY_STOP_DEADLINE');self.assertEqual(r.legacy_run_docs,1369)
  events=[json.loads(l) for l in logs.getvalue().splitlines() if l.startswith('{')];self.assertEqual([x['phase'] for x in events],['legacy_start','legacy_end','modern_decision'])
 def test_service_outage_fails_after_durable_status(self):
  m=self.m
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DART_API_KEY':'synthetic-test-only'}),patch.object(m,'STATUS_FILE',Path(d)/'status.csv'),patch.object(m,'legacy_fast',return_value=dict(legacy_stop_reason='SERVICE_MAINTENANCE_800',legacy_run_docs=0,legacy_rate_limited=False)),patch.object(m,'modern_fast',side_effect=AssertionError('No fresh phase during service outage')) as modern,contextlib.redirect_stdout(io.StringIO()):
   m.main.__globals__.update(vars(m))
   with self.assertRaisesRegex(RuntimeError,'maintenance'):m.main()
   self.assertFalse(modern.called)
   r=pd.read_csv(Path(d)/'status.csv').iloc[0];self.assertTrue(r.modern_skipped);self.assertEqual(r.legacy_stop_reason,'SERVICE_MAINTENANCE_800')
if __name__=='__main__':unittest.main(verbosity=2)
