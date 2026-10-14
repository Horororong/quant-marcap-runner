# 금융 정확성 결함 수정 및 독립 재검증 — 1차 수정

**판정: 부분 개선, 투자 백테스트 사용 불가. main 병합 및 2,000건 전체 재처리 금지 상태를 유지한다.**
기존40+고정 신규20=60개 원본 ZIP의 SHA256/CRC/XML member SHA를 확인하고 실제 process_filing을 실행했다.
원문 숫자는 생산 파서를 import하지 않는 별도 XML DOM/수동 표제·단위·기간 통제로 대조했다.
HTTP만 원본 fixture로 교체했으며 재무 파싱·선택·계산을 mock하지 않았다.

## 실제 결과

|분모와 의미|PASS|FAIL|UNVERIFIED|
|---|---:|---:|---:|
|기존565 대상 수정 전 종합|0|565|0|
|기존565 대상 수정 후 구조·금액|430|0|135|
|60건의 실제 출력 재무값700개|518|0|182|
|신규20의 사전 고정 핵심값64개|59|5|0|
|60개 표본 종합|0|5|55|
|8항목 적용 체크434개|81|5|348|

행들이 겹치므로 합산 금지. 일치율은430/565=76.1062%, 518/700=74%, 59/64=92.1875%.
**값을 제거·보류한 것을 정확한 값 복구로 계산하지 않았다.** 기존135개는 UNVERIFIED다.
기존 감사 금액 항목 PASS였던123개도 다시 인증하지 못했다.
과거 정상값의 현재 기간 사용 차단과 추출/증거 공백이 섞여 있어 기존 정상 사례의 회귀 오류가 없다고 선언하지 않는다.
518개의 PASS도 구조·금액에 한정되며 기업 매핑·공개시점 인증이 아니다.

신규64의 FAIL5는 알려진 당기 순이익의 추출 실패:
N10/N11: 손익 계정과 주당이익이 붙은 셀. CF 순이익 행에서 정확한 값을 독립 확인했다.
N12: 반(당)기순이익 별칭 미지원. N15/N16: 금액 뒤 연속 등호 밑줄 장식 미지원.
원문에 맞춘 임의 분할이나 표본별 규칙으로 PASS시키지 않았다.
기존 NO_METRICS10 및 신규4는 재무정보 존재를 확인했지만 경계를 확정해 추출하지 못했다.
현재 EXTRACTION_FAILED이며 진짜 금융 데이터 부재가 아니다.

## 기존40 항목 비교

|항목|수정 전 P/F/U|수정 후 P/F/U|
|---|---|---|
|기업명·종목·DART 코드|0/0/40|0/0/40|
|접수번호·보고서·기간 종합|0/40/0|0/0/40|
|금액: 기존 대상 보류 포함|9/21/10|13/0/27|
|단위: 실제 출력값|28/1/11|27/0/13|
|연결·별도: 실제 출력값|28/2/10|27/0/13|
|원공시·정정 전체 체인|0/3/37|0/0/40|
|NO_METRICS 오분류|0/10/0|10/0/0|
|미래정보 사용 여부|0/0/40|0/0/40|

종료일만 따로 보면60건의 원문 표지와 출력 종료일은 일치했다.
그러나 접수번호·보고서의 독립 실시간 인증은 확보하지 않아 항목2는 UNVERIFIED다.
항목3은 고정565의 보류도 포함한다. 4/5는 출력된 값의 판정으로, 보류된 값의 단위·범위를 PASS시킨 것이 아니다.
정정 전 선택 결함은 제거했지만 전체 정정 접수 체인이 없어 항목6은 UNVERIFIED다.
PIT/기업 매핑을 확인하지 못한60건 모두 backtest_eligible=False이고 normalized 입력에서 격리한다.

## 수정 파일과 원인

