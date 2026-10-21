# v5 보존 및 남은29문서 의미 검토 — RESEARCH_ONLY

## 완료 범위

승인된 v5는 기존8635482바이트/46payload파일/SHA256 c1de9872045c0d1d066b37fb7aab5f968f986c5854bda1083f238a261ff46490 그대로 보존했다. 공개 저장소 Horororong/quant-marcap-runner(visibility=public)이며 draft를 비공개 경계로 취급하지 않았다. 모든 ZIP entry에서 설정된 비밀값의 실제 바이트와 PAT/개인키/AWS access key/credential URL/리터럴 secret assignment 패턴을 검사해 검출0이었다. 공개 DART 원문 증거, RESEARCH_ONLY 결과, public-source provenance, 실행ID/작업공간 경로와 인수인계 자료를 승인된 공개 적합 범위로 확인했다. 비밀값을 로그나 검사 결과에 출력하지 않았다.

새 draft release: https://github.com/Horororong/quant-marcap-runner/releases/tag/untagged-78757edecdfa41d49e4b

release id419190338. 3개 독립 Base64 part와 manifest/다운로드 helper를 업로드했다. 실제 원격 asset API로 인증 다운로드 후 순서대로 복호화/결합하고, 별도 /tmp/quant-v5-remote-cw51279g에서 전체 크기/SHA256, ZIP CRC,46파일별 길이/SHA256 및 별도 unpack을 검증했다. 메타데이터 asset과 최종 delivery receipt도 원격에서 원본 바이트와 대조했다. 단일 ZIP의 직접 다운로드 링크라고 소개하지 않는다. 저장소에 로그인해 draft에서 download_backup.py와 download_manifest_text.json 및 .b64part001~003을 받을 수 있다. GitHub CLI 인증 사용 시 helper의 자동 모드도 제공한다. 기존 백업·원본·kit는 변경/재전송하지 않았다.

v5 ZIP 내부의 이전 pending 기록은 봉인 시점의 상태다. SHA를 유지하기 위해 수정하지 않았다. 최신 전달 상태는 외부 DELIVERY_COMPLETED.json 및 이 보고서가 우선한다. 이번 새29문서 증거는 승인된 v5에 들어 있지 않으며 별도의 Git 증분으로 보존한다.

## 의미 검토 판정

큐로홀딩스20100331001983부터 남은29문서의523개 기존 후보를 원문과 대조했다. 신규512PASS/11검토후UNVERIFIED/0FAIL이며 기존348개 판정을 그대로 유지해 누적848PASS/23검토후UNVERIFIED/미검토0개다. 후보가 존재한48문서의 기존 후보 판정은 끝났고 후보0인9SOURCE_GAP 문서는 원래 원인별 triage 상태로 보존했다. 이것은57문서 전체의 재무·추출 완전성/PIT 인증 완료가 아니다.

PASS의 동일 기준: 원문에 보고된 특정 회계 행의 기간·실제 당기 열·연결/개별·단위·부호·항목 라벨 의미와 후보의 일치다. IS의 감가/상각 비용 부분을 CF 조정액 또는 회사 전체 합계로 취급하지 않는다. 연결 순이익을 지배주주 귀속으로 변환하지 않는다. 현금유출 항목은 원문 보고된 지급/취득 양수 표기를 확인했으며 포트폴리오 cash-flow 부호 계약을 인증하지 않는다. 원문 보고회사명과 현재 meta의 회사명 변경/PIT 종목 연결도 이 행 대조만으로 인증하지 않는다.

모든871개 실제사용가능일/PIT/정정체인과 전체 주석·첨부·모든 account의 추출 완전성은 UNVERIFIED다. 이전 숫자/부호/단위871개 증거는 그대로이며 전체 감사를 반복하지 않았다. 신규 후보를 검토하면서 해당 원문 현재 셀을 독립 Decimal/단위 배수와 대조했다. 생산 parser 재실행을 정확성 oracle로 사용하지 않았다. 새 원문 fetch0, 운영값 교체0, 금융 게시0이다.

문서별 직접 지정한 primary BS/IS/CF/term/unit/current-column controls는 independent_inventory.py에 있고 원문 header/row/cell attrs 및 member/archive SHA는 document-source-evidence.json과 primary-table-inventory.json에 있다. 케이티알파/LS일렉트릭 CFS의 당기 COLSPAN2를 직접 확인해 물리열1/2를 같은 현재기간 그룹으로 대조했다. 현대페인트 비교기는1개월짜리 기간이며 LS CFS의2007비교기 날짜 표기 문제도 당기2009와 분리했다. 첨부추가/정정 flag와 filed-body 대조, 실제 법적 정정체인/최초 사용가능일은 별도다.

