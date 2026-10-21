# 복원 이후 개발 인수인계

고정 복원 기준b5aaa7f01c17f77527c07baa36f27415de9aba31, 전체복원 기준5bb0523bb192598c51923549a21fd5a87ae87366. 데이터751개 실재/원본749개 SHA256/원격Git복구출처는완료한감사이며반복하지않는다. 원본없는원격전용전체복원시험은미실시다. 기존원본·최소복원본·v1·v2는보존했다.

## CI

5bb 대상 고정kit CI 성공: https://github.com/Horororong/quant-marcap-runner/actions/runs/39510053377
workflow driver SHA12296994def8c6b622554bb632a6d96d3b1b93d1, checkout실제target5bb. 연구커밋에직접연결된check-run인것처럼표시하지않는다. 로그에exact checkout,kit검증,언어/web12시험,generated계약,실제브라우저/공통engine/CURRENT/독립장부PASS가있다. 이번새최종연구/운영수정커밋의CI결과·정확한SHA·PR은새v3 release의FINAL_STATUS.md에기록한다. 코드자체가자기commit SHA를담도록재귀수정하지않는다.

## 회귀 예외

COMPARISON_EXCEPTIONS.md와comparison-exceptions-21.json을먼저읽는다. 130엄격일치/6실행계획버전차이/3preflight구조차이/12전체byte비교제외다. 12개가전부메타데이터라는보장은없다. 새감사로HTML/chat payload 및840성과값과14,155현재표시NAV점의canonicalCSV일치를허용오차0으로확인했다. 원본12개상세diff는artifact12118487392의로컬전송부재로UNVERIFIED. artifact는현재expired=False지만직접redirect는정책403,공식connector파일전송도이실행환경에서미지원이다. 이를위해새로운권한우회/대용량복원반복을하지않았다.

## 운영 수집

수정은운영main기반별도fix/finite-resume-budget-20261020 브랜치/PR에보존하며main에직접적용하지않는다. 600초를늘리지않고document_seconds+종료reserve가남지않으면새worker를시작하지않으며문서수cap/remaining_queue/정상PAUSED를기록한다. 로컬lease·부모SIGKILL시worker종료·원문/결과/체크포인트단계복구·hash검증·캐시replay를추가했다. 완료문서는재수집하지않고완료후보를중복등록하지않는다. 실제SIGKILL시험및실제원문2건의오프라인분할/재개PASS. 시험합성데이터는금융증거가아니다.

실제신규HTTP소규모배치는ONCE_PER_KST_DAY로차단됐다. 기존HOLD_FAILURE와20100331002054,57보존원문,예약200/300은변경하지않았다. 기존100예약의남은43건에서다음2개20100331002062/20100331002063을고정한다. 새예약0, 재개실행도최대3실행한도에산입한다. 다음KST일일창은2026-10-21T15:00:00Z(10/22 00:00KST). 운영PR검토/적용과gate재확인후기존workflow를resume_parent_run=39504052321,batch_documents=2로한번dispatch한다. 성공확인전다음배치를시작하지않고,자동금융게시HOLD/PIT0/6을유지한다.

## 원문 검토

57고유접수번호/57archive/후보871/고유후보871/중복0. 독립literal-cell/Decimal검사871 PASS는숫자바인딩·부호·단위환산에한정된다. 원문표제/회계기간/당기열/연결별도/백만원/음수/정정본문을직접대조한표본은7문서8값PASS,FAIL0이며후보863값과문서50건은상세미검토다. 전체문서추출완전성검토0, 모든871 PIT는UNVERIFIED,운영값교체/신규금융게시0. reviewed-source-controls.json에원문row/header와판정,source-audit-candidates.json에전체연결을남겼다.

## 사용자 기능

규칙기반한국어+JSON이며모델기반이아니다. 지원/미지원표현과로컬접속범위를화면에추가했다. 실행전확인digest와모호한조건차단은유지하며언어/web12시험은통과했다. 외부모델credential/SDK/승인비용한도가없어모델호출/설치를하지않았다. 휴대폰외부접속은localhost bind이므로미제공이며별도호스팅/사용자인증/공개범위설계가필요하다.

## 재개

새기본개발경로 /workspace/quant-project-full-20261020/code, branch restore/full-project-20261020. Python은기존 /workspace/quant-restore-b5aaa7f/runtime/.venv/bin/python -I만사용한다. 기존kit·복원데이터·기존회귀결과·전체백업전송은새문제가없으면반복하지않는다. 다음작업은원본envelope12개추가대조,남은863후보의독립원문검토/추출누락검토,일일gate와운영PR적용후2문서실제배치다. 모든결과RESEARCH_ONLY이며환경복원과금융/PIT인증은별개다.
