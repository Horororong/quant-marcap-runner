# 실행과 다음 재개 위치

계산은고정kit verify후전용Python -I만사용한다. 인터넷pip설치금지. 실제UI기능의원격검증대상은29b이고새annualquery는별도새로컬커밋이다. 정확한head/증분은 /workspace/quant-pit-deploy-20261021/FINAL_STATUS.md를따른다.

```sh
cd /workspace/quant-parser-repair-20261021/code
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/research_web.py --store /workspace/quant-pit-period-20261021/period-comparison-followup-fixed-order/store --port 8765
```

새로컬annual조회검토는완료했으므로같은상태에서는반복하지않는다. 변경이있을때만새output경로에서재검증한다.

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/verify_reviewed_annual_income.py --output /workspace/NEW_UNIQUE_ANNUAL_SOURCE_CHECK
```

현재2문서시험미실행/checkpoint20100331002054완료/다음02062DEFERRED·02063PENDING. 다음10/22KST00:00이후실제main/state/config/sourcehash/firstreview/인증/동시실행/저장경로를다시확인하고허용될때만기존workflow를1회dispatch한다. 아래명령은자동예약이아니며현재차단중실행하지않았다.

```sh
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=2
```

HTTP는progress.jsonl의http_start로모든재시도를포함해집계한다. 원문ZIPsha/CRC·후보추출·중복·checkpoint·정상종료를별도로검증해조건을충족할때만이미승인된후속41예산을사용한다. 추가예산을재승인요청하지않는다. 단현재운영3run보호계약은추가2run을지원하지않고이번main병합미승인이므로,supplemental최소운영배포문제는별도다. 원래장부리셋/버전·hash승인완화/금융게시/PIT우회는금지한다. 세부조건·41orderSHA는evidence/APPROVED_FINITE_COLLECTION_SCOPE.json을따른다. 미래실행은아직설정하지않았다.

자료연결우선순위:사조Q3접수20091116000562의기존원문byte/기간·범위·버전/공개·종목연결찾기→검증되면기존provider분기차분에명시적연결. legacyv5후보31행이있다는것만으로원문재수집/자동반영하지않는다. 그접수는현재43HTTP승인범위밖이다. 전체1495모집단은그와별도로막힌다.
