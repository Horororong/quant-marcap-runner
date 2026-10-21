# 이번 작업의 실행·재개

작업공간 `/workspace/quant-parser-repair-20261021/code`, 별도연구브랜치 `feat/pit-analysis-period-20261021`. 기본전체복원/원본/최소복원/기존백업은 보존했다. 필수수정9365b9f51e052198ac50537e858ab1799b966763과 새기능/증거커밋을 구분한다. 새최종전체SHA는 인계와 증분 FINAL_STATUS.md를 따른다.

```sh
cd /workspace/quant-parser-repair-20261021/code
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I \
  /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/research_web.py \
  --store /workspace/quant-pit-period-20261021/period-comparison-followup-fixed-order/store --port 8765
```

이는localhost용이며 외부전화접속을 완료했다는 뜻이 아니다. loopback소켓을 허용한 환경에서 사용한다. 새 백테스트/분석은새출력경로만 생성하며 기준결과를 덮어쓰지 않는다. 기존NAV분석과새백테스트의구분은보고서와화면을 따른다. source자료/비용/버전은저장실행snapshot이 기준이다.

동일상태의완료검증을반복하지 않는다. 변경이생겨재검증할때만 새경로로 실행한다.

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/verify_source_pit_case.py \
  --output /workspace/NEW_UNIQUE_PIT_CHECK
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/test_research_periods_e2e.py \
  --source-store /workspace/quant-integration-20261021/browser-e2e-final/store \
  --source-proof /workspace/quant-integration-20261021/browser-e2e-final/browser/verification.json \
  --output /workspace/NEW_UNIQUE_PERIOD_E2E
```

새클라우드CI에서는동일고정kit을restore/bootstrap/verify하고현재공통browser E2E산출물을source-store/proof로사용하면된다. 별도제안driver의새suite는PIT원문연결,새기간browser,unit/checked-lifecycle를추가한다. 실제대상코드SHA와driverSHA를분리한다.7cCI39575278064SUCCESS는새추가커밋CI가아니다. source HTTP/금융게시/main병합없이실행한다. 인터넷pip/npm설치는없다.

현재source실행은KST하루1회내부정책에막혔다. 기존잔여1실행으로2062/2063 두문서를시험할때만live gate/state/hash/auth/concurrency를재확인한뒤다음기존workflow를사용한다. 지금실행하지않았고미래자동재개도설정하지않았다.

```sh
gh workflow run backfill-dart-legacy-2000-2014.yml \
  --repo Horororong/quant-marcap-runner --ref main \
  -f resume_parent_run=39504052321 -f batch_documents=2
```

실제요청수는document worker의progress.jsonl `http_start/http_received/http_retry`를구분해집계하고완료zip/후보/중복/정상종료/체크포인트와연결한다.2문서최대4HTTP/문서당재시도1회/90초/run600초/worker75초/admission종료여유15초다.0요청success를수집성공으로세지않는다.2문서후마지막실행슬롯이소진되면추가실행은새승인전금지한다. 추가41문서의조건부예산안은evidence/NEXT_FINITE_BACKFILL_BUDGET_PROPOSAL.json에있으며active설정이아니다. main parser9.2와연구9.3/금융HOLD/PIT0/6을유지한다.

필수복구의존성:원격Git의7c코드와그부모들,원래26e4ec02e569kit/의존성,기존751data출처,공식source-readiness증거pack. 새코드/새결과는새로컬증분에있으며원격미게시범위를그명세에서확인한다. 비교store는기존v9source snapshot과새증분을함께별도경로에놓아복구한다. 구버전상태CSV를새현행인증값으로합산하거나Git브랜치게시를ZIP업로드로세지않는다.
