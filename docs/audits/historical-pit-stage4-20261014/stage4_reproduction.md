# 4단계 재현·복구

원격 기준8a1a46730e01cce1767bf549bebf5c6543512835, 같은fix/financial-accuracy-20261014.
로컬 기준1fc5fb5adcd9eacaee57b7fd11eee968ea375e35와 원격8a1a의 tree는
90ae5ef245d8897881d6772f9def056a74e0fb55로 같다. Git 연결 도구/로컬의 ancestry 차이를 SHA 동일이라고 표현하지 않는다.
금융3단계 코드와 데이터는 보존한다. kit_manifest SHA는 stage4_evidence_manifest.json에 있다.

## 실제 로컬 명령

```bash
STAGE4_PYTHON=/workspace/financial-repair/runtime/.venv/bin/python
$STAGE4_PYTHON -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
$STAGE4_PYTHON -I tests/test_financial_accuracy_repair.py
$STAGE4_PYTHON -I tests/test_financial_extraction_stage3.py
$STAGE4_PYTHON -I docs/audits/historical-pit-stage4-20261014/test_stage4_audit.py
$STAGE4_PYTHON -I docs/audits/historical-pit-stage4-20261014/run_stage4.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --replay /workspace/financial-repair/stage3/after-replay60 --output docs/audits/historical-pit-stage4-20261014/results
$STAGE4_PYTHON -I docs/audits/historical-pit-stage4-20261014/review_ci_triggers.py --output docs/audits/historical-pit-stage4-20261014/ci_trigger_review.json
```

금융 계산은 기존 verify를 통과한 전용 Python만 사용한다.
run_stage4는 금융 추출 파서를 사용하여 인증값을 생성하지 않는다.
독립 XML 판독 후 별도로 native gate 함수만 실제 기존 row에서 차단 여부를 테스트한다.
오프라인 재실행은 현재 인터넷 가용성을 다시 인증하지 않는다. 공식 페이지의 재조회는 별도 근거 갱신이다.

## 입력·재현성

- 불변 선택/ZIP/member manifest: 원40와holdout20 review packet. 경로를 찾을 때 접수번호만의 임의 파일명을 만들지 말고 manifest artifact_member를 사용한다.
- 전용 runtime와 original kit는 이미 검증됐으며 재설치하지 않는다.
- 기존 baseline stage3 artifact11891266805:252633bytes,
  SHA256 2f459eba7bf4e3bbd91bad5f00d81a117515f357b71eccdb05b70fa0d91fb812,
  run38558616835, exact8a1a commit.60개 replay의 바이트가 로컬과 일치함을 확인했다.
- 원60 보존 artifact11891556581: SHA256985de2844cc3d0235690a2afcf6ec0303895e9ad81fb563aed0430d2826672af,
  만료2027-01-12. GitHub artifact 만료 전 접근 가능한 별도 보존이 필요하며 URL만 남긴 것을 영구 보존으로 간주하지 않는다.
- CI는 기존 restore_inputs.py/restore_holdout.py/restore_before.py와 원 bundled wheels를 재사용한다.
  백필·새60 선정·원문 재수집은 하지 않는다. 재실행 결과를 pinned preservation_controls 및4개 Stage4 결과와 대조한다.
- source_facts의 ELEMENT index는 lossless decode된 원문 DOM의 전역 pre-order 순번이다. COMPANY-NAME/@AREGCIK와 COVER 위치도 제공한다.
- 선언은utf-8이나 실제cp949인 원문이 있다. lossless round-trip 확인 후 bare ampersand만 XML 구조 판독에서 escape한다.
  보존 원문 ZIP/XML bytes는 수정하지 않는다. 회사명은 법인 표기·공백만 정리하며 alias/fuzzy merge하지 않는다.
- repository_leads는 원 data gzip SHA에 연결된 파이프라인 산출 단서다. 원본 공식 응답의 대체물이 아니다.

