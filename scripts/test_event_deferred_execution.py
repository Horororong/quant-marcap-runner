"""Independent units/cash oracle for the separately opted-in liquid-target model.

Synthetic assumptions only. No historical event is inferred or registered here.
"""
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from test_stock_dividend_execution import fixture, proof
from strategy_dsl_runner import load_project_engine
from execution_scheduling import resolve_deferred_schedule
ROOT=Path(__file__).resolve().parents[1]
POLICY='defer_full_rebalance_events_v1'


def oracle(px, targets, plans, mask, common, sell_tax, capital=10000.):
    """Own actual shares, cash and rights. No engine returns/weights/schedule."""
    shares={c:0. for c in px};cash=capital;claims={};pending=None;rows=[];orders=[]
    arrivals={px.index[px.index.get_loc(s)+1]:(s,w) for s,w in targets.iterrows()}
    for date,prices in px.iterrows():
        ds=str(date.date())
        for p in plans:
            t=p['terms'];eid=t['event_id'];c=t['security']
            if t['ex_date']==ds:claims[eid]=dict(q=shares[c]*float(t['rate']),security=c,state='conditional',value=0.)
            if eid not in claims:continue
            a=claims[eid]
            for d in p['decisions']:
                if ds==d.get('recognition_date',d['actual_date']):a['state']='approved' if d['approved'] else 'cancelled'
            if any(ds==x['actual_date'] for x in p['credits']):a['state']='locked'
            if any(ds==x['actual_date'] for x in p['listings']):
                shares[c]+=a['q'];a['state']='released'
            a['value']=(a['q']*next(float(x['unit_value']) for x in p['marks'] if x['session']==ds) if a['state'] in ['conditional','approved'] else a['q']*prices[c] if a['state']=='locked' else 0.)
        illiquid=sum(x['value'] for x in claims.values());stock={c:shares[c]*prices[c] for c in px};value=cash+sum(stock.values())+illiquid;fee=0.
        if date in arrivals:
            assert pending is None
            sig,w=arrivals[date];pending=(sig,w)
        if pending is not None:
            sig,w=pending;required={c for c in px if shares[c]>1e-12 or w[c]>0}
            if all(mask.at[date,c] and pd.notna(prices[c]) and prices[c]>0 for c in required):
                # Allocation is on liquid capital. Claims are never sold or spent.
                liquid=cash+sum(stock.values());desired={c:w[c]*liquid for c in px}
                fee=sum(max(desired[c]-stock[c],0)*common+max(stock[c]-desired[c],0)*(common+sell_tax) for c in px)
                new={c:w[c]*(liquid-fee)/prices[c] for c in px}
                cash-=sum((new[c]-shares[c])*prices[c] for c in px)+fee;shares=new
                value=cash+sum(shares[c]*prices[c] for c in px)+illiquid
                orders.append((sig,date));pending=None
        assert cash>=-1e-8
        rows.append(dict(nav=value,cash=cash,illiquid=illiquid,fee=fee,shares=dict(shares)))
    assert pending is None
    return rows,orders


