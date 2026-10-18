import base64,gzip,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audited_source_extensions as source
import audited_krx_calendar as calendar

class Extension(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for p in ['base.csv','evidence.txt']:(self.root/p).write_text('exact source')
  self.base=pd.DataFrame(dict(Date=['2026-01-02'],Close=[1.]))
 def registry(self,dates=('2026-01-05',),values=(2.,)):
  raw=pd.DataFrame(dict(Date=dates,Close=values)).to_csv(index=False).encode();b=base64.b64encode(gzip.compress(raw));(self.root/'extra.b64').write_bytes(b)
  row=dict(dataset='index:KOSPI',start='2026-01-02',end='2026-01-30',base=dict(path='base.csv',sha256=source.digest(self.root/'base.csv')),data=dict(path='extra.b64',sha256=hashlib.sha256(b).hexdigest(),csv_sha256=hashlib.sha256(raw).hexdigest(),rows=len(dates)),evidence=[dict(path='evidence.txt',sha256=source.digest(self.root/'evidence.txt'))])
  p=self.root/source.REGISTRY;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(version=1,datasets=[row])))
 def load(self):return source.append(self.root,'index:KOSPI',self.base,self.root/'base.csv','2026-01-02','2026-01-30')
 def test_append_and_unchanged_old_period(self):
  self.registry();self.assertEqual(self.load().Close.tolist(),[1.,2.]);self.assertIs(source.append(self.root,'index:KOSPI',self.base,self.root/'base.csv','2025-01-01','2025-12-31'),self.base)
 def test_overlaps_duplicates_nonfinite_fail(self):
  for dates,values in [(('2026-01-02',),(2.,)),(('2026-01-05','2026-01-05'),(2.,2.)),(('2026-01-05',),(float('nan'),))]:
   self.registry(dates,values)
   with self.assertRaises(ValueError):self.load()
 def test_changed_base_or_evidence_never_overwritten(self):
  self.registry();(self.root/'base.csv').write_text('changed')
  with self.assertRaises(ValueError):self.load()
  self.registry();(self.root/'evidence.txt').write_text('changed')
  with self.assertRaises(ValueError):self.load()
 def test_actual_calendar_dated_evidence_and_old_year_unchanged(self):
  old=pd.bdate_range('2024-01-01','2024-12-31');self.assertTrue(calendar.apply(old).equals(old))
  days=pd.bdate_range('2026-06-01','2026-07-20');result=calendar.apply(days)
  self.assertEqual(list(days.difference(result)),[pd.Timestamp('2026-06-03'),pd.Timestamp('2026-07-17')])
 def test_actual_two_loaders_match_complete_extensions(self):
  from krx_backtest_data import load_krx_equity_panel
  from strategy_dsl_runner import load_project_engine
  from krx_backtest_data import resolve_project_root
  root=resolve_project_root();engine=load_project_engine(root)
  kwargs=dict(start='2026-10-12',end='2026-10-16',repo_root=root,columns=['Date','Code','Market','Close','Marcap','ChangesRatio'])
  a=load_krx_equity_panel(**kwargs);b=engine.load_krx_equity_panel(**kwargs)
  pd.testing.assert_frame_equal(a,b,check_exact=True);self.assertEqual(len(a),13808);self.assertEqual(a.Date.nunique(),5)
if __name__=='__main__':unittest.main(verbosity=2)
