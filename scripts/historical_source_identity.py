"""Named-signal issuer/security evidence, separate from publication and PIT.

Current code-map names never establish historical identity. Nonliteral names
require a reviewed, source-bound self-identification quote and bounded dates.
"""
import hashlib
import re
from datetime import date


def legal_name(name):
    # Legal forms only: no transliteration, abbreviation guessing or 우 removal.
    return re.sub(r'\s+', '', name.replace('주식회사', '').replace('(주)', '').replace('㈜', ''))


def source_binding(identity):
    return {k: identity.get(k) for k in ('corp_code', 'rcept_no', 'source_member_sha256', 'source_archive_sha256')}


def assess_identity(identity, raw_member, official_rows, official_evidence, signal_date, alias_reviews=()):
    def held(reason):
        return dict(verdict='UNVERIFIED', reason=reason, signal_date=signal_date,
                    publication_certified=False, whole_PIT_eligible=False)

    signal = date.fromisoformat(signal_date)
    if hashlib.sha256(raw_member).hexdigest() != identity.get('source_member_sha256'):
        return held('SOURCE_MEMBER_HASH_MISMATCH')
    text = None
    for enc in ('utf-8', 'cp949', 'euc-kr'):
        try:
            decoded = raw_member.decode(enc)
            if decoded.encode(enc) == raw_member:
                text = decoded
                break
        except UnicodeError:
            continue
    if text is None:
        return held('SOURCE_ENCODING_UNVERIFIED')
    issuer = re.search(r'<COMPANY-NAME\b[^>]*AREGCIK="(\d{8})"[^>]*>([^<]+)', text[:3000])
    if not issuer or issuer[1] != identity.get('corp_code') or issuer[2] != identity.get('original_issuer'):
        return held('ORIGINAL_ISSUER_BINDING_MISMATCH')
    if official_evidence.get('date') != signal_date or not official_evidence.get('sha256') or not official_evidence.get('source'):
        return held('OFFICIAL_SNAPSHOT_DATE_OR_SOURCE_UNVERIFIED')
    rows = [r for r in official_rows if r['ISU_CD'] == identity['stock_code']]
    if len(rows) != 1:
        return held('NO_UNIQUE_OFFICIAL_SECURITY_AT_SIGNAL')
    official = rows[0]
    name = legal_name(official['ISU_NM'])
    if sum(legal_name(r['ISU_NM']) == name for r in official_rows) != 1:
        return held('HISTORICAL_NAME_NOT_UNIQUE')
    method = 'EXACT_ORIGINAL_ISSUER_AND_OFFICIAL_NAME'
    accepted = None
    if name != legal_name(issuer[2]):
        plain = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text))
        for review in alias_reviews:
            if review.get('verdict') != 'PASS' or review.get('binding') != source_binding(identity):
                continue
            if review.get('scope') != 'CURRENT_ISSUER_SELF_IDENTIFICATION' or not review.get('evidence'):
                continue
            if legal_name(review.get('official_alias', '')) != name:
                continue
            if not date.fromisoformat(review['from']) <= signal <= date.fromisoformat(review['through']):
                continue
            quote = review.get('source_quote', '')
            literal = review.get('alias_literal', '')
            if not quote or not literal or quote not in plain or literal not in quote:
                continue
            method = 'REVIEWED_BOUND_SOURCE_SELF_NAME_OR_ALIAS'
            accepted = review
            break
        if accepted is None:
            return held('HISTORICAL_ALIAS_OR_CHANGE_NOT_ATTESTED')
    evidence = [dict(original=source_binding(identity), official=official_evidence, method=method,
                     official_name=official['ISU_NM'], source_alias=accepted)]
    return dict(verdict='PASS', reason=method, signal_date=signal_date,
                historical_security_mapping=dict(verdict='PASS', stock_code=identity['stock_code'],
                                                 **{'from': signal_date, 'through': signal_date}, evidence=evidence),
                publication_certified=False, whole_PIT_eligible=False,
                interval_between_snapshots_certified=False)