- scripts/legacy_native_financials.py: 표지/표제의 정확한 날짜, 현재 기수 헤더와 span, 3개월/누적 시작·종료일,
  CFS/OFS, 기업 전체 기본재무제표, 정정 본문을 함께 확인한다. 인접 날짜·단위 헤더만 상속한다.
  당기 대시/공란을 지나 전기 값으로 진행하지 않고 모순 후보·미확정 단위를 보류한다.
  Decimal 원 단위 정확 비교, 오차0. 이익(손실)의 양수를 유지하고 순손실 계정·괄호·△·(-) 음수를 보존한다.
- scripts/backfill_dart_legacy_2000_2014.py: 월까지만 주어진 보고서명은 달력 월말, 잘못된 명시 날짜는 NaT.
  원문 종료일을 index 추정 날짜로 덮어쓰지 않는다. source member/hash/기간/측정 근거를 보존한다.
  데이터 존재·추출 실패를 NO_METRICS와 구분하고 미확정 결과를 normalized 대신 structural_review에 저장한다.
  review 완료도 SHA/행 수로 확인해 중복 요청을 피한다.
- scripts/legacy_financial_fields.py: 기업 전체 순매출액 별칭 및 (-) 음수 토큰 공통 처리.
  생산 코드에 접수번호/표본별 분기 없음.
- tests/test_financial_accuracy_repair.py: 안전 경계18개.
  기존 파서 테스트를 명시적인 구조 근거, Decimal 문자열, 새 버전 계약으로 갱신했다.
- docs/audits/financial-repair-20261014/: 독립 통제/선정/원본 SHA/실행/세부CSV/보고서.
- .github/workflows/financial-accuracy-revalidation.yml: 원래 kit의 dedicated Python으로 동일60건 재현.
  인터넷pip를 실행하는 기존 DSL CI는 이 수정 브랜치에서만 제외했다.
  main 및 다른 브랜치 동작은 변경하지 않았다. 전체pytest 통과를 뜻하지 않는다.

근본 원인: 보고서명 월을 day1로 변환해 원문 종료일을 덮어쓴 코드,
첫 유한 숫자를 찾다가 당기 대시 뒤 전기까지 넘어간 선택,
이익(손실) 대안 표기를 순손실과 혼동한 부호 처리,
표 숫자까지 포함한 이전2600자 문맥/약한 우선순위가 부문·합병·정정전·과거 CFS를 현재 주재무제표로 선택한 문제.
미확정 단위와 전체 셀 경계 소실도 같은 부재 분류에 들어갔다.

## 지정 사례 실행

results/regressions.json의25 assertion 통과.
S01 종료일2007-06-30; S05/S09/S38 양수 순이익;
S24 정정후 PPE4,776,788,895와 잘못된 유동부채7,205,734,7733 보류;
S39 정정후 매출1,721,725,595; S40 매출5,361,076,009원/순손실-6,848,255,870원;
S11 전기 배당금 차단, S17/S36 과거 CFS 및 전기 차입금 차단;
S21 전체 매출350,592,000,000원, S37 전체 누적 순매출171,879,491,773원.
이 통과는 지정된 결함의 안전 처리 증거이며 모든 필드 복구나 PIT 인증은 아니다.

## 감사 프로그램 오류 검토

Stage1 number()는 쉼표를 제거한 뒤 검증해 malformed7,205,734,7733도 받아들일 수 있다.
원 Stage1은 S24 별도 통제로 이미 UNVERIFIED였으므로 원 판정을 덮어쓰지 않았다.
수정 감사는 쉼표 그룹부터 검증하며 원 보고서·CSV·통제를 별도 baseline으로 보존한다.
새 감사 초안에서 COVER를 직접 자식으로만 조회한 오류, 띄어 쓴 이익/손실 계정 판별 오류,
CF 누적을 혼합 헤더로 오인한 오류도 수정했다.
초안 P0/F518/U182→P502/F16/U182→최종P518/F0/U182는 감사 프로그램 수정이다.
생산 코드의 개선 수치로 계산하지 않았다. 원 감사와 수정 감사의 측정 구간 기준 차이도 명시한다.

