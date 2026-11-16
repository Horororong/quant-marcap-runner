"""Common path tests for an explicit cohort, without financial admissions/NAV."""
import copy,json,unittest
from pathlib import Path
import pandas as pd
from strategy_dsl import StrategySpec
from strategy_dsl_runner import build_target_weights_from_panel
from test_ncav_link import ProviderTests

class Cohort(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((Path(__file__).resolve().parents[1]/'config/strategies/kr_equity_report_validation_2019_2020.json').read_text())
        self.raw['factors']=[dict(name='size',source='krx',field='Marcap',direction='high',weight=1,transform='identity')]
        self.raw['universe']={'markets':['KOSPI','KOSDAQ'],'codes':['000001','000002'],'filters':[],'require_tradable_on_signal':False}
        self.raw['portfolio']={'number_of_positions':1,'weighting':'equal'}
        self.raw['rebalance']={'frequency':'months','months':[4],'trading_day':'last'}
        self.raw['period']={'start':'2020-04-01','end':'2020-04-30','book_start':'2020-04-01','book_end':'2020-04-30','as_of_date':'2020-04-30'}
        self.panel=pd.DataFrame([dict(Date=pd.Timestamp('2020-04-30'),Code=c,Name=c,Market='KOSPI',Marcap=m,Close=10,Volume=100,Amount=1000)for c,m in [('000001',100),('000002',200),('000003',900)]])
    def test_larger_outside_company_not_silently_included(self):
        s=StrategySpec.from_dict(self.raw);_,selected=build_target_weights_from_panel(self.panel,s)
        self.assertEqual(selected.Code.tolist(),['000002']);self.assertEqual(len(self.panel),3)
    def test_missing_cohort_member_is_not_pruned(self):
        with self.assertRaisesRegex(RuntimeError,'FIXED_COHORT_MISSING'):
            build_target_weights_from_panel(self.panel[self.panel.Code!='000001'],StrategySpec.from_dict(self.raw))
    def test_empty_and_duplicate_cohort_rejected(self):
        for codes in [[],['000001','000001']]:
            self.raw['universe']['codes']=codes
            with self.assertRaises(ValueError):StrategySpec.from_dict(self.raw)
    def test_cohort_affects_strategy_identity(self):
        first=StrategySpec.from_dict(self.raw).fingerprint();self.raw['universe']['codes']=['000001','000003']
        self.assertNotEqual(first,StrategySpec.from_dict(self.raw).fingerprint())
    def test_unspecified_cohort_preserves_legacy_serialization(self):
        self.raw['universe'].pop('codes');s=StrategySpec.from_dict(self.raw)
        self.assertNotIn('codes',s.to_dict()['universe'])

class ScopedProvider(ProviderTests):
    # Reuse fixture builder only; execute additional boundaries separately.
    def test_explicit_members_do_not_require_unrelated_ncav(self):
        from ncav_provider import NcavProvider
        r=self.admitted('20260814000001',100,'2026-08-17T00:00:00');self.write([r])
        frame=pd.DataFrame([dict(Code='005930',Marcap=200),dict(Code='999999',Marcap=999)])
        p=NcavProvider(self.root)
        out=p.factor_frame('2026-11-02',frame,['ncav_to_market_cap'],securities=['005930'])
        self.assertEqual(out.Code.tolist(),['005930'])
        self.assertTrue(p.coverage_report('2026-11-02',['ncav_to_market_cap'],securities=['005930'],cross_section=frame)[0]['raw_ok'])
        with self.assertRaisesRegex(RuntimeError,'FIXED_COHORT_MISSING'):
            p.factor_frame('2026-11-02',frame,['ncav'],securities=['000001'])

if __name__=='__main__':unittest.main()
