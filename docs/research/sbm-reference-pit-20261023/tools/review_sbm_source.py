"""Named source-row controls, independent of the production account extractor.

The four strategy-core controls were read before the new parser's result;
eleven other named rows were subsequently checked directly against the source.
Neither constitutes whole-filing completeness or PIT certification.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--candidates', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.root / 'scripts'))
from financial_source_grid import Grid

CONTROLS = [
    ('current_assets','BS',71,2,'유동자산','18504191029'),
    ('cash_and_equivalents','BS',71,4,'현금및현금성자산','1164638780'),
    ('ppe','BS',71,29,'유형자산','652435008'),
    ('total_assets','BS',71,53,'자산총계','22954462773'),
    ('current_liabilities','BS',71,55,'유동부채','2996123333'),
    ('short_term_borrowings','BS',71,57,'단기차입금','1400000000'),
    ('total_liabilities','BS',71,78,'부채총계','8013965846'),
    ('equity','BS',71,92,'자본총계','14940496927'),
    ('revenue','IS',73,1,'매출액','26825640512'),
    ('cost_of_sales','IS',73,4,'매출원가','13970812968'),
    ('gross_profit','IS',73,11,'매출총이익(손실)','12854827544'),
    ('amortization','IS',73,32,'무형자산상각비','182030610'),
    ('operating_income','IS',73,36,'영업이익(손실)','9103471972'),
    ('net_income','IS',73,67,'당기순이익(손실)','7265064249'),
    ('ocf','CF',79,1,'영업활동으로인한현금흐름','7041030972'),
]
archive_sha = hashlib.sha256(a.archive.read_bytes()).hexdigest()
assert archive_sha == '10f1e6aebdf5f245bd4026a030d494cf64cd94813c33eb89064c0e3989408c13'
member = '20100331001822.xml'
with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None
    raw = z.read(member)
sha = hashlib.sha256(raw).hexdigest()
assert sha == '72060bc182d3145be2e3e8623c043c05bb9f7bba684e3331074b38d156cb55ea'
for enc in ['utf-8', 'cp949', 'euc-kr']:
    try:
        text = raw.decode(enc); assert text.encode(enc) == raw; break
    except (UnicodeError, AssertionError): pass
else: raise ValueError('SOURCE_ENCODING')
g = Grid(); g.feed(text)
# The explicit OFS declaration precedes the BS. Later statement contexts are
# bounded excerpts and can no longer contain that declaration. Keep its own
# source location instead of treating an inherited excerpt as new evidence.
scope_context = g.tables[70]['context']
assert 'XBRL개별재무제표' in re.sub(r'\s+', '', scope_context)
candidates = json.loads(a.candidates.read_text())
assert len(candidates) == 15
reviews = []
for metric, statement, ti, ri, label, expected in CONTROLS:
    table = g.tables[ti]; row = table['rows'][ri]
    assert row[0].strip() == label and row[1].replace(',', '') == expected
    context = re.sub(r'\s+', '', table['context'])
    assert not re.search(r'연결(?:재무상태표|대차대조표|손익계산서|현금흐름표)', context)
    assert '(단위:원)' in context and '2009년12월31일' in context
    if statement != 'BS': assert '2009년01월01일' in context
    assert table['rows'][0][1:] == ['제13기', '제12기', '제11기']
    matches = [r for r in candidates if r['metric'] == metric]
    assert len(matches) == 1
    c = matches[0]
    assert (c['scope'], c['statement'], c['table_index'], c['row_index'], c['value_col']) == ('OFS', statement, ti, ri, 1)
    assert c['source_member'] == member and c['source_member_sha256'] == sha
    assert Decimal(c['amount_krw']) == Decimal(expected)
    assert c['period_end'] == '2009-12-31'
    assert c['period_start'] == ('' if statement == 'BS' else '2009-01-01')
    assert c['unit'] == '원' and Decimal(c['unit_multiplier']) == 1
    assert not c['backtest_eligible'] and c['availability_status'] == 'UNVERIFIED'
    reviews.append(dict(receipt='20100331001822', corp_code='00265227', stock_code_hint='037630',
        metric=metric, scope='OFS', statement=statement, source_archive_sha256=archive_sha,
        source_member=member, source_member_sha256=sha, table=ti, row=ri, current_physical_column=1,
        source_row_label=label, source_comparison_cells=row[2:], current_header=table['rows'][0],
        period_start=c['period_start'], period_end=c['period_end'], measurement_basis=c['measurement_basis'],
        reference_unit='원', reference_unit_multiplier='1', independent_amount_krw=expected,
        candidate_amount_krw=c['amount_krw'], source_context=table['context'],
        scope_declaration_table=70, scope_declaration_context=scope_context,
        period_current_comparative='PASS', scope_heading='PASS', unit_sign='PASS', account_definition='PASS',
        semantic_verdict='PASS', PIT='UNVERIFIED_PUBLICATION_AND_VERSION_CHAIN',
        whole_filing_extraction_completeness='UNVERIFIED', engine_eligible=False))
# Independent table arithmetic is extra evidence, never a substitute for source cells.
assert Decimal('22954462773') == Decimal('8013965846') + Decimal('14940496927')
assert Decimal('26825640512') - Decimal('13970812968') == Decimal('12854827544')
result = dict(classification='RESEARCH_ONLY', rows=reviews,
    summary=dict(source_semantic_PASS=15, new_strategy_core_fields=4, new_company_hints=1,
                 whole_document_complete=False, PIT_eligible=0, live_engine_eligible=0,
                 actual_source_HTTP=0, review_method='Named actual primary-source cells/headers read independently of production parser; four core controls frozen before new extraction output'))
a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result['summary'], indent=2))
