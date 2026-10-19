# 재현

검증된 kit의 .venv/bin/python만 PY로 사용한다. 인터넷 pip 설치 없음.

```bash
"$PY" -I "$RUNTIME/scripts/sandbox_runtime.py" verify
"$PY" -I -m unittest discover -s tests -p 'test_financial*.py' -v
"$PY" -I scripts/financial_verified_subset.py --check
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-source-readiness-20261019 --check
```

실제 source 실행은 main 전용 Actions의 financial_limited_resume.py다. 로컬에서
키를 옮겨 실행하지 않는다. 최초 실행은 필수 CI 후 main merge marker
[financial-resume-first]로1회, 이후는 schedule/dispatch를 같은 일일·총량 gate로
검사한다. run attempt1만 허용하고 첫 실제 independent review 승인 전에는
다음 예약을 실행하지 않는다. freeze 규칙과 selection은 HTTP 이전 main commit.
모든 신규 후보는 미검토이며 독립 샘플 PASS를 전체 후보에 적용하지 않는다.

source/quality/run manifest, 원문pack SHA, 확인된 최종 main commit은
data/status/dart_legacy_limited_resume_v1.json 및 quality_v9/limited_resume_v1/runs/
아래의 source packs/manifest와 CI artifact에 남는다. collection completion과
financial publication completion은 별도다. 기존93개와 신규199개의 field key,
원문 bytes/hash/위치·단위·기간·scope는 publication_manifest.json에서 재현한다.


첫 관찰100는 이미 완료됐다. DART 수집을 다시 실행하지 않는다.

```bash
"$PY" -I scripts/financial_review_gate.py docs/audits/financial-limited-resume-20261019/first_observation --check
"$PY" -I scripts/financial_limited_review.py
```

first_observation의 review_plan/controls/source_manifest/field_details.csv는 고정
sample·기대 literal·위치·판정·기간·scope를 보존한다. raw_grid_review는 생산
파서 금액을 읽지 않고 원문만 표시한 증거다. freeze_controls.py.txt는 원문
통제 동결 절차의 보존본이며 생산 parser에 쓰이지 않는다. 첫 source artifact
12186145612(zip SHA00b1e7e1d996fa7b9452869356d4b42b86c7c8c583021059681440f6a722c7d2)는
완료 run39248507369에서만 읽고, CI financial_limited_artifact.py로 원문100과
실제 progress HTTP/retry·90/600 경계를 검증한다. 이 읽기는 새 DART 호출0이다.
--approve는 검토한 frozen 상태 WAIT_FIRST_REVIEW에서 별도 PR로만 수행한다.
운영 소급 변경/새 source 재수집이 아닌, 이미 보존한100의 source-only 승인이다.
