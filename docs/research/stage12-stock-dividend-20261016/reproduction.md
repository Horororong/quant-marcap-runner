# Stage12 재현·인계

기준 원격577278bc869a76d80523b14e8600380ad37f415b.
최초 로컬47f6bf6ae209fc4837167887ca2b413ae6fc1a9a와 같은 트리였고 원래 로컬 이력을 보존했다.
연속 로컬/원격 커밋은 SHA가 다를 수 있으나 게시 전에 전체 Git tree를 대조했다.
force push·main merge·기존 원본 변경은 없다.

원래 전용 Python은 `/workspace/financial-repair/runtime/.venv/bin/python`이다.
원래 kit_manifest는 `/workspace/financial-repair/runtime/kit_manifest.json`,
kit ID26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd.
새 환경은 기존 `restore_kit_only.py`가 고정한 원래 릴리스/해시와 번들 wheels만 사용한다.
인터넷 pip/의존성 변경/다른 Python 계산 우회는 금지한다.

저장소 root, 새로운 출력 경로에서:

```bash
/workspace/financial-repair/runtime/.venv/bin/python -I /workspace/financial-repair/runtime/scripts/sandbox_runtime.py verify
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage12-stock-dividend-20261016/validate.py --defer-dart-e2e-after-native-crash --output /tmp/stage12-new-validation
/workspace/financial-repair/runtime/.venv/bin/python -I docs/research/stage12-stock-dividend-20261016/preserve.py --output /tmp/stage12-new-preservation --originals /workspace/financial-repair/preserved-originals60.zip
```

validate.py는 각 테스트를 같은 전용 Python의 isolated child로 실행하며 파일별150초 상한,
실제 종료코드·로그·로그SHA를 기록한다.16개 테스트 파일+생성 계약 검사이며 실패는 exit1이다.
현재 위 명령의 명시적 defer는 UNVERIFIED와 exit2가 예상 결과다. 전체 통과가 아니다.
전체 원문 재파싱/재수집이나 원래2019~2020 전략 재실행은 포함하지 않는다.
기존 실제 소규모 DART/KRX/분할/합병 E2E는 소프트웨어 회귀 목적이다.
새37개 unittest에는 합성 장부/수집·CI 경계와 실제4건의 가상 보유 guard probe가 포함된다.
합성 통과와 실제 사건의 독립 인증은 구분한다.

**현재 기본 전체 명령을 무작정 반복하지 않는다.** CI39003674278의 기존 DART E2E exit124와
한 번의 로컬 비동기 스택 진단 exit139가 미해결이다. native_runtime_incident.json 참조.
동일 실패의 재실행 없이 나머지를 검증하려면 validate.py에
`--defer-dart-e2e-after-native-crash`를 명시한다. 이 모드는 원래 시험을 UNVERIFIED로 기록하고
항상 exit2를 반환한다. 전체 PASS로 사용하면 안 된다. 최종 CI는 이 모드이며,
보존 검사는 테스트 실패와 독립된 단계로 실행한다.150초 상한·패키지·Python 변경은 없다.

preserve.py는 preservation_manifest.json의 기존566개 파일 byte/SHA를 대조하고518/64 기존 통제를 읽는다.
--originals를 제공하면 기존60개 ZIP의 모든 멤버 SHA/CRC도 대조한다. 생략하면 물리 원문60은 UNVERIFIED다.
CI는 추가로 기존 verify_preserved60.py를 통해 고정 원문/기존 replay artifact를 복원·해시 확인한다.
금융 추출을 다시 실행하지 않는다. 실패/복원 불가를 성공 처리하지 않는다.

## 실제 공식 자료 확보와 실패

첫 구현 원격b7a12ff56e9f4b64b1b26f02b68cb6c2626250bb,
CI38980154097/job117238857041 성공.2개 법인/2개 HTTP200/DART000 응답/98개 메타데이터.
원본은 official_metadata/에 보존했다. state.json의 바이트·SHA256, 전체 페이지/건수와 대조한다.
쿼리20191201..20210430, 유형I,last_reprt_at=N, 각page_count100/page1으로 제한됐다.
당시 법적 상장 상태/공개시각/모든 정정 이력/문서 승인 내용까지 인증하지 않는다.