## 신규29문서의 기존 후보 판정

|접수번호|문서|후보|PASS|검토 후 미검증|
|---|---|---:|---:|---:|
|20100331001983|큐로홀딩스|17|17|0|
|20100331001986|알루코|18|16|2|
|20100331001987|동일산업|17|17|0|
|20100331001990|현대페인트|15|15|0|
|20100331001993|CS홀딩스|16|16|0|
|20100331001994|에이원마이크로|15|15|0|
|20100331001996|퍼스텍|18|18|0|
|20100331001997|KCC건설|19|17|2|
|20100331001998|현대지에프홀딩스|15|15|0|
|20100331002001|구영테크|19|18|1|
|20100331002002|메티스|17|17|0|
|20100331002003|메카포럼|17|16|1|
|20100331002007|씨모텍|14|14|0|
|20100331002017|케이티알파|26|26|0|
|20100331002019|에이프로젠|19|18|1|
|20100331002024|선우중공업|17|17|0|
|20100331002026|신라에스지|18|18|0|
|20100331002027|오라바이오틱스|15|15|0|
|20100331002028|KBI동양철관|17|17|0|
|20100331002029|알보젠코리아|18|18|0|
|20100331002033|SK디스커버리|16|15|1|
|20100331002034|모보|18|18|0|
|20100331002036|우경|15|15|0|
|20100331002037|한일홀딩스|22|21|1|
|20100331002039|태광산업|16|16|0|
|20100331002043|제일기획|18|18|0|
|20100331002046|엘에스일렉트릭|37|35|2|
|20100331002053|알이네트웍스|19|19|0|
|20100331002054|브이오산업|15|15|0|
|합계|신규29문서|523|512|11|

기존12미검증은 새 근거 없이 다시 판정하지 않았다. 신규11개는 비유동 사채9개(알루코/KCC건설/구영테크/메카포럼/에이프로젠/SK디스커버리/한일홀딩스/LS일렉트릭OFS+CFS)의 총사채 정의와 current maturity 포함 여부, 알루코 유동성장기차입금1개 및 KCC건설 유동성사채1개가 전체 유동성장기부채를 대표하는지의 문제다. 유동성장기차입금도 기존 accepted label인 유동성장기부채로 자동 승격하지 않았다. 누적23개 전부에 원문 위치·정의 문제·재판정에 필요한 근거를 unverified-23-cause-ledger.json으로 남겼다.

## 누락/보류 및 우선순위

기존66표/402등록 원문행과 신규93표/590등록 원문행을 합해159primary표/992행의 제한된 inventory를 만들었다. 기존46행/27key에 신규54행/27key가 더해져 원문 present/후보 absent100행/54metric-scope key다. 이는100개의 확정 parser 결함이 아니다.

1. P1: STC CFS8항목8행. 기존 원인 진단에서 보통 문장 '연결재무제표에 대한 주석 참조'가 financial zone을 닫아 원문 current IS/CF가 사라지는 제어 흐름 결함을 확인했다. 수리 시 실제 주석/사업부문 진입은 계속 닫고, fresh source date/term/unit/physical-column/scope guards를 유지해야 한다. 현재 운영 parser/version/승인 source hash는 바꾸지 않았다.
2. P1: CJ CFS자산총계1항목. 원문의 숫자 뒤 &cr; 및 underline을 INVALID_NUMERIC_TOKEN으로 거부한다. 별도 원문 근거/숫자경계 계약/두 숫자 합쳐짐 거부 시험을 갖춘 제한된 lexer 수리가 필요하다. 해당 값은 기존100행의 밖에 있는 presentation case이며 중복으로 합산하지 않는다.
3. P2: 감가/상각42key84행. IS 비용 부분과 CF 조정액의 개념 충돌이다. 동일 key로 모이는 서로 다른 수치를 fail-closed로 보류한 상태이며 모든 중간 추출 경로를 trace한 것은 아니다. statement/basis 개념을 분리한 뒤 비교해야 한다. 임의 우선순위·합산으로 채우지 않는다.
4. P2: 유동성장기부채3key6행(구영테크/오라바이오틱스/SK디스커버리), 삼성카드 사채1key2행. 구성항목/합계 정의와 상충 값 문제다. 새 aggregate 계약 없이 보류 해제하지 않는다.

14presentation case는 CJ표기 거부1개와 현재 칸 빈칸/대시이고 이전 값만 있는13개다. 빈칸을0으로 변경하지 않았다. 큐로홀딩스 첨부00761의CFS primary표처럼 기존OFS후보 외의 연결 자료도 존재한다. 해당 annex의 존재/미추출 범위를 기록했으나 전체 annex/미등록 alias 완전성은 인증하지 않는다.

