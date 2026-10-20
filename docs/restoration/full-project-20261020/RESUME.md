# 전체 프로젝트 복원과 개발 재개

최소 복원 기준은 `Horororong/quant-marcap-runner`, `fix/financial-accuracy-20261014`, **b5aaa7f01c17f77527c07baa36f27415de9aba31**다. 원격 연구 브랜치의 마지막 커밋도 이 값이다. 운영 main은 **55e8efcb02e1021f57448131df5e411eafca2ab9**로 별도 진척했다. 양쪽은 main51/연구84개 커밋이 갈라져 있다. 인수인계의 옛 main-v5 기록은 현재 main의 v9.2 유한 수집/HOLD 설정을 대체하지 않는다.

기존 두 작업 트리는 미커밋 변경이 없었다. 원본과 최소 복원본은 수정하지 않는다. 새 개발 브랜치는 `restore/full-project-20261020`, 작업공간은 `/workspace/quant-project-full-20261020/code`다. 원본 전체 비 Git 파일은 데이터751개 union과 `../preserved-main/` 운영 snapshot으로 보존한다. 연구와 운영의 차이를 임의 병합하지 않았다. 정확한 원본749개와 연구 커밋의 추가2개는 각각 manifest로 식별한다.

현재 Python은 기존 검증 kit의 `/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python`을 그대로 사용한다. 설치/verify/기존 v1 백업 전송을 반복하지 않는다. 다른 호스트에서 runtime이 없다면 기존 v1 백업의 공식 kit bootstrap 절차로 새 runtime을 복원하고 `--runtime`에 그 위치를 지정한다.

```bash
cd /workspace/quant-project-full-20261020/code
export QUANT_PINNED_RUNTIME=/workspace/quant-restore-b5aaa7f/runtime
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/restored_workspace.py layout
"$QUANT_PINNED_RUNTIME/.venv/bin/python" -I scripts/restored_workspace.py web --store /workspace/quant-project-full-20261020/user-store --port 8765
```

연구 실행은 같은 launcher의 `run --strategy config/strategies/research_size_top1_2024.json --report-periods config/reports/research_2024.json --output-dir <새폴더>`를 사용한다. 이미 완료한 검증 폴더에 다시 실행하지 않는다.

원본 데이터749개/1,372,088,236bytes를 모두 SHA256 확인하여 복사했다. 최소 환경과6일치/743누락/0불일치였다. 추가2개 2026공식 확장은 고정 커밋 Git blob에서 복구했으며 신규 원자료 수집이 아니다. 전체751개/1,373,060,882bytes의 manifest가 복원 근거다. 가격1995~2026 32개 Parquet schema와1995/2000/2010/2021/2026 공통 엔진 로딩을 확인했다. 파일 일치·로딩은 금융 정확성/PIT 인증이 아니다.

최초 UI 검증은 최소 sparse 복원에서 `web/` 누락으로 실패했다. 웹 자산을 고정 커밋에서 복원한 뒤 전체 실제 브라우저 E2E가 통과했다. 기존 코드 기능을 다시 구현하지 않았다. 원본 문서에 있는 과거 절대경로는 역사적 증거로 보존한다. 새 launcher는 현재 repo 루트를 계산하고 전용 runtime을 명시적으로 선택하며, 누락된 웹 자산을 실행 전 드러낸다.

CURRENT는 실제 파일 `scripts/quant_backtest_template_CURRENT.py` v2-18과 `quant_backtest_postprocess.py`를 의미한다. 공통 PROJECT 실행 v2-16-exec-10과 성과 계산 소유자를 혼동하지 않는다. OS는 현재 Linux x86_64이며 기존 PC OS·시스템 이미지·일시 캐시는 확인할 수 없다. UTC 기록/KST 관찰 예산/XKRX 거래일 계약은 유지한다. 비밀값은 환경 secret에서만 공급한다.

운영 fast 스케줄은 `bounded-canary`의 if가 schedule 이벤트를 허용하지 않아 skipped(0 steps)였다. 실제 유한 수집은 `backfill-dart-legacy-2000-2014.yml`이다. READY_NEXT/첫 독립 검토/100x3 총300/KST하루1회/공유 concurrency/원문 선저장 체크포인트를 검사한다. 신규 후보 자동게시 HOLD와 backtest_eligible=false, 투자PIT0/6은 유지한다. 읽기 전용 선정과 소규모 중복·체크포인트 시험을 통과한 뒤 기존 예산 안에서1회 dispatch했다. 최종 실제 실행 결과는 별도 단계 증거와 최종 보고를 확인한다.

원래 PC 전체 백업 SHA256 `725991950af01331042c74b05b1a52bcb3fc9ebb1502839a2a6fd5eac9844f4d`의 파일은 미확보다. 과거 `/workspace/financial-repair`, `/workspace/research-stage*`, 이전 세션 store 등의 비 Git 자료는 manifest의 누락 경로와 기존 artifact 출처를 참조한다. 누락을 빈 폴더나 새 baseline으로 대체하지 않는다.

모든 실행은 RESEARCH_ONLY. 금융 품질/PIT·기업행위·1bp held-return·기간/모집단 차단을 유지한다. 원래 장기 다종목의 미완료를 이번 파일 복원으로 성공 처리하지 않는다. 새 외부 언어 모델은 연결하지 않았으며 현재 UI는 명시한 제한 한국어/JSON만 해석한다.
