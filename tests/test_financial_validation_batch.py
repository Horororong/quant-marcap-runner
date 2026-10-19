import hashlib,json,sys,tempfile,unittest,os
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.financial_validation_batch import canonical,collect,digest,review_selection,rank,freeze,CONTRACT
class BatchBoundaries(unittest.TestCase):
    def plan(self):return dict(contract=CONTRACT,samples=[dict(rcept_no=str(i))for i in range(100)],primary_review=[str(i)for i in range(20)])
    def test_selection_tamper_refused_before_HTTP(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t)/'plan.json';obj=self.plan();obj['selection_sha256']='wrong';p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'INTEGRITY'):collect(p,Path(t)/'out',0)
    def test_cannot_skip_prior_failure_or_recollect_existing_source(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);p=root/'plan.json';obj=self.plan();obj['selection_sha256']=digest(canonical(obj['samples']));p.write_text(json.dumps(obj))
            folder=root/'out/chunk00';folder.mkdir(parents=True);(folder/'run_status.json').write_text(json.dumps(dict(completed=1,stop_reason='SERVICE800')))
            with self.assertRaisesRegex(ValueError,'PRIOR_CHUNK'):collect(p,root/'out',1)
            with self.assertRaisesRegex(ValueError,'PRESERVED'):collect(p,root/'out',0)
    def test_scarce_extracted_all_included_and_gaps_kept(self):
        plan=self.plan();s={str(i):dict(field_count=4,extraction_state='PARSED_4F')for i in [30,31,32]};s['70']=dict(field_count=0,extraction_state='SOURCE_GAP')
        actual=review_selection(plan,s);self.assertTrue({'30','31','32','70'}.issubset(actual));self.assertTrue(set(plan['primary_review']).issubset(actual))
    def test_review_selection_deterministic_independent_of_amounts(self):
        plan=self.plan();s={str(i):dict(field_count=4,extraction_state='PARSED_4F',amount='secret')for i in range(50)}
        a=review_selection(plan,s)
        for x in s.values():x['amount']='changed'
        self.assertEqual(a,review_selection(plan,s));self.assertGreaterEqual(len(a),20)
    def test_consumed_batch_cannot_expand_automatically(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);p=root/'data/status/dart_legacy_validation100_status.json';p.parent.mkdir(parents=True);p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'ALREADY_CONSUMED'):freeze(root,root/'plan.json')
    def test_actions_retry_cannot_recollect_frozen100(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);obj=self.plan();obj['selection_sha256']=digest(canonical(obj['samples']));p=root/'plan.json';p.write_text(json.dumps(obj))
            with patch.dict(os.environ,{'GITHUB_RUN_ATTEMPT':'2'}):
                with self.assertRaisesRegex(ValueError,'NO_AUTOMATIC_RUN_RETRY'):collect(p,root/'out',0)
            self.assertFalse((root/'out').exists())
if __name__=='__main__':unittest.main()