## 선정·보존·버전

기존40/seed20261014는 원 감사 branch audit/financial-accuracy-20261014,
commit042faa8f31c13ea889e6e6b459ee1e85751a97a2 그대로다.
원2000 배치 run38498706052, 수집 checkout c3d12f3313a95f25162a1503be624f3b0617f8c0.
신규20 seed2026101402: SHA256 순위로 full10/partial6/NO_METRICS4, 기존40의 접수번호 및 기업 제외.
원본·값을 열기 전에 목록 고정, 신규 파서 실행 전에 핵심64 원문 값 통제 고정.
나머지 출력 필드 통제는 미완료라 UNVERIFIED가 남는다.
신규20은 이 배치의2007 중간보고서 중심이며 다른 연도/서식까지 일반화하지 않는다.
2000의 metadata만 선정에 읽었고 전체 파서 재처리나 DART 재수집은 하지 않았다.

원40 packet artifact11871753367, 신규20 packet11883255192; 모든 원본 SHA/CRC/member-SHA 검증.
로컬 보존본 /workspace/financial-repair/preserved-originals60.zip (5,521,417bytes),
SHA a7dfb0cc7764e21b9cc660f33d47a811e54785823d1beefadb93a54a486123c7.
CI도 동일60 원본/선정을 별도90일 artifact로 보존한다. 영구 저장이 아니므로 만료 전 장기 보관 필요.
원 공시 파일·기존 audit branch·운영 데이터는 변경하지 않았다.

전용 Python /workspace/financial-repair/runtime/.venv/bin/python,
kit_id26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd,
원 kit source822c435f4b6148c2832e12370a6ccb324a9e875f.
verify exit0/status ok; 원래 bootstrap/bundled wheels만 사용, 인터넷pip/시스템Python 계산 없음.
안전18+기존 source품질6 테스트, 지정25회귀, 실제60 collector replay, 독립 DOM 비교, DSL 계약 검사 exit0.
results/evidence에 실제 stdout/stderr/verify, results에 판정과 세부CSV.
CI 성공은 재현/지정 회귀 성공이며 남은 FAIL5/UNVERIFIED가 정확성 통과한 것이 아니다.
kit에 pytest/requests/bs4가 없어 전체pytest와 online 수집 통합 경로는 미검증이다.

## 미해결 및 전체 재처리 전 우선순위3

1. 높음: 순이익5 실패, 합쳐진 셀14건, 기존135 보류, 출력182 미검증 해결.
   계정·EPS·밑줄을 일반 문법으로 처리하고, XBRL/HTML에서 경계를 증명하기 전에는 붙은 금액을 나누지 않는다.
2. 치명적: 역사적 기업/종목 매핑, 접수 API·전체 정정 체인, 공개시각·사용 가능일 인증.
   기존/신규 모두 증거가 없어서 투자 입력 사용 불가.
3. 높음: 기존 정상 금액123 미재인증, 전체 기존pytest/수집·재개·저장 계약 검증.
   원래 고정 의존성을 포함한 검증 환경이 필요하며 인터넷pip나 임의 패키지 버전으로 통과시키지 않는다.
   review/coverage 마이그레이션과 소규모 고정 배치 검증 후 전체2000/merge는 별도 승인 대상.

작업 branch fix/financial-accuracy-20261014, 준비commit441df5e30548767c77df36369d3c8e62d81a0619.
신규20 준비CI38541918907 성공. 최종 SHA/run은 이 보고서를 포함한 커밋과 CI에서 확인한다.
게시 전 main3e9c42a1d3e028874eefb84c958a65d23083d088, 원 audit042faa8... 그대로 확인.
main 병합과 전체2000 재처리는 하지 않았다.

## 표본 목록

