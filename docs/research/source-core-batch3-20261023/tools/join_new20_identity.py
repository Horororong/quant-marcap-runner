import base64,gzip,hashlib,io,json,re,sys,zipfile
from collections import Counter
from pathlib import Path
import argparse
a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--workdir',type=Path,required=True);args=a.parse_args();R=args.root;P=args.workdir;sys.path.insert(0,str(R/'scripts'));from historical_source_identity import assess_identity,source_binding
from financial_record_readiness import assess,binding
from reviewed_financial_batch_bridge import normalise_reviewed
H=R/'docs/research/source-readiness-20261019';packed=base64.b64decode((H/'official-market-proof.json.gz.b64').read_bytes());assert hashlib.sha256(packed).hexdigest()=='52edb555b2fb880699255770b5af9ab3dde6ef4ddb3b252b5586d3c24bea8f23';files={k:base64.b64decode(v)for k,v in json.loads(gzip.decompress(packed))['files'].items()};scope=json.loads((P/'FROZEN_NEW_REVIEW_SCOPE.json').read_text())['documents'];source_review=json.loads((P/'new20-review/NEW20_CORE_SOURCE_REVIEW.json').read_text());rows=source_review['rows'];decisions=[];aliases=[]
def quote_match(plain,pattern):
 matches=list(re.finditer(pattern,plain));assert matches,pattern;return matches[0].group()
for d in scope:
 receipt=d['receipt'];review=next(r for r in rows if r['receipt']==receipt);part=(P/'first100-chunks'/d['result']).parents[1];archive=next((part/'native').glob(receipt+'-*.zip'))
 with zipfile.ZipFile(archive)as z:raw=z.read(receipt+'.xml')
 for enc in ['utf-8','cp949','euc-kr']:
  try:t=raw.decode(enc);break
  except UnicodeError:continue
 plain=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',t));identity=dict(corp_code=review['corp_code'],rcept_no=receipt,stock_code=d['stock_hint'],original_issuer=review['original_issuer'],source_member_sha256=review['source_member_sha256'],source_archive_sha256=review['source_archive_sha256']);alias=None
 if receipt=='20100331001780':
  quote=quote_match(plain,r'당사의 명칭은 "씨앤에이치주식회사".{0,100}CNH CO\.,LTD\..{0,30}표기합니다\.')
  alias=dict(official_alias='CNH',alias_literal='CNH CO.,LTD.',source_quote=quote,**{'from':'2010-04-01','through':'2010-04-30'},meaning='Own English legal name explicitly reported as CNH CO.,LTD.; legal-form suffix only, no counterparty substring or transliteration inference')
 elif receipt=='20100331001888':
  quote=quote_match(plain,r'당사의 명칭은 에스케이커뮤니케이션즈 주식회사.{0,250}SK컴즈라고 표기합니다\.')
  history=quote_match(plain,r'당사는 1996년9월19일.{0,500}사명을 SK커뮤니케이션즈주식회사로 변경하였습니다\.')
  alias=dict(official_alias='SK컴즈',alias_literal='SK컴즈',source_quote=quote,**{'from':'2010-04-01','through':'2010-04-30'},meaning='Original XML company header is stale 지식발전소; actual issuer self-name, explicit short name and dated corporate history link the same source CIK',supporting_history_quote=history)
 elif receipt=='20100331001840':
  quote=quote_match(plain,r'2010년 3월 26일 정기주주총회.{0,250}변경되었습니다\.')
  alias=dict(official_alias='LIG에이디피',alias_literal='LIG에이디피주식회사',source_quote=quote,**{'from':'2010-03-26','through':'2010-04-30'},meaning='Explicit2010-03-26 own-name change, legal suffix removed; old KRX4/1 에이디피 alias remains unproved')
 if alias:
  alias.update(verdict='PASS',binding=source_binding(identity),scope='CURRENT_ISSUER_SELF_IDENTIFICATION',evidence=['Independent reading of original company overview self-name/alias/history; member hash and exact quote retained; no current-code map inference']);aliases.append(dict(receipt=receipt,**alias))
 for day in ['20100401','20100430']:
  day_iso=day[:4]+'-'+day[4:6]+'-'+day[6:];allmarket=[];filenames=[f'stk_bydd_trd_{day}.json',f'ksq_bydd_trd_{day}.json']
  for name in filenames:allmarket.extend(json.loads(files[name])['OutBlock_1'])
  evidence=dict(date=day_iso,source=filenames,sha256={n:hashlib.sha256(files[n]).hexdigest()for n in filenames},source_pack_sha256=hashlib.sha256(packed).hexdigest())
  verdict=assess_identity(identity,raw,allmarket,evidence,day_iso,[alias]if alias else[]);decisions.append(dict(receipt=receipt,stock_code=d['stock_hint'],corp_code=d['corp'],**verdict))
# Bind the partial identity evidence into the existing readiness owner for every
# newly reviewed field, without inventing publication or version attestations.
records=json.loads((P/'provider-new80/BOUND_SOURCE_REVIEW_RECORDS.json').read_text());field_checks=[]
for signal in ['2010-04-01','2010-04-30']:
 for item in records:
  prepared=normalise_reviewed(item['row'],item['review'],item['filing_index_date']);row=prepared['row'];att=dict(binding=binding(row),financial_accuracy=dict(verdict='PASS',evidence=item['review']['evidence']));ident=next(d for d in decisions if d['receipt']==row['rcept_no']and d['signal_date']==signal)
  if ident['verdict']=='PASS':att['historical_security_mapping']=ident['historical_security_mapping']
  check=assess(row,signal,att,dict(verdict='UNVERIFIED',evidence=[]));field_checks.append(check);assert not check['research_record_ready']
out=P/'identity-final';out.mkdir();(out/'REVIEWED_SELF_NAME_ALIASES.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2)+'\n');(out/'IDENTITY_AT_SIGNALS.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n');(out/'FIELD_READINESS_AT_SIGNALS.json').write_text(json.dumps(field_checks,ensure_ascii=False,indent=2)+'\n');summary=dict(classification='RESEARCH_ONLY',issuer_signal_checks=len(decisions),PASS=sum(x['verdict']=='PASS'for x in decisions),UNVERIFIED=sum(x['verdict']=='UNVERIFIED'for x in decisions),by_signal={signal:dict(Counter(d['verdict']for d in decisions if d['signal_date']==signal))for signal in ['2010-04-01','2010-04-30']},reviewed_alias_rules=len(aliases),mapping_PASS_field_signal_pairs=sum(c['dimensions']['historical_security_mapping']=='PASS'for c in field_checks),new_complete_PIT_records=0,new_live_engine_ready_records=0,remaining_blockers=dict(Counter(dim for c in field_checks for dim in c['blockers'])),interval_between_signals_certified=False,source_HTTP=0)
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
