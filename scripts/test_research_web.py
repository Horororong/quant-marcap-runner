import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research_web import Workspace,identifier,requirements,browser_numbers,saved_run_provenance
from research_language import translate
from test_research_language import TEXT
ROOT=Path(__file__).resolve().parents[1]
class WorkspaceContract(unittest.TestCase):
 def test_reopened_result_uses_saved_cost_and_source_not_current_editor(self):
  with tempfile.TemporaryDirectory()as t:
   folder=Path(t);run=folder/'run';run.mkdir();saved=translate(TEXT)['strategy']
   (run/'strategy_normalized.json').write_text(json.dumps(saved))
   (run/'preflight.json').write_text(json.dumps(dict(source_files=[dict(path='data/original.parquet',sha256='preserved-source')],control_files=[])))
   (run/'run_status.json').write_text(json.dumps(dict(run_id='saved-execution',strategy_fingerprint='saved-fingerprint',versions={})))
   edited=translate('수수료를 2.5bp로 변경',base=saved)
   actual=saved_run_provenance(folder)
   self.assertEqual(actual['cost_scenarios']['fixed_cost']['commission_bps'],1.5)
   self.assertEqual(edited['strategy']['cost_scenarios']['fixed_cost']['commission_bps'],2.5)
   self.assertEqual(actual['data_files'][0]['sha256'],'preserved-source');self.assertEqual(actual['run_id'],'saved-execution')
   (run/'preflight.json').unlink()
   self.assertEqual(saved_run_provenance(folder)['status'],'unavailable')
 def test_browser_cannot_round_unsafe_integer_into_a_valid_strategy(self):
  with self.assertRaisesRegex(ValueError,'BROWSER_UNSAFE_INTEGER'):
   browser_numbers({'threshold':9007199254740993})
 def test_browser_numeric_roundtrip_keeps_confirmation_and_fingerprint(self):
  with tempfile.TemporaryDirectory()as t:
   w=Workspace(ROOT,Path(t));preview=w.preview(dict(text=TEXT))
   wire=browser_numbers(json.loads(json.dumps(preview)))
   with patch.object(w.pool,'submit'):
    job=w.submit(dict(strategy=wire['strategy'],confirmation_digest=wire['confirmation_digest']),'check')
   self.assertEqual(job['fingerprint'],preview['strategy_fingerprint'])
   altered=browser_numbers(wire['strategy']);altered['universe']['filters'][0]['value']+=1000000
   with self.assertRaisesRegex(ValueError,'확인'):
    w.submit(dict(strategy=altered,confirmation_digest=wire['confirmation_digest']),'run')
 def test_exact_confirmation_and_append_only_save(self):
  with tempfile.TemporaryDirectory()as t:
   w=Workspace(ROOT,Path(t));p=translate(TEXT);request=dict(strategy=p['strategy'],confirmation_digest=p['confirmation_digest'])
   for digest in [None,'wrong']:
    with self.assertRaisesRegex(ValueError,'확인'):w.submit({**request,'confirmation_digest':digest},'run')
   with patch.object(w.pool,'submit')as submit:
    one=w.submit(request,'run');self.assertEqual(one['status'],'queued');submit.assert_called_once()
   a=w.save_strategy(dict(strategy=p['strategy'],name='원래'));b=w.save_strategy(dict(strategy=p['strategy'],name='복사'))
   self.assertNotEqual(a['id'],b['id']);self.assertEqual(a['fingerprint'],b['fingerprint']);self.assertEqual(len(w.saved('strategies')),2)
   with self.assertRaises(ValueError):identifier('../secret')
 def test_failed_or_incomplete_runs_cannot_masquerade_as_success(self):
  with tempfile.TemporaryDirectory()as t:
   w=Workspace(ROOT,Path(t));p=translate(TEXT)
   with patch.object(w.pool,'submit'):j=w.submit(dict(strategy=p['strategy'],confirmation_digest=p['confirmation_digest']),'run')
   f=w.store/'jobs'/str(j['id']+'.json');o=json.loads(f.read_text());o['status']='ok';f.write_text(json.dumps(o))
   with self.assertRaisesRegex(ValueError,'NAV'):w.status(j['id'])
   with self.assertRaises(ValueError):w.comparison([j['id'],j['id']])
 def test_known_requirements_are_evidence_not_automatic_registration(self):
  rows=requirements(ROOT,dict(incident=dict(security='207940',date='2022-02-28')))
  self.assertEqual(len(rows),1);self.assertIn('신주인수권증서',rows[0]['required_inputs'][0]);self.assertIn('UNVERIFIED',rows[0]['status'])
  self.assertEqual(requirements(ROOT,dict(security='207940',date='2022-03-01')),[])
if __name__=='__main__':unittest.main(verbosity=2)
