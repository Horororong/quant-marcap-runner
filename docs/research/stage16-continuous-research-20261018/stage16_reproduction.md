# 재현 절차

저장소 Horororong/quant-marcap-runner, 브랜치fix/financial-accuracy-20261014.
시작 원격019075550256b9796fd5475fe8d6aa43a6d53b21 및 성공CI39078538435를 확인했다.
로컬 이전commit f530477b91647df2a3347c175286c0a921b798fc의 tree는 원격과 동일한
 d9872bf5d1786892be7552b01ff932e7765eb8fb였다. 로컬 원본·기존 결과를reset하지 않고
같은 tree의 후속 변경만 GitData로 게시한다. 일반 fast-forward ref update와expected SHA를
사용하며 force push·main merge를 하지 않는다. 최종 code SHA는실제CI의GITHUB_SHA를 참조한다.

고정 환경:

- 전용Python `/workspace/financial-repair/runtime/.venv/bin/python`, CPython3.12.14.
- kit_id `26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd`.
- kit_manifest SHA256 `a396ca2750bd55939b6915a90522a61a301e7b17ad095a6d8f4f422efa2a6018`.
- numpy2.4.6,pandas3.0.6,pyarrow25.0.1,XKRX exchange_calendars4.13.2.
- 실행 전 `/workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify` 실제exit0.
  결과는 `/workspace/research-stage16-20261018/runtime_verify.json`.
- 인터넷pip·패키지 버전 변경·시스템Python으로 계산하는 우회를 하지 않는다.

```bash
RESEARCH_PY=/workspace/financial-repair/runtime/.venv/bin/python
"$RESEARCH_PY" -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
"$RESEARCH_PY" -I -c 'import runpy,sys;sys.path.insert(0,"scripts");sys.argv=["scripts/export_strategy_dsl_contract.py","--check"];runpy.run_path(sys.argv[0],run_name="__main__")'
"$RESEARCH_PY" -I docs/research/stage13-stock-dividend-integration-20261017/validate.py --output /tmp/new-original-regression
"$RESEARCH_PY" -I docs/research/stage15-research-environment-20261017/validate_environment.py --check --output /tmp/new-baseline-regression
"$RESEARCH_PY" -I docs/research/stage16-continuous-research-20261018/validate_continuous.py --check --baselines /tmp/new-baseline-regression --output /tmp/new-continuous-validation
"$RESEARCH_PY" -I docs/research/stage16-continuous-research-20261018/verify_primary.py
"$RESEARCH_PY" -I docs/research/stage16-continuous-research-20261018/preserve.py --output /tmp/new-preservation --originals /workspace/financial-repair/preserved-originals60.zip
```

출력 경로는 전부 새 경로를 사용한다.
선행baseline regression의summary가 완료되기 전 종속 검증을 시작하지 않는다.
CLI `-I`는 자동 script 경로를 제거하므로 일반 import형 검사는 위처럼명시적으로scripts를
주입한다. workbench와문서별 검증 entrypoint는 자체 경로 주입을 보유한다.

validate_continuous는 실제13개 명령의 종료 상태를 보존한다. 그중 원래확장10분위,
2001–2025두 요청,2026은 예상exit3을 **차단 증거**로 확인한다. 이를성공 전략으로 세지
않는다. 성공한두7년한국어/JSON실행과독립 장부,151파일 고정 회귀를 추가 대조한다.
최종 CI는 --finalize-existing 없이 전체 명령을 새로실행한다. 이 옵션은 완료된모든
실행명령·입력/통제SHA·상태·독립 장부가 있을 때 감사기 수정 후 마지막 비교만 재개하는
로컬 복구 용도다. 데이터·NAV·기존 기대값을 바꾸지 않으며 미완료 명령을skip하지 않는다.
초기FileNotFoundError/헤더 이름AssertionError는local_validation의원문 로그를 보존했다.

원본 자료:

