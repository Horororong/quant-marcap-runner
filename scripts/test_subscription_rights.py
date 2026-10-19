import copy,sys,unittest
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from subscription_rights import RightsIssueBook
from stock_dividend import Evidence,Trade
E=Evidence('synthetic:rights','a'*64,'synthetic independent fixture','2022-01-01','synthetic')
T=dict(event_id='a',security='000001',ex_date='2022-02-01',record_date='2022-02-02',rate='0.1',evidence=E)
def mark(s,v='4'):return dict(event_id='a',session=s,unit_value=v,evidence=E,rationale='synthetic observed quote, not Samsung')
def book(c='0',q='100',policy='sell_observed_rights'):return RightsIssueBook(c,{'000001':D(q)},scope='synthetic',quantity_policy='synthetic_pro_rata',policy=policy)
def state(b):return copy.deepcopy({**b.__dict__,'owner':b.owner.__dict__})
class Rights(unittest.TestCase):
    def test_sale_receivable_cannot_fund_trades_and_independent_cash(self):
        for opening_cash,shares,fee in [('100','100','0'),('90','99','1')]:
            b=book(opening_cash,shares);q=D(shares)/10
            s=b.close('2022-02-01',{'000001':'10'},entitlements=[T],marks=[mark('2022-02-01')])
            self.assertEqual(D(s['value']),D(opening_cash)+D(shares)*10+q*4)
            # Selling old shares leaves rights; buying after ex creates none.
            s=b.close('2022-02-02',{'000001':'11'},marks=[mark('2022-02-02','5')],trades=[Trade('000001','sell',D(shares),'0')])
            expected_cash=D(opening_cash)+D(shares)*11
            self.assertEqual(D(s['settled_cash']),expected_cash);self.assertEqual(D(s['rights']['a']),q)
            sale=dict(event_id='a',rights_security='SYNTHETIC_RIGHT',quantity=str(q),unit_price='5',fee=fee,trading_start='2022-02-03',trading_end='2022-02-04',settlement_date='2022-02-07',evidence=E,settlement_evidence=E)
            s=b.close('2022-02-03',{'000001':'11'},sales=[sale]);self.assertEqual(D(s['settled_cash']),expected_cash)
            proceeds=q*5-D(fee);self.assertEqual(D(s['value']),expected_cash+proceeds)
            before=state(b)
            with self.assertRaisesRegex(ValueError,'insufficient settled cash'):b.close('2022-02-04',{'000001':'1'},trades=[Trade('000001','buy',expected_cash+1)])
            self.assertEqual(state(b),before)
            s=b.close('2022-02-07',{'000001':'11'});self.assertEqual(D(s['settled_cash']),expected_cash+proceeds);self.assertEqual(D(s['value']),expected_cash+proceeds)
    def test_subscription_payment_locked_release_no_second_gain(self):
        b=book('100','100','funded_subscription')
        b.close('2022-02-01',{'000001':'10'},entitlements=[T],marks=[mark('2022-02-01')])
        s=b.close('2022-02-02',{'000001':'10'},subscriptions=[dict(event_id='a',quantity='10',unit_price='6',payment_date='2022-02-02',evidence=E)])
        self.assertEqual(D(s['value']),D('1140'));self.assertEqual(D(s['settled_cash']),D('40'));self.assertEqual(D(s['paid_untradable']['a']),10)
        with self.assertRaisesRegex(ValueError,'insufficient tradable shares'):b.close('2022-02-03',{'000001':'10'},trades=[Trade('000001','sell',D('101'))])
        s=b.close('2022-02-03',{'000001':'10'},releases=[dict(event_id='a',quantity='10',actual_date='2022-02-03',evidence=E,basis='verified_actual_credit_and_listing')])
        self.assertEqual(D(s['value']),D('1140'));self.assertEqual(D(s['ordinary']['tradable_shares']['000001']),110)
    def test_missing_mark_future_evidence_and_new_buyer_no_right(self):
        b=book();before=state(b)
        with self.assertRaisesRegex(ValueError,'NO_NAV'):b.close('2022-02-01',{'000001':'10'},entitlements=[T])
        self.assertEqual(state(b),before)
        late=Evidence('synthetic:future','a'*64,'later','2022-02-02','synthetic');t={**T,'evidence':late}
        with self.assertRaisesRegex(ValueError,'future'):b.close('2022-02-01',{'000001':'10'},entitlements=[t],marks=[mark('2022-02-01')])
        b=book('1000','0');s=b.close('2022-02-01',{'000001':'10'},entitlements=[T],trades=[Trade('000001','buy',D('100'))])
        self.assertEqual(D(s['rights']['a']),0)
    def test_insufficient_payment_and_duplicate_entitlement_atomic(self):
        b=book('0','100','funded_subscription');b.close('2022-02-01',{'000001':'10'},entitlements=[T],marks=[mark('2022-02-01')]);before=state(b)
        with self.assertRaisesRegex(ValueError,'SETTLED_CASH'):b.close('2022-02-02',{'000001':'10'},subscriptions=[dict(event_id='a',quantity='10',unit_price='6',payment_date='2022-02-02',evidence=E)])
        self.assertEqual(state(b),before)
if __name__=='__main__':unittest.main(verbosity=2)
