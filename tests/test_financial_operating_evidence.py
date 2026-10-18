"""Actual preserved canary sources and failure-to-publish corruption boundaries."""
import json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from financial_operating_evidence import check,HOME,BASE
class OperatingEvidence(unittest.TestCase):
    def fixture_copy(self,dest):
        for rel in [HOME,BASE]:shutil.copytree(ROOT/rel,dest/rel)
        for rel in [Path('config/financial_backfill_rollout.json'),Path('data/status/dart_legacy_backfill_state.csv')]:
            (dest/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest/rel)
    def test_actual_source_eight_fields_and_closed_investment_gate(self):
        result=check(ROOT);self.assertEqual(result['source_verified_published_fields'],8);self.assertEqual(result['investment_PIT'],'0/6')
    def test_wrong_posted_amount_is_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            dest=Path(t);self.fixture_copy(dest);p=next((dest/BASE/'metrics').glob('*.json'));data=json.loads(p.read_text());data['rows'][0]['amount_krw']=str(int(data['rows'][0]['amount_krw'])+1);p.write_text(json.dumps(data))
            with self.assertRaisesRegex(AssertionError,'amount mismatch'):check(dest)
    def test_investment_promotion_is_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            dest=Path(t);self.fixture_copy(dest);p=next((dest/BASE/'metrics').glob('*.json'));data=json.loads(p.read_text());data['rows'][0]['backtest_eligible']=True;p.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):check(dest)
if __name__=='__main__':unittest.main(verbosity=2)
