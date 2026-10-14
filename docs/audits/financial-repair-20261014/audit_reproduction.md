# 재현 절차 및 복구 기록

운영 데이터 수정 없이 기존 dedicated Python으로 실행한다.

~~~bash
PYTHON=/workspace/financial-repair/runtime/.venv/bin/python
$PYTHON -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
$PYTHON -I tests/test_financial_accuracy_repair.py
$PYTHON -I docs/audits/financial-repair-20261014/replay60.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --runtime /workspace/financial-repair/runtime --output /workspace/financial-repair/replay60
$PYTHON -I docs/audits/financial-repair-20261014/revalidate.py --original40 /workspace/financial-repair/evidence/review --holdout20 /workspace/financial-repair/heldout20/review --replay /workspace/financial-repair/replay60 --output docs/audits/financial-repair-20261014/results
$PYTHON -I docs/audits/financial-repair-20261014/assert_regressions.py --replay /workspace/financial-repair/replay60 --output docs/audits/financial-repair-20261014/results/regressions.json
$PYTHON -I -c 'import sys,runpy; sys.path.insert(0,"scripts"); sys.path.insert(0,"."); runpy.run_path("scripts/test_legacy_document_quality.py",run_name="__main__")'
$PYTHON -I -c 'import sys,runpy; sys.path.insert(0,"scripts"); sys.argv=["scripts/export_strategy_dsl_contract.py","--check"]; runpy.run_path(sys.argv[0],run_name="__main__")'
~~~

replay60.py는 sys.executable 경로/kit_manifest ID를 확인하고 verify를 직접 통과해야 금융 파싱한다.
kit에 requests가 없어 HTTP를 실패시키는 stub을 주입하고 fetch_document가 원본ZIP을 반환하게 한다.
파싱/선택/재무 계산/pandas/저장 함수는 대체하지 않는다. 임시cwd에서 import, normalized/state는 쓰지 않는다.
독립 revalidate.py는 생산 파서를 import하지 않고 원본 XML DOM cell 및 수동 통제를 사용한다.

baseline-controls/details/summary는 원 audit SHA042faa8... 복사본으로 원 판정 보존.
holdout_controls64 금액은 신규 파서 실행 전에 고정했다.
선정과 모든 source SHA/member-SHA는 original40/holdout20 selection/source-manifest.json에서 확인.
원40 packet SHA44b9ba097cc8c724be3b6025a4964b8be223f364d5ddf6204487497e101736fa (artifact11871753367).
신규20 packet SHA4fdb23600a2ce6e3cde106ff93382f74aa92da90fb9a040e8bf02f77b7dd2b23 (artifact11883255192).
원 kitZIP SHA f76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784.
전체 kit package versions/ID/source revision은 results/evidence/runtime-verify.json.

CI restore_inputs.py/restore_holdout.py는 정확한 archive와 kit을 받고,
원 bootstrap_quant.py가 bundled wheels로 원 kit Python을 만든다.
Actions setup/system Python은 download/SHA/ZIP/bootstrap transport만 수행.
금융 검증은 dedicated verify 통과 후만 실행한다. 인터넷pip/버전 변경 없음.
CI의 GITHUB_SHA/run ID와 artifact는 최종 코드 버전 증거다.

오류와 복구:
- shell git fetch: proxy port8080 접근 실패. 원인 수정 없이 재시도하지 않고 GitHub connector로 전환.
- 추가 network 권한을 동반한 fetch/curl은 사용자 중단:5484초/1742초 aborted.
  완료/다운로드 증거와 종료코드 없음. 다시 실행하지 않았다.
- 패치 context 실패: 변경 위치의 순서 불일치. 부분 변경 없음 확인 후 순서를 수정.
- 조회 cwd 누락/잘못된 comprehension: os error2/SyntaxError(exit1), cwd·문법을 수정.
- API wrapper: structuredContent 없는 응답을 해석해 '"undefined" is not valid JSON'.
  branch slash encoding endpoint 대신 git/ref/heads를 조회해 실제 ref를 확인.
- DSL 최초 -I: ModuleNotFoundError execution_contract.
  원 kit에 source scripts 경로를 명시 등록해 재실행, exit0/PASS.
  최초 결합 shell 전체exit0은 뒤 tail 명령의 코드라 성공으로 보고하지 않음.
- 새 감사 초안 오류3개는 보고서에서 생산 수정과 별도 기록.
- 보고서 작성 JS template의 Markdown backtick SyntaxError: 호출 전 오류, 파일 변경 없음.
  명령 문법을 수정해 실제 파일/manifest 생성 확인.
- 최종21+6 테스트/회귀25/실제60/독립대조/계약검사 exit0.
  명령 실행 완료와 금융 판정의 FAIL5/UNVERIFIED는 별개다.

보존 및 정확한 재개:
- 완료된40/20 선정·원본 수집을 반복하지 않는다.
- /workspace/financial-repair/preserved-originals60.zip에 original40/holdout20 입력을 보존했다.
  SHA a7dfb0cc7764e21b9cc660f33d47a811e54785823d1beefadb93a54a486123c7.
- artifact 만료 시 이 ZIP 또는 CI preserved-originals60을 먼저 복구하고 위 입력 경로만 해당 폴더로 지정.
  SHA가 달라지면 중단; 다른 데이터/기간/계산법으로 교체 금지.
- report/validation_summary/CSV에서 미완료 대상을 읽고 일반 수정 후 동일 고정 표본부터 재검증.
  main merge/2000 재처리 없음.
- 전체pytest/online 검증의 현재 blocker는 원 kit에 필요한 패키지가 없는 점이다.
  인터넷pip/임의 버전/시스템Python 우회 금지.

CSV 분모: FIELD700/BASELINE_TARGET565/HOLDOUT_TARGET64/CHECK434는 겹치므로 합산하지 않는다.
기존 보류 UNVERIFIED, 신규 알려진 금액 누락 FAIL. CHECK2는 기간이 고쳐져도 live receipt 인증 없어서 UNVERIFIED.
공개시각/역사 mapping/전체 correction chain 부족: 투자 사용 가능0건.

게시 추가 복구: CSV CRLF 보존 실패는 Path.read_text의 줄바꿈 정규화 때문이었다. read_bytes().decode(utf-8)로 원래 바이트를 유지했다. 기존 validate-legacy-parser job도 이 branch에서 제외하고 이전 자동 run을 취소하도록 했다. 최종 결과의 수치/원본/계산 방법은 바꾸지 않았다.

추가 실제 오류: 기존 자동 CI38547275390은 pip 설치 후 resume 테스트3개 실패(exit1). 원 kit 기반 검증으로 인정하지 않는다. fixture REVIEW_DIR 미격리와 review/normalized 새 계약의 경로 충돌을 수정했다. 해당 경계3개를 기존 kit unittest로 실제 재현/검증해 총21개 통과. 원 pytest 전체는 여전히 미검증. 취소 race는 이미 끝난 skipped run에 대한 API 오류였으며 cancel job 제거와 branch guard로 이후 잘못된 설치/재시도를 막았다. 원문은 results/evidence의2개 failure log.
