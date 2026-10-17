"""Real-source/price component checks, never a substitute for event execution.

No registry write, network, inferred payment date or conditional-right mark.
The expected block is reported as UNVERIFIED, not a successful real event.
"""
import argparse
import base64
from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from stock_dividend import Evidence, Terms, Trade, StockDividendBook, validate_market_reference


def review():
    raw=base64.b64decode((HOME/'evidence/20191218800434.raw.b64').read_bytes().rstrip(b'\n'),validate=True)
    assert hashlib.sha256(raw).hexdigest()=='ac7535444b78db7ac3524e0988147739f0e37a7741bd0aa9b4853100b630924a'
    text=raw.decode('cp949');assert text.encode('cp949')==raw
    # Independently inspect the original member, not the collector's text JSON.
    root=ET.fromstring(text)
    flat=' '.join(' '.join(root.itertext()).split())
    controls=['셀트리온','2019.12.18','0.05','6,360,313','2019-12-31','정기주주총회 전일 종가']
    for value in controls: assert value in flat,value
    issuer=' '.join((HOME/'evidence/issuer_697_text.txt').read_text().split())
    for value in ['2020.04.06','2020년 3월 27일 결의된','4월 24일 상장 예정','소득세 14%','지방소득세 1.4%','액면가 기준','증권사에 확인']:
        assert value in issuer,value
    listing=(HOME/'evidence/kind_body_0.html').read_bytes()
    assert hashlib.sha256(listing).hexdigest()=='7f481944f225981bb635ec204b9686eb78c80fc458c6ed38023fd4acbda7e161'
    listing=listing.decode('utf-8')
    for value in ['(주)셀트리온 보통주 추가상장','6,360,313주','발행일 : 2020년03월27일','주식배당','상장일 : 2020년04월24일','KR7068270008','A068270']:
        assert value in listing,value
    official=json.loads((HOME.parent/'stage12-stock-dividend-20261016/official_krx/state.json').read_bytes())
    rows={(x['security'],x['date']):x for x in official['target_rows']}
    before=rows['068270','20191226']['raw_api_row'];after=rows['068270','20191227']['raw_api_row']
    assert before['ISU_CD']==after['ISU_CD']=='068270'
    assert before['BAS_DD']=='20191226' and after['BAS_DD']=='20191227'
    n=lambda x:Decimal(x.replace(',',''))
    old,close,reported=n(before['TDD_CLSPRC']),n(after['TDD_CLSPRC']),n(after['FLUC_RT'])
    assert (old,close,reported)==(Decimal(189500),Decimal(184000),Decimal('1.66'))
    old_evidence=ROOT/'docs/research/stage11-official-event-evidence-20261016/evidence.json'
    source=next(s for s in json.loads(old_evidence.read_bytes())['sources'] if s['id']=='E11-01')
    assert source['short_exact_excerpt']=='셀트리온 : 181,000원' and source['effective_date_as_read']=='2019.12.27(금)'
    e=Evidence(source['url'],hashlib.sha256(old_evidence.read_bytes()).hexdigest(),
        'E11-01 preserved official-page observation; hash is authored observation JSON, NOT original HTTP bytes',
        '2019-12-27','primary')
    price=validate_market_reference(session='2019-12-27',security='068270',close=str(close),reference_price='181000',
        changes_ratio_pct=str(reported),evidence=e,scope='evidenced_research')
    price['verdict']='PASS_PRICE_COMPONENT_ONLY'
    with localcontext() as ctx:
        ctx.prec=50
        raw_return=str(close/old-1)
    # Fixed opening quantity is an explicitly chosen functional-test account,
    # not the original deciles allocation or a historical brokerage account.
    terms=Terms('stage14-unregistered-probe','068270','2019-12-27','2019-12-31','0.05',
        Evidence('https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20191218800434',hashlib.sha256(raw).hexdigest(),
            'proposal rows1/4; ex-date independently reused from Stage11 E11-01; component probe only',
            '2019-12-27','primary'))
    book=StockDividendBook('0',{'068270':100},scope='evidenced_research')
    opening=book.close('2019-12-26',{'068270':str(old)})
    snapshot=deepcopy(book.__dict__)
    try: book.close('2019-12-27',{'068270':str(close)},entitlements=[terms])
    except ValueError as error:
        reason=str(error)
        assert reason=='explicit as-of mark required for every pending right; no default valuation',reason
    else: raise AssertionError('unvalued actual rights unexpectedly accepted')
    assert book.__dict__==snapshot,'failed actual-source close changed financial state'
    # Ex-date new buyer has no opening entitlement. No mark/payment is invented.
    new=StockDividendBook(str(close*100),scope='evidenced_research')
    new_snapshot=new.close('2019-12-27',{'068270':str(close)},entitlements=[terms],trades=[Trade('068270','buy',100)])
    assert new.claims[terms.event_id]['quantity']==0 and new.shares['068270']==100
    return dict(scope='RESEARCH_ONLY_COMPONENT_CHECKS_NOT_FULL_EVENT',security='068270',ex_date='2019-12-27',
        new_primary_controls=len(controls)+14,price_check=price,raw_close_return=raw_return,
        official_listing=dict(receipt='20200421000196',document='20200421000468',date='2020-04-24',shares=6360313,
            account_credit_proved=False,postfact_not_2019_signal_information=True),
        economic_holding_return=None,opening_functional_test=opening,
        pending_right_probe=dict(status='BLOCKED_UNVERIFIED',reason=reason,atomic_rollback=True,
            eligible_test_quantity=100,unvalued_entitlement_quantity='5.00',invented_mark=None),
        ex_date_new_buyer_probe=dict(status='PASS_COMPONENT_ONLY',snapshot=new_snapshot,entitlement_quantity='0.00',
            parameters='100-share zero-trading-fee functional account, not original strategy or historical tax account'),
        actual_registered_events=0,actual_complete_event_verdict='UNVERIFIED',investment_approved=False,
        exact_publication_time_certified=False,source_hash_scope_warning='Stage11 base reused from observation; no raw HTML falsely claimed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists(),'refuse overwrite'
    result=review();a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['actual_registered_events','actual_complete_event_verdict','investment_approved']}))
    # Software assertions passed, while the real event remains UNVERIFIED in the
    # artifact. This command is never named/counted as successful event execution.
    return 0


if __name__=='__main__': raise SystemExit(main())
