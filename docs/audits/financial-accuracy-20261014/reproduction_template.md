# 감사 재현

## 고정 입력과 버전

- main/data SHA: 3e9c42a1d3e028874eefb84c958a65d23083d088.
- 실제2,000배치 실행 코드 checkout: c3d12f3313a95f25162a1503be624f3b0617f8c0; run38498706052/job115640295063.
- original batch artifact11866183704: 240867410 bytes, SHA4d7ba8748a50a78d5fc15304b16072258105bbdb5c90c5374901e023943b61e5.
- frozen review artifact11871753367: 3011815 bytes, SHA44b9ba097cc8c724be3b6025a4964b8be223f364d5ddf6204487497e101736fa; review.part001이 전체 고정 ZIP이다.
- ledger artifact11871948035: 67940 bytes, SHA13ae94569bb80878800fc700eea4fd3539ec0771f3af77f91cd5126614e7a15f.
- original offline kit ZIP: 311922550 bytes, SHAf76f38e1c9ed9401cd3607db67100cf6211d8c96fc5dadcbda13eff940984784; release quant-report-26e4ec02e569.
- kit_id26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd; kit source822c435f4b6148c2832e12370a6ccb324a9e875f. kit_manifest와 sandbox_runtime verify로 고정 패키지를 확인한다.
- 선정 시드20261014, selection.json은 원문 숫자를 읽기 전에 보존했다. 감사코드와 runtime의 source_revision을 혼동하지 않는다.

## 실제 실행 명령

GitHub Actions에서 다음 순서로 실행한다. seed Python3.12는 전송/압축 해제/원래 bootstrap에만 쓰며 숫자 감사는 검증된 전용 Python으로 실행한다.

    python docs/audits/financial-accuracy-20261014/restore_inputs.py --workdir "$RUNNER_TEMP/independent-audit"
    python "$RUNNER_TEMP/independent-audit/kit-parts/bootstrap_quant.py" --parts-dir "$RUNNER_TEMP/independent-audit/kit-parts" --destination "$RUNNER_TEMP/independent-audit/runtime"
    "$RUNNER_TEMP/independent-audit/runtime/.venv/bin/python" -I "$RUNNER_TEMP/independent-audit/runtime/scripts/sandbox_runtime.py" verify > "$RUNNER_TEMP/independent-audit/verify.json"
    "$RUNNER_TEMP/independent-audit/runtime/.venv/bin/python" -I docs/audits/financial-accuracy-20261014/source_view.py --workdir "$RUNNER_TEMP/independent-audit" --output docs/audits/financial-accuracy-20261014/review
    "$RUNNER_TEMP/independent-audit/runtime/.venv/bin/python" -I docs/audits/financial-accuracy-20261014/audit_compare.py --workdir "$RUNNER_TEMP/independent-audit" --review docs/audits/financial-accuracy-20261014/review --controls docs/audits/financial-accuracy-20261014/manual_controls.json --output docs/audits/financial-accuracy-20261014

original bootstrap은 번들 wheel만 설치한다. 인터넷 pip, 패키지 버전 변경, 시스템 Python 계산 우회, DART 재수집/백필 재실행, main merge, 원본 변경은 수행하지 않았다. 검증 실패 시 감사 계산은 실행하지 않는다.

## 산출물 검증과 독립 재현

audit_summary.json의 실제 run ID·코드 SHA·Python 경로·입력/통제 SHA·판정합계를 확인한다. audit_details.csv는 FIELD565 + CHECK320 행이다. 금융 비율 계산은 row_type=FIELD만 사용한다. CHECK7 비적용30행은 applicable=False로 체크 집계에서 제외한다. 원문40ZIP의SHA/CRC/member SHA와 표본40유일성 및 행수 보존을 계산 전에 assert한다. audit_artifact_manifest.json은 요청 산출물3개와 summary의 바이트·SHA를 기록한다.

고정 코드 commit을 checkout하고 frozen 입력을 복원한다. 원문 TXT/XML 및 개별 표의 헤더·단위·정정 구역을 manual_controls.json과 함께 확인한다. 생산자 표/행좌표는 locator이고 정답은 원문이다. 통제값에 이견이 있으면 감사 통제만 수정하고 원본/추출값은 바꾸지 않는다. Decimal 허용오차0, 대시0가정 없음. NO_METRICS 블록은 숫자 존재의 근거이며 임의 필드 추출이 아니다. 공개시각/수정체인/과거 종목 이력은 공식 추가자료가 필요한 미완료 근거다.

## 실제 실패와 복구 기록

- 선정 workspace: failed to query executor configuration capabilities for environment ccarenv_b64_Y2NhcmVudl8zNmE3ZTFmYjA3NTQ4MTkxODAwMTNkMmVjN2EzNzRlZQ. 셸은 시작하지 못했다. 로컬 Python 경로를 확인했다고 주장하지 않는다. 명령 종료코드가 있는 실행 실패가 아니다.
- download_file: requires a ready execution workspace. 로컬 파일 생성/명령 실행을 주장하지 않고 GitHub Actions 원래 kit로 복구했다.
- prep run38510098063/job115676381389: exit1, urllib.error.HTTPError: HTTP Error 401: Unauthorized. GitHub→Azure cross-host redirect에 Authorization 헤더가 전달된 원인. 감사 전송 코드에서 cross-host Authorization을 제거한 뒤 실행; 같은401 반복 재시도 없음.
- 복구 prep run38516985176: 성공, selected40 / metric565 / original40. 이미 완료된2,000수집 artifact를 사용하여 중복 수집하지 않았다.
- 원문 보기 run38517563612 / 38518514256 / 38519458859: 성공. TD/TH만 보던 감사 viewer에 TE/TU 문자보존을 추가했고 운영 파서는 변경하지 않았다.
- connector >1MiB 파일은 content가 비어 JSON.parse가 실패할 수 있어100000자 원문 chunk와 개별 표 파일로 복구했다. JSON.parse undefined 오류는 금융 부재가 아니다.
- RemoteProtocolError: Server disconnected without sending a response: 1회 한정 재조회로 성공했다.
- 긴 tool 출력이 잘려 mutation 결과가 불명확했을 때 branch HEAD와 실제 workflow 결과부터 확인했다. 실행 시도를 완료라고 계산하지 않았다.
- 감사 보고서 코드 작성 중 JS SyntaxError: missing ) after argument list가 발생했으나 스크립트 실행 전 구문 오류로 어떠한 파일/commit mutation도 실행되지 않았다. Markdown backtick을 템플릿에서 분리한 뒤 정상 코드 저장을 확인했다.
- 모든 성공 수집/백필/원본 checkpoint는 보존했다. 서버 원본 archive와 frozen review/ledger, selection.json/source_manifest.json/selected_metrics.*, 원문 보기, 감사 브랜치가 재개 지점이다.

## 정확한 재개 절차

감사 job이 실패하면 job 원문로그·종료코드와 branch HEAD를 기록한다. 해당 감사-only 원인을 수정하고 고정 입력을 복원한 뒤 원래 offline kit bootstrap → dedicated sandbox_runtime verify=ok → 같은40표본/같은controls의 audit_compare를 재개한다. 성공한 수집/백필은 다시 실행하지 않는다. artifact 만료 시 이전 보존 원본ZIP의 정확한SHA로만 복원하고 최신 정정본을 같은 입력으로 대체하지 않는다. 근거 복원이 불가능하면 해당항목을 UNVERIFIED로 기록하고 접수번호·SHA·경로를 남긴다. 이 workflow는 전용 감사 브랜치의 보기/보고서만 커밋한다.
