# 6단계 게시 마무리 체크포인트

기존 감사 결과는 변경하지 않았다. 기준 로컬 결과 commit `537a869e84ac789d0295f71fecacfca7493f2004`, tree `d54a772052200acebef8a33ffe3a795be12a3607`, 부모 `1d7bcd997682438cc6a017e7764374d0a2f2dec9`이다. 부모 tree는 `e91c4ac5d9832cace2be15b83fab9c1cbe9a018f`로, 새로 확인한 원격 `c209a8f9b84a9de5afddbdcd4d3136d8533beb46`의 tree와 정확히 같다. 계보는 다르므로 remote 변경을 보존하는 통합 후 일반 push가 필요하다. force push 및 main 병합은 허용하지 않는다.

## 로컬 보존 및 검증

기존 evidence manifest 56개 파일, 기존 입력 103개 파일, 보존 원문 60건의 ZIP/member SHA·CRC, 60개 replay SHA, 12문서 SHA·CRC 및 518/64개 검증 결과를 확인했다. SHA 검사이며 새 금융 재처리는 하지 않았다.

| 기존 산출물 | SHA256 |
|---|---|
| stage6_report.md | 305881cfe03cd6e80423a252347d42df2e080d4c49afe3038fe271fe3d566cfe |
| stage6_details.csv | 566080b4eddafe37522adb2b182d96657eb7aa3c85a4abcb7055ca1c7dc8240a |
| stage6_version_chains.json | bbcef7cb75beae74b7becfb030e8c202622fe905126dba02020b5911a986e1a1 |
| stage6_reproduction.md | 4e906e0f50a26b3577740ac6d9298ceed5ea7338dee9a023f8e0b034033bcc6e |

백업은 `/workspace/financial-repair/stage6-publication/`에 보존했다.

- `stage6-local-final.bundle`: 기존 537a869e 결과 commit 및 추가 객체, prerequisite는 기존 부모 1d7bcd9. `git bundle verify` 통과. SHA256 `ac28cf8cc8763becc8b92edbd176ec66ba3d7f87886b99402f5ad0d93fdd7123`.
- `stage6-evidence-and-existing60.tar.gz`: 감사 폴더, 원문40/holdout20, replay60의 별도 전체 파일 백업. SHA256 `a8f0177ed9e95cf89bb31715c5e3f31172278cc98ca544b3ccaea6799166b699`.
- `local_preservation.json`: 위 해시 및 보호 대상 검증 기록.

원공시·정정 판정, S39 원문의 날짜 오기, 상세 108항목의 PASS38/FAIL1/UNVERIFIED69 및 투자 PIT 인증 **0/6**을 변경하지 않았다. 공식 2007년 주식시장 거래일, 유효기간을 가진 역사적 종목 연결, 정확한 공개시각, S39/S19 및 N14 직전 버전 증거 공백은 남는다.

## 최종 CI를 위한 최소 보완

기존 `[stage6-evidence]` job에 `verify_preserved60.py`를 추가했다. 이 검증기는 재수집이나 재파싱 대신 이미 성공한 CI `38588549687`의 고정 아티팩트를 각 1회 복원하고 원본·재현 결과의 SHA·CRC·bytes를 검사한다.

- originals artifact `11906556857`: 4,473,693 bytes, SHA `07fc734b53aa966974f42ec4836629394362d01e07b3f1fc33d7f5c15822c105`.
- financial replay artifact `11906601896`: 265,460 bytes, SHA `07c671aa0b6025f181b32179af084e6a1fd5db5e6291cfb768899e9df9ba99b9`.

두 아티팩트가 존재하고 만료되지 않았다는 metadata를 확인했다. **현재 최종 CI에서 다운로드 성공을 확인한 것은 아니다.** 접근 장애는 UNVERIFIED로 기록하고 재시도하지 않는다. 실제 bytes/hash 불일치는 FAIL 및 비정상 종료로 처리한다. 로컬 보존 아티팩트 모드에서 60원문/60replay/8재무결과/518/64 모두 PASS, 네트워크 요청 0회를 확인했다.

