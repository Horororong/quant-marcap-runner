# 재개 명령

기존 원본/최소 복원/kit/회귀 출력/v1~v8 백업을 보존한다. 최신 기능 작업공간은 `/workspace/quant-parser-repair-20261021/code`, 브랜치 `feat/saved-comparisons-20261021`이며 게시된 ba26에서 분기했다. 최종 feature SHA는 증분 백업 FINAL_STATUS.md 및 `git rev-parse HEAD`를 따른다.

```sh
cd /workspace/quant-parser-repair-20261021/code
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I \
  /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
```

로컬 웹은 새 영구 저장 폴더를 지정한다. 이번 검증 store를 읽으려면 `--store /workspace/quant-progress-20261021/saved-comparison-e2e-final/store`를 사용한다. 이 store에는 이전 실제 결과 두 개의 복사와 새 비교 record가 있으며 금융값 인증은 없다. 기존 store를 새 실행으로 덮어쓰지 않는다.

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/research_web.py \
  --store /workspace/quant-progress-20261021/saved-comparison-e2e-final/store --port 8765
```

주소 `http://127.0.0.1:8765`. localhost 소켓이 허용되는 실행 환경이 필요하다. 외부 공개/휴대폰 접속용 주소가 아니다. 인터넷 pip 설치나 새 의존성 설치 없이 기존 runtime/Chromium/Node로 검사했다.

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I - <<'PY'
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()))
suite=unittest.defaultTestLoader.loadTestsFromNames(['test_research_language','test_research_web','test_saved_research_comparisons'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

바뀐 새 기능에 재검증이 필요한 경우에만 새 output 경로로 다음을 실행한다. 기존 회귀/동일 코드 CI를 이유 없이 반복하지 않는다.

```sh
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/test_saved_comparisons_e2e.py \
  --source-store /workspace/quant-integration-20261021/browser-e2e-final/store \
  --source-proof /workspace/quant-integration-20261021/browser-e2e-final/browser/verification.json \
  --output /workspace/NEW_UNIQUE_COMPARISON_CHECK
```

새 코드 원격 CI에는 고정kit driver의 별도 workspace suite에서 위18시험을 실행하고 기존 실제 browser E2E 출력으로 저장 비교 E2E를 이어 실행하면 된다. 새 정확한 checkout SHA를 기록하고 pinned kit 외 설치를 금지한다. 현재 ba26의 parser CI를 새 기능 CI로 대신하지 않는다. 이 새 증분의 공개 게시/CI는 이번 ba26 한정 승인 범위 밖이므로 새 manifest에 대한 승인 후 진행한다.

수집은 REPORT.md의 live gate/명령을 따른다. 아직0HTTP이며 다음 예정 시각만으로 자동 재개됐다고 판단하지 않는다. 운영 parser9.2 유지, 연구9.3 배포는 별도 최소 변경/운영 승인 필요. 확인되지 않은 원문을 재수집하거나871운영값을880제안으로 바꾸지 않는다.