원문 자체의 cross-statement 불일치(CS홀딩스1원, 메카포럼 자본총계200000원 차이 등)와 비교기 표기/옛 주석 문구는 source-conflicts-and-scope-limits.json에 별도로 남겼다. 현재 후보가 보고된 primary 행에 일치한다는 사실로 이런 차이를 해소하거나 허용오차로 숨기지 않았다. 운영 자동 게시/계산 입력 승격은 없다.

이번 범위는 확정 원인과 보류를 분류하고 우선순위를 정한 단계다. 생산 parser 수정은 아직 하지 않았으므로 '수리 완료' 또는 '수리 후 PASS 회귀 완료'라고 보고하지 않는다. 다음 수리 단위는 독립 원문 golden, 실제57문서의 기존848PASS 보존, 합성 경계 실패 시험, 버전/명시적 migration/source-owner 승인, 고정-kit CI를 갖춘 별도 변경이어야 한다. 현재 approved9.2를 수정한 것으로 가장하지 않는다.

## 실제 수집 gate와 재개

2026-10-21T05:28:52.633004+00:00 UTC(KST10월21일14:28), main fd232d129bfa2ef01714b94890460c5ef47bdbf0의 live ledger/config를 읽었다. recovery check는 ONCE_PER_KST_DAY로 멈췄다. 일일 기준 KST00:00이며 다음 가능 창은10월22일00:00KST/10월21일15:00UTC다. 그 시간이 됐다는 이유만으로 dispatch하지 않으며 first-review/source hash/만료/실행·예약 예산/중복 등 모든 live gate를 다시 통과해야 한다. DART 계정 전체 실제 잔여 HTTP quota는 이 ledger에서 관측할 수 없다.

실행2/3, 예약200/300, 미완료 예약43개. 완료 checkpoint20100331002054는 completed_receipts에 있고 다음2062/2063은 없다. 원문HTTP0/신규원문0/신규후보0/추가중복0/workflow dispatch0, 종료사유ONCE_PER_KST_DAY다. 실제 성공 증거가 없으므로 HOLD_FAILURE를 유지했다. 금융 게시HOLD/backtest_eligible=False/PIT0/6도 그대로다.

승인된 다음 명령(실행 전 live gate 재확인 필수):

```bash
gh workflow run backfill-dart-legacy-2000-2014.yml --repo Horororong/quant-marcap-runner --ref main -f resume_parent_run=39504052321 -f batch_documents=2
```

이2건은 남은 세 번째 실행을 사용한다. 성공 후 영수증/원문/후보/중복/checkpoint를 확인하되 다음 batch/네 번째 실행은 현 예산에 포함되지 않는다. 새 parser가 개발되더라도 이번 continuation을 새 버전으로 몰래 교체하거나 승인 hash를 변경하지 않는다.

## 보존과 다음 지점

기존 원본/최소복원/v1~v5/kit/751개 baseline/130strict/과거12미검증은 변경하지 않았다. 동일 생산 코드의 통합CI39540516627은 반복하지 않았다. 운영 main에는 새 코드/재무값/수집 상태 변경이 없다.

이번29문서 증거와 합산 장부,23원인별 미검증,누락 우선순위,현재 gate,승인·전달 영수증은 연구브랜치의 이 폴더 및 HANDOFF_CURRENT.md로 보존한다. 이전19문서 증거는 원래 docs/research/operating-source-review-20261021 그대로 참조한다. 이 증분에 원문ZIP/현재12envelope/v5archive를 다시 포함하지 않는다.

다음 의미 검토 high-water receipt는 없다. 기존 후보48문서/871개 판정은 끝났고 새 근거가 필요한23개가 정확한 다음 작업목록이다. P1STC/CJ추출 수리, annex/미등록 account/whole-filing 누락 검증, 실제사용가능일과 정정체인/PIT가 남았다. 수집 checkpoint는 이 의미 검토 장부와 별개인20100331002054다.

## 이번 증분 원격 게시의 실제 상태

로컬 증거 commit b83fcab263100dd889e050cae3732d6e5d90c215의 새25파일/약17MB 감사 자료를 공개 GitHub 연구브랜치에 게시하는 명령은 자동 승인 검토에서 시작 전에 거부됐다. 사유는 exact v5의 외부 전송 승인에 이 이후 생성된 새 source evidence/파생 자료가 포함되지 않는다는 것이다. 원격 게시/새 draft 전송은 하지 않았다. 승인된v5의 원격 검증은 이미 성공했다. 이번 후속 delta는 로컬 Git/새 로컬v6백업으로만 보존하며 새 정확한 payload에 대한 공개 게시 승인이 필요하다.