아티팩트12080946966은13557바이트/SHA256
5a6de9ddcc8e2fd72f8633e0a6ae4ecef32f7677c77e06caf7a6c450275ba382다.
외부 다운로드 명령은 권한 대기 뒤 중단되어 결과 파일/종료코드가 없었다.
CI39003485145/job117311092019에서 같은 고정 artifact만 읽어 decoded job logs로 전달하고
로컬에서 원래 ZIP 길이/SHA/CRC와 두 원본 JSON 해시를 확인했다. DART 요청은0이다.
해당 임시 전송 코드는 read_stock_dividend_artifact.py이며 인증키를 복사/출력하지 않는다.

원문 조회 원격57cdba365bc82aae0be35e5dde9c978e6d7b95cf,
CI39003674278/job117311639886. 먼저20191226900748을1회 조회했다.
HTTP200이나 DOCUMENT_CORP_MISMATCH/exit2, 완료0건,20201228900943은 미조회다.
official_documents/run_state.json 및 response_manifest.json에 보존했다.
그 당시 검증 실패 원문은 저장되지 않았으므로 원본 SHA를 제시하거나 법인 불일치의 실제 원인을 확정하지 않는다.
현재 wrapper는 안전 검사를 마친 식별 거부 원문을 UNVERIFIED로 격리 보존하도록 수정됐고 합성 시험만 했다.
동일 요청 재호출·검증 조건 완화는 하지 않았다.
원문 조회 job의 실패와 같은 run의 엔진 회귀/보존 job 결과는 별개로 기록한다.
최종 CI는 수집을 건너뛰어야 하며, 수집 오류가 해결됐다는 뜻이 아니다.

## 실제 사건과 다음 구현 경계

공식181000원은 Stage11 E11-01의068270/2019-12-27에만 적용한다.
세 미확인 기준가를 역산하지 않는다. 배당률/승인/발행 이력은 Stage9~11 참조.
입고/실제 거래 가능일/단주/세금/당시 규정/공식 시세는 별도 독립 근거가 필요하다.

공통 stock_dividend 모듈은 부분 장부이지 완성된 public execution이 아니다.
StockDividendBook의 scope는 synthetic 또는 evidenced_research이며 투자 승인은 항상false다.
Evidence.usable_session은 호출자가 증명한 세션이어야 한다. 해시/URL만으로 사실을 인증하지 않는다.
신규매수 권리중복·지급 전 기존 주식매도·조건부 승인·실제 입고·미상장 주식·단주/세무 차단을 유지한다.
Gross/Net 목표비중·비용·정수/단주 수량 정책과의 통합 전 registry/PROJECT는 사건을 계속 거부한다.
운영 PIT gate는 그대로이며 Stage6 투자 PIT0/6, 네 실제 사건 완전 인증0/4다.
증거/회계 계약을 충족한 사건만 등록한 뒤 원래10분위를 동일 입력으로 재실행한다.

## 새 공식 KRX 시세

기존 update-market-data/update-quant-data의 KRX_AUTH_KEY 참조를 재사용했다.
원격68aed33e8b206a39d45d8168be6254c3e6b72e52, CI39004603672/job117314391668 성공.
공식 현물 KOSPI/KOSDAQ 일별매매 endpoint,20191226/27 및20201228/29에만8회 요청했다.
원본8개는 artifact12090049835,539408바이트/SHA256
66a75e106ca32101e2a49114dccdfce7fa48a02bf7bc746e993f0e1043d5ba8b에 보존했다.
Git에는 선택8행과 원본응답 SHA/행 위치만 official_krx/state.json으로 보존했다.
이 상태 전달SHA는9ed9a7158caeec2d020391e47bde9195f9cf70a6fe93e0d0c845f46998a1c711이다.
원본 whole-market 응답을 로컬에서 재다운로드한 것은 아니다.

`compare_krx.py --output <new.json>`을 같은 전용 Python으로 실행하고
official_krx/comparison.json과 byte 비교한다. 공식 원문행과 Stage10 CSV를 독립
Decimal 비교해12 PASS/0 FAIL/0 UNVERIFIED, 허용 반올림0을 확인했다.
원시 종가 수익률과 공식 FLUC_RT의 차이는 보존하며, 기준가3개를 역산하지 않는다.
공식181000원만 기존 Stage11 근거로 재사용한다. 실제 권리 보유수익률은 null/UNVERIFIED다.
API 제공기간·2026년 명세를2019/20 규정이나 PIT의 인증으로 사용하지 않는다.
추가 API 요청 없이 재현하며, 최종 CI에서도 수집 경로는 모두 skip돼야 한다.
