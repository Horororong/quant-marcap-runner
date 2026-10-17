"""Synthetic software evidence; no real Celltrion event is registered here."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from stock_dividend import (Evidence, Terms, Decision, Credit, Listing, RightMark,
                            Trade, StockDividendBook, validate_market_reference)
from corporate_action_registry import load_corporate_actions
from strategy_dsl_runner import load_project_engine


def proof(session="2024-01-02"):
    return Evidence("synthetic:stock-dividend-fixture", "a" * 64, "fixture row 1", session, "synthetic")


def terms(**kw):
    return replace(Terms("A", "000001", "2024-01-02", "2024-01-03", "0.1", proof()), **kw)


def mark(session, value="90", event="A"):
    return RightMark(event, session, value, "SYNTHETIC explicit conditional/liquidity valuation assumption", proof(session))


def credit(session="2024-01-04", **kw):
    return replace(Credit("A", session, 10, proof(session), "verified_none", proof(session)), **kw)


class LedgerTests(unittest.TestCase):
    def opened(self, quantity=100, rate="0.1"):
        b = StockDividendBook("0", {"000001": quantity}, scope="synthetic")
        b.close("2024-01-02", {"000001": "90"}, entitlements=[terms(rate=rate)], marks=[mark("2024-01-02")])
        return b

    def approved(self):
        b = self.opened()
        b.close("2024-01-03", {"000001": "90"},
                decisions=[Decision("A", "2024-01-03", True, proof("2024-01-03"))], marks=[mark("2024-01-03")])
        return b

    def unchanged_failure(self, b, fragment, fn):
        before = deepcopy(b.__dict__)
        with self.assertRaisesRegex((ValueError, KeyError), fragment):
            fn()
        self.assertEqual(before, b.__dict__, "failed close must be atomic including history")

    def test_independent_amount_book_sale_then_credit_and_listing(self):
        # Independent oracle uses fixed quantities/cash, not a return multiplier.
        # Sell old 100, buy 10 AFTER ex-date; only original 100 get 10 rights.
        b = StockDividendBook("0", {"000001": 100}, scope="synthetic")
        r = b.close("2024-01-02", {"000001": "90"}, entitlements=[terms()],
                    trades=[Trade("000001", "sell", 100, "9"), Trade("000001", "buy", 10)],
                    marks=[mark("2024-01-02", "85")])
        self.assertEqual(Decimal(r["cash"]), Decimal(100 * 90 - 9 - 10 * 90))
        self.assertEqual(Decimal(r["value"]), Decimal(100 * 90 - 9 + 10 * 85))
        self.assertEqual(r["claims"]["A"]["eligible_shares"], 100)
        r = b.close("2024-01-03", {"000001": "95"},
                    decisions=[Decision("A", "2024-01-03", True, proof("2024-01-03"))], marks=[mark("2024-01-03", "95")])
        self.assertEqual(Decimal(r["value"]), Decimal(8091 + 10 * 95 + 10 * 95))
        r = b.close("2024-01-04", {"000001": "100"}, credits=[credit()])
        self.assertEqual(r["tradable_shares"]["000001"], 10)
        self.assertEqual(r["claims"]["A"]["locked_shares"], 10)
        self.assertEqual(Decimal(r["value"]), Decimal(8091 + 20 * 100))
        value = r["value"]
        r = b.close("2024-01-05", {"000001": "100"}, listings=[Listing("A", "2024-01-05", proof("2024-01-05"))])
        self.assertEqual(r["tradable_shares"]["000001"], 20)
        self.assertEqual(r["value"], value)
        r = b.close("2024-01-08", {"000001": "100"}, trades=[Trade("000001", "sell", 20, "20")])
        self.assertEqual(Decimal(r["value"]), Decimal(10071))
        self.assertEqual(r["cash"], r["value"])
        self.assertFalse(r["investment_approved"])
        self.assertEqual(b.history[0]["claims"]["A"]["state"], "conditional")
        self.assertEqual(b.history[1]["claims"]["A"]["state"], "approved")
        self.assertEqual(b.history[2]["inputs"]["credits"][0]["evidence"]["sha256"], "a" * 64)

    def test_ex_date_new_buyer_has_no_rights(self):
        b = StockDividendBook("1000", scope="synthetic")
        r = b.close("2024-01-02", {"000001": "90"}, entitlements=[terms()], trades=[Trade("000001", "buy", 10)])
        self.assertEqual(r["claims"]["A"]["quantity"], "0.0")
        self.assertEqual(r["value"], "1000")

    def test_sale_keeps_rights_but_cannot_sell_them(self):
        b = self.opened()
        self.unchanged_failure(b, "tradable", lambda: b.close("2024-01-03", {"000001": "90"},
            trades=[Trade("000001", "sell", 110)], marks=[mark("2024-01-03")]))
        r = b.close("2024-01-03", {"000001": "90"}, trades=[Trade("000001", "sell", 100)], marks=[mark("2024-01-03")])
        self.assertEqual(r["rights_value"], "900.0")

    def test_rights_cannot_fund_trade(self):
        b = self.opened()
        self.unchanged_failure(b, "settled cash", lambda: b.close("2024-01-03", {"000001": "90"},
            trades=[Trade("000001", "buy", 1)], marks=[mark("2024-01-03")]))

    def test_missing_mark_fails_after_successful_actions_atomically(self):
        b = self.opened()
        self.unchanged_failure(b, "explicit as-of mark", lambda: b.close("2024-01-03", {"000001": "90"},
            decisions=[Decision("A", "2024-01-03", True, proof())], trades=[Trade("000001", "sell", 1)]))

    def test_approval_and_actual_credit_are_required(self):
        for modified in [credit(), credit(actual_date="2024-01-05")]:
            b = self.opened()
            self.unchanged_failure(b, "approved right", lambda: b.close("2024-01-04", {"000001": "90"}, credits=[modified]))

    def test_fractional_entitlement_is_kept_and_settlement_blocked(self):
        b = self.opened(quantity=101)
        self.assertEqual(b.claims["A"]["quantity"], Decimal("10.1"))
        b.close("2024-01-03", {"000001": "90"}, decisions=[Decision("A", "2024-01-03", True, proof())], marks=[mark("2024-01-03")])
        self.unchanged_failure(b, "fractional cash", lambda: b.close("2024-01-04", {"000001": "90"}, credits=[credit()]))

    def test_no_withholding_or_partial_receipt_guess(self):
        for c, msg in [(credit(tax_treatment="unknown"), "tax unsupported"), (credit(shares=9), "differs from entitlement")]:
            b = self.approved()
            self.unchanged_failure(b, msg, lambda: b.close("2024-01-04", {"000001": "90"}, credits=[c]))

    def test_locked_shares_cannot_be_sold(self):
        b = self.approved()
        b.close("2024-01-04", {"000001": "90"}, credits=[credit()])
        self.unchanged_failure(b, "tradable", lambda: b.close("2024-01-05", {"000001": "90"}, trades=[Trade("000001", "sell", 110)]))

    def test_credit_and_release_create_no_second_gain(self):
        b = self.approved()
        r = b.close("2024-01-04", {"000001": "90"}, credits=[credit()], listings=[Listing("A", "2024-01-04", proof())])
        self.assertEqual(Decimal(r["value"]), Decimal(9900))
        self.assertEqual(r["tradable_shares"]["000001"], 110)
        self.unchanged_failure(b, "approved right", lambda: b.close("2024-01-05", {"000001": "90"}, credits=[credit("2024-01-05")]))

    def test_listing_without_credit_or_wrong_date_fails(self):
        b = self.approved()
        self.unchanged_failure(b, "tradable release", lambda: b.close("2024-01-04", {"000001": "90"}, listings=[Listing("A", "2024-01-04", proof())]))

    def test_rejection_requires_own_contract(self):
        b = self.opened()
        self.unchanged_failure(b, "cancellation", lambda: b.close("2024-01-03", {"000001": "90"}, decisions=[Decision("A", "2024-01-03", False, proof())]))

    def test_missing_prices_never_filled(self):
        b = self.approved()
        self.unchanged_failure(b, "000001", lambda: b.close("2024-01-04", {}, credits=[credit()]))

    def test_duplicate_entitlement_and_overlapping_events_reject(self):
        for second, msg in [(replace(terms(), event_id="B"), "duplicate security"), (terms(), "duplicate stock")]:
            b = StockDividendBook("0", {"000001": 100}, scope="synthetic")
            self.unchanged_failure(b, msg, lambda: b.close("2024-01-02", {"000001": "90"}, entitlements=[terms(), second], marks=[mark("2024-01-02")]))
        b = self.opened()
        self.unchanged_failure(b, "overlapping", lambda: b.close("2024-01-03", {"000001": "90"}, entitlements=[terms(event_id="B", ex_date="2024-01-03")]))

    def test_duplicate_close_and_future_evidence_fail(self):
        b = self.opened()
        self.unchanged_failure(b, "strictly increase", lambda: b.close("2024-01-02", {"000001": "90"}))
        self.unchanged_failure(b, "future evidence", lambda: b.close("2024-01-03", {"000001": "90"},
            marks=[replace(mark("2024-01-03"), evidence=proof("2024-01-04"))]))

    def test_numeric_and_evidence_boundaries(self):
        for value in [True, 0.1, "NaN", "Infinity", "-1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                StockDividendBook(value, scope="synthetic")
        with self.assertRaises(ValueError):
            StockDividendBook("0", {"1": 100}, scope="synthetic")
        with self.assertRaises(ValueError):
            StockDividendBook("0", {"000001": 1.1}, scope="synthetic")
        for ev in [proof(), replace(proof(), kind="primary", source="https://official.invalid/doc", sha256="bad")]:
            b = StockDividendBook("0", {"000001": 100}, scope="evidenced_research")
            with self.assertRaises(ValueError):
                b.close("2024-01-02", {"000001": "90"}, entitlements=[terms(evidence=ev)], marks=[mark("2024-01-02")])

    def test_multiple_securities_independent(self):
        b = StockDividendBook("200", {"000001": 100, "000002": 20}, scope="synthetic")
        r = b.close("2024-01-02", {"000001": "90", "000002": "40"},
            entitlements=[terms(), terms(event_id="B", security="000002", rate="0.2")],
            marks=[mark("2024-01-02"), mark("2024-01-02", "40", "B")])
        self.assertEqual(Decimal(r["value"]), Decimal(200 + 100 * 90 + 20 * 40 + 10 * 90 + 4 * 40))

    def test_decimal_precision_is_not_caller_global_context(self):
        with localcontext() as ctx:
            ctx.prec = 2
            b = self.opened(quantity=12345, rate="0.012345")
        self.assertEqual(str(b.claims["A"]["quantity"]), "152.399025")

    def test_generator_inputs_remain_in_reproduction_log(self):
        b = StockDividendBook("0", {"000001": 100}, scope="synthetic")
        r = b.close("2024-01-02", {"000001": "90"}, entitlements=(x for x in [terms()]), marks=(x for x in [mark("2024-01-02")]))
        self.assertEqual(r["inputs"]["entitlements"][0]["event_id"], "A")
        self.assertEqual(len(r["inputs"]["marks"]), 1)

    def test_large_cash_cannot_silently_round_away_a_share_value(self):
        b = StockDividendBook("1e60", {"000001": 1}, scope="synthetic")
        self.unchanged_failure(b, "no silent rounding", lambda: b.close("2024-01-02", {"000001": "90"}))


class IntegrationTests(unittest.TestCase):
    def test_four_real_source_anomalies_still_fail_before_nav(self):
        # This is a local guard probe with hypothetical holdings, NOT the
        # original strategy rerun, an event registration or economic certificate.
        root = Path(__file__).resolve().parents[1]
        rows = pd.read_csv(root / "docs/research/stage10-return-diagnostic-20261016/results/planned_holding_mismatches.csv", dtype={"Code": str})
        engine = load_project_engine(root)
        panels = {year: pd.read_parquet(root / f"data/krx_equities/yearly/marcap-{year}.parquet", columns=["Date", "Code", "Close", "Volume", "ChangesRatio"])
                  for year in (2019, 2020)}
        self.assertEqual(len(rows), 4)
        for _, row in rows.iterrows():
            # The immutable diagnostic's exact codes/dates select the probes;
            # no species of price jump is inferred as a corporate action.
            dt, security = pd.Timestamp(row["Date"]), row["Code"]
            with self.subTest(security=security, date=str(dt.date())):
                panel = panels[dt.year]
                x = panel[(panel["Code"] == security) & (panel["Date"] <= dt)].sort_values("Date").tail(3).set_index("Date")
                self.assertEqual(len(x), 3)
                px = x[["Close"]].rename(columns={"Close": security})
                ref = (x[["ChangesRatio"]] / 100).rename(columns={"ChangesRatio": security})
                target = pd.DataFrame({security: [1.]}, index=px.index[:1])
                with self.assertRaisesRegex(RuntimeError, "held-return reference check failed"):
                    engine.simulate_target_weight_portfolio(px, target, reference_returns=ref)

    def test_market_reference_and_economic_book_are_different(self):
        checked = validate_market_reference(session="2024-01-02", security="000001", close="90", reference_price="91", changes_ratio_pct="-1.10", evidence=proof(), scope="synthetic")
        b = StockDividendBook("0", {"000001": 100}, scope="synthetic")
        r = b.close("2024-01-02", {"000001": "90"}, entitlements=[terms()], marks=[mark("2024-01-02")])
        # Economic marked value 9900 / 10000 - 1 = -1%, independent
        # reference-price return 90/91 - 1 ~= -1.0989%; intentionally unequal.
        self.assertNotEqual(Decimal(checked["return"]), Decimal(r["value"]) / 10000 - 1)
        self.assertFalse(checked["economic_return_certified"])
        for base in [None, "100"]:
            with self.assertRaises(ValueError):
                validate_market_reference(session="2024-01-02", security="000001", close="90", reference_price=base, changes_ratio_pct="-1.10", evidence=proof(), scope="synthetic")

    def test_existing_registry_and_project_reject_stock_dividend_until_integrated(self):
        row = dict(event_type="stock_dividend", event_date="2024-01-03", predecessor_code="000001", successor_code="000001", share_ratio="0.1", cash_per_share="0", source="synthetic:fixture")
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "config"
            p.mkdir()
            pd.DataFrame([row]).to_csv(p / "kr_corporate_actions.csv", index=False)
            with self.assertRaisesRegex(ValueError, "stock_dividend capability_gap"):
                load_corporate_actions(folder)
        engine = load_project_engine(Path(__file__).resolve().parents[1])
        dates = pd.date_range("2024-01-01", periods=3)
        px = pd.DataFrame({"000001": [100., 100., 90.]}, index=dates)
        target = pd.DataFrame({"000001": [1.]}, index=dates[:1])
        with self.assertRaisesRegex(ValueError, "stock_dividend capability_gap"):
            engine.simulate_target_weight_portfolio(px, target, corporate_action_events=pd.DataFrame([row]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
