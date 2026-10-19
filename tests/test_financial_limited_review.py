import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import financial_limited_review as m
class FirstApproval(unittest.TestCase):
    def test_missing_changed_and_extra_control_inputs_never_authorize(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);(root/m.HOME).mkdir(parents=True)
            a=dict(status=m.STATUS,backtest_eligible=False,automatic_financial_publication='HOLD',files={})
            for n in m.NAMES:
                (root/m.HOME/n).write_text('frozen');a['files'][n]=m.sha(b'frozen')
            m.check_hashes(root,a)
            (root/m.HOME/'controls.json').write_text('changed')
            with self.assertRaisesRegex(ValueError,'INPUT_HASH'):m.check_hashes(root,a)
            a['files']['../controls.json']='x'
            with self.assertRaisesRegex(ValueError,'INPUT_SET'):m.check_hashes(root,a)
    def test_financial_PIT_or_auto_publication_promotion_refused(self):
        for key,value in [('status','PASS_ALL_DATA'),('backtest_eligible',True),('automatic_financial_publication','ON')]:
            a=dict(status=m.STATUS,backtest_eligible=False,automatic_financial_publication='HOLD',files={});a[key]=value
            with self.assertRaisesRegex(ValueError,'SCOPE_OR_PROMOTION'):m.check_hashes(Path('/unused'),a)
if __name__=='__main__':unittest.main(verbosity=2)
