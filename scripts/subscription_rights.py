"""Atomic rights/cash subledger; common ordinary-share owner, no new backtester.

Not connected to public execution until event inputs and daily marks exist.
An absent right price is not zero. Rights and unsettled sales never fund trades.
"""
from copy import deepcopy
from decimal import Decimal,localcontext,Context,Inexact
from stock_dividend import StockDividendBook,number,day,code
CONTRACT='subscription-rights-cash-v1'

class RightsIssueBook:
    def __init__(self,cash,shares=None,*,scope,quantity_policy,policy):
        if policy not in {'sell_observed_rights','funded_subscription'}:raise ValueError('EXPLICIT_PREDECLARED_RIGHTS_POLICY_REQUIRED')
        self.policy=policy
        self.owner=StockDividendBook(cash,shares,scope=scope,quantity_policy=quantity_policy)
        self.claims={};self.receivables=[];self.history=[]
    def close(self,session,prices,*,entitlements=(),marks=(),sales=(),subscriptions=(),releases=(),trades=()):
        draft=deepcopy(self)
        with localcontext(Context(prec=50))as ctx:
            ctx.traps[Inexact]=True
            try:result=draft._close(session,prices,entitlements,marks,sales,subscriptions,releases,trades)
            except Inexact:raise ValueError('EXACT_RIGHTS_ARITHMETIC_REQUIRED')from None
        self.__dict__.update(draft.__dict__);return result
    def _close(self,session,prices,entitlements,marks,sales,subscriptions,releases,trades):
        dt=day(session);scope=self.owner.scope;actions=[]
        if self.owner.last_session and dt<=day(self.owner.last_session):raise ValueError('STRICT_SESSION_ORDER')
        def proof(e,*,fact=False):
            e.check(session,scope)
            if fact and scope!='synthetic'and e.kind!='primary':raise ValueError('HISTORICAL_FACT_REQUIRES_PRIMARY_SOURCE')
        for t in entitlements:
            proof(t['evidence'],fact=True);code(t['security'])
            if t['event_id']in self.claims or any(c['security']==t['security']and c['ex_date']==t['ex_date']for c in self.claims.values()):raise ValueError('DUPLICATE_ENTITLEMENT')
            if day(t['ex_date'])!=dt or day(t['record_date'])<dt:raise ValueError('EXACT_EX_DATE_AND_RECORD_DATE_REQUIRED')
            q=Decimal(self.owner.shares.get(t['security'],0))*number(t['rate'],'rights ratio',positive=True)
            if self.owner.quantity_policy=='whole'and q!=q.to_integral_value():raise ValueError('FRACTIONAL_RIGHTS_UNSUPPORTED')
            self.claims[t['event_id']]=dict(security=t['security'],ex_date=t['ex_date'],rights=q,paid_shares=Decimal(0),eligible_opening_shares=self.owner.shares.get(t['security'],0))
            actions.append(dict(action='rights_created_from_opening_holdings',event=t['event_id'],quantity=str(q)))
        for r in self.receivables:
            if not r['settled']and day(r['settlement_date'])<=dt:
                proof(r['evidence']);self.owner.cash+=r['amount'];r['settled']=True
                actions.append(dict(action='rights_sale_cash_received',amount=str(r['amount'])))
        for s in sales:
            if self.policy!='sell_observed_rights':raise ValueError('RIGHTS_POLICY_CHANGED')
            proof(s['evidence'],fact=True);proof(s['settlement_evidence'])
            if not s['rights_security']or not day(s['trading_start'])<=dt<=day(s['trading_end'])or day(s['settlement_date'])<dt:raise ValueError('RIGHT_SECURITY_TRADING_AND_SETTLEMENT_REQUIRED')
            c=self.claims[s['event_id']];q=number(s['quantity'],'sold rights',positive=True)
            if self.owner.quantity_policy=='whole'and q!=q.to_integral_value():raise ValueError('FRACTIONAL_RIGHTS_UNSUPPORTED')
            if q>c['rights']:raise ValueError('INSUFFICIENT_OWNED_RIGHTS')
            gross=q*number(s['unit_price'],'observed rights execution price',positive=True);fee=number(s['fee'],'rights cost')
            if fee>gross:raise ValueError('RIGHTS_COST_EXCEEDS_PROCEEDS')
            c['rights']-=q;net=gross-fee
            if day(s['settlement_date'])==dt:self.owner.cash+=net
            else:self.receivables.append(dict(amount=net,settlement_date=s['settlement_date'],evidence=s['settlement_evidence'],settled=False))
            actions.append(dict(action='rights_sold',event=s['event_id'],quantity=str(q),gross_proceeds=str(gross),fee=str(fee),settled_cash=str(net)if day(s['settlement_date'])==dt else'0'))
        for s in subscriptions:
            if self.policy!='funded_subscription':raise ValueError('RIGHTS_POLICY_CHANGED')
            proof(s['evidence'],fact=True)
            if day(s['payment_date'])!=dt:raise ValueError('EXACT_PAYMENT_DATE_REQUIRED')
            c=self.claims[s['event_id']];q=number(s['quantity'],'subscribed shares',positive=True);cost=q*number(s['unit_price'],'asof confirmed subscription price',positive=True)
            if self.owner.quantity_policy=='whole'and q!=q.to_integral_value():raise ValueError('FRACTIONAL_RIGHTS_UNSUPPORTED')
            if q>c['rights']or cost>self.owner.cash:raise ValueError('INSUFFICIENT_RIGHTS_OR_SETTLED_CASH')
            c['rights']-=q;c['paid_shares']+=q;self.owner.cash-=cost
            actions.append(dict(action='subscription_paid',event=s['event_id'],quantity=str(q),cash_outflow=str(cost)))
        for r in releases:
            proof(r['evidence'],fact=True);c=self.claims[r['event_id']]
            if day(r['actual_date'])!=dt or number(r['quantity'],'released quantity',positive=True)!=c['paid_shares']:raise ValueError('EXACT_RELEASE_QUANTITY_AND_DATE_REQUIRED')
            if r['basis']not in {'verified_actual_credit_and_listing','explicit_virtual_listing'}or(r['basis']=='explicit_virtual_listing'and scope!='modeled_research'):raise ValueError('ACCOUNT_VS_VIRTUAL_LISTING_BASIS_REQUIRED')
            security=c['security'];self.owner.shares[security]=self.owner.shares.get(security,0)+c['paid_shares'];c['paid_shares']=Decimal(0)
            actions.append(dict(action='paid_shares_tradable',event=r['event_id'],quantity=r['quantity'],basis=r['basis'],no_second_income=True))
        # Reuse common share/cash/fee accounting. Pending rights, paid locked
        # shares, and unsettled proceeds are outside the spendable sleeve.
        ordinary=self.owner.close(session,prices,trades=trades)
        required={e for e,c in self.claims.items()if c['rights']>0};observed={}
        for mark in marks:
            proof(mark['evidence'])
            if mark['event_id']not in required or mark['event_id']in observed or day(mark['session'])!=dt or not mark['rationale']:raise ValueError('EXACT_ASOF_RIGHTS_MARK_REQUIRED')
            observed[mark['event_id']]=number(mark['unit_value'],'rights mark')
        if required!=set(observed):raise ValueError('MISSING_RIGHTS_VALUATION_NO_NAV')
        rv=sum((c['rights']*observed[e]for e,c in self.claims.items()if c['rights']>0),Decimal(0))
        paid=sum((c['paid_shares']*number(prices[c['security']],'underlying close',positive=True)for c in self.claims.values()if c['paid_shares']),Decimal(0))
        receivable=sum((r['amount']for r in self.receivables if not r['settled']),Decimal(0))
        result=dict(session=session,contract=CONTRACT,policy=self.policy,scope=scope,ordinary=ordinary,rights={e:str(c['rights'])for e,c in self.claims.items()},paid_untradable={e:str(c['paid_shares'])for e,c in self.claims.items()},rights_value=str(rv),paid_share_value=str(paid),unsettled_sale_receivable=str(receivable),settled_cash=str(self.owner.cash),value=str(Decimal(ordinary['value'])+rv+paid+receivable),actions=actions,investment_approved=False,distribution_tax_basis='before_distribution_tax',public_execution_connected=False)
        self.history.append(deepcopy(result));return result
