"""Bounded public KIND actual change-listing evidence, without credentials.

One search and at most two returned original documents. No retries, inferred
body URLs, price collection, financial collection or bulk history requests.
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from urllib import request, parse, error

HOME = Path(__file__).resolve().parent
ROOT = HOME.parents[2]
s = importlib.util.spec_from_file_location('safe14', ROOT / 'docs/research/stage14-celltrion-2019-20261017/collect_sources.py')
safe = importlib.util.module_from_spec(s)
s.loader.exec_module(safe)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    state = dict(requests=0, retries=0, responses=[], candidates=[], errors=[], investment_approved=False)

    def capture(url, name, data=None):
        if state['requests'] >= 7:
            raise ValueError('REQUEST_BUDGET7')
        state['requests'] += 1
        try:
            with request.build_opener(safe.safe.NoRedirect()).open(request.Request(url, data=data), timeout=25) as r:
                raw = r.read(safe.safe.MAX_BYTES + 1)
                status, content_type = r.status, r.headers.get('Content-Type', '')
            if not raw or len(raw) > safe.safe.MAX_BYTES:
                raise ValueError('EMPTY_OR_OVERSIZE')
            text = safe.safe.decode(raw)
            (a.output / name).write_bytes(raw)
            state['responses'].append(dict(file=name, source=url, http=status, content_type=content_type,
                                           bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            return text
        except error.HTTPError as e:
            state['errors'].append(dict(file=name, http=e.code, reason='HTTP_FAILURE'))
            raise RuntimeError('HTTP_FAILURE_STOP') from None

    try:
        params = dict(method='searchDetailsSub', forward='details_sub', currentPageSize='100', pageIndex='1',
                      orderMode='0', orderStat='D', fromDate='2018-05-01', toDate='2018-05-04',
                      searchCodeType='char', repIsuSrtCd='A005930', searchCorpName='삼성전자',
                      oldSearchCorpName='삼성전자', reportNm='변경상장', reportNmTemp='변경상장')
        text = capture('https://kind.krx.co.kr/disclosure/details.do', '005930_search.html', parse.urlencode(params).encode())
        for row in re.findall(r'<tr\b.*?</tr>', text, re.S | re.I):
            if '변경상장' not in row:
                continue
            for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})", row):
                state['candidates'].append(dict(receipt=receipt, row=re.sub('<[^>]+>', ' ', row)))
        targets = list(dict.fromkeys(r['receipt'] for r in state['candidates']))
        if not targets or len(targets) > 2:
            raise ValueError('EXPECTED_1_OR_2_RETURNED_CANDIDATES')
        for receipt in targets:
            text = capture('https://kind.krx.co.kr/common/disclsviewer.do?' + parse.urlencode(dict(method='searchInitInfo', acptNo=receipt)), receipt + '_viewer.html')
            m = re.search(r"<option value=['\"](\d{14})\|Y['\"]", text)
            if not m:
                raise ValueError('NO_RETURNED_DOCNO')
            text = capture('https://kind.krx.co.kr/common/disclsviewer.do?' + parse.urlencode(dict(method='searchContents', docNo=m[1])), receipt + '_path.html')
            urls = re.findall(r"[\"'](https://kind\.krx\.co\.kr/external/[^\"'\s]+\.htm)[\"']", text)
            if not urls:
                raise ValueError('NO_RETURNED_BODY_PATH')
            capture(urls[0], receipt + '_body.html')
    except Exception as e:
        state['errors'].append(dict(reason=type(e).__name__, detail=str(e) if isinstance(e, ValueError) else 'bounded collection stopped; no retry'))
    (a.output / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    safe.emit_bundle(a.output, state)
    return int(bool(state['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