|ID|상태|출력 필드 수|원문 필드 P/F/U|종합|
|---|---|---:|---|---|
|S01|PARSED_4F|17|17/0/0|UNVERIFIED|
|S02|PARSED_4F|18|18/0/0|UNVERIFIED|
|S03|PARSED_4F|18|18/0/0|UNVERIFIED|
|S04|PARSED_4F|19|19/0/0|UNVERIFIED|
|S05|PARSED_4F|16|16/0/0|UNVERIFIED|
|S06|PARSED_4F|10|10/0/0|UNVERIFIED|
|S07|PARSED_4F|18|18/0/0|UNVERIFIED|
|S08|PARSED_4F|18|18/0/0|UNVERIFIED|
|S09|PARSED_4F|12|12/0/0|UNVERIFIED|
|S10|PARSED_4F|17|17/0/0|UNVERIFIED|
|S11|PARSED_4F|15|15/0/0|UNVERIFIED|
|S12|PARSED_4F|13|13/0/0|UNVERIFIED|
|S13|PARSED_4F|16|16/0/0|UNVERIFIED|
|S14|PARSED_4F|17|17/0/0|UNVERIFIED|
|S15|PARSED_4F|18|18/0/0|UNVERIFIED|
|S16|PARSED_PARTIAL|8|8/0/0|UNVERIFIED|
|S17|PARSED_PARTIAL|14|14/0/0|UNVERIFIED|
|S18|PARSED_4F|11|11/0/0|UNVERIFIED|
|S19|PARSED_4F|16|16/0/0|UNVERIFIED|
|S20|PARSED_PARTIAL|15|15/0/0|UNVERIFIED|
|S21|PARSED_PARTIAL|14|14/0/0|UNVERIFIED|
|S22|PARSED_PARTIAL|16|16/0/0|UNVERIFIED|
|S23|PARSED_PARTIAL|15|15/0/0|UNVERIFIED|
|S24|PARSED_PARTIAL|14|14/0/0|UNVERIFIED|
|S25|PARSED_PARTIAL|14|13/0/1|UNVERIFIED|
|S26|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S27|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S28|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S29|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S30|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S31|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S32|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S33|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S34|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S35|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|S36|PARSED_4F|19|19/0/0|UNVERIFIED|
|S37|PARSED_PARTIAL|17|17/0/0|UNVERIFIED|
|S38|PARSED_4F|17|17/0/0|UNVERIFIED|
|S39|PARSED_4F|16|15/0/1|UNVERIFIED|
|S40|PARSED_4F|14|13/0/1|UNVERIFIED|
|N01|PARSED_4F|15|4/0/11|UNVERIFIED|
|N02|PARSED_4F|18|4/0/14|UNVERIFIED|
|N03|PARSED_4F|18|4/0/14|UNVERIFIED|
|N04|PARSED_4F|18|4/0/14|UNVERIFIED|
|N05|PARSED_4F|17|4/0/13|UNVERIFIED|
|N06|PARSED_4F|19|4/0/15|UNVERIFIED|
|N07|PARSED_4F|15|4/0/11|UNVERIFIED|
|N08|PARSED_4F|11|4/0/7|UNVERIFIED|
|N09|PARSED_4F|17|4/0/13|UNVERIFIED|
|N10|PARSED_PARTIAL|17|3/0/14|FAIL|
|N11|PARSED_PARTIAL|16|3/0/13|FAIL|
|N12|PARSED_PARTIAL|13|3/0/10|FAIL|
|N13|PARSED_4F|11|4/0/7|UNVERIFIED|
|N14|PARSED_4F|15|4/0/11|UNVERIFIED|
|N15|PARSED_PARTIAL|9|3/0/6|FAIL|
|N16|PARSED_PARTIAL|9|3/0/6|FAIL|
|N17|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|N18|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|N19|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
|N20|EXTRACTION_FAILED|0|0/0/0|UNVERIFIED|
