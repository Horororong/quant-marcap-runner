"""Bounded public KIND LG/LX demerger change/new-listing evidence, without credentials.

Three fixed searches and at most five returned original documents. No retries, inferred
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
    p.add_argument('--followup', action='store_true')
    p.add_argument('--historical', action='store_true')
    p.add_argument('--skt', action='store_true')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    state = dict(requests=0, retries=0, responses=[], candidates=[], errors=[], investment_approved=False)

    def capture(url, name, data=None):
        if state['requests'] >= (24 if a.skt else 18):
            raise ValueError('REQUEST_BUDGET18')
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
        targets = []
        queries = [('A003550', 'LG', '변경상장'), ('A383800', 'LX홀딩스', '신규상장'), ('A003550', 'LG', '기준가격')]
        if a.followup:
            # New evidence: a demerger-created company uses RE-listing, not
            # initial-listing. This is a changed, bounded search, not a retry.
            queries = [('A383800', '', '재상장'), ('A383800', '', '기준가격')]
            capture('https://kind.krx.co.kr/external/2020/11/26/000378/20201126000891/11345.htm', '20201126000378_decision.html')
        queries=[(*q,'2021-05-20','2021-05-31') for q in queries]
        if a.historical:
            queries=[('A015580','','주식이전','2001-08-01','2001-09-10'),('A012170','','변경상장','2001-06-15','2001-06-21')]
        if a.skt:
            queries=[('A017670','','변경상장','2021-11-15','2021-11-30'),('A402340','','재상장','2021-11-15','2021-11-30'),('A017670','','기준가격','2021-11-15','2021-11-30'),('A017670','','회사분할결정','2021-06-01','2021-06-30')]
        for code, company, title, start, end in queries:
            params = dict(method='searchDetailsSub', forward='details_sub', currentPageSize='100', pageIndex='1',
                          orderMode='0', orderStat='D', fromDate=start, toDate=end,
                          searchCodeType='char', repIsuSrtCd=code, searchCorpName=company,
                          oldSearchCorpName=company, reportNm=title, reportNmTemp=title)
            text = capture('https://kind.krx.co.kr/disclosure/details.do', code+'_'+title+'_search.html', parse.urlencode(params).encode())
            for row in re.findall(r'<tr\b.*?</tr>', text, re.S | re.I):
                if a.skt and any(x in row for x in ['주식선물','파생상품','우선주']):
                    continue
                if title not in row:
                    continue
                for receipt in re.findall(r"openDisclsViewer\(['\"](\d{14})", row):
                    state['candidates'].append(dict(receipt=receipt, code=code, title=title, row=re.sub('<[^>]+>', ' ', row)))
                    if receipt not in targets:
                        targets.append(receipt)
            if len(targets)>(6 if a.skt else 4 if a.followup else 5):
                raise ValueError('MORE_THAN_FIVE_CANDIDATES_REVIEW_BEFORE_COLLECTION')
        if not targets:
            raise ValueError('NO_RETURNED_CANDIDATES')
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
