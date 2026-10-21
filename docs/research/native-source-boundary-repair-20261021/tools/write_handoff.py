import hashlib,json,shutil
from pathlib import Path
R=Path('/workspace/quant-parser-repair-20261021/code');P=R.parent/'evidence'
D=R/'docs/research/native-source-boundary-repair-20261021';D.mkdir(exist_ok=False)
report='''# STC 주석 참조 / CJ 숫자 표기 수리 — RESEARCH_ONLY 실험 브랜치

## 실제 수정과 보존 범위

별도 worktree `/workspace/quant-parser-repair-20261021/code`, 브랜치 `fix/native-source-boundaries-20261021`, 기준01731c73ff3d8023d1747d5d1b11cfacad509eb0에서 작업했다. 기본 작업공간/최소복원본/원본/기존결과/kit/v1~v6는 변경하지 않았다. 새 worktree는 로컬 Git 객체에서 만들었고 원문은 기존 보존ZIP을 읽었다. 전체 데이터 감사/복구 시험/대용량 전송/기존 통합CI를 반복하지 않았다.

수정 파일은 `scripts/legacy_native_financials.py`다. parser version은 `legacy-v9.3-note-reference-token-guard`다. 두 변화만 적용했다.

- 원문에 있는 정확한 일반 문구 `연결재무제표에 대한 주석 참조`/`재무제표에 대한 주석 참조`를 zone 경계 토큰으로 오인하지 않는다. 이 문구는 닫힌 zone을 열 수 없고 실제 `주석`/부문/합병전후 경계는 계속 닫는다. 현재기간·단위·물리 당기 열·연결/개별·정정구간 검사는 그대로다.
- 숫자 한 개 뒤에 DART의 리터럴 `&cr;`와 terminal underline이 있는 형태를 원문의 장식 구분으로 처리한다. 숫자 사이의 `&cr;`, 두 수치, 잘못된 쉼표·주석·%·빈칸·대시는 숫자로 합치거나 추정하지 않는다. 새 경우의 `numeric_normalization`은 `native_linebreak_terminal_underline`이며 원문 raw_amount를 보존한다.

## 실제 원문 회귀와 독립 대조

보존된57문서에 기존9.2와 새9.3을 각각 적용하고 unchanged source diagnostics와 SOURCE_GAP gate를 함께 적용했다. 원문 재수집0이다. 기존9.2 replay는 저장된871후보와 선택된 금융·출처·기간·열·부호·단위·품질 필드가 전부 일치했다. 새9.3에서도 기존871후보의 키/해당 필드 변경0·제거0이다. 기존848PASS/23reviewedUNVERIFIED가 유지되고9SOURCE_GAP은 후보0으로 유지됐다. 비교 필드는 replay_originals.py의 `fields`에 명시되어 있으며 parser version 자체의 변경을 숨기지 않는다.

오프라인 새 구조 후보는9개다. STC CFS8개와 CJ CFS자산총계1개이며 다른 문서에 추가/제거는 없다. 제안 출력만871→880이다. 운영 수집 장부와 기존 데이터는 여전히871이다.

생산 parser로 다시 계산한 일치는 회귀 증거다. 정확성 판정은 별도 `audit_new_source_rows.py`가 원문ZIP의 실제 table/row/cell/header/current COLSPAN/단위/부호를 읽고, 원문에서 미리 전사한 기대값과 독립 Decimal로 대조했다. 생산 추출 함수를 import하지 않았다. 신규9개 source-row semantics PASS이며 PIT와 whole-filing completeness는 모두 UNVERIFIED다. 제안 집합은 source-row PASS857/미검증23, 기존 운영 집합은848/23으로 구분한다.

|접수번호|scope/항목|현재 원 단위 값|원문 table/row/물리열|
|---|---|---:|---|
|20100331001972|CFS revenue|3507674422|60/1/2|
|20100331001972|CFS cost_of_sales|2192294089|60/5/2|
|20100331001972|CFS gross_profit|1315380333|60/9/2|
|20100331001972|CFS depreciation|280329158|60/18/1|
|20100331001972|CFS amortization|127621339|60/19/1|
|20100331001972|CFS operating_income|-5134536307|60/37/2|
|20100331001972|CFS net_income|-9844112035|60/61/2|
|20100331001972|CFS ocf|-4481694015|64/1/2|
|20100331001982|CFS total_assets|4877276061000|135/73/2|

STC매출−원가=매출총이익을 추가 확인했다. CJ는 원문4877276061천원×1000이며 기존 독립 검토 부채3039674339천원+자본1837601722천원과 정확히 같다. 감가/상각 PASS는 해당 원문의 IS판매관리비 행만 뜻하며 회사 전체 합계나 CF조정액으로 해석하지 않는다. 새 구조 후보/원문행 PASS가 운영 데이터 인증·정정체인·실제 사용 가능일·투자PIT를 대신하지 않는다. 기존23미검증과9SOURCE_GAP 판정은 새 근거 없이 바꾸지 않았다.

## 시험 결과와 남은 차단

새 경계 시험은9개 통과했다. 당기/비교기, COLSPAN현재그룹, 잘못된단위/기간/합쳐진숫자, 실제 주석/부문 폐쇄, 단순 참조가 닫힌 구간을 다시 열지 않음, 원문 보존과 새 normalization, 기존 승인 버전의 새 parser 거부를 포함한다. 수정 전 새 경계시험8개 실행 중6개 subcase 실패를 재현했고 수정 후 통과했다. 추가된9번째 시험은 승인 guard다.

관련 suite 실제 결과는 **114실행/112PASS/2ERROR**다. 남은 두 시험은 기존 운영승인9.2 config의 허용 경로를 새9.3에서 기대하는 곳에서 `UNAPPROVED_PARSER_OR_DIAGNOSTIC_VERSION`으로 멈춘다.

- `test_financial_limited_resume.Limited.test_first_schedule_review_daily_total_and_failure_gates`
- `test_financial_batch_resume.Resume.test_same_day_and_three_attempt_caps_remain_closed`

이는 새9.3을 운영 승인한 것으로 간주하지 않았기 때문이며 전체 suite 성공이라고 보고하지 않는다. 기대값/fixture/운영config/source hash를 시험 통과 목적으로 변경하지 않았다. `ApprovalBoundary.test_old_approved_collection_contract_rejects_new_parser`가 새 parser를 기존계약으로 실행할 수 없고 state가 변하지 않음을 별도로 확인했다. source-owner hash 불일치와 명시적 parser migration 필요 상태를 `MIGRATION_AND_TEST_STATUS.json`으로 보존했다.

원격 새 CI는 미실행이다. 새 감사 payload의 공개 Git 게시가 이전 자동 승인 검토에서 거부돼 원격에 이 변경을 올리지 않았다. 해당 차단은 우회하지 않았다. 과거39540516627SUCCESS는305cb에 대한 증거이며 이9.3을 검증한 CI가 아니다. 코드 수리는 로컬 오프라인 회귀/원문 대조 범위까지 확인했으며 운영 반영/새 CI/승인된 migration 완료를 주장하지 않는다.

## 수집과 게시

2026-10-21T07:53:09.565954UTC(KST16:53)에 실제 main의 state/config와 승인된 기존9.2 gate를 새 경로에서 읽었다. main은fd232d129bfa2ef01714b94890460c5ef47bdbf0이고 ONCE_PER_KST_DAY 차단이 유지됐다. sourceHTTP0,새원문0,실제수집후보0,workflow dispatch0이다. 새 research9.3의 거부와 실제 main9.2의 일일 제한을 혼동하지 않는다.

HOLD_FAILURE/checkpoint20100331002054 COMPLETED,다음2062/2063 미완료,예약pending43,실행2/3·예약200/300이다. earliestwindowUTC15:00 이후에도 모든livegate/만료/first-review/hash/예산을 다시 확인해야 한다. 하루가 바뀐다는 이유로 dispatch하지 않는다. 허용되면 기존main9.2에서2건은 가능하지만, 세 번째 실행을 쓰므로 네 번째나 다음batch는 승인 범위 밖이다. 새9.3을 사용하도록 승인 설정을 몰래 바꾸지 않는다.

금융 게시HOLD/backtest_eligibleFalse/투자PIT0/6 유지, 운영값 교체0이다.

## 재개 명령과 다음 단위

```bash
cd /workspace/quant-parser-repair-20261021/code
PY=/workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python
"$PY" -I /workspace/quant-restore-b5aaa7f/runtime/scripts/sandbox_runtime.py verify
"$PY" -I -m unittest discover -s tests -p test_native_source_boundary_repairs.py -v
```

원문 replay 증거는57문서 전체로 이미 완료했으므로 코드/원문/판정에 새 변경이 없으면 반복하지 않는다. 증거 script는 tools/replay_originals.py이며 보존원문 위치는 `/workspace/quant-project-full-20261020/continuation/39504052321/decoded`다. 완전 원격복원 시험을 한 것은 아니다. 이 원문의 원격Git/v2복구 출처는 이전 증거 manifest를 재사용한다.

다음 단계는 새 감사·수리 payload의 공개 게시 승인을 확보한 뒤 별도 연구브랜치 게시/새 고정-kit CI, 그 후 explicit reviewed migration 범위와 최소 운영PR를 분리하는 것이다. 전체 연구브랜치를main에 병합하지 않는다. 수리되지 않은 개념충돌42감가상각key/3유동성장기부채key/1사채key 및 annex/whole-filing누락/23항목정의/PIT는 별도 후속 과제다.9새값을 원래 전체금융 인증 건수로 확대하지 않는다.
'''
(D/'REPORT.md').write_text(report)
for name in ['before-tests.log','after-tests.log','focused-regression.log','related-suite.log','original-57-replay.json','new-9-independent-source-controls.json','MIGRATION_AND_TEST_STATUS.json']:
 shutil.copy2(P/name,D/name)