class EventDeferred(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=load_project_engine(ROOT)

    def run_fixture(self, *, cancel=False, second=False, new_buyer=False):
        d,p,w,events,ref=fixture();mask=pd.DataFrame(True,index=d,columns=p.columns)
        # Full liquid allocation, sell old shares while right remains, buy anew,
        # rebalance during locked interval, and rebalance after release.
        w=pd.DataFrame([[.6,.4],[0.,1.],[.3,.7],[.4,.6],[0.,1.]],index=d[[0,2,3,7,9]],columns=p.columns)
        if new_buyer:w=w.iloc[1:]
        plans=[json.loads(events.iloc[0].stock_dividend_contract)]
        if cancel:
            plans[0]['decisions'][0].update(approved=False,cancellation_treatment='verified_no_compensation',cancellation_evidence=proof(str(d[6].date())))
            plans[0]['credits']=[];plans[0]['listings']=[]
            plans[0]['marks']=[x for x in plans[0]['marks'] if x['session']<str(d[6].date())]
            events.stock_dividend_contract=json.dumps(plans[0])
        if second:
            q=json.loads(events.iloc[0].stock_dividend_contract);q['terms'].update(event_id='B',security='000002',ex_date=str(d[4].date()),record_date=str(d[5].date()),rate='0.2')
            q['market_reference']['reference_price']='50';q['marks']=[dict(session=str(d[i].date()),unit_value='40',rationale='synthetic second claim',evidence=proof(str(d[i].date()))) for i in range(4,7)]
            row=events.iloc[0].to_dict();row.update(event_date=d[4],predecessor_code='000002',successor_code='000002',share_ratio=.2,stock_dividend_contract=json.dumps(q));events=pd.concat([events,pd.DataFrame([row])],ignore_index=True);plans.append(q)
        # Defer whole third order while both original and target quantities earn
        # their observed returns. The original signal target is not reselected.
        mask.loc[d[4],'000002']=False
        result=self.engine.simulate_target_weight_portfolio(p,w,initial_capital=10000.,tradable_mask=mask,corporate_action_events=events,reference_returns=ref,
          cost_assumptions=self.engine.TradingCostAssumptions(commission_bps=100,sell_tax_bps=100),execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy=POLICY))
        for label,common,tax,key in [('Gross',0.,0.,'weights'),('Net',.01,.01,'net_weights')]:
            expected,orders=oracle(p,w,plans,mask,common,tax)
            np.testing.assert_allclose(result['daily_nav'][label]*10000,[x['nav'] for x in expected],rtol=0,atol=1e-8)
            weights=result[key]
            for col,field in [('Cash','cash'),('StockDividendIlliquid','illiquid')]:
                np.testing.assert_allclose(weights[col]*result['daily_nav'][label]*10000,[x[field] for x in expected],rtol=0,atol=1e-8)
            for code in p:
                np.testing.assert_allclose(weights[code]*result['daily_nav'][label]*10000/p[code],[x['shares'][code] for x in expected],rtol=0,atol=1e-10)
            actual=list(zip(result['execution_schedule'].signal_date,result['execution_schedule'].execution_date));self.assertEqual(actual,orders)
        self.assertEqual(result['execution_schedule'].iloc[2 if not new_buyer else 1].execution_date,d[5])
        return result

    def test_full_liquid_targets_independent_two_book_daily_quantities_cash_costs(self):self.run_fixture()
    def test_cancellation_is_real_loss_and_cannot_create_settlement(self):self.run_fixture(cancel=True)
    def test_two_simultaneous_claims_are_not_spent_or_double_credited(self):self.run_fixture(second=True)
    def test_post_ex_buyer_has_no_preexisting_entitlement(self):
        r=self.run_fixture(new_buyer=True)
        self.assertTrue(all(float(x['claims'].get('A',{}).get('quantity',0))==0 for x in r['stock_dividend_books']))
    def test_dividend_release_after_original_share_sale_requires_liquidity(self):
        d,p,w,ev,_=fixture();w=pd.DataFrame([[1.,0.],[0.,1.],[0.,1.]],index=d[[0,2,8]],columns=p.columns);mask=pd.DataFrame(True,index=d,columns=p.columns);mask.loc[d[9],'000001']=False
        base=self.engine._schedule_signal_execution_dates(d,w.index,1)
        schedule,_=resolve_deferred_schedule(base,w,p,mask,events=ev)
        self.assertEqual(schedule[d[8]],d[10])
    def test_merger_replaces_required_sale_security_before_pending_close_fill(self):
        d=pd.bdate_range('2024-01-02',periods=6)
        p=pd.DataFrame({'000001':[100.,100.,float('nan'),float('nan'),float('nan'),float('nan')], '000002':[50.,55.,58.,60.,66.,70.], '000003':[100.]*6},index=d)
        mask=p.notna();mask.loc[d[3],'000002']=False
        targets=pd.DataFrame([[1.,0.,0.],[0.,0.,1.]],index=d[[0,2]],columns=p.columns)
        ev=pd.DataFrame([dict(event_date=d[3],event_type='stock_merger',predecessor_code='000001',successor_code='000002',share_ratio=2.,cash_per_share=0.,source='synthetic')])
        ref=p.pct_change(fill_method=None)
        r=self.engine.simulate_target_weight_portfolio(p,targets,initial_capital=10000.,tradable_mask=mask,corporate_action_events=ev,reference_returns=ref,execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy=POLICY))
        self.assertEqual(r['execution_schedule'].iloc[1].execution_date,d[4])
        self.assertAlmostEqual(r['daily_nav'].at[d[4],'Gross']*10000,13200.)
        self.assertEqual(r['weights'].at[d[4],'000002'],0.)

    def test_cash_exchange_receivable_is_outside_full_liquid_target_budget(self):
        from test_cash_share_exchange import fixture as cash_fixture
        d,p,v,mask,ref,targets,ev=cash_fixture()
        targets.iloc[1]=[0.,1.];targets=targets.iloc[:2]
        r=self.engine.simulate_target_weight_portfolio(p,targets,initial_capital=10000.,tradable_mask=mask,source_volumes=v,corporate_action_events=ev,reference_returns=ref,execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy=POLICY))
        # First60 shares become7200 fixed cash claim; other20 shares gain to120.
        # Cash2000 does not earn the stock decline. The existing20 shares
        # decline120->90 before the actual day4 close: liquid=2000+20*90.
        self.assertAlmostEqual(r['daily_nav'].at[d[4],'Gross']*10000,7200+2000+20*90)
        self.assertAlmostEqual(r['weights'].at[d[4],'000002']*r['daily_nav'].at[d[4],'Gross']*10000,2000+20*90)
        self.assertEqual(r['weights'].at[d[4],'Cash'],0.)
        # At payment cash becomes liquid exactly once, value unchanged by receipt.
        self.assertGreater(r['weights'].at[d[6],'Cash'],0.)

    def test_projected_observations_preserve_original_full_source_float_reduction(self):
        import numpy as np
        d=pd.bdate_range('2024-01-02',periods=120);names=[f'{i:06d}' for i in range(1,2427)];used=[names[i] for i in [325,725,1817]]
        raw=np.random.default_rng(42).normal(0,.01,(120,3));small=pd.DataFrame(100*np.cumprod(1+raw,axis=0),index=d,columns=used)
        full=pd.DataFrame(100.,index=d,columns=names);full[used]=small
        weight=pd.DataFrame(0.,index=d[:1],columns=names);weight[used]=1/3
        base=self.engine.simulate_target_weight_portfolio(full,weight,initial_capital=10000.,tradable_mask=full.notna())
        projected=self.engine.simulate_target_weight_portfolio(small,weight[used],initial_capital=10000.,tradable_mask=small.notna(),execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy=POLICY,aggregation_assets=tuple(names)))
        pd.testing.assert_frame_equal(base['daily_nav'],projected['daily_nav'],check_exact=True)
        pd.testing.assert_frame_equal(base['trades'],projected['trades'],check_exact=True)
        pd.testing.assert_frame_equal(base['weights'][used+['Cash']],projected['weights'][used+['Cash']],check_exact=True)
        with self.assertRaisesRegex(ValueError,'omits'):
            self.engine.simulate_target_weight_portfolio(small,weight[used],tradable_mask=small.notna(),execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy=POLICY,aggregation_assets=tuple(used[:2])))

    def test_unknown_spinoff_fails_without_inventing_successor_rights(self):
        d,p,w,ev,_=fixture();ev['event_type']='spin_off'
        with self.assertRaisesRegex(ValueError,'unsupported_event'):
            resolve_deferred_schedule(self.engine._schedule_signal_execution_dates(d,w.index,1),w,p,p.notna(),events=ev)
    def test_original_contract_does_not_accept_dividend_extension(self):
        d,p,w,ev,ref=fixture()
        with self.assertRaisesRegex(ValueError,'split/no-action'):
            self.engine.simulate_target_weight_portfolio(p,w,tradable_mask=p.notna(),corporate_action_events=ev,reference_returns=ref,execution_assumptions=self.engine.ExecutionAssumptions(nontradable_policy='defer_full_rebalance'))

if __name__=='__main__':unittest.main(verbosity=2)
