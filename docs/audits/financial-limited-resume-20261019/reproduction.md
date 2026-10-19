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