## 실패 원문·원인·복구

명령 실행과 결과 검증을 구분했다. 실패를 원인 수정 없이 재시도하지 않았다.

1. 읽기 rg에서 존재하지 않는 scripts/legacy_pit* glob, exit2. 실제 파일 목록에서 legacy_native_financials.py와 adapter를 찾았다.
2. 임의 receipt.zip 경로로 FileNotFoundError, exit1. manifest의 receipt-SHA.zip 이름으로 수정했다.
3. 원 XML의 bare ampersand로 ParseError line4 column87553, exit1. 원문 round-trip encoding 후 판독용 구조 escape를 적용했고 원본은 보존했다.
4. 보호 목록에 replay_summary/runtime-verify까지 넣어 count==60 AssertionError, exit1.
   보존60 표본 [SN][0-9]{2}.json을 정확히 지정했다. 초기 오류는 evidence에 보존했다.
5. S26에 금융row가 있다고 가정한 AssertionError: S26, exit1.
   row없는3개 시나리오를 UNVERIFIED로 바꿨다. 실제 row없는 경우 vacuous PASS를 허용하지 않는다.
6. 초기 감사 결과가 정정일을 P 요소에서만 찾아 TABLE/TD 날짜를 누락하고 N14 옛COVER 날짜를 선택한 문제를 직접 원문 대조로 발견했다.
   초기source_facts/summary를 evidence에 보존했다. TITLE 정정신고~첫 정정항목 사이의 확정 날짜만 선택하도록 감사 프로그램을 고쳤다.
   직접 확인한10개 정정일/9개 최초제출일/20개 발행명·코드 통제를 별도로 고정하고 모두 대조했다.
   이는 감사 도구 수정이며 금융 생산 값·원3단계 판정은 바꾸지 않았다.
7. Stage3 CI scanner가3개 매칭을 가정하여 실제 한 개만 매칭된 변경에 AssertionError, exit1.
   이후 HANDOFF를 추가하자 DSL workflow도 매칭됐다. 고정 개수 가정 대신 각 실제 매칭의 원kit/기존skip guard를 검증하도록 Stage4 scanner를 수정했다.
   고정kit workflow가 반드시 매칭돼야 하며 unreviewed workflow/unsupported shape는 여전히 중단한다.
8. DART 두 뷰어 접근 실패는 tool 응답의 접근불가 문자열만 존재, HTTP 상태/종료코드 미제공.
   같은 호스트18건 반복 요청 대신 모두근거 미확보를 기록했다. 공개일시를 접수번호에서 만들지 않았다.

## 정확한 재개 순서

1. 같은 branch/exact SHA, 현재 Actions, kit_manifest와 전용verify를 확인한다. 원본/518/64/60 replay SHA가 달라지면 중단한다.
2. stage4_evidence_manifest와 selection20을 확인하고 미확보 항목만 진행한다. 완료된 금융재파싱/원문수집/커밋을 반복하지 않는다.
3. 공식 DART/KRX 접근이 지원되는 환경/도구가 갖춰지면 같은20 receipt의 전체 버전 및 거래·증권 이력을 한정 수집한다.
   auth 값이나 secret을 보고서에 넣지 않는다. shell의 프록시/목적지 정책을 우회하지 않는다.
4. 실제 응답 bytes/공식 URL/접수번호/확인일시/hash/원·정정관계를 보존하고 공개일과 작성일을 분리한다.
5. 공식 calendar를 확인한 뒤 receipt/hash/법인/종목/버전/신호일에 대한 사용 가능성을 독립 판정한다.
   현재 closure PASS65를 실제availability PASS로 재사용하지 않는다.
6. 인증 근거가 없는 항목은 U로 유지한다. 같은20 우선 재인증 후 새 위험표본으로 일반성을 검증한다.
   main 병합/전체2000 재처리/미인증값의 투자 투입은 계속 금지다.
