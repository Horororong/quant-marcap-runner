"""Synthetic integration, independently accounted in shares and cash.

No real dividend record, mark, payment date, tax certification or performance.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import os
import unittest
import numpy as np
import pandas as pd

from stock_dividend import Evidence
from strategy_dsl_runner import execute_daily_nav, load_project_engine
from strategy_dsl_deciles import execute_decile_nav, DECILE_LABELS
from test_strategy_dsl_deciles import make_spec

ROOT = Path(__file__).resolve().parents[1]


def proof(d):
    return asdict(Evidence("synthetic:stage13", "a" * 64, "explicit test assumptions, not primary evidence", d, "synthetic"))


def fixture():
    dates = pd.bdate_range("2024-01-02", periods=12)
    ds = [str(d.date()) for d in dates]
    px = pd.DataFrame({"000001": [100,100,90,92,95,96,97,98,100,101,102,103], "000002": [50]*12}, index=dates, dtype=float)
    tw = pd.DataFrame([[.6,.2],[0,.2],[.3,.1],[.4,.1]], index=dates[[0,2,3,8]], columns=px.columns)
    p = dict(scope="synthetic", quantity_policy="synthetic_pro_rata",
        terms=dict(event_id="A", security="000001", ex_date=ds[2], record_date=ds[3], rate="0.1", evidence=proof(ds[1])),
        decisions=[dict(actual_date=ds[6], approved=True, evidence=proof(ds[6]))],
        credits=[dict(actual_date=ds[7], evidence=proof(ds[7]), tax_treatment="verified_none", tax_evidence=proof(ds[7]))],
        listings=[dict(actual_date=ds[9], evidence=proof(ds[9]))],
        marks=[dict(session=ds[i], unit_value=str(80+i), rationale="synthetic explicit conditional and liquidity mark", evidence=proof(ds[i])) for i in range(2,7)],
        market_reference=dict(reference_price="90", evidence=proof(ds[1])))
    ev = pd.DataFrame([dict(event_type="stock_dividend", event_date=dates[2], predecessor_code="000001", successor_code="000001", share_ratio=.1,cash_per_share=0,source="synthetic:stage13", stock_dividend_contract=json.dumps(p))])
    ref = px.pct_change(fill_method=None).fillna(0)
    ref.loc[dates[2], "000001"] = 0
    return dates, px, tw, ev, ref


def independent_book(px, targets, plans, commission, sell_tax, capital=10000.):
    """Units + cash oracle; no portfolio returns, drift weights or engine calls.

    Fees follow the existing pre-cost notional / post-cost target convention.
    This explicitly theoretical continuous-quantity fixture has no fractional
    cash payment and does not claim legal account allocation.
    """
    cash, shares, claims, rows = capital, {c: 0. for c in px}, {}, []
    schedule = {px.index[px.index.get_loc(sig)+1]: w for sig,w in targets.iterrows()}
    for dt, prices in px.iterrows():
        date = str(dt.date())
        for p in plans:
            t = p["terms"]; eid = t["event_id"]; sec = t["security"]
            if date == t["ex_date"]:
                claims[eid] = dict(quantity=shares[sec]*float(t["rate"]), state="conditional", security=sec, value=0.)
            if eid not in claims:
                continue
            c = claims[eid]
            for a in p["decisions"]:
                if date == a["actual_date"]:
                    c["state"] = "approved" if a["approved"] else "cancelled"
            if any(date == a["actual_date"] for a in p["credits"]):
                c["state"] = "locked"
            if any(date == a["actual_date"] for a in p["listings"]):
                shares[sec] += c["quantity"]
                c["state"] = "released"
            if c["state"] in {"conditional", "approved"}:
                c["value"] = c["quantity"] * next(float(a["unit_value"]) for a in p["marks"] if a["session"] == date)
            else:
                c["value"] = c["quantity"] * prices[sec] if c["state"] == "locked" else 0.
        illiquid = sum(c["value"] for c in claims.values())
        stocks = {c: shares[c]*prices[c] for c in shares}
        value = cash + sum(stocks.values()) + illiquid
        fee = 0.
        if dt in schedule:
            w = schedule[dt]
            desired = {c: float(w[c])*value for c in shares}
            buys = sum(max(desired[c]-stocks[c],0) for c in shares)
            sells = sum(max(stocks[c]-desired[c],0) for c in shares)
            fee = buys*commission + sells*(commission+sell_tax)
            value -= fee
            new = {c: float(w[c])*value/prices[c] for c in shares}
            cash -= sum((new[c]-shares[c])*prices[c] for c in shares) + fee
            shares = new
            assert cash >= -1e-8
        rows.append(dict(value=value, cash=cash, illiquid=illiquid, fee=fee, shares=dict(shares), claims=deepcopy(claims)))
    return rows


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = load_project_engine(ROOT)

    def execute(self, *, ev=None, tw=None, ref=None, costs=True):
        dates, px, targets, events, reference = fixture()
        return self.engine.simulate_target_weight_portfolio(px, targets if tw is None else tw,
            initial_capital=10000., corporate_action_events=events if ev is None else ev,
            reference_returns=reference if ref is None else ref,
            cost_assumptions=self.engine.TradingCostAssumptions(commission_bps=100 if costs else 0, sell_tax_bps=100 if costs else 0))

    def test_independent_daily_gross_net_quantity_cash_and_nav(self):
        dates, px, tw, ev, ref = fixture()
        result = self.execute()
        plans = [json.loads(s) for s in ev.stock_dividend_contract]
        reconciliation=[]
        for label, comm, tax, weights_key in [("Gross",0,0,"weights"),("Net",.01,.01,"net_weights")]:
            oracle = independent_book(px,tw,plans,comm,tax)
            np.testing.assert_allclose(result["daily_nav"][label]*10000,[r["value"] for r in oracle],rtol=0,atol=1e-8)
            w = result[weights_key]
            np.testing.assert_allclose(w.Cash*result["daily_nav"][label]*10000,[r["cash"] for r in oracle],rtol=0,atol=1e-8)
            np.testing.assert_allclose(w.StockDividendIlliquid*result["daily_nav"][label]*10000,[r["illiquid"] for r in oracle],rtol=0,atol=1e-8)
            for security in px:
                np.testing.assert_allclose(w[security]*result["daily_nav"][label]*10000/px[security],
                                           [r["shares"][security] for r in oracle],rtol=0,atol=1e-10)
            for i,date in enumerate(dates):
                reconciliation.append(dict(book=label,date=str(date.date()),oracle_value=oracle[i]["value"],
                    engine_value=result["daily_nav"].loc[date,label]*10000,oracle_cash=oracle[i]["cash"],
                    engine_cash=w.loc[date,"Cash"]*result["daily_nav"].loc[date,label]*10000,
                    oracle_illiquid=oracle[i]["illiquid"],fee=oracle[i]["fee"],
                    **{f"oracle_shares_{c}":oracle[i]["shares"][c] for c in px}))
            audits = [r for r in result["stock_dividend_books"] if r["book"] == label]
            # Entitlement survives old-stock sale and later new buying. Credit
            # locks it; release adds it once without a trade or receipt income.
            q = oracle[2]["claims"]["A"]["quantity"]
            for i in range(2,12):
                self.assertAlmostEqual(float(audits[i]["claims"]["A"]["quantity"]),q)
            self.assertEqual(audits[7]["claims"]["A"]["state"],"credited_locked")
            self.assertEqual(audits[9]["claims"]["A"]["state"],"released")
        gross_q = result["stock_dividend_books"][4]["claims"]["A"]["quantity"]
        net_q = result["stock_dividend_books"][5]["claims"]["A"]["quantity"]
        self.assertNotEqual(gross_q, net_q)
        self.assertEqual(len(result["stock_dividend_price_checks"]),1)
        if os.getenv("STAGE13_LEDGER_OUTPUT"):
            output=Path(os.environ["STAGE13_LEDGER_OUTPUT"])
            output.parent.mkdir(parents=True,exist_ok=True)
            if output.exists(): raise ValueError("never overwrite an existing independent ledger")
            pd.DataFrame(reconciliation).to_csv(output,index=False)

    def test_rights_and_locked_stock_cannot_fund_targets(self):
        dates,px,tw,ev,ref = fixture()
        for sig in (dates[2], dates[6]):
            target = pd.DataFrame([[.6,.2],[1,0]],index=[dates[0],sig],columns=px.columns)
            with self.assertRaisesRegex(RuntimeError,"insufficient settled cash"):
                self.execute(tw=target)

    def test_post_ex_new_buyer_has_zero_rights(self):
        dates,px,tw,ev,ref = fixture()
        tw = pd.DataFrame([[.3,.2]],index=dates[2:3],columns=px.columns)
        r = self.execute(tw=tw)
        self.assertTrue(all(float(x["claims"].get("A",{}).get("quantity",0))==0 for x in r["stock_dividend_books"]))

    def test_no_compensation_cancellation_recognizes_real_marked_loss(self):
        dates,px,tw,ev,ref = fixture()
        p=json.loads(ev.iloc[0].stock_dividend_contract)
        p["decisions"][0].update(approved=False,cancellation_treatment="verified_no_compensation",cancellation_evidence=proof(str(dates[6].date())))
        p["credits"]=[];p["listings"]=[]
        p["marks"]=[a for a in p["marks"] if a["session"] < str(dates[6].date())]
        ev.stock_dividend_contract=json.dumps(p)
        r=self.execute(ev=ev)
        oracle=independent_book(px,tw,[p],0,0)
        np.testing.assert_allclose(r["daily_nav"].Gross*10000,[x["value"] for x in oracle],rtol=0,atol=1e-8)
        self.assertEqual(r["stock_dividend_books"][12]["claims"]["A"]["state"],"cancelled")
        p["decisions"][0].pop("cancellation_evidence")
        ev.stock_dividend_contract=json.dumps(p)
        with self.assertRaisesRegex(ValueError,"cancellation accounting"):
            self.execute(ev=ev)

    def test_fractional_primary_and_whole_boundaries_fail_without_rounding(self):
        dates,px,tw,ev,ref=fixture()
        p=json.loads(ev.iloc[0].stock_dividend_contract);p["quantity_policy"]="whole"
        ev.stock_dividend_contract=json.dumps(p)
        with self.assertRaisesRegex(ValueError,"cannot round fractional"):
            self.execute(ev=ev)
        p["scope"]="evidenced_research";p["quantity_policy"]="synthetic_pro_rata"
        ev.stock_dividend_contract=json.dumps(p)
        with self.assertRaises(ValueError): self.execute(ev=ev)

    def test_no_blanket_price_exception_or_implicit_mark(self):
        dates,px,tw,ev,ref=fixture()
        for date in (dates[2],dates[3]):
            bad=ref.copy();bad.loc[date,"000001"]+=.01
            with self.assertRaises((RuntimeError,ValueError)): self.execute(ref=bad)
        p=json.loads(ev.iloc[0].stock_dividend_contract);p["marks"].pop()
        ev.stock_dividend_contract=json.dumps(p)
        with self.assertRaisesRegex(ValueError,"explicit as-of mark"):
            self.execute(ev=ev)

    def test_top_n_and_all_deciles_share_identical_two_book_execution(self):
        dates,px,tw,ev,ref=fixture()
        spec=make_spec()
        cfg,costs,execution=__import__("strategy_dsl_runner").engine_inputs(spec,self.engine)
        expected=execute_daily_nav(self.engine,px,tw,costs,execution,cfg.initial_capital,corporate_action_events=ev,reference_returns=ref)
        panel=px.rename_axis("Date").reset_index().melt(id_vars="Date",var_name="Code",value_name="Close");panel["Volume"]=1000.
        all_buckets=execute_decile_nav(panel,spec,{b:tw for b in DECILE_LABELS},self.engine,ev,ref)
        for b in DECILE_LABELS:
            pd.testing.assert_frame_equal(all_buckets["decile_results"][b]["daily_nav"],expected["daily_nav"])

    def test_two_events_same_security_after_release_keep_accounts_separate(self):
        dates,px,tw,ev,ref=fixture()
        p=json.loads(ev.iloc[0].stock_dividend_contract)
        p["terms"].update(event_id="B",ex_date=str(dates[10].date()),record_date=str(dates[11].date()),rate="0.2")
        p["decisions"]=[];p["credits"]=[];p["listings"]=[]
        p["marks"]=[dict(session=str(dates[i].date()),unit_value="50",rationale="synthetic explicit new right",evidence=proof(str(dates[i].date()))) for i in [10,11]]
        p["market_reference"]["reference_price"]="102"
        row=ev.iloc[0].to_dict();row.update(event_date=dates[10],share_ratio=.2,stock_dividend_contract=json.dumps(p))
        ev=pd.concat([ev,pd.DataFrame([row])],ignore_index=True)
        ref.loc[dates[10],"000001"]=0
        r=self.execute(ev=ev,ref=ref)
        for label,comm,tax in [("Gross",0,0),("Net",.01,.01)]:
            oracle=independent_book(px,tw,[json.loads(x) for x in ev.stock_dividend_contract],comm,tax)
            np.testing.assert_allclose(r["daily_nav"][label]*10000,[x["value"] for x in oracle],rtol=0,atol=1e-8)

    def test_credit_and_listing_at_unchanged_value_have_no_income_or_cost(self):
        dates,px,tw,ev,ref=fixture()
        px.loc[dates[2]:,"000001"]=90.
        tw=tw.iloc[:1]
        p=json.loads(ev.iloc[0].stock_dividend_contract)
        for a in p["marks"]: a["unit_value"]="90"
        ev.stock_dividend_contract=json.dumps(p)
        ref=px.pct_change(fill_method=None).fillna(0);ref.loc[dates[2],"000001"]=0
        r=self.engine.simulate_target_weight_portfolio(px,tw,initial_capital=10000.,corporate_action_events=ev,reference_returns=ref,
            cost_assumptions=self.engine.TradingCostAssumptions(commission_bps=100))
        for i in [6,7,9]:
            np.testing.assert_allclose(r["daily_nav"].iloc[i],r["daily_nav"].iloc[i-1],rtol=0,atol=1e-12)
            self.assertEqual(r["trades"].iloc[i].cost_fraction,0)

    def test_sale_while_credited_cannot_dispose_of_locked_quantity(self):
        dates,px,tw,ev,ref=fixture()
        tw=pd.concat([tw.iloc[:3],pd.DataFrame([[0,0]],index=dates[7:8],columns=px.columns)])
        r=self.execute(tw=tw)
        for label,comm,tax in [("Gross",0,0),("Net",.01,.01)]:
            oracle=independent_book(px,tw,[json.loads(ev.iloc[0].stock_dividend_contract)],comm,tax)
            np.testing.assert_allclose(r["daily_nav"][label]*10000,[x["value"] for x in oracle],rtol=0,atol=1e-8)
            weights=r["weights" if label=="Gross" else "net_weights"]
            self.assertEqual(weights.loc[dates[8],"000001"],0)
            self.assertGreater(weights.loc[dates[8],"StockDividendIlliquid"],0)
            self.assertGreater(weights.loc[dates[9],"000001"],0)

    def test_simultaneous_pending_rights_on_different_securities(self):
        dates,px,tw,ev,ref=fixture()
        p=json.loads(ev.iloc[0].stock_dividend_contract)
        p["terms"].update(event_id="B",security="000002",ex_date=str(dates[4].date()),record_date=str(dates[5].date()),rate="0.2")
        p["market_reference"]["reference_price"]="50"
        p["marks"]=[dict(session=str(dates[i].date()),unit_value="40",rationale="synthetic second security",evidence=proof(str(dates[i].date()))) for i in range(4,7)]
        row=ev.iloc[0].to_dict();row.update(event_date=dates[4],predecessor_code="000002",successor_code="000002",share_ratio=.2,stock_dividend_contract=json.dumps(p))
        ev=pd.concat([ev,pd.DataFrame([row])],ignore_index=True)
        r=self.execute(ev=ev)
        for label,comm,tax in [("Gross",0,0),("Net",.01,.01)]:
            oracle=independent_book(px,tw,[json.loads(x) for x in ev.stock_dividend_contract],comm,tax)
            np.testing.assert_allclose(r["daily_nav"][label]*10000,[x["value"] for x in oracle],rtol=0,atol=1e-8)


if __name__=="__main__": unittest.main(verbosity=2)