원래 154개 테스트, 12문서 버전 감사 재현, 신호 경계36 및 결과5파일 bytes identity는 기존 job을 유지한다. `[stage6-evidence]` 메시지는 DART 수집, KRX 신규 조회, 예전 전체 금융 재처리 job을 실행하지 않는다. 기존 kit release만 내려받고 원래 SHA/CRC 및 dedicated Python verify를 통과한 뒤 고정 패키지로 검증한다. 인터넷 pip 설치나 의존성 변경은 없다.

## 게시 장애와 실제 실행 여부

원격 HEAD는 여전히 `c209a8f9b84a9de5afddbdcd4d3136d8533beb46`이다. 새 브랜치 ref 업데이트, push, 최종 CI 실행은 완료하지 못했다.

1. 일반 `git fetch`는 proxy 연결 실패로 exit128. native `gh api`는 `socket: operation not permitted`로 exit1이었다. 계정의 repo push 권한은 metadata상 true여서 권한 부재로 단정하지 않는다.
2. sandbox network 추가 요청과 이후 escalation 요청은 각각 응답 없이 중단되었다. HTTP 상태·프로세스 종료코드·승인 결과가 반환되지 않아 실제 실행 성공으로 계산하지 않았다. 동일 요청을 반복하지 않았다.
3. GitHub 연결의 작은 summary-only `create_tree` 요청도 20초 안에 응답하지 않았다. branch ref를 갱신하는 후속 요청은 하지 않았다. 과거 대용량 요청과 달리 작은 요청도 실패하므로 대용량만의 문제라고 단정하지 않는다.
4. 일반 fetch 도구의 artifact 단일 endpoint는 unsupported400이어서 적절한 workflow artifact metadata 도구로 확인했다. 실제 artifact 복원 실패로 혼동하지 않는다.
5. 이전 실패 CI `38592204895`는 artifact restore HTTP503/exit1, 성공 CI `38592615003`은 공식 DART 원문6건 확보 및 당시 안전 테스트12개이다. 어느 것도 이번 최종154 CI 성공으로 표기하지 않는다.

## 안전한 재개

먼저 GitHub 쓰기 도구가 정상 응답하거나, 동일 승인 proxy를 사용하는 터미널 네트워크 권한이 실제 적용되어야 한다. 직접 연결·proxy 해제·임의 인증 우회는 하지 않는다. 현재 로컬 내용을 삭제하거나 새 checkout으로 덮어쓰지 않는다.

1. 현재 branch/HEAD/worktree와 bundle·파일 백업을 확인한다.
2. `git fetch --no-tags origin fix/financial-accuracy-20261014`로 실제 원격 객체를 확보한다. 원격 HEAD가 바뀌었으면 그 내용을 먼저 비교한다. API metadata만으로 원격 commit 객체를 임의 생성하지 않는다.
3. 원격 tree가 위 e91c4ac5와 여전히 같다면, 로컬 최종 tree의 변경이 원격 내용을 모두 보존한다. 서로 다른 양쪽 commit을 부모로 보존하는 통합 commit을 만들고 메시지에는 `[stage6-evidence]`만 사용한다. 원격 tree가 달라졌으면 변경 내용을 통합·검증한 뒤 진행한다.
4. `git merge-base --is-ancestor <현재원격SHA> HEAD`가 통과한 상태에서 해당 브랜치에 한 번의 일반 `git push origin HEAD:refs/heads/fix/financial-accuracy-20261014`를 실행한다. force를 사용하지 않는다.
5. 실제 새 head/run의 workflow job·원문 복원 JSON·154 테스트 로그·5파일 bytes identity를 확인한다. CI에서 복원하지 못한 항목은 local PASS와 구분하여 UNVERIFIED로 보고한다.
6. 저장소의 전체 새 tree와 로컬 tree를 비교하면 게시된 모든 산출물의 bytes identity를 확인할 수 있다. 불일치한 파일은 개별 SHA256을 대조한다.

최종 게시/CI가 완료되기 전에는 추가 개발이나 2,000건 처리로 진행하지 않는다.
