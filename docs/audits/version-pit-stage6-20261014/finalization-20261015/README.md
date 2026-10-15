# Stage 6 최종화 후속 검증

기존 commit `859bc1236423acc8824460d2e621e123ddf464c5`, ZIP, 원본 공시, 기존 금융 결과 및 루트의 Stage 6 보고서/CSV/JSON은 보존한다. 이 디렉터리의 결과가 아래 보수적 판정 수정의 후속 결과다. 기존 증거를 새 증거처럼 바꾸지 않았다.

## 수정과 증거 범위

- `verify_preserved60.py`: RestoreGap은 상태 UNVERIFIED와 원래 오류/HTTP 상태를 보존하면서 exit 2를 반환한다. 실제 SHA/내용 불일치는 FAIL/exit 1, 확인된 성공은 PASS/exit 0이다. 무조건 재시도하지 않는다.
- `audit_versions.py`: 최초제출일 참조의 법인·보고서·회계기간 시작/종료가 모두 일치해야 원공시 참조를 인증한다. 현재 원문 12개의 사실 및 명시적 원공시 참조 4건 인증/2건 후보는 변하지 않았다.
- 최초제출일 참조는 직전 정정본을 명시하는 증거가 아니다. 기존 직전 버전 CERTIFIED 2건을 CANDIDATE로 낮춰 6건 모두 후보로 유지한다.
- 원공시와 정정본 두 개를 확보했다는 사실만으로 전체 이력의 완전성이 증명되지 않는다. N12의 full_chain_verdict를 CERTIFIED에서 UNVERIFIED로 낮춘다. 전체 6건의 완전한 체인은 모두 UNVERIFIED다.
- 원공시 자체의 신원 확인은 정정본의 원공시 참조 인증과 다르다. 원공시 5건에 잘못 부여됐던 version_root_relationship PASS를 UNVERIFIED로 낮춘다. document_identity PASS는 유지한다.
- S39 원문 `2007년 05년 15일`은 수정하지 않는다. 정확한 공개시각, 공식 2007 거래일, 유효기간을 가진 역사적 종목 연결은 여전히 미인증이다.

## 실행한 로컬 검증

원래 kit `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`의 전용 Python과 `sandbox_runtime.py verify`를 사용했다. 인터넷 pip 및 의존성 변경은 없다.

- 기존 154개 + 신규 12개, 총 166개 테스트 PASS. 개별 명령/종료코드/실제 로그 해시는 `evidence/test_status.json`에 있다.
- 원래 CLI를 별도 임시 디렉터리에 원문 그대로 두고 키가 없는 환경에서 UNVERIFIED/exit 0 결함을 재현했다. 수정된 실제 CLI는 UNVERIFIED/exit 2이며 네트워크를 보내지 않는다.
- 실제 보존 원문 60개 ZIP/member SHA·CRC, replay 60개 SHA, 금융 결과 8개 bytes/hash를 확인했다. 보호값 518/518 및 핵심 64/64 PASS. 금융 원문 재수집/재파싱/대량 재처리는 하지 않았다.
- 공식 API 응답 22개는 기존 파일로 재확인했고 새 API 요청은 0이다.
- 기존 57개 변경 파일과 ZIP/patch/manifest SHA는 수정 전에 모두 확인했다. 패치 적용의 기존 tree 동일성 증거를 재사용했다.
- 증거 범위 수정 후 감사 결과: 108항목 PASS 33 / FAIL 1 / UNVERIFIED 74. 이전 결과는 38 / 1 / 69였다. 신호 경계 36개와 보조 달력 결과는 이전과 바이트 동일하다. 투자 PIT 인증은 계속 0/6이다.

결과 바이트 비교 기준은 `results/`의 다섯 파일이다. 기존 루트 결과는 이전 판정의 보존본이다. `evidence/before-after.json`에 전후 수치와 해시, `evidence/local-preservation.json`에 보호 검증 결과가 있다. 외부 원격 아티팩트 전송의 성공 여부는 로컬 파일 무결성과 별도다.

## CI 및 재현

기존 workflow의 `[stage6-evidence]` job만 사용한다. DART 수집 marker와 KRX 조사 marker는 사용하지 않는다. Stage6 결과의 기대 경로를 이 디렉터리의 `results/`로 변경하고 신규 12개 회귀 테스트를 추가했다. 기존 154개 테스트 경로는 유지한다. 아티팩트 복원 실패가 발생하면 이제 job이 실패한다. CI 성공만으로 투자 인증을 부여하지 않는다.

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/version-pit-stage6-20261014/test_finalization.py
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/version-pit-stage6-20261014/test_stage6.py
/workspace/financial-repair/runtime/.venv/bin/python -I docs/audits/version-pit-stage6-20261014/audit_versions.py --output /tmp/stage6-finalization-review
```

출력 디렉터리는 기존 결과와 분리한다. 같은 고정 kit에서 `results/` 다섯 파일과 대조한다. 원격 게시/최종 CI 상태는 실제 새 commit/run을 확인한 후 별도의 게시 결과 기록으로 남긴다. 과거 수집 성공 CI를 최종 검증 CI로 간주하지 않는다.

## 실행 장애와 복구 기록

- 최초 로컬 결함 재현용 임시 파일은 HOME.parents[2]에 필요한 디렉터리 깊이를 확보하지 않아 진단 파일이 생성되지 않았고 외부 검증 스크립트가 FileNotFoundError/exit 1로 중단했다. 원본 코드나 데이터를 바꾸지 않고 임시 경로의 깊이를 수정한 뒤 최초제출일/금융 계산과 무관한 CLI 종료코드 결함을 실제로 재현했다. 전체 테스트/보존 검증은 그 이후 한 번 실행했다.
- 읽기 전용 경로 확인에서 추측한 `stage6/financial/validation_summary.json`은 없었다. 실제 기존 경로 `stage6/financial-results/validation_summary.json`을 확인해 보존 검증에 사용했다.
- 이번 native git ls-remote는 exit 128: `Failed to connect to proxy port 8080 after 0 ms: Could not connect to server`. 직접 연결·proxy 해제·반복 권한 요청은 하지 않았다. 공식 GitHub connector의 원격 ref 조회는 c209a8f9를 반환했다. 게시 성공과는 구분한다.

공식 거래일, 역사적 종목 연결, S39/S19 및 N14의 미확정 관계에 필요한 독립 공식 증거 확보가 다음 연구 우선순위다. main 병합, 전체 2,000건 처리와 운영 데이터 수정은 포함하지 않는다.
