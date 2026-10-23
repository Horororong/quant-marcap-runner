# v12 실전 인증 재확인·전송 완료 — 2026-10-23KST

RESEARCH_ONLY. 기존 정확한 v12 승인으로만 전송했다. 새 연구 코드·CI driver·main·금융/PIT 게이트는 게시·변경하지 않았다.

사용자의 “다시 확인해라”에 따라 현재 환경 revision80의 GH_BACKUP_TOKEN을 gh 하위 프로세스 인증에 명시했다. 저장소GET와 기존 draftGET가 실제 성공했다. 현재 사용자의 Contents 읽기·쓰기/Metadata 읽기 설정은 충분하며 추가 권한·재발급 요구는 불필요하다. 이전401의 정확한 과거 원인은 여전히 단정하지 않는다. 환경 revision은 이전73과 다르나 비밀값 변경 여부는 로그에 남기지 않았다.

첫 재개는 네트워크 인증이 아니라 로컬 태그 assertion으로 중단됐다. 실제 draft421514386의 tag_name은 GitHub가 부여한 untagged-03579765533e135a15a1이며, 코드가 요청 당시 backup-quant-… 문자열과 같다고 가정했다. 기존 draft ID/이름/draft상태/target commit을 확인한 후 그 바인딩으로 검사하고 API가 반환한 태그를 사용하도록 바로잡았다. 원인 수정 뒤에만 재개했다. 인증 거절 반복·새 release·다른 전송 경로·asset 덮어쓰기 없음.

같은 draft421514386에 승인한 ZIP538254바이트/SHA256464aa445c1c1d92a891bad9072973f34cc27bf2e92cbb13b8947f38c4a3a820e 및 원래 manifest/VERIFICATION/SHA256SUMS sidecar3개, 합계4assets를 업로드했다. 모두 인증된 실제 다운로드로 원본 바이트와 대조했고, 별도/tmp 경로에서 ZIP CRC·SHA·42entry·41payload 전체해시 PASS다. GitHub asset digest도 동일SHA256이다. 원래 ZIP·기존 백업 불변. ZIP41payload+1manifest=42entry와 외부sidecar3개=4releaseassets를 구분한다.

완료 링크: https://github.com/Horororong/quant-marcap-runner/releases/tag/untagged-03579765533e135a15a1

release는 draft=true/published_at=null이다. 로그인한 저장소 소유자 계정의 브라우저에서 첨부4개를 확인할 수 있다. 인증 없는 공개 다운로드로 검증한 것은 아니다. ZIP 업로드와 f8/7691/589 Git 게시, 새 로컬dbb6287 연구 코드의 게시·원격CI는 별개다. v12에는dbb6287 이후 연구 코드가 포함되지 않는다. 원격 자료만의 전체 프로젝트 복원 시험 미실시 상태도 그대로다.

이번 작업에서 DART 수집/소스 HTTP·금융값 변경·PIT 승격0이다. 오늘의 source기회 사용/체크포인트2063/추가41문서·2실행·82HTTP 예산은 변경하지 않았다. 완료된 전체복원·751감사·130/UI/동일CI·대용량 재전송은 반복하지 않았다. 이 승인된 v12 전송은 완료이므로 이상이 없는 한 다시 실행하지 않는다.