- 기존60원문과518·64검증결과는기존보존 경로를사용한다. 신규원문은evidence/에만추가.
- 기존2019/2020배당4건과원가·등락률·기준가:Stage12~15증거와원래catalog 그대로 보존.
- 새2021생애주기: `evidence_manifest.json`,rawDART ZIP은.b64의원래 바이트를decode해
  SHA를대조한다. `.xml.utf8.txt`는가독성 파생물이며원문 바이트로 인증하지 않는다.
- 새Kakao분할/LG정지: `actions2021_manifest.json` 및evidence/actions2021/.
- 직접공식분할기준가: `reference2021_manifest.json` 및evidence/reference2021/.
- 연간원자료·벤치마크·model/registry SHA는각preflight/control_files와
  preservation_manifest.json에기록한다. 이미보유한연도파일은읽기만했다.
- 모든수집job은명시한완료SHA/run_attempt1에고정했다. 재현을위한API재호출은필요없다.

로컬검증 위치:

- `/workspace/research-stage16-20261018/regression_final/`:19명령의기존연구환경회귀,
  원래10분위·민감도2건·모멘텀·상위1종목·한국어 및독립장부.
- `/workspace/research-stage16-20261018/full-regression/`:원래DART E2E를포함한19명령.
- `/workspace/research-stage16-20261018/continuous_verified/`:실제13명령,전체7년2실행,
  원래확장요청차단·2001요청·2026진단·생애주기기능검사·독립장부.
- `continuous_verified.log`의초기마지막헤더비교중단 후정상최종비교는
  `/workspace/research-stage16-20261018/finalize_existing.log`.
- 정밀2026진단은 `readiness2026_precise.json`. 최초파일은덮어쓰지않았다.
- 기존151파일동결ZIP은regression_baseline.json의local_preserved_zip경로/SHA로확인.
  변경전9계약스냅샷은그ZIP에서원해시확인후baseline_contracts/에추출했다.
- 단기실제2021배당사례와Kakao분할은개별기능검사이며원래전략축소실행이아니다.

기계적결과보존:
`results/`의전체7년daily NAV·선정·목표비중·CURRENT성과,
세장기요청의구조화준비도·2026진단·독립장부summary·소프트웨어summary와
`numeric_manifest.json`을대조한다. 새5개고정파일은이전151/15개기대값과분리한다.
한국어선정은같은팩터정의전항목확인후audit컬럼이름만매핑하며모든셀을정확비교한다.
CURRENT이외의성과계산기나전략전용백테스터를만들지않았다.

최종CI는기존 `.github/workflows/financial-accuracy-revalidation.yml`의
stock-dividend-regression job을[stage16]commit에서실행한다. 원래StrategyDSL workflow는
이수정브랜치에서이미인터넷설치job을제외하며,고정kit경로의실제검사가이를대체한다.
518/64보호검사와원문60·기존8결과복원 검증을 별도로실행한다. 후자는verify_preserved60.py의
fail-closed종료를사용한다.수집job0건을수집성공으로세지않는다.

실제브라우저는CI에이미있는Chrome을NodeCDP로구동한다. 설치없이기존10분위와
새7년보고서의기간/비용/포트폴리오선택,표·누적자산·로그2·드로우다운일치,
공유zoom,실제포인터hover,모바일폭,스크린샷을확인한다.
로컬sandbox의알려진Chromium setsockopt EPERM/SIGTRAP경로는반복하지않는다.

```bash
node scripts/verify_research_dashboard.cjs /tmp/new-continuous-validation/size2019_2025/report/report_CURRENT.html /tmp/new-browser-check
```

실제CI결과는RunURL의job/steps와stage16-continuous-research artifact를확인한다.
아티팩트에는정확한GITHUB_SHA/RunID,테스트로그,검증NAV/보고서,브라우저JSON/PNG,
재수집없는금융/원문보존결과가있다. 시각·절대경로가있는HTML/로그의바이트와
고정numeric파일의바이트를혼동하지않는다.
투자PIT0/6,518/64원검증의범위,원래10분위장기차단은CI성공으로승격하지않는다.
