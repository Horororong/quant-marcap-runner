# 재개 — RESEARCH_ONLY

작업 경로 `/workspace/quant-parser-repair-20261021/code`, 연구 branch
`research/sbm-reference-pit-20261023`. 원본/최소복원본/full snapshot/기존백업은 유지한다.
고정 Python은 `/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python`이다.
계산/연구 명령에 `-I`를 사용하고 새 세션에는 고정kit verify부터 한다. 인터넷pip 금지.

완료된180원문 파서 비교(159+신규21),118시험,273해시/CRC,UI/130/전체복원/백업은
코드·입력 변경이 없으면 다시 하지 않는다. 원격 CI는 신규 공개 승인 이후 실행한다.
수집Actions40024818567 SUCCESS는 연구 코드의 CI가 아니다.

## 다음 실제 수집

10/24KST는 실행 완료. 추가예산장부는 이미 원격에 존재하므로 없어진다면 초기화하지
말고 조사한다. 기존3회 history hash와 frozen41 순서/진행 prefix를 보존한다.
현재checkpoint20100331002116,다음20100331002117,고정잔여20은
`evidence/finite21/SUPPLEMENTAL_AFTER.json`에 정확한 순서로 있다.
잔여1실행/20문서/40HTTP(retry포함)/600초,최대1/KST일,
유한만료2026-10-25KST23:59:59다. 실제소비21HTTP/보수적42예약이므로
예약미사용분을 풀어 문서를 늘리거나 추가실행을 만들지 않는다.

**10/25KST의 허용창에서만** 그때의 main/config/원래장부/별도장부/다른진행중run을
한 번 읽고 병합된 `financial_supplemental_resume.check`로 같은 보호조건을 확인한다.
모두 허용되면 이미 승인된 입력으로 실행한다. 동일 예산을 다시 요청하지 않는다.

```bash
gh workflow run backfill-dart-legacy-2000-2014.yml \
  --repo Horororong/quant-marcap-runner --ref main \
  -f resume_parent_run=39504052321 \
  -f batch_documents=20 \
  -f supplemental_approval=finite41-20261023
```

명령 예시는 자동 설정이 아니다. 현재cron에는 supplemental 입력이 없다.
정상 배치 후 source/result pack·HTTP·retry·SHA/CRC·ID중복·정상종료·checkpoint를 확인한다.
오류면HOLD/처리상태를 보존하고 중단한다. 예산소진 목적 재시도는 하지 않는다.
GitHub호출은 이미 작동하는 GH_BACKUP_TOKEN을 gh 자식 환경의GH_TOKEN으로만 전달하고
값을 출력/저장하지 않는다. credential 재교체/v12 업로드는 필요하지 않다.

## 원문·PIT 다음 작업

1. 20회사 FY80과 새SBM FY4의 공식 원문 공개/원문 버전·정정 목록을 신호일에 연결한다.
   index 날짜와현재ZIP만으로 인증하지 않는다. 정정이 없으면 닫힌 단일버전 proof가
   충분하며 불필요한 두번째 버전 요구는 금지한다. 날짜만 확인되면 다음 공식세션
   CLOSE 규칙,실제체결은기존엔진계약을 유지한다.
2. 전략은super_value_dart_dsl/원래1946종목/2010-04-30신호,필수7slot이다.
   Q3원문 회수/검토는 revenue/NI/OCF 세 누적흐름에 집중한다. 이미 목록화한
   68legacy행/22접수의 정확한SHA를 기존복구자료에서 먼저 찾고,원문/기간/정정증거 없는
   기존v5값을 provider에 자동 입장시키지 않는다. 파일이름 검색 부재를 전체백업의
   원문 부재 인증으로 해석하지 않는다. SBM은현재2009Q3필수후보가 없다.
3. 7identity 미완료는 신성FA/ENG 각2,KSR2,ADP4/1이다. 상대회사 표에 나온 약칭이나
   음역추정으로 해결하지 않는다. 기존33/40는 재검토하지 않고 새 근거가 생긴 사례만
   처리한다. SBM의2새point증거는별도다. 53값충돌·기존23UV·기존gap는새증거없이반복하지않는다.
4. 이번273신규 후보는17문서/68FYcore힌트가 있으나 의미미검토다. 마지막20수집과
   병행해 전략에필요한필드·기간을 우선 검토한다. SOURCE_GAP4는XML형식/주석/표문제와
   원문부재를구분하며수집성공이나PARSER_4F를완전성/PIT인증으로세지않는다.

## 재현 명령(변경 후 또는 새 검증 환경에서만)

고정입력 원문은 source run39248507369의 이미원격에있는pack5개다. 새경로에
`source-core-batch3-20261023/tools/unpack_first100_preserved.py`로 열 수 있다.

```bash
/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I \
  docs/research/sbm-reference-pit-20261023/tools/check_sbm_actual.py \
  --root . \
  --archive <NEW_AUDIT>/first100-chunks/part01/native/20100331001822-10f1e6aebdf5f245bd4026a030d494cf64cd94813c33eb89064c0e3989408c13.zip \
  --output <NEW_SBM_CHECK>
```

`build_strategy_pit_matrix.py --root . --output <NEW_MATRIX>`는 기존 source/readiness/provider를
사용한다. 실제새273 원문pack은 main의 고정결과commit
`299e97b47a06cadcf2414c07f9dac606a428e233`의 run40024818567에서 확보한다.
큰pack의Contents API encoding=none이면 Git blobSHA로 본문을 읽는다.
`verify_finite21_preserved.py --help`의 인자로 원문pack/기존원장/ID명세/새output을 지정한다.
직접Actions artifact다운로드는Azure redirectForbidden으로중단했고반복하지않았다.

## 공개·복구

승인된v12는이미원격draft421514386/ZIP SHA464aa445… 검증완료다. 반복업로드금지.
공개 연구브랜치는확인된589a3ea…까지다. 이전미승인89파일의고정target33abf89…와
이번수리/감사증분을구분한최종전송명세를기준으로한번에공개승인을요청한다.
driver는코드파일수에포함하지않고별도SHA/크기/대상codeSHA를표시한다.
manifest에없는코드나과거거절CI색인을임의게시하지않는다. main연구전체병합/금융게시/
PIT해제승인으로해석하지않는다. 원문21pack은이미원격이고새연구코드·증거/driver만
승인전에는로컬복구자료에의존한다. 원본없는전체프로젝트remote-only복원은미실시다.
