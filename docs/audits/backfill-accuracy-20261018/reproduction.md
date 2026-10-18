# 재현과 안전한 인계

저장소Horororong/quant-marcap-runner,기존fix/financial-accuracy-20261014.
시작remote39682b9fdaafcd83978e024e65b931582553379d,실제CI39129005933success.
main수집데이터2038421602956bf7abe098286d5a2edd554d849b/v5와
연구v8.1은별개다. 원본운영데이터를고치거나자동백필을실행하지않는다.

```bash
PY=/workspace/financial-repair/runtime/.venv/bin/python
"$PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$PY" -I docs/audits/backfill-accuracy-20261018/validate.py \
  --check --runtime /workspace/financial-repair/runtime \
  --originals /workspace/financial-repair/preserved-originals60.zip \
  --output /tmp/financial-repair-new-run
"$PY" -I docs/audits/backfill-accuracy-20261018/test_main_proposal.py
```

출력은새경로만허용한다. verify통과kit_id는
26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd.
인터넷pip/패키지변경/시스템Python대체계산없음.
원본60외부ZIP의타임스탬프가달라도내부정확한60개원문ZIP/memberSHA/CRC로검증한다.
CI는Stage6 verify_preserved60가핀한기존originals60/replay60artifact만복원한다.
실패시nonzero이며그시점명령·stdout/stderr·exitcode를commands.json/log에남긴다.
기존518/64통제는재생새값으로덮어쓰지않는다.

개별조사명령:

```bash
"$PY" -I docs/audits/backfill-accuracy-20261018/replay.py --before --cohort development --output /tmp/v7-new
"$PY" -I docs/audits/backfill-accuracy-20261018/replay.py --output /tmp/v81-new
"$PY" -I docs/audits/backfill-accuracy-20261018/compare.py --replay /tmp/v81-new --output /tmp/independent-new
```

replay.py는검사대상으로실제생산원문reader/select_verified를사용한다.
compare.py는그모듈을import하지않으며별도그리드/수동좌표/리터럴/Decimal통제다.
금액동일성만으로성공시키지않고source_location/memberSHA·시작/말일·basis를별도검사한다.
기간시작일은별도development_period_controls와holdout_controls의고정원문통제다.
기존32통제원본및기존20감사파일은그대로다.

원문:
- 기존배치artifact12122416836,199816317bytes,
  SHA6faea3647a128da272d76aa0d315f4bdb93c7e46ba4554a8314add2d5b8f2f65.
- 새독립배치39125956115/artifact12138475303,233268008bytes,
  SHAe0aefa960b97c26b1a7987085828acf95ed8ed2d05ea7dbe3c04246982aa5a4d.
- 선정복원CI39132454920(첫2건메타데이터선정결함)과39132718687(수정된12건).
- sources/selected_originals.json.gz.b64는기존공식ZIP중개발12+독립12만포함한다.
  base64→gzip→JSON;files값은원래ZIP의base64다.압축SHA는parser_freeze에핀했다.
  새DART호출0. 원래ZIP/member/SHA를그대로유지하며동일표본중복API호출없음.
- 첫선정소스blob6f4aeb49338148e119cadce49bcdf8d33040fcfc와artifact12138810942는보존한다.
  최종고정subset의Gitblob은f9ad56c6bc85d1494d6ce70a93152464faeb931c이다.
  응답의인증키/요청URL/서명된저장소URL을기록하지않았다.

main_proposal은현재main코드핀에서생성한2개패치와바이트동일rollback증거다.
01은서비스/phase만,02는재무shadow후보이다. 운영적용명령을자동실행하지않는다.
02는14정상값재추출공백과유한migration검사가미완료라운영배포금지다.
향후승인받은동일main코드에서만git apply --check,격리canary,독립감사를거친다.
main자체가달라졌으면해당패치를그대로덮어쓰지말고먼저diff를확인한다.

현재최소복구20건과3998서비스후보는서로다른범위다. 운영확정수정목록이아니다.
518/64/원문60/기존849핀/원래전략계약·NAV를보존한다.
장기다종목은기존차단이유가그대로며별도권리/승계원천자료없이재실행성공을만들지않는다.

최종메시지marker는[financial-backfill] [stage16] [multi-asset] [continuation-verified]다.
financial-backfill-repair가새금융검증을,기존stock-dividend/multi-asset/
continuous-baseline jobs가원래JSON/한국어·독립장부·CURRENT브라우저회귀를실행한다.
새수집job은이미완료한정확한과거SHA에고정되어재실행되지않는다.
CI미실행/skip은PASS가아니며financial_population_certification은계속UNVERIFIED다.
