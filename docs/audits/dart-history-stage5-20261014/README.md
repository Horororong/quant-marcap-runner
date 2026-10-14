# 5단계: 공식 OpenDART 공시 이력 확보 경로

기준 d6d3d5e16e3e6180c24253a94c18e93950c6d4e0, 같은 fix/financial-accuracy-20261014.
현재 단계의 목적은20건의 공식 API 응답 확보이며 완전한PIT/역사적KRX 인증이 아니다.
실제 호출 결과는 exact commit의 Actions run/artifact로 확인한다. 접근 실패시2기업 실증에서 중단하며 감사통과 보고서를 만들지 않는다.

기존 main-only 백필 workflow는 인터넷pip/운영저장/2000문서 처리 때문에 실행하지 않는다.
동일한 repository secrets.DART_API_KEY를 기존 financial-accuracy-revalidation workflow의 단일 step env에만 연결한다.
키 값, URL, 예외문자열/응답message를 로그에 남기지 않는다. 공식응답이 키를 echo하면 파일 저장도 거부한다.
GET secret metadata는 connector가 지원하지 않아HTTP400; 이것으로 secret 부재를 단정하지 않는다.
실제 step에 전달되지 않으면 AUTH_ENV_MISSING, DART가 거절하면HTTP 상태/DART숫자코드만 기록한다.

## 제한된 단일 실증

- 기존 Stage4 selection20을 그대로 사용: 먼저S01/S02 두 기업의 전체조회 페이지 및 대상접수번호를 확인한다.
  두 기업이 모두 성공한 경우 같은 실행에서 나머지18개 기업으로 확대한다.
- list.json, corp_code, last_reprt_at=N, 정기공시A, page_count100, 오름차순.
- 시작일은 해당 원문 회계기간/접수년 중 이른 년도의1월1일. 종료일은 실행 당시한국날짜.
  2007년에 한정하지 않으며 S40은2005년부터 조회한다.
- 최대80요청/기업별5페이지/600초/응답2MiB/합계32MiB. 페이지·총건수·실제건수 일치와 법인/접수번호/날짜 검증.
  시간제한·HTTP/DART 오류·rate limit·누락 대상·출처 불일치가 생기면 중단한다. 재시도0회.
- 관련 제목 후보는 보존하되 제목 일치로 정정 체인을 확정하지 않는다.
  정기공시A 밖의 관계, 조회 시작 전/종료 후, 실제 후속정정 연결은 미확인 범위다.
- 첫 push의 commit 메시지에 `[stage5-dart-proof]`가 있을 때만 실제 조회한다. run_attempt1만 허용한다.
  일상적인 문서push/CI재실행으로 API 호출이 반복되지 않는다. 재수집은 checkpoint/error/기존artifact 확인 후 별도 명시적 재개다.
- 모든 결과는 RUNNER_TEMP/stage5에 저장, Actions artifact로 보존한다. 운영 data 경로/Git main에는 쓰지 않는다.

## 새로 확인 가능한 항목과 계속 보류할 항목

성공한 공식 응답의 exact 접수번호/법인코드/접수일은 원래 index와 대조한다.
접수일은 작성일 및 공개시각과 구별한다. list API에는 정확한 intraday 공개시각이나 명시적인 전버전접수번호가 없다.
완전한 체인·시간단위PIT·역사적KRX연결은UNVERIFIED 유지한다.
일봉 보수적 규칙은 검증된접수일보다 엄격히 이후의 공식거래일이어야 한다.
공식session 증거가 없으므로 exchange_calendars/평일계산만으로 이용가능일을 만들지 않는다.

## 실행과 보존

기존 검증 kit의 sandbox_runtime.py verify 통과 후 전용.venv Python만 사용한다. Python표준라이브러리 이외 신규의존성0, 인터넷pip0.
키 없이 로컬에서 실행해 실패한 파일을 성공 증거로 만들지 않는다. 로컬에서는 synthetic transport 보안/오류/페이지테스트만 수행한다.
기존60 원문·Stage4 결과·금융518/64는 수정하지 않는다. 성공한 workflow는 기존 독립검증/보호검사를 그대로 수행한다.
원본 응답raw/SHA/조회범위/page/수신시각은 response_manifest, 전체진행/에러는 run_state, 20건판정은 stage5_details.csv.
정상 응답을 실제 다운로드하여hash/원본payload/법인/접수번호를 확인한 뒤 확보 건수를 보고한다.
실패면 응답/code/완료기업/미실행기업/정확한 필요한조치만 보고하고, 같은 실패를 반복하지 않는다.
