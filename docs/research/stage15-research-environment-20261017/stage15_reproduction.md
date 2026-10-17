# Stage15 재현

브랜치 `fix/financial-accuracy-20261014`. 시작 원격
`eea1887309911a607b3bd20b002da66b3e48f0ec`. 새 소스 원격
`3dadfd7b25281b0707e54f5dd7fbd873e2bf41fe`, 보강
`a5b2559ffb6b3eb7c710fce976145051931ac488`, 모델 체크포인트
`cef04745b61dbb6e0392b77771db18bafed1bb66`.
최종 실행 버전은 실제 CI `execution.json`/`summary.json`의 github_sha를 확인한다.
미래 자기 커밋 SHA를 문서에 임의 기입하지 않는다.

## 환경과 원본

로컬 전용 Python `/workspace/financial-repair/runtime/.venv/bin/python`.
원래 `kit_manifest.json` kit_id
`26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`.
CPython3.12.14, pandas3.0.6/numpy2.4.6/pyarrow25.0.1 고정.
검증 결과는 results/runtime_verify.json. 인터넷 pip/임의 버전 변경은 하지 않는다.
CI는 기존 restore_kit_only와 원래 묶음 wheel bootstrap 후 verify를 실행한다.

```bash
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I docs/research/stage15-research-environment-20261017/preserve.py --output /tmp/new-preservation --originals /workspace/financial-repair/preserved-originals60.zip
"$PY" -I docs/research/stage15-research-environment-20261017/verify_evidence.py
```

`preservation_manifest.json`은730개 불변 데이터/기존 감사와9개 명시적 코드 변경을
구분한다. `evidence_manifest.json`은 새 원문27개를 고정한다. 원시2019·2020
parquet, 운영 레지스트리, 518/64 결과와 원문60건은 바꾸지 않는다.

## 단위·회귀·실제 연구

```bash
"$PY" -I docs/research/stage13-stock-dividend-integration-20261017/validate.py --output /tmp/new-original-regression
"$PY" -I docs/research/stage15-research-environment-20261017/validate_environment.py --check --output /tmp/new-stage15
node scripts/verify_research_dashboard.cjs /tmp/new-stage15/original/report/report_CURRENT.html /tmp/new-stage15-browser
```

첫 명령은 원래19명령 및 실제 DART E2E를 skip/timeout 확장 없이 실행한다.
두 번째는 추가10명령, 인벤토리·전체패널 준비도, CT2019 실제가격87일 기능시험,
원래2년10분위·두 가정 시나리오·모멘텀2020·시총2024·한국어 원래전략을 실행한다.
각 실행의 raw 가격/수량/권리/현금 독립 감사, 선정·체결 불변과 한국어 결과
동일성도 필수다. `--check`는 로컬 `numeric_manifest.json`의15개 숫자 산출물
bytes/SHA256과 일치해야 한다. 절대경로·실행시각이 있는 HTML/manifest 전체를
바이트 동일하다고 주장하지 않는다. HTML은 동일 CURRENT payload·수치 및 실제
상호작용으로 검증한다. 로컬 sandbox 브라우저 장애는 별도 기록했고 CI의 기존
Chrome을 사용하며 npm/pip 설치나 우회는 하지 않는다.

`/tmp/new-stage15/*/report/report_CURRENT.html`을 오프라인 브라우저로 열 수 있다.
기준자산10000·KOSPI 가격지수·기간·분위·Gross/Net 선택과 세 차트를 확인한다.
`artifacts/`는 선정·비용·가격·권리·현금 감사, `*_independent/`는 독립 일별장부다.
개별 사용 명령과 제한 문법은 `docs/RESEARCH_WORKBENCH.md` 참조.

## 소스 재다운로드 금지

`source_ci.json`의39030154599/39030327589는 성공한 수집 이력이다.
22요청/재시도0, 원본 artifact digest와 보존된 b64/HTML SHA를 확인한다.
CI source jobs는 완료된 SHA/attempt1에만 묶여 있으므로 최종 `[stage15]`에서는
실행하지 않는다. 최종 회귀·원문60개 복구는 보존 artifact 읽기이며 DART 호출이나
금융 전체 재처리가 아니다. 비밀키는 출력·저장·복사하지 않는다.

## 판정 범위

관측 원가 대비 시장수익률4개는 원래1bp 검사. 경제적 권리는 명시적 모델을
적용한 연구 검증이다. 합성 단위시험, 실제가격 장부 일치, 실제 계좌 인증 및
역사적 투자 PIT 인증은 서로 다르다. RESEARCH_ONLY와 투자 불가를 유지한다.
2020 말 이후의 승인·상장 자료 없이 장기 권리를 계속 이어가지 않으며,
지원하지 않는 사실·모델·벤치마크·기술적 lookback은 gap으로 반환한다.
