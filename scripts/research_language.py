"""Controlled Korean -> existing StrategySpec. No model, codegen or calculations.

Every consumed financial condition is explicit; residue is rejected. Defaults
are returned for confirmation, never permission to run. Original labeled CLI
and its fingerprints are unchanged. Raw text belongs to the session envelope.
"""
import copy, hashlib, json, re
from research_workbench import korean_spec
from strategy_dsl import StrategySpec

CONTRACT='controlled-korean-research-v1'
SUPPORT={'provider':'deterministic_rules','external_model_connected':False,
 'scope':'Single registered size or explicit 3-1/6-1/12-1/12-0 momentum; equal top-N/deciles; calendar month-end; next-close; explicit fixed bps. Labeled legacy syntax also supported. Not arbitrary free language.',
 'unsupported':['ad-hoc factors/lookbacks','stop-loss/leverage/options','same-close/next-open','unregistered accounting definitions','ambiguous or unconsumed instructions']}
DEFAULT_COSTS={'수수료':'1.5','매도세':'15','스프레드':'3','슬리피지':'5'}
def canonical(raw):
    raw=copy.deepcopy(raw)
    raw['metadata']={'classification':'RESEARCH_ONLY','investment_use_allowed':False,'official_PIT_certified':False,
        'language_contract':CONTRACT,'benchmark_return_basis':'price_index_without_distributions',
        'scope':'Historical observed universe; fixed trading costs, before distribution taxes; no cash-dividend total return or investment PIT approval'}
    raw['universe']['markets']=sorted(raw['universe']['markets'],key=lambda x:['KOSPI','KOSDAQ'].index(x))
    raw['rebalance']['months']=sorted(set(raw['rebalance']['months']))
    key={k:v for k,v in raw.items()if k not in {'strategy_id','title'}}
    raw['strategy_id']='research_'+hashlib.sha256(json.dumps(key,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:16]
    raw['title']='RESEARCH_ONLY · 확인된 연구 조건'
    return StrategySpec.from_dict(raw)
def translate(text,*,research=None,execution_contract=None,base=None):
    if not isinstance(text,str)or not text.strip()or len(text)>16000:raise ValueError('비어 있거나 너무 긴 전략 요청입니다')
    defaults=[]
    if base is not None:
        raw=StrategySpec.from_dict(base).to_dict();changes=[]
        for part in re.split(r'[;\n]+',text.strip()):
            part=part.strip().rstrip('.');m=re.fullmatch(r'(수수료|매도세|스프레드|슬리피지)(?:를|을)?\s*(\d+(?:\.\d+)?)\s*bp(?:로)?\s*(?:변경|바꿔(?:줘)?)',part)
            if m:
                field={'수수료':'commission_bps','매도세':'sell_tax_bps','스프레드':'spread_bps','슬리피지':'slippage_bps'}[m[1]]
                if 'fixed_cost'not in raw['cost_scenarios']:raise ValueError('fixed_cost 시나리오가 없는 전략입니다')
                raw['cost_scenarios']['fixed_cost'][field]=float(m[2]);changes.append(field);continue
            m=re.fullmatch(r'종목\s*수(?:를)?\s*(\d+)\s*(?:개|종목)(?:로)?\s*(?:변경|바꿔(?:줘)?)',part)
            if m:
                if raw['portfolio']['selection']!='top_n':raise ValueError('10분위의 종목 수는 직접 변경할 수 없습니다')
                raw['portfolio']['number_of_positions']=int(m[1]);changes.append('number_of_positions');continue
            m=re.fullmatch(r'기간(?:을)?\s*(\d{4})년(?:으로|로)?\s*(?:변경|바꿔(?:줘)?)',part)
            if m:
                y=m[1];raw['period']=dict(start=y+'-01-01',end=y+'-12-31',book_start=y+'-01-01',book_end=y+'-12-31',as_of_date=y+'-12-31');changes.append('period');continue
            raise ValueError('지원하지 않거나 모호한 수정 요청: '+part)
        if len(changes)!=len(set(changes)):raise ValueError('같은 조건을 중복 변경했습니다')
        spec=canonical(raw)
        return response(spec,defaults,changes)
    if ':'in text:
        spec=canonical(korean_spec(text,research=research,execution_contract=execution_contract).to_dict())
        return response(spec,defaults,[])
    remaining=text.strip()
    def take(pattern,required=True):
        nonlocal remaining
        matches=list(re.finditer(pattern,remaining,re.I))
        if len(matches)>1:raise ValueError('중복/모호한 조건: '+pattern)
        if not matches:
            if required:raise ValueError('필요한 조건이 없거나 모호합니다: '+pattern)
            return None
        m=matches[0];remaining=remaining[:m.start()]+' '+remaining[m.end():];return m
    d=take(r'(\d{4}-\d{2}-\d{2})\s*(?:~|부터)\s*(\d{4}-\d{2}-\d{2})(?:까지)?',False)
    if d:dates=d[1]+'~'+d[2]
    else:
        d=take(r'(\d{4})년\s*(?:부터|~)\s*(\d{4})년까지',False)
        if d:dates=d[1]+'-01-01~'+d[2]+'-12-31'
        else:
            d=take(r'(\d{4})년');dates=d[1]+'-01-01~'+d[1]+'-12-31'
    market=take(r'((?:코스피\s*(?:·|와|및|,|\+)\s*코스닥)|코스피|코스닥)에서')[1]
    markets='코스피·코스닥'if'코스피'in market and'코스닥'in market else market
    f=take(r'시가총액\s*(>=|<=|이상|이하)?\s*(\d+(?:\.\d+)?)\s*(조원|억원|원)\s*(이상|이하)?',False)
    filter_clause=''
    if f:
        op=f[1]or f[4]
        if not op or(f[1]and f[4]and f[1]!=f[4]):raise ValueError('시가총액 필터의 비교 방향을 명시하세요')
        op={'>=':'>=','<=':'<=','이상':'>=','이하':'<='}[op];filter_clause=';필터:시가총액'+op+f[2]+f[3]
    else:defaults.append('추가 유니버스 필터 없음; 당시 KOSPI/KOSDAQ 관측과 신호일 거래 가능성 계약 유지')
    mom=take(r'(3-1|6-1|12-1|12-0)\s*모멘텀(?:이)?\s*(높은|낮은)\s*순(?:으로)?',False)
    if mom:factor=mom[1]+' 모멘텀 '+mom[2]
    else:
        size=take(r'(?:시가총액|시총)(?:이)?\s*(낮은|작은|높은|큰)\s*순(?:으로)?')
        factor='시가총액 '+('낮은'if size[1]in{'낮은','작은'}else'높은')
    dec=take(r'10\s*분위',False)
    if dec:portfolio='10분위'
    else:portfolio='상위'+take(r'상위\s*(\d+)\s*(?:종목|개)')[1]+'개'
    if not take(r'동일\s*비중|균등\s*비중|같은\s*비중',False):defaults.append('선정 종목 동일비중')
    monthly=take(r'매월\s*말(?:마다)?|월말마다',False)
    if monthly:months=','.join(map(str,range(1,13)))
    else:
        quarter=take(r'분기\s*말(?:마다)?',False)
        if quarter:months='3,6,9,12'
        else:months=take(r'(?:매년\s*)?(\d+(?:\s*,\s*\d+)*)\s*월말(?:마다)?')[1].replace(' ','')
    lag=take(r'(\d+)\s*거래일\s*(?:뒤|후)\s*종가(?:로)?\s*(?:체결)?',False)
    lag=lag[1]if lag else'1'
    if not lag or lag=='0':raise ValueError('당일 종가 체결은 지원하지 않습니다')
    if not re.search(r'거래일',text):defaults.append('신호 다음 1거래일 종가 체결')
    costs={}
    for label,default in DEFAULT_COSTS.items():
        c=take(label+r'\s*(\d+(?:\.\d+)?)\s*bp',False);costs[label]=c[1]if c else default
        if not c:defaults.append(label+' '+default+'bp 고정 연구 가정; 실제 역사 세율/계좌 인증 아님')
    bm=take(r'벤치마크\s*(코스피200|코스닥150|코스피|코스닥)',False)
    benchmark=bm[1]if bm else'코스피'
    if not bm:defaults.append('벤치마크 KOSPI 가격지수; 현금배당 미포함')
    residue=re.sub(r'[\s,.·]+','',remaining)
    for word in sorted(['리밸런싱','백테스트해줘','백테스트','재조정','구성하고','투자하고','종목을','종목','선정하고','뽑아서','보유하고','리밸런싱해줘','으로','로','에서','하고','을','를'],key=len,reverse=True):
        residue=residue.replace(word,'')
    if residue:raise ValueError('미해석/미지원 구절이 남아 실행할 수 없습니다: '+residue)
    labeled='기간:'+dates+';시장:'+markets+filter_clause+';팩터:'+factor+';포트폴리오:'+portfolio+';리밸런싱:'+months+'월말;체결:'+lag+'거래일뒤종가;비용:'+','.join(k+v+'bp'for k,v in costs.items())+';벤치마크:'+benchmark
    spec=canonical(korean_spec(labeled,research=research,execution_contract=execution_contract).to_dict())
    return response(spec,defaults,[])
def response(spec,defaults,changes):
    raw=spec.to_dict()
    return dict(status='interpreted_requires_confirmation',language=SUPPORT,language_contract=CONTRACT,
        strategy=raw,strategy_fingerprint=spec.fingerprint(),confirmation_digest=confirmation_digest(raw),
        defaults_applied=defaults,changed_conditions=changes,investment_approved=False,
        limitations=['RESEARCH_ONLY','Net is after configured trading costs, before distribution taxes','Cash dividends and full historical corporate-action completeness not certified','DART source-linked observations do not bypass investment PIT gate'])
def confirmation_digest(raw):
    return hashlib.sha256((CONTRACT+'\n'+StrategySpec.from_dict(raw).fingerprint()+'\nrequested_complete_period_CURRENT').encode()).hexdigest()