shutil.copy2(P/'live-gate/deployed-runtime-gate.json',D/'live-gate.json')
(D/'tools').mkdir()
for name in ['replay_originals.py','audit_new_source_rows.py','write_handoff.py']:shutil.copy2(R.parent/name,D/'tools'/name)
header='''## 2026-10-21 새9.3 원문 추출 수리 — 로컬만, 운영 migration 미승인

- 별도fix/native-source-boundaries-20261021, /workspace/quant-parser-repair-20261021/code에서 STC주석참조와CJnativebreak숫자 장식을 수정했다. 기본workspace01731c7/백업v1~v6는 보존했다.
- 57원문 old9.2 replay=저장871일치;new9.3도 기존871의 금융·출처 비교필드 변경/삭제0. 기존848PASS/23UV/9SOURCE_GAP 유지. 새오프라인9후보(STC8,CJ1)는 별도 독립원문행PASS. 제안880=857source-rowPASS+23UV;운영데이터871은 그대로다. 금융게시0/PIT미인증.
- 새9경계시험PASS;관련114시험112PASS/2ERROR. 두오류는9.2승인config가9.3을거부한것이며fixture/config/hash를바꾸지않았다. 명시적 migration/새원격CI/운영배포는아직미완료다.
- 실제main9.2 livegate07:53UTC/16:53KST는ONCE_PER_KST_DAY,HTTP0;HOLD_FAILURE/checkpoint2054완료,next2062/2063,pending43,실행2/3.새parser미승인과실제main의일일제한은별개다.
- 새감사payload 공개Git전송은자동승인검토거부후 추가승인대기. 이번 수정도 원격미게시/새CI미실행. 이미승인·검증된v5는재전송하지않는다. 보고/원문controls/회귀/실제test오류: [수리증거](docs/research/native-source-boundary-repair-20261021/REPORT.md).

'''
f=R/'HANDOFF_CURRENT.md';f.write_text(header+f.read_text())
files=[]
for f in sorted(D.rglob('*')):
 if f.is_file():files.append(dict(path=str(f.relative_to(D)),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
(D/'EVIDENCE_MANIFEST.json').write_text(json.dumps(dict(classification='RESEARCH_ONLY',source_base='01731c73ff3d8023d1747d5d1b11cfacad509eb0',source_root=str(Path('/workspace/quant-project-full-20261020/continuation/39504052321/decoded')),files=files),indent=2)+'\n')
print('Prepared14repair evidence files',len(files))
