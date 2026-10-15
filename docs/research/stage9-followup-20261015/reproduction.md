# Stage 9 후속 재현 및 확인 범위

확인 시각: 2026-10-15 13:17:28 UTC.
원격 기준 a4aa49440d24a50030a44f60f18a6a687626672b,
로컬 기준 9b2cc02e91e5c592973553b0b23bcc269c094f0d,
동일 기준 트리 022c759de0f5ac8f46c619255315b6d8dd72c38f.
브랜치 fix/financial-accuracy-20261014 유지.

## 실제 원문 확인

승인된 웹 도구로 A/B 공식 URL을 열었다. 증거는 evidence.json의 A/B에 있다.
A: 표지 발행회사·분기·대상기간·제출일, VI > 3 > 바 주총 의사록 요약의 2020-03-27 부모 행.
B: 표지 발행회사·사업연도·제출일, 7 > 7-1 > 가 증자(감자)현황의 열 제목과 2020-03-27 행.
기존 파서 결과를 재사용하여 두 새 사실을 인증하지 않았다.
문서 위치는 장·절·표·날짜를 우선하며 웹 추출 행번호는 이 확인 시점의 보조 위치다.
원문 파일 전체나 HTTP 원본 SHA는 확보하지 않았고, authored evidence의 SHA와 혼동하지 않는다.

기존 Stage9 E03 배당안의 회사·주총 날짜·예정 주식 종류·수량을 대조했다.
주총 안건 승인 사실과 발행 기록을 서로 구분했다.
B의 발행일은 입고일이나 KRX 상장일로 변환하지 않는다.
C06만 기존 고정10 항목에서 U→P, I01 발행 사실은 분모 밖 별도 PASS다.
기존 Stage9 원본 CSV/보고서/status는 수정하지 않는다.

## 제한 조회 기록

공식 도메인 검색 두 묶음, 총 6개:
- kind.krx.co.kr: 셀트리온헬스케어 배당락 2019 기준가격
- law.krx.co.kr: 코스닥시장 업무규정 시행세칙 2019 제17조 기준가격
- kind.krx.co.kr: 셀트리온헬스케어 2020 7,116,148 상장일
- kind.krx.co.kr: 셀트리온헬스케어 2019-12-27 배당락
- law.krx.co.kr: 000113 20191127
- kind.krx.co.kr: 셀트리온헬스케어 추가상장 2020-04-24

검색 결과의 후대 규정, 타 발행회사 자료, 파생상품 자료는 해당 사건의 증거에서 제외했다.
새로 찾은 2021년 코스닥 법규 URL을 1회 열었으나 '(400) Timeout fetching'으로 실패했다.
이는 취득 도구 오류이며 원천 서버 HTTP 상태는 미관측, 프로세스 exit code는 해당 없음.
같은 법규 사이트의 Stage9 실패를 함께 고려하여 즉시 수집 종료; 재시도/추가 수집 코드/오류 후 원문 요청 없음.
추가 필요 자료는 remaining_gaps.csv의 세 그룹뿐이며 공개 검색 실패를 원자료 부재로 단정하지 않는다.

## 실제 로컬 명령

저장소 /workspace/quant-marcap-runner에서:

```bash
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
git branch --show-current
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify > /workspace/research-stage9-followup-20261015/runtime-verify.json
```

원래 Python /workspace/financial-repair/runtime/.venv/bin/python 사용.
manifest /workspace/financial-repair/runtime/kit_manifest.json.
verify exit0/status ok. 고정 kit ID:
26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd.

hashlib 및 git show로 기존 Stage9 manifest 전 항목과 주요 보호 통제 파일의 바이트 동일성을 확인했다.
이는 금융 재검증/재실행이 아니다.
새 폴더 파일별 bytes/SHA는 artifact_manifest.json에 있다 (manifest 자체는 제외).
공식 원본 응답의 SHA로 표현하면 안 된다.

## CI 및 재개 조건

기존 financial-accuracy-revalidation.yml 및 test-strategy-dsl.yml의 push paths와 repair-branch guard를 읽었다.
해당 신규 docs/research 폴더는 두 워크플로의 push 필터와 일치하지 않는다.
워크플로 수정/수동 dispatch/인터넷 설치/원문 재수집 없음.
엔진/입력 변경이 없으므로 회귀 테스트나 10분위를 다시 실행하지 않았다.

추가 인증에 필요한 것은 새 수집기가 아니라 remaining_gaps.csv의 공식 파일이다.
입고와 상장, 현물 기준가와 보유자 경제적 수익률을 각각 확인할 수 있을 때에만 후속 모델 검토로 진행한다.
현재 운영 PIT 승인 및 실행 차단 판정을 유지한다.
