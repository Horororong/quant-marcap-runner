# 재개 — RESEARCH_ONLY

최신 보고는 이 폴더 REPORT.md와 `/workspace/quant-source-audit-next-20261023/FINAL_STATUS.md`다.
v12는 draft421514386에서 원격4assets/ZIP SHA·CRC·41payload 검증 완료다. 다시 전송하지 않는다.
이전 백업·전체감사·130/UI/동일CI도 새 변경 영향 없으면 반복하지 않는다.

## 실제 다음 수집

체크포인트2063완료,다음20100331002066. 기존 승인 finite41-20261023의 고정41순서,
21+20문서/추가최대2실행/합계82HTTP/각600초/재시도포함/하루1회/10월25일KST23:59:59만료.
오늘10/23KST기회는 실제39863731314로 사용했으므로 같은 날 gate/dispatch 반복하지 않는다.
다음10/24KST창에서 실제main/state/sourcehash/인증/동시실행/모든gate를 확인하고 허용되면
이미 승인된21문서 실행을 보낸다. 실제오류면중단/원인/상태보존, 같은실패요청 반복없음.

```bash
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=21 -f supplemental_approval=finite41-20261023
```

위 명령은 이 세션에서 미실행이다. 실제 정상 종료·원문/후보/HTTP/중복/체크포인트 증거가
확인된 뒤 다음 허용일에 cap20을 사용한다. 같은 예산을 다시 묻지 않는다.
자동으로 supplemental입력을 제공하는 예약은 설정하지 않았다. 기존 cron존재와 구분한다.

## 데이터 검토 재개 위치

새20회사 FY2009 OFS4행80판정은 완료, 문서전체 검토는 미완료다. 해당20의 나머지232개
후보는 evidence/new20-review/NEW20_CORE_SOURCE_REVIEW.json의 documents[].unreviewed_candidate_indices에 있다.
첫후속은20100331001761의 남은11개다. 첫100 총1283개미검토,기존914=891PASS+23UV는불변.
합계2277연구후보=971PASS+23reviewedUV+1283unreviewed, 별도사조canary4는포함하지않는다.

이름7사례는 identity-final/IDENTITY_AT_SIGNALS.json에서 UNVERIFIED만 이어간다.
새 근거 없이 재판정하지 않는다. company-header만 보면 SK/ADP의 역사명이 낡아 있으므로
본문 자기 명칭/날짜/약칭과 원문SHA·공식snapshot을 바인딩한다. 일반 음역/유사도 규칙 금지.
33개의 mapping PASS는 날짜별 component증거이며 fullPIT/연속상장/공개version 인증이 아니다.

에스비엠20100331001822는 SBM_ZERO_ROOT_CAUSE.json의 main table70 경계부터 수리한다.
9.3은 그 문서0건이므로 같은 재파싱을 반복하지 않는다. 정확한 reference paragraph가
실제 note-entry와 다른 근거 및 실패회귀를 먼저 만든 뒤 parser/승인hash migration을 한다.
첨부 cover 종료일을 main에서 무단 상속하거나 날짜/당기/단위 보호를 풀지 않는다.

## 변경된 코드의 관련 검증·재현만

원문 재다운로드는 불필요하다. evidence/FIXED_EXISTING_SOURCE_LOCATIONS.json의 public589
고정 Git blob과 기존 pack5개가 출처다. kit는 기존26e4ec02e569 고정Python만 사용한다.
새 workdir을 지정하며 이미 완료한 동일 상태 검증을 이유 없이 반복하지 않는다.

```bash
cd /workspace/quant-parser-repair-20261021/code
PY=/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python
"$PY" -I /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
"$PY" -I -m unittest discover -s scripts -p test_historical_source_identity.py -v
"$PY" -I -m unittest discover -s scripts -p test_reviewed_source_extensions.py -v
"$PY" -I docs/research/source-core-batch3-20261023/tools/unpack_first100_preserved.py --root . --workdir /tmp/quant-core-NEW-UNIQUE
"$PY" -I docs/research/source-core-batch3-20261023/tools/review_new20_core.py --root . --workdir /tmp/quant-core-NEW-UNIQUE
"$PY" -I scripts/apply_reviewed_financial_batch.py --root . --extension-only --review-extension /tmp/quant-core-NEW-UNIQUE/new20-review/NEW20_CORE_SOURCE_REVIEW.json --output /tmp/quant-core-NEW-UNIQUE/provider-new80
"$PY" -I docs/research/source-core-batch3-20261023/tools/join_new20_identity.py --root . --workdir /tmp/quant-core-NEW-UNIQUE
"$PY" -I scripts/check_source_core_increment.py --audit-root /tmp/quant-core-NEW-UNIQUE
```

준비한 고정kit source_core driver는 /workspace/quant-source-audit-next-20261023/fixed-kit-source-core-driver.yml에 있다.
기존 공개 승인은589까지이므로 새 코드와 driver를 임의로 게시하지 않는다. 필요한 추가
공개 범위는 새 전송manifest로 한 번에 정리한다. 거절된 기존CI색인 게시를 우회 재시도하지 않는다.
