# 재개 순서 — RESEARCH_ONLY

1. 환경설정의GH_BACKUP_TOKEN을유효한토큰으로교체해야v12배송을계속할수있다. 값은채팅/로그/Git에넣지않는다. 기존정확ZIP승인은충족했으므로다시승인을묻지않는다. 공개repo Contents read/write와만료를확인한다. 교체후에만/workspace/quant-legacy-resolution-20261023/deliver_v12.py를고정Python-I로재개한다. release생성기록이있으면같은새release만이어간다. 공개전송범위는정확v12+기존보고manifest/검증자료만이며CI색인이나추가연구commit을push하지않는다.

2. 오늘10/23KST수집은이미실제완료돼gate재조회/dispatch하지않는다.10/24다음창부터main의livegate를한번확인하고승인된41중21을실행할수있다.그다음허용day20. 예산2실행/82HTTP/각600초/일일1회/만료10/25KST23:59:59,동일예산재승인불필요. 자동실행미설정. checkpoint20100331002063, next20100331002066. 금융HOLD/PIT0/6.

3. 새금융검증이필요할때만새output경로를사용한다. 완료한동일case를반복하지않는다.

```sh
cd /workspace/quant-parser-repair-20261021/code
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/test_legacy_conflict_diagnostics.py
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/test_legacy_reviewed_provider_bridge.py
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I scripts/verify_reviewed_legacy_ocf.py --output /workspace/NEW_UNIQUE_OCF
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I docs/research/legacy-resolution-20261023/tools/analyze_requirements.py --output /workspace/NEW_UNIQUE_REQUIREMENTS
```

4.25접수의원문복구를먼저찾고없을때만별도Powerlogics2ZIP≤4HTTP를제안한다. 원래41밖이며아직승인/실행하지않았다.53그룹원문금액해결0;4개FY1월hint분리는값해결이아니다. 확정근거없이unit1000차이/부호를수정하지않는다. 단위·기간·당기·누적·정정버전을원문으로연결한후에만승인attestation을만든다.

5.새canary4FY필드중OCF1은이번증가다.914와분리하며연간값을Q4/순위전략사용으로확대하지않는다.1495는장부gate,원래신호모집단1946은별도다.456을임의제외하지않고공식issuer연결을조사한다. 신규전체전략/기간0.
