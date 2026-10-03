# 원문 품질 점검 결과

사전 고정한 위험 표본 6기업/12본문을 사용했다. 원문 45항목: 당기 별도 30항목 + 전기 연결 연간 15항목. 원문 응답 bytes/원래 viewer SHA, 정확한 TR/cell/line 위치와 literal 값을 독립적으로 확인했다. 수집 금융 parser는 호출하지 않았다. 원문 자산·부채·자본·매출·순손익과 접수일(title)을 직접 대조했다.

## 발견한 자료 문제

- 최신 main의 6 receipt는 모두 legacy-v5-single-amount / opendart-document-v1 / NO_METRICS / metric_rows=0이다. 당기 30개 원문 숫자는 존재하지만 저장 상태가 usable 값을 제공하지 않는다. 기존 OpenDART XML의 잘림/깨진 문자와 viewer 본문 간 차이가 관련 원인이다. 수집 상태의 NO_METRICS는 공시 원문 숫자 부재의 증거가 아니다.
- 이번 감사표의 stored_value 빈 값은 0이 아니다. 최신 main receipt state의 선언을 대조했으며, 최신 normalized 대용량 gzip의 전 행 물리적 대조는 수행하지 못했다. 로컬 normalized는 이전 snapshot이므로 최신 main의 numeric 저장값을 대신 인증하지 않았다. independently_matched_stored_amounts=0이다.
- 비츠로테크 당기 BS/IS는 원문 단위가 빈 칸이다(5항목). 원 단위라고 추정하지 않았다.
- 대구백화점 BS 총계 3항목은 괄호 표시의 회계적 부호 문맥 추가 확인이 필요하다. 괄호를 기계적으로 음수로 확정하거나 저장 값을 교정하지 않았다.
- 피어리스 순손실은 amount가 양의 숫자로 표시되고 account label이 당기순손실이다. 독립 기대값을 음수로 기록했다. 대우중공업의 (-), 피어리스의 △ 표시도 원문대로 보존했다.
- 연결 상세 제표에는 전기 연간 1999-01-01~12-31, 1999-04-01~2000-03-31이 포함된다. 이 15개 원문 값은 당기 Q3로 대체/비교하지 않는다. 당기 OCF는 확인된 CF heading이 전기 연간인 경우가 있어 아직 인증하지 않는다.
- source title의 접수일 6개가 목록 rcept_dt와 일치한다. 전체 정정 관계·공개 시각·과거 결산기 변경은 미검증이다. legacy의 strategy_usable_date는 비워 두었고 PIT 인증은 False다. 접수번호만으로 이용 가능 날짜를 만들지 않았다.

## 차단됨/미완료

직접 DART/외부 공시 접근은 Work proxy 연결 실패로 차단됨. 현대 공시·정정공시·더 넓은 연도/업종의 독립 표본 확대는 원문 확보 후 진행해야 한다. 이번 위험 표본은 전체 데이터 대표성/인증을 충족하지 않는다. 30건의 당기 원문 점검은 완료했으나 30건의 저장 수치 일치 검증을 통과한 것이 아니다.

현대 금융 provider는 full_history만 사용하며 legacy는 공개 실행 capability에 포함되지 않는다. 위험한 viewer fallback·period/sign/unit 변경을 즉시 production에 넣지 않았다. 필요한 후속은 보존한 원문 기대값으로 완결성/인코딩 및 당기 기간·열·scope·단위 guard를 먼저 검증하는 것이다.

## 소프트웨어 검증

verify_primary.py는 45 literal cell과 본문/viewer SHA를 대조했다. 잘못 기록한 금액, 훼손된 원문, 바뀐 receipt state를 거부하는 3개 failure boundary가 통과했다. 이것은 감사 도구의 소프트웨어 검증이며 실제 투자 성과나 전체 데이터 품질 인증이 아니다.

첫 실행은 capture 상태명 DOWNLOADED를 잘못 가정해 실패했다. 실제 저장 계약 HTTP_RESPONSE_CAPTURED/HTTP 200으로 바로잡고 SHA 검사를 유지한 재실행이 통과했다. 수집 코드·원자료·고정 manifest·registry는 변경하지 않았다.
